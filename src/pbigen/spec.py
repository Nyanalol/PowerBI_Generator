"""Modelo tipado del contrato `spec_lock.yaml` (v1).

El LLM (o una persona) escribe el YAML; el código lo valida aquí y lo serializa a TMDL y
PBIR. Todo lo que no esté en estos modelos no se puede expresar, y por tanto no se genera:
el emisor falla en vez de improvisar. Perímetro v1 (docs/01 §4.3.2): textbox, card, line,
column, bar, matrix, slicer; relaciones; tabla de fechas generada; tema por identidad.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DataType = Literal["string", "int64", "double", "decimal", "dateTime", "boolean"]
Summarize = Literal["none", "sum", "count", "min", "max", "average"]
VisualType = Literal["textbox", "card", "line", "column", "bar", "matrix", "slicer"]

CANVAS_W, CANVAS_H = 1280, 720
# 12 columnas x 8 filas: fila de 79 px (>= 76 px que exige un slicer desplegable con cabecera)
GRID_COLS, GRID_ROWS, GRID_MARGIN, GRID_GUTTER = 12, 8, 16, 8


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------------- orígenes / modelo


class SourceSpec(StrictModel):
    id: str
    type: Literal["excel"]
    path: str  # relativa al directorio del proyecto


class ColumnSpec(StrictModel):
    name: str
    type: DataType
    source_column: str | None = None
    summarize: Summarize = "none"
    format: str | None = None
    hidden: bool = False
    sort_by: str | None = None  # otra columna de la misma tabla
    description: str | None = None


class MeasureSpec(StrictModel):
    name: str
    dax: str
    format: str = "#,##0"
    description: str | None = None
    folder: str | None = None


class TableSourceSpec(StrictModel):
    source: str
    sheet: str | None = None
    table: str | None = None
    # Dimensión derivada de una hoja plana: una fila por `distinct_key`, atributos con el primer
    # valor observado (Table.Group + List.First). Garantiza clave única aunque el origen esté sucio.
    distinct_key: str | None = None
    attributes: list[str] = []

    @model_validator(mode="after")
    def _one_of(self) -> "TableSourceSpec":
        if bool(self.sheet) == bool(self.table):
            raise ValueError("indica exactamente uno de `sheet` o `table`")
        if self.attributes and not self.distinct_key:
            raise ValueError("`attributes` requiere `distinct_key`")
        return self


class TableSpec(StrictModel):
    name: str
    source: TableSourceSpec
    columns: list[ColumnSpec] = Field(min_length=1)
    measures: list[MeasureSpec] = []
    description: str | None = None

    @model_validator(mode="after")
    def _sort_by_exists(self) -> "TableSpec":
        names = {c.name for c in self.columns}
        for c in self.columns:
            if c.sort_by and c.sort_by not in names:
                raise ValueError(f"tabla {self.name!r}: sort_by {c.sort_by!r} de {c.name!r} no existe")
        if self.source.distinct_key:
            allowed = {self.source.distinct_key, *self.source.attributes}
            for c in self.columns:
                if (c.source_column or c.name) not in allowed:
                    raise ValueError(
                        f"tabla {self.name!r}: la columna {c.name!r} no está en distinct_key ni en attributes"
                    )
        return self


class DateTableSpec(StrictModel):
    """Tabla de fechas calculada y marcada como tal. Columnas fijas: Fecha, Año, MesNum, Mes, Trimestre, AñoMes."""

    name: str = "Fechas"
    start: date
    end: date
    locale_month_format: str = "MMM"

    @property
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(name="Fecha", type="dateTime", format="dd/MM/yyyy"),
            ColumnSpec(name="Año", type="int64"),
            ColumnSpec(name="MesNum", type="int64", hidden=True),
            ColumnSpec(name="Mes", type="string", sort_by="MesNum"),
            ColumnSpec(name="Trimestre", type="string"),
            ColumnSpec(name="AñoMes", type="string"),
            # Eje temporal para series largas: 4 años son 48 meses (ilegibles) pero solo 16 trimestres
            ColumnSpec(name="AñoTrimestre", type="string"),
        ]


_FIELD_RE = re.compile(r"^(?P<table>[^\[\]]+)\[(?P<prop>[^\[\]]+)\]$")


class FieldRef(StrictModel):
    """Referencia `Tabla[Propiedad]` a una columna o medida del modelo."""

    table: str
    prop: str

    @classmethod
    def parse(cls, text: str) -> "FieldRef":
        m = _FIELD_RE.match(text.strip())
        if not m:
            raise ValueError(f"referencia de campo inválida: {text!r}; usa Tabla[Campo]")
        return cls(table=m.group("table").strip(), prop=m.group("prop").strip())

    def __str__(self) -> str:
        return f"{self.table}[{self.prop}]"


class RelationshipSpec(StrictModel):
    from_: str = Field(alias="from")  # lado "muchos": Ventas[ProductoId]
    to: str  # lado "uno": Productos[ProductoId]
    cross_filter: Literal["single", "both"] = "single"
    active: bool = True

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelSpec(StrictModel):
    tables: list[TableSpec] = Field(min_length=1)
    date_table: DateTableSpec | None = None
    relationships: list[RelationshipSpec] = []


# ----------------------------------------------------------------------------- informe


class GridPos(StrictModel):
    col: int = Field(ge=0, lt=GRID_COLS)
    row: int = Field(ge=0, lt=GRID_ROWS)
    cols: int = Field(ge=1, le=GRID_COLS)
    rows: int = Field(ge=1, le=GRID_ROWS)

    @model_validator(mode="after")
    def _fits(self) -> "GridPos":
        if self.col + self.cols > GRID_COLS or self.row + self.rows > GRID_ROWS:
            raise ValueError(f"celda fuera de la rejilla {GRID_COLS}x{GRID_ROWS}: {self}")
        return self

    def to_px(self, width: int = CANVAS_W, height: int = CANVAS_H) -> tuple[float, float, float, float]:
        cw = (width - 2 * GRID_MARGIN - (GRID_COLS - 1) * GRID_GUTTER) / GRID_COLS
        rh = (height - 2 * GRID_MARGIN - (GRID_ROWS - 1) * GRID_GUTTER) / GRID_ROWS
        x = GRID_MARGIN + self.col * (cw + GRID_GUTTER)
        y = GRID_MARGIN + self.row * (rh + GRID_GUTTER)
        w = self.cols * cw + (self.cols - 1) * GRID_GUTTER
        h = self.rows * rh + (self.rows - 1) * GRID_GUTTER
        return round(x, 2), round(y, 2), round(w, 2), round(h, 2)


class VisualSpec(StrictModel):
    type: VisualType
    name: str  # estable: de aquí sale el id
    grid: GridPos | None = None
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None
    title: str | None = None
    # textbox
    text: str | None = None
    font_size_pt: int = 24
    # card
    measure: str | None = None
    # line / column / bar
    category: str | None = None
    values: list[str] = []
    series: str | None = None
    sort: Literal["auto", "category", "value"] = "auto"  # auto: categoría si es temporal, valor si no
    # `asc` sobre el valor pone lo peor arriba: es como se destacan las pérdidas en un ranking
    sort_direction: Literal["auto", "asc", "desc"] = "auto"
    # Con pocas barras, el número junto al dato sustituye al eje de valores y aprovecha el ancho
    data_labels: bool = False
    # El color dice de qué habla el visual; no decora. Se resuelve contra la identidad del cliente
    accent: Literal["primary", "secondary", "positive", "negative", "warning", "neutral"] | None = None
    # matrix
    rows: list[str] = []
    columns: list[str] = []
    # slicer
    field: str | None = None
    mode: Literal["list", "dropdown"] = "list"

    @model_validator(mode="after")
    def _by_type(self) -> "VisualSpec":
        if (self.grid is None) == (self.x is None and self.y is None and self.w is None and self.h is None):
            raise ValueError(f"visual {self.name!r}: indica `grid` o bien x/y/w/h")
        if self.grid is None and None in (self.x, self.y, self.w, self.h):
            raise ValueError(f"visual {self.name!r}: x, y, w y h son obligatorios sin `grid`")
        t = self.type
        need = {
            "textbox": bool(self.text),
            "card": bool(self.measure),
            "line": bool(self.category and self.values),
            "column": bool(self.category and self.values),
            "bar": bool(self.category and self.values),
            "matrix": bool(self.rows and self.values),
            "slicer": bool(self.field),
        }[t]
        if not need:
            raise ValueError(f"visual {self.name!r} ({t}): faltan campos obligatorios para su tipo")
        for ref in self.field_refs():
            FieldRef.parse(ref)
        return self

    def field_refs(self) -> list[str]:
        refs = [r for r in (self.measure, self.category, self.series, self.field) if r]
        return refs + list(self.values) + list(self.rows) + list(self.columns)

    def position(self, width: int, height: int) -> tuple[float, float, float, float]:
        if self.grid is not None:
            return self.grid.to_px(width, height)
        return float(self.x), float(self.y), float(self.w), float(self.h)  # type: ignore[arg-type]


class PageSpec(StrictModel):
    name: str
    display_name: str | None = None
    width: int = CANVAS_W
    height: int = CANVAS_H
    visuals: list[VisualSpec] = []

    @property
    def shown_name(self) -> str:
        return self.display_name or self.name

    @model_validator(mode="after")
    def _unique_visual_names(self) -> "PageSpec":
        names = [v.name for v in self.visuals]
        if len(names) != len(set(names)):
            raise ValueError(f"página {self.name!r}: nombres de visual repetidos")
        return self


class ThemeSpec(StrictModel):
    brand: str | None = None  # templates/brands/<brand>/brand.yaml


class ReportSpec(StrictModel):
    pages: list[PageSpec] = Field(min_length=1)
    theme: ThemeSpec = ThemeSpec()


# ----------------------------------------------------------------------------- raíz


class SpecLock(StrictModel):
    version: Literal[0, 1]
    project: str
    locale: str = "es-ES"
    sources: list[SourceSpec] = Field(min_length=1)
    model: ModelSpec
    report: ReportSpec

    @field_validator("project")
    @classmethod
    def _project_name(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$", v):
            raise ValueError("`project` solo admite letras, números, espacio, guion y guion bajo")
        return v

    # --- catálogo de objetos del modelo (tablas del origen + tabla de fechas)
    def columns_of(self, table: str) -> set[str]:
        for t in self.model.tables:
            if t.name == table:
                return {c.name for c in t.columns}
        if self.model.date_table and self.model.date_table.name == table:
            return {c.name for c in self.model.date_table.columns}
        raise KeyError(table)

    def measures_of(self, table: str) -> set[str]:
        for t in self.model.tables:
            if t.name == table:
                return {m.name for m in t.measures}
        if self.model.date_table and self.model.date_table.name == table:
            return set()
        raise KeyError(table)

    def field_kind(self, ref: str) -> Literal["Column", "Measure"]:
        r = FieldRef.parse(ref)
        try:
            if r.prop in self.measures_of(r.table):
                return "Measure"
            if r.prop in self.columns_of(r.table):
                return "Column"
        except KeyError:
            raise ValueError(f"tabla {r.table!r} no existe en el modelo") from None
        raise ValueError(f"{ref}: no es columna ni medida de {r.table!r}")

    @model_validator(mode="after")
    def _cross_refs(self) -> "SpecLock":
        source_ids = {s.id for s in self.sources}
        names = [t.name for t in self.model.tables] + ([self.model.date_table.name] if self.model.date_table else [])
        if len(names) != len(set(names)):
            raise ValueError("nombres de tabla repetidos")
        for t in self.model.tables:
            if t.source.source not in source_ids:
                raise ValueError(f"tabla {t.name!r}: origen {t.source.source!r} no declarado")
        # Restricciones de nombres de Tabular (Desktop no abre el modelo si se incumplen):
        # una medida no puede llamarse como una tabla, ni como una columna de su tabla,
        # y los nombres de medida son únicos en todo el modelo.
        seen_measures: dict[str, str] = {}
        for t in self.model.tables:
            col_names = {c.name for c in t.columns}
            for m in t.measures:
                if m.name in names:
                    raise ValueError(f"medida {m.name!r} se llama igual que una tabla; renómbrala (p. ej. 'Nº {m.name}')")
                if m.name in col_names:
                    raise ValueError(f"medida {m.name!r} se llama igual que una columna de {t.name!r}; renombra la columna base")
                if m.name in seen_measures:
                    raise ValueError(f"medida {m.name!r} repetida en {seen_measures[m.name]!r} y {t.name!r}")
                seen_measures[m.name] = t.name
        for rel in self.model.relationships:
            for side in (rel.from_, rel.to):
                if self.field_kind(side) != "Column":
                    raise ValueError(f"relación {rel.from_} -> {rel.to}: {side} debe ser una columna")
        for p in self.report.pages:
            for v in p.visuals:
                for ref in v.field_refs():
                    kind = self.field_kind(ref)
                    if ref == v.measure and kind != "Measure":
                        raise ValueError(f"visual {v.name!r}: `measure` debe ser una medida: {ref}")
                    if ref in v.values and kind != "Measure":
                        raise ValueError(f"visual {v.name!r}: `values` deben ser medidas: {ref}")
                    if ref in (v.category, v.series, v.field) or ref in v.rows or ref in v.columns:
                        if kind != "Column":
                            raise ValueError(f"visual {v.name!r}: {ref} debe ser una columna")
        return self


def load_spec(path: Path) -> SpecLock:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SpecLock.model_validate(data)


def load_sources(path: Path) -> list[SourceSpec]:
    """Solo la sección `sources`: lo único que existe antes de diseñar el modelo."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = [SourceSpec.model_validate(s) for s in data.get("sources") or []]
    if not sources:
        raise ValueError(f"{path}: declara al menos un origen en `sources`")
    return sources

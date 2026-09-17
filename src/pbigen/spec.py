"""Modelo tipado del contrato `spec_lock.yaml`.

El LLM (o una persona) escribe el YAML; el código lo valida aquí y lo
serializa a TMDL y PBIR. Todo lo que no esté en estos modelos no se puede
expresar, y por tanto no se genera: el emisor falla en vez de improvisar.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DataType = Literal["string", "int64", "double", "decimal", "dateTime", "boolean"]
Summarize = Literal["none", "sum", "count", "min", "max", "average"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSpec(StrictModel):
    id: str
    type: Literal["excel"]
    path: str  # relativa al directorio del proyecto


class ColumnSpec(StrictModel):
    name: str
    type: DataType
    source_column: str | None = None  # nombre en el origen; por defecto = name
    summarize: Summarize = "none"
    format: str | None = None
    hidden: bool = False


class MeasureSpec(StrictModel):
    name: str
    dax: str
    format: str = "#,##0"
    description: str | None = None
    folder: str | None = None


class TableSourceSpec(StrictModel):
    source: str  # id de SourceSpec
    sheet: str | None = None
    table: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "TableSourceSpec":
        if bool(self.sheet) == bool(self.table):
            raise ValueError("indica exactamente uno de `sheet` o `table`")
        return self


class TableSpec(StrictModel):
    name: str
    source: TableSourceSpec
    columns: list[ColumnSpec] = Field(min_length=1)
    measures: list[MeasureSpec] = []


class ModelSpec(StrictModel):
    tables: list[TableSpec] = Field(min_length=1)


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


class VisualSpec(StrictModel):
    type: Literal["textbox", "card"]
    name: str | None = None  # nombre estable para derivar el id; por defecto tipo+posición
    x: float
    y: float
    w: float
    h: float
    title: str | None = None
    text: str | None = None  # textbox
    font_size_pt: int = 24  # textbox
    measure: str | None = None  # card: Tabla[Medida]

    @model_validator(mode="after")
    def _by_type(self) -> "VisualSpec":
        if self.type == "textbox" and not self.text:
            raise ValueError("textbox requiere `text`")
        if self.type == "card":
            if not self.measure:
                raise ValueError("card requiere `measure` (Tabla[Medida])")
            FieldRef.parse(self.measure)
        return self

    @property
    def stable_name(self) -> str:
        return self.name or f"{self.type}@{int(self.x)},{int(self.y)}"


class PageSpec(StrictModel):
    name: str
    display_name: str | None = None
    width: int = 1280
    height: int = 720
    visuals: list[VisualSpec] = []

    @property
    def shown_name(self) -> str:
        return self.display_name or self.name


class ReportSpec(StrictModel):
    pages: list[PageSpec] = Field(min_length=1)


class SpecLock(StrictModel):
    version: Literal[0]
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

    @model_validator(mode="after")
    def _cross_refs(self) -> "SpecLock":
        source_ids = {s.id for s in self.sources}
        tables = {t.name: t for t in self.model.tables}
        for t in self.model.tables:
            if t.source.source not in source_ids:
                raise ValueError(f"tabla {t.name!r}: origen {t.source.source!r} no declarado")
        for p in self.report.pages:
            for v in p.visuals:
                if v.measure:
                    ref = FieldRef.parse(v.measure)
                    table = tables.get(ref.table)
                    if table is None:
                        raise ValueError(f"visual {v.stable_name!r}: tabla {ref.table!r} no existe")
                    if ref.prop not in {m.name for m in table.measures}:
                        raise ValueError(
                            f"visual {v.stable_name!r}: medida {ref.prop!r} no existe en {ref.table!r}"
                        )
        return self


def load_spec(path: Path) -> SpecLock:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SpecLock.model_validate(data)

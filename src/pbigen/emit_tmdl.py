"""Emisor TMDL: SpecLock -> carpeta `<proyecto>.SemanticModel/`.

Formato basado en modelos guardados por Power BI Desktop y en las guías TMDL de Microsoft:
tabulador como indentación, medidas antes que columnas, `formatString` en toda medida, sin
lineageTag (el motor los asigna al guardar). La tabla de fechas es una tabla calculada con
`dataCategory: Time` y su columna de fecha marcada `isKey`.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .platform_file import write_platform
from .spec import ColumnSpec, DateTableSpec, FieldRef, RelationshipSpec, SourceSpec, SpecLock, TableSpec

DATA_FOLDER_PARAM = "DataFolder"

_M_TYPES = {
    "string": "type text",
    "int64": "Int64.Type",
    "double": "type number",
    "decimal": "Currency.Type",
    "dateTime": "type datetime",
    "boolean": "type logical",
}

_LCID = {"es-ES": 3082, "en-US": 1033, "en-GB": 2057, "pt-PT": 2070, "fr-FR": 1036, "de-DE": 1031}
_REL_NS = uuid.UUID("2b6a9a1e-9d3a-4a6b-8a1c-3f2e5d7c9b11")


def _q(name: str) -> str:
    """Entrecomilla un nombre TMDL si lleva espacios o caracteres especiales."""
    if any(c in name for c in " .=:'-()[]") or not name.isidentifier():
        return "'" + name.replace("'", "''") + "'"
    return name


def _m_string(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


def _dax_col(ref: str) -> str:
    r = FieldRef.parse(ref)
    return f"{_q(r.table)}[{r.prop}]"


def _partition_source(table: TableSpec, source: SourceSpec) -> str:
    file_name = Path(source.path).name
    if table.source.sheet:
        item, kind = table.source.sheet, "Sheet"
    else:
        item, kind = table.source.table, "Table"
    types = ", ".join(
        "{" + _m_string(c.source_column or c.name) + ", " + _M_TYPES[c.type] + "}" for c in table.columns
    )
    lines = [
        "let",
        f'    Source = Excel.Workbook(File.Contents(#"{DATA_FOLDER_PARAM}" & "\\{file_name}"), null, true),',
        f"    Item = Source{{[Item={_m_string(item)},Kind={_m_string(kind)}]}}[Data],",
    ]
    if kind == "Sheet":
        lines.append("    Headers = Table.PromoteHeaders(Item, [PromoteAllScalars=true]),")
        prev = "Headers"
    else:
        prev = "Item"
    lines += [
        f"    Typed = Table.TransformColumnTypes({prev}, {{{types}}})",
        "in",
        "    Typed",
    ]
    return "\n".join(lines)


def _column(c: ColumnSpec, calculated: bool = False) -> list[str]:
    out = []
    if c.description:
        out.append(f"\t/// {c.description}")
    out += [f"\tcolumn {_q(c.name)}", f"\t\tdataType: {c.type}"]
    if c.hidden:
        out.append("\t\tisHidden")
    if calculated:
        out.append("\t\tisNameInferred")
    if c.format:
        out.append(f"\t\tformatString: {c.format}")
    elif c.type == "dateTime":
        out.append("\t\tformatString: General Date")
    if c.sort_by:
        out.append(f"\t\tsortByColumn: {_q(c.sort_by)}")
    out.append(f"\t\tsummarizeBy: {c.summarize}")
    out.append(f"\t\tsourceColumn: {'[' + c.name + ']' if calculated else (c.source_column or c.name)}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    return out


def _measures(table_measures) -> list[str]:  # type: ignore[no-untyped-def]
    out: list[str] = []
    for m in table_measures:
        if m.description:
            out.append(f"\t/// {m.description}")
        if "\n" in m.dax:
            body = "\n".join("\t\t\t" + line for line in m.dax.strip().splitlines())
            out.append(f"\tmeasure {_q(m.name)} = ```\n{body}\n\t\t\t```")
        else:
            out.append(f"\tmeasure {_q(m.name)} = {m.dax.strip()}")
        out.append(f"\t\tformatString: {m.format}")
        if m.folder:
            out.append(f"\t\tdisplayFolder: {m.folder}")
        out.append("")
    return out


def table_tmdl(table: TableSpec, source: SourceSpec) -> str:
    out = []
    if table.description:
        out.append(f"/// {table.description}")
    out += [f"table {_q(table.name)}", ""]
    out += _measures(table.measures)
    for c in table.columns:
        out += _column(c)
    out.append(f"\tpartition {_q(table.name)} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    out += ["\t\t\t\t" + line for line in _partition_source(table, source).splitlines()]
    out.append("")
    out.append("\tannotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out)


def date_table_dax(dt: DateTableSpec) -> str:
    s, e = dt.start, dt.end
    return "\n".join(
        [
            f"VAR _inicio = DATE({s.year}, {s.month}, {s.day})",
            f"VAR _fin = DATE({e.year}, {e.month}, {e.day})",
            "RETURN",
            "    ADDCOLUMNS(",
            '        SELECTCOLUMNS(CALENDAR(_inicio, _fin), "Fecha", [Date]),',
            '        "Año", YEAR([Fecha]),',
            '        "MesNum", MONTH([Fecha]),',
            f'        "Mes", FORMAT([Fecha], "{dt.locale_month_format}"),',
            '        "Trimestre", "T" & FORMAT([Fecha], "q"),',
            '        "AñoMes", FORMAT([Fecha], "yyyy-MM")',
            "    )",
        ]
    )


def date_table_tmdl(dt: DateTableSpec) -> str:
    out = ["/// Tabla de fechas generada; marcada como tabla de fechas del modelo", f"table {_q(dt.name)}", "\tdataCategory: Time", ""]
    for c in dt.columns:
        lines = _column(c, calculated=True)
        if c.name == "Fecha":
            lines.insert(2, "\t\tisKey")
        out += lines
    out.append(f"\tpartition {_q(dt.name)} = calculated")
    out.append("\t\tmode: import")
    out.append("\t\tsource = ```")
    out += ["\t\t\t\t" + line for line in date_table_dax(dt).splitlines()]
    out.append("\t\t\t\t```")
    out.append("")
    out.append("\tannotation PBI_Id = " + _q(dt.name).strip("'").lower())
    out.append("")
    return "\n".join(out)


def relationships_tmdl(rels: list[RelationshipSpec]) -> str:
    out: list[str] = []
    for r in rels:
        rid = uuid.uuid5(_REL_NS, f"{r.from_}->{r.to}")
        out.append(f"relationship {rid}")
        if not r.active:
            out.append("\tisActive: false")
        if r.cross_filter == "both":
            out.append("\tcrossFilteringBehavior: bothDirections")
        out.append(f"\tfromColumn: {_dax_col(r.from_).replace('[', '.').rstrip(']')}")
        out.append(f"\ttoColumn: {_dax_col(r.to).replace('[', '.').rstrip(']')}")
        out.append("")
    return "\n".join(out)


def model_tmdl(spec: SpecLock) -> str:
    out = [
        "model Model",
        f"\tculture: {spec.locale}",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        f"\tsourceQueryCulture: {spec.locale}",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ]
    for t in spec.model.tables:
        out.append(f"ref table {_q(t.name)}")
    if spec.model.date_table:
        out.append(f"ref table {_q(spec.model.date_table.name)}")
    out.append("")
    out.append(f"ref cultureInfo {spec.locale}")
    out.append("")
    return "\n".join(out)


def database_tmdl(spec: SpecLock) -> str:
    lcid = _LCID.get(spec.locale, 1033)
    return "\n".join(
        [f"database {_q(spec.project)}", "\tcompatibilityLevel: 1702", "\tcompatibilityMode: powerBI", f"\tlanguage: {lcid}", ""]
    )


def expressions_tmdl(data_folder: Path) -> str:
    value = str(data_folder).replace("/", "\\")
    return "\n".join(
        [
            f"expression {DATA_FOLDER_PARAM} = {_m_string(value)} meta "
            '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            "",
            "\tannotation PBI_ResultType = Text",
            "",
        ]
    )


def culture_tmdl(locale: str) -> str:
    return f"cultureInfo {locale}\n"


PBISM = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2",
    "settings": {"qnaEnabled": True},
}


def write_semantic_model(spec: SpecLock, out_dir: Path, data_folder: Path) -> Path:
    """Escribe `<out_dir>/<project>.SemanticModel/` y devuelve su ruta."""
    sm = out_dir / f"{spec.project}.SemanticModel"
    d = sm / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    (d / "cultures").mkdir(parents=True, exist_ok=True)
    sources = {s.id: s for s in spec.sources}

    def w(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8", newline="\n")

    w(sm / "definition.pbism", json.dumps(PBISM, indent=2) + "\n")
    w(d / "database.tmdl", database_tmdl(spec))
    w(d / "model.tmdl", model_tmdl(spec))
    w(d / "expressions.tmdl", expressions_tmdl(data_folder))
    w(d / "cultures" / f"{spec.locale}.tmdl", culture_tmdl(spec.locale))
    if spec.model.relationships:
        w(d / "relationships.tmdl", relationships_tmdl(spec.model.relationships))
    for t in spec.model.tables:
        w(d / "tables" / f"{t.name}.tmdl", table_tmdl(t, sources[t.source.source]))
    if spec.model.date_table:
        w(d / "tables" / f"{spec.model.date_table.name}.tmdl", date_table_tmdl(spec.model.date_table))
    write_platform(sm, spec.project, "SemanticModel")
    return sm

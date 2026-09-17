"""Emisor TMDL: SpecLock -> carpeta `<proyecto>.SemanticModel/`.

Formato basado en modelos guardados por Power BI Desktop y en las guías TMDL de
Microsoft (skill semantic-model-authoring): tabulador como indentación,
medidas antes que columnas, `formatString` en toda medida, sin lineageTag
(el motor los asigna al guardar).
"""

from __future__ import annotations

import json
from pathlib import Path

from .platform_file import write_platform
from .spec import ColumnSpec, SourceSpec, SpecLock, TableSpec

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


def _q(name: str) -> str:
    """Entrecomilla un nombre TMDL si lleva espacios o caracteres especiales."""
    if any(c in name for c in " .=:'-()[]") or not name.isidentifier():
        return "'" + name.replace("'", "''") + "'"
    return name


def _m_string(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


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


def _column(c: ColumnSpec) -> list[str]:
    out = [f"\tcolumn {_q(c.name)}", f"\t\tdataType: {c.type}"]
    if c.hidden:
        out.append("\t\tisHidden")
    if c.format:
        out.append(f"\t\tformatString: {c.format}")
    elif c.type == "dateTime":
        out.append("\t\tformatString: General Date")
    out.append(f"\t\tsummarizeBy: {c.summarize}")
    out.append(f"\t\tsourceColumn: {c.source_column or c.name}")
    out.append("")
    out.append("\t\tannotation SummarizationSetBy = Automatic")
    out.append("")
    return out


def table_tmdl(table: TableSpec, source: SourceSpec) -> str:
    out = [f"table {_q(table.name)}", ""]
    for m in table.measures:
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
    out.append("")
    out.append(f"ref cultureInfo {spec.locale}")
    out.append("")
    return "\n".join(out)


def database_tmdl(spec: SpecLock) -> str:
    lcid = _LCID.get(spec.locale, 1033)
    return "\n".join(
        [
            f"database {_q(spec.project)}",
            "\tcompatibilityLevel: 1702",
            "\tcompatibilityMode: powerBI",
            f"\tlanguage: {lcid}",
            "",
        ]
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
    for t in spec.model.tables:
        w(d / "tables" / f"{t.name}.tmdl", table_tmdl(t, sources[t.source.source]))
    write_platform(sm, spec.project, "SemanticModel")
    return sm

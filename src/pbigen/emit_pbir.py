"""Emisor PBIR: SpecLock -> carpeta `<proyecto>.Report/` + fichero `.pbip`.

Estructura y versiones de esquema tomadas de informes guardados por Power BI Desktop y de la
documentación pública de Microsoft (json-schemas/fabric). Los nombres de página y visual se
derivan del spec (ids deterministas). Perímetro v1: textbox, card, line, column, bar, matrix,
slicer. Cualquier otra cosa hace fallar al emisor.
"""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path

from .ids import hex_id
from .platform_file import write_platform
from .spec import FieldRef, FilterSpec, PageSpec, SpecLock, TopNSpec, VisualSpec
from .theme import accent_colors, build_theme, load_brand

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric"
S_DEF_PROPS = f"{SCHEMA_BASE}/item/report/definitionProperties/2.0.0/schema.json"
S_VERSION = f"{SCHEMA_BASE}/item/report/definition/versionMetadata/1.0.0/schema.json"
S_REPORT = f"{SCHEMA_BASE}/item/report/definition/report/3.0.0/schema.json"
S_PAGES = f"{SCHEMA_BASE}/item/report/definition/pagesMetadata/1.0.0/schema.json"
S_PAGE = f"{SCHEMA_BASE}/item/report/definition/page/2.0.0/schema.json"
S_VISUAL = f"{SCHEMA_BASE}/item/report/definition/visualContainer/2.4.0/schema.json"
S_PBIP = f"{SCHEMA_BASE}/pbip/pbipProperties/1.0.0/schema.json"
VERSION_AT_IMPORT = {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"}

BASE_THEME = "CY26SU08"  # copiado de Power BI Desktop 2.157; ver resources/base_themes

_VISUAL_TYPES = {
    "shape": "shape",
    "card": "cardVisual",
    "table": "tableEx",
    "donut": "donutChart",
    "treemap": "treemap",
    "waterfall": "waterfallChart",
    "scatter": "scatterChart",
    "line": "lineChart",
    "column": "clusteredColumnChart",
    "bar": "clusteredBarChart",
    "matrix": "pivotTable",
    "slicer": "slicer",
    "textbox": "textbox",
}


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


# Codificación de literales PBIR, comprobada con `powerbi-report-author expr encode`
def _num(value: float) -> dict:
    return {"expr": {"Literal": {"Value": f"{value}D"}}}


def _int(value: int) -> dict:
    return {"expr": {"Literal": {"Value": f"{value}L"}}}


def _fill(hex_color: str) -> dict:
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_color}'"}}}}}


def _field(spec: SpecLock, ref: str) -> dict:
    r = FieldRef.parse(ref)
    kind = spec.field_kind(ref)
    return {kind: {"Expression": {"SourceRef": {"Entity": r.table}}, "Property": r.prop}}


def _projection(spec: SpecLock, ref: str, active: bool | None = None) -> dict:
    r = FieldRef.parse(ref)
    p = {"field": _field(spec, ref), "queryRef": f"{r.table}.{r.prop}", "nativeQueryRef": r.prop}
    if active is not None:
        p["active"] = active
    return p


def _role(spec: SpecLock, refs: list[str], active_first: bool = False) -> dict:
    return {"projections": [_projection(spec, ref, (i == 0) if active_first else None) for i, ref in enumerate(refs)]}


def _sort(spec: SpecLock, ref: str, direction: str) -> dict:
    return {"sort": [{"field": _field(spec, ref), "direction": direction}], "isDefaultSort": True}


def _is_temporal(spec: SpecLock, ref: str) -> bool:
    """Una categoría es temporal si pertenece a la tabla de fechas o es de tipo dateTime."""
    r = FieldRef.parse(ref)
    dt = spec.model.date_table
    if dt and r.table == dt.name:
        return True
    for t in spec.model.tables:
        if t.name == r.table:
            return any(c.name == r.prop and c.type == "dateTime" for c in t.columns)
    return False


def _filter_name(*parts: str) -> str:
    return "Filter" + hex_id(*parts, length=24)


def _literal_value(value: object) -> dict:
    if isinstance(value, bool):
        return {"Literal": {"Value": "true" if value else "false"}}
    if isinstance(value, int):
        return {"Literal": {"Value": f"{value}L"}}
    if isinstance(value, float):
        return {"Literal": {"Value": f"{value}D"}}
    return {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}


def _categorical_filter(spec: SpecLock, f: FilterSpec, scope: str) -> dict:
    """Filtro fijo por lista de valores. En `Where` la fuente es el alias de `From`, no la entidad."""
    ref = FieldRef.parse(f.field)
    alias = "f"
    column = {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": ref.prop}}
    condition: dict = {"In": {"Expressions": [column], "Values": [[_literal_value(v)] for v in f.values]}}
    if f.exclude:
        condition = {"Not": {"Expression": condition}}
    return {
        "name": _filter_name(scope, f.field, *(str(v) for v in f.values)),
        "field": _field(spec, f.field),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": ref.table, "Type": 0}],
            "Where": [{"Condition": condition}],
        },
        "howCreated": "User",
    }


_AGG_FUNCTIONS = {"sum": 0, "count": 5}


def _top_n_filter(spec: SpecLock, v: VisualSpec, t: TopNSpec) -> dict:
    """Top N de la categoría del visual.

    Dos restricciones del motor, comprobadas en Desktop 2.157: el `OrderBy` del subconsulta debe
    ser una agregación sobre columna (una medida da error), y cada tabla implicada necesita su
    propia entrada en `From` con su alias. Si la columna de orden vive en otra tabla que la
    categoría (lo normal: categoría en la dimensión, importe en el hecho), hacen falta dos.
    """
    cat = FieldRef.parse(v.category or "")
    by = FieldRef.parse(t.by)
    cat_alias = "c"
    by_alias = cat_alias if by.table == cat.table else "m"
    sources = [{"Name": cat_alias, "Entity": cat.table, "Type": 0}]
    if by_alias != cat_alias:
        sources.append({"Name": by_alias, "Entity": by.table, "Type": 0})
    return {
        "name": _filter_name("topn", v.name, v.category or "", t.by),
        "field": _field(spec, v.category or ""),
        "type": "TopN",
        "filter": {
            "Version": 2,
            "From": [
                {
                    "Name": "subquery",
                    "Expression": {
                        "Subquery": {
                            "Query": {
                                "Version": 2,
                                "From": sources,
                                "Select": [
                                    {
                                        "Column": {
                                            "Expression": {"SourceRef": {"Source": cat_alias}},
                                            "Property": cat.prop,
                                        },
                                        "Name": "field",
                                    }
                                ],
                                "OrderBy": [
                                    {
                                        "Direction": 2 if t.direction == "top" else 1,
                                        "Expression": {
                                            "Aggregation": {
                                                "Expression": {
                                                    "Column": {
                                                        "Expression": {"SourceRef": {"Source": by_alias}},
                                                        "Property": by.prop,
                                                    }
                                                },
                                                "Function": _AGG_FUNCTIONS[t.agg],
                                            }
                                        },
                                    }
                                ],
                                "Top": t.n,
                            }
                        }
                    },
                    "Type": 2,
                },
                {"Name": cat_alias, "Entity": cat.table, "Type": 0},
            ],
            "Where": [
                {
                    "Condition": {
                        "In": {
                            "Expressions": [
                                {"Column": {"Expression": {"SourceRef": {"Source": cat_alias}}, "Property": cat.prop}}
                            ],
                            "Table": {"SourceRef": {"Source": "subquery"}},
                        }
                    }
                }
            ],
        },
        "howCreated": "User",
    }


def _container_objects(v: VisualSpec) -> dict:
    objs: dict = {}
    if v.title:
        objs["title"] = [{"properties": {"show": _literal("true"), "text": _literal(f"'{v.title}'")}}]
    return objs


def visual_json(
    spec: SpecLock,
    page: PageSpec,
    v: VisualSpec,
    z: int,
    card_value_size: int = 40,
    card_label_size: int = 12,
    accents: dict[str, str] | None = None,
) -> dict:
    name = hex_id(spec.project, page.name, v.name)
    x, y, w, h = v.position(page.width, page.height)
    doc: dict = {
        "$schema": S_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
    }
    vt = _VISUAL_TYPES[v.type]
    visual: dict = {"visualType": vt}
    if v.type == "shape":
        # Bloque de color: barra de acento junto al título, separadores, fondos de sección
        color = (accents or {}).get(v.accent or "primary", "#1F4E79")
        visual["objects"] = {
            "shape": [{"properties": {"tileShape": _literal(f"'{v.shape_kind}'")}}],
            "fill": [{"properties": {"show": _literal("true"), "fillColor": _fill(color), "transparency": _num(0)}}],
            "outline": [{"properties": {"show": _literal("false")}}],
        }
        visual["visualContainerObjects"] = {
            "title": [{"properties": {"show": _literal("false")}}],
            "background": [{"properties": {"show": _literal("false")}}],
            "border": [{"properties": {"show": _literal("false")}}],
        }
    elif v.type == "textbox":
        # El título de página manda en la jerarquía: seminegrita, color fuerte y, si se pide,
        # una banda con el color de la identidad y el texto en blanco.
        banner = v.style == "banner"
        accents_ = accents or {}
        title_color = "#FFFFFF" if banner else accents_.get("title_text", "#1F2933")
        subtitle_color = "#E8EDF2" if banner else accents_.get("neutral", "#605E5C")
        paragraphs = [
            {
                "textRuns": [
                    {
                        "value": v.text,
                        "textStyle": {
                            "fontFamily": accents_.get("font_bold", "Segoe UI Semibold"),
                            "fontSize": f"{v.font_size_pt}pt",
                            "fontWeight": "bold",
                            "color": title_color,
                        },
                    }
                ],
                "horizontalTextAlignment": "left",
            }
        ]
        if v.subtitle:
            paragraphs.append(
                {
                    "textRuns": [
                        {
                            "value": v.subtitle,
                            "textStyle": {
                                "fontFamily": accents_.get("font", "Segoe UI"),
                                "fontSize": f"{max(10, v.font_size_pt // 2)}pt",
                                "color": subtitle_color,
                            },
                        }
                    ],
                    "horizontalTextAlignment": "left",
                }
            )
        visual["objects"] = {"general": [{"properties": {"paragraphs": paragraphs}}]}
        container: dict = {
            "title": [{"properties": {"show": _literal("false")}}],
            "border": [{"properties": {"show": _literal("false")}}],
        }
        if banner:
            container["background"] = [
                {"properties": {"show": _literal("true"), "color": _fill(accents_.get("primary", "#1F4E79")), "transparency": _num(0)}}
            ]
            container["padding"] = [
                {"properties": {"top": _num(10), "bottom": _num(10), "left": _num(16), "right": _num(16)}, "selector": {"id": "default"}}
            ]
        else:
            container["background"] = [{"properties": {"show": _literal("false")}}]
        visual["visualContainerObjects"] = container
    elif v.type == "card":
        visual["query"] = {"queryState": {"Data": _role(spec, [v.measure or ""])}, "sortDefinition": {"isDefaultSort": True}}
        visual["drillFilterOtherVisuals"] = True
        # La tarjeta ignora estas propiedades cuando llegan por el tema, así que las escribe el
        # emisor: cifra grande, sin marco interior y sin relleno que desaproveche el espacio.
        objects: dict = {
            "value": [{"properties": {"fontSize": _num(card_value_size + (4 if v.emphasis else 0))}}],
            "layout": [{"properties": {"paddingUniform": _int(2)}, "selector": {"id": "default"}}],
        }
        accent_hex = (accents or {}).get(v.accent or "", None)
        if accent_hex:
            # Franja de color a la izquierda: da jerarquía y dice de qué habla la tarjeta
            objects["accentBar"] = [
                {
                    "properties": {
                        "show": _literal("true"),
                        "position": _literal("'Left'"),
                        "color": _fill(accent_hex),
                        "width": _num(4),
                    },
                    "selector": {"id": "default"},
                }
            ]
        # La tarjeta dibuja su propia caja (cardCalloutArea). Con el borde y el fondo del contenedor
        # se ven dos marcos concéntricos, así que el contenedor se apaga y manda la caja interna.
        container_off = {
            "border": [{"properties": {"show": _literal("false")}}],
            "background": [{"properties": {"show": _literal("false")}}],
        }
        if v.title:
            # La tarjeta ya tiene etiqueta propia: el título va ahí y el del contenedor se oculta
            # (patrón recomendado por Microsoft; evita "Importe total" dos veces).
            objects["label"] = [
                {
                    "properties": {
                        "show": _literal("true"),
                        "text": _literal(f"'{v.title}'"),
                        "fontSize": _num(card_label_size),
                        # Etiqueta arriba y cifra debajo: el patrón de KPI que llena la caja
                        "position": _literal("'aboveValue'"),
                    },
                    "selector": {"id": "default"},
                }
            ]
            container_off["title"] = [{"properties": {"show": _literal("false")}}]
        visual["visualContainerObjects"] = container_off
        visual["objects"] = objects
    elif v.type in ("line", "column", "bar"):
        qs = {"Category": _role(spec, [v.category or ""], active_first=True), "Y": _role(spec, v.values)}
        if v.series:
            qs["Series"] = _role(spec, [v.series])
        by_category = v.sort == "category" or (v.sort == "auto" and (v.type == "line" or _is_temporal(spec, v.category or "")))
        if by_category:
            direction = "Descending" if v.sort_direction == "desc" else "Ascending"
            sort = _sort(spec, v.category or "", direction)
        else:
            direction = "Ascending" if v.sort_direction == "asc" else "Descending"
            sort = _sort(spec, v.values[0], direction)
        visual["query"] = {"queryState": qs, "sortDefinition": sort}
        visual["drillFilterOtherVisuals"] = True
        chart_objects: dict = {}
        if v.data_labels:
            # El valor va junto a la barra; el eje entonces sobra y su espacio pasa al gráfico
            chart_objects["labels"] = [{"properties": {"show": _literal("true")}}]
            chart_objects["valueAxis"] = [{"properties": {"show": _literal("false")}}]
        accent_hex = (accents or {}).get(v.accent or "", None)
        if v.color_measure:
            # Formato condicional real: el color sale de una medida DAX que devuelve el HEX,
            # así una barra negativa se pinta distinta de una positiva en el mismo gráfico.
            ref = FieldRef.parse(v.color_measure)
            chart_objects["dataPoint"] = [
                {
                    "properties": {
                        "fill": {
                            "solid": {
                                "color": {
                                    "expr": {"Measure": {"Expression": {"SourceRef": {"Entity": ref.table}}, "Property": ref.prop}}
                                }
                            }
                        }
                    }
                }
            ]
        elif accent_hex and not v.series:
            chart_objects["dataPoint"] = [{"properties": {"defaultColor": _fill(accent_hex)}}]
        if chart_objects:
            visual["objects"] = chart_objects
    elif v.type == "table":
        refs = list(v.rows) + list(v.values)
        visual["query"] = {"queryState": {"Values": _role(spec, refs, active_first=True)}}
        visual["drillFilterOtherVisuals"] = True
    elif v.type in ("donut", "treemap"):
        role = "Category" if v.type == "donut" else "Group"
        visual["query"] = {
            "queryState": {role: _role(spec, [v.category or ""], active_first=True), "Values" if v.type == "treemap" else "Y": _role(spec, v.values)},
            "sortDefinition": _sort(spec, v.values[0], "Descending"),
        }
        visual["drillFilterOtherVisuals"] = True
    elif v.type == "waterfall":
        qs = {"Category": _role(spec, [v.category or ""], active_first=True), "Y": _role(spec, v.values)}
        if v.series:
            qs["Breakdown"] = _role(spec, [v.series])
        visual["query"] = {"queryState": qs}
        visual["drillFilterOtherVisuals"] = True
    elif v.type == "scatter":
        qs = {
            "Category": _role(spec, [v.category or ""], active_first=True),
            "X": _role(spec, [v.x_measure or ""]),
            "Y": _role(spec, v.values),
        }
        if v.size_measure:
            qs["Size"] = _role(spec, [v.size_measure])
        visual["query"] = {"queryState": qs}
        visual["drillFilterOtherVisuals"] = True
    elif v.type == "matrix":
        qs = {"Rows": _role(spec, v.rows, active_first=True), "Values": _role(spec, v.values)}
        if v.columns:
            qs["Columns"] = _role(spec, v.columns, active_first=True)
        visual["query"] = {"queryState": qs}
        visual["drillFilterOtherVisuals"] = True
    elif v.type == "slicer":
        visual["query"] = {"queryState": {"Values": _role(spec, [v.field or ""])}}
        objects: dict = {}
        if v.mode == "dropdown":
            objects["data"] = [{"properties": {"mode": _literal("'Dropdown'")}}]
        if v.title:
            # El slicer ya tiene cabecera propia: el título va ahí, no en el contenedor (evita duplicarlo)
            objects["header"] = [{"properties": {"show": _literal("true"), "text": _literal(f"'{v.title}'")}}]
        if objects:
            visual["objects"] = objects
        visual["visualContainerObjects"] = {"title": [{"properties": {"show": _literal("false")}}]}
    else:  # pragma: no cover - el modelo pydantic ya lo impide
        raise ValueError(f"tipo de visual no soportado por el emisor: {v.type}")
    if v.type not in ("slicer", "card"):
        objs = _container_objects(v)
        if objs:
            visual.setdefault("visualContainerObjects", {}).update(objs)
    doc["visual"] = visual
    if v.top_n:
        doc["filterConfig"] = {"filters": [_top_n_filter(spec, v, v.top_n)]}
    return doc


def page_json(spec: SpecLock, page: PageSpec) -> dict:
    doc = {
        "$schema": S_PAGE,
        "name": hex_id(spec.project, page.name),
        "displayName": page.shown_name,
        "displayOption": "FitToPage",
        "height": page.height,
        "width": page.width,
    }
    if page.filters:
        doc["filterConfig"] = {"filters": [_categorical_filter(spec, f, f"page:{page.name}") for f in page.filters]}
    return doc


def report_json(custom_theme: str | None, spec: SpecLock | None = None) -> dict:
    doc: dict = {
        "$schema": S_REPORT,
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": VERSION_AT_IMPORT, "type": "SharedResources"}
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]}
        ],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True},
    }
    if spec is not None and spec.report.filters:
        doc["filterConfig"] = {"filters": [_categorical_filter(spec, f, "report") for f in spec.report.filters]}
    if custom_theme:
        doc["themeCollection"]["customTheme"] = {"name": custom_theme, "reportVersionAtImport": VERSION_AT_IMPORT, "type": "RegisteredResources"}
        doc["resourcePackages"].append(
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": custom_theme, "path": custom_theme, "type": "CustomTheme"}]}
        )
    return doc


def pbip_json(spec: SpecLock) -> dict:
    return {
        "$schema": S_PBIP,
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{spec.project}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }


def _dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write_report(spec: SpecLock, out_dir: Path) -> Path:
    """Escribe `<out_dir>/<project>.Report/` y `<out_dir>/<project>.pbip`; devuelve la carpeta del informe."""
    rp = out_dir / f"{spec.project}.Report"
    d = rp / "definition"
    _dump(
        rp / "definition.pbir",
        {"$schema": S_DEF_PROPS, "version": "4.0", "datasetReference": {"byPath": {"path": f"../{spec.project}.SemanticModel"}}},
    )
    _dump(d / "version.json", {"$schema": S_VERSION, "version": "2.0.0"})

    custom_theme: str | None = None
    card_value, card_label = 40, 12
    brand = None
    if spec.report.theme.brand:
        brand = load_brand(spec.report.theme.brand)
        card_value, card_label = brand.fonts.callout_size, brand.fonts.label_size + 1
        custom_theme, tdoc = build_theme(brand)
        _dump(rp / "StaticResources" / "RegisteredResources" / custom_theme, tdoc)
    _dump(d / "report.json", report_json(custom_theme, spec))

    accents = accent_colors(brand)
    page_ids = [hex_id(spec.project, p.name) for p in spec.report.pages]
    _dump(d / "pages" / "pages.json", {"$schema": S_PAGES, "pageOrder": page_ids, "activePageName": page_ids[0]})
    for p in spec.report.pages:
        pdir = d / "pages" / hex_id(spec.project, p.name)
        _dump(pdir / "page.json", page_json(spec, p))
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        for i, v in enumerate(p.visuals):
            doc = visual_json(
                spec, p, v, z=(i + 1) * 1000, card_value_size=card_value, card_label_size=card_label, accents=accents
            )
            _dump(pdir / "visuals" / doc["name"] / "visual.json", doc)
    themes = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    themes.mkdir(parents=True, exist_ok=True)
    with resources.as_file(resources.files("pbigen") / "resources" / "base_themes" / f"{BASE_THEME}.json") as src:
        shutil.copyfile(src, themes / f"{BASE_THEME}.json")
    write_platform(rp, spec.project, "Report")
    _dump(out_dir / f"{spec.project}.pbip", pbip_json(spec))
    return rp

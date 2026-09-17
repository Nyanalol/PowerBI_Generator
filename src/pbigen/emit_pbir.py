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
from .spec import FieldRef, PageSpec, SpecLock, VisualSpec
from .theme import build_theme, load_brand

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
    "card": "cardVisual",
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


def _container_objects(v: VisualSpec) -> dict:
    objs: dict = {}
    if v.title:
        objs["title"] = [{"properties": {"show": _literal("true"), "text": _literal(f"'{v.title}'")}}]
    return objs


def visual_json(
    spec: SpecLock, page: PageSpec, v: VisualSpec, z: int, card_value_size: int = 40, card_label_size: int = 12
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
    if v.type == "textbox":
        visual["objects"] = {
            "general": [
                {
                    "properties": {
                        "paragraphs": [{"textRuns": [{"value": v.text, "textStyle": {"fontSize": f"{v.font_size_pt}pt"}}]}]
                    }
                }
            ]
        }
        visual["visualContainerObjects"] = {
            "title": [{"properties": {"show": _literal("false")}}],
            "background": [{"properties": {"show": _literal("false")}}],
            "border": [{"properties": {"show": _literal("false")}}],
        }
    elif v.type == "card":
        visual["query"] = {"queryState": {"Data": _role(spec, [v.measure or ""])}, "sortDefinition": {"isDefaultSort": True}}
        visual["drillFilterOtherVisuals"] = True
        # La tarjeta ignora estas propiedades cuando llegan por el tema, así que las escribe el
        # emisor: cifra grande, sin marco interior y sin relleno que desaproveche el espacio.
        objects: dict = {
            "value": [{"properties": {"fontSize": _num(card_value_size)}}],
            "layout": [{"properties": {"paddingUniform": _int(2)}, "selector": {"id": "default"}}],
        }
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
                    "properties": {"show": _literal("true"), "text": _literal(f"'{v.title}'"), "fontSize": _num(card_label_size)},
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
        if v.data_labels:
            # El valor va junto a la barra; el eje entonces sobra y su espacio pasa al gráfico
            visual["objects"] = {
                "labels": [{"properties": {"show": _literal("true")}}],
                "valueAxis": [{"properties": {"show": _literal("false")}}],
            }
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
    return doc


def page_json(spec: SpecLock, page: PageSpec) -> dict:
    return {
        "$schema": S_PAGE,
        "name": hex_id(spec.project, page.name),
        "displayName": page.shown_name,
        "displayOption": "FitToPage",
        "height": page.height,
        "width": page.width,
    }


def report_json(custom_theme: str | None) -> dict:
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
    if spec.report.theme.brand:
        brand = load_brand(spec.report.theme.brand)
        card_value, card_label = brand.fonts.callout_size, brand.fonts.label_size + 1
        custom_theme, tdoc = build_theme(brand)
        _dump(rp / "StaticResources" / "RegisteredResources" / custom_theme, tdoc)
    _dump(d / "report.json", report_json(custom_theme))

    page_ids = [hex_id(spec.project, p.name) for p in spec.report.pages]
    _dump(d / "pages" / "pages.json", {"$schema": S_PAGES, "pageOrder": page_ids, "activePageName": page_ids[0]})
    for p in spec.report.pages:
        pdir = d / "pages" / hex_id(spec.project, p.name)
        _dump(pdir / "page.json", page_json(spec, p))
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        for i, v in enumerate(p.visuals):
            doc = visual_json(spec, p, v, z=(i + 1) * 1000, card_value_size=card_value, card_label_size=card_label)
            _dump(pdir / "visuals" / doc["name"] / "visual.json", doc)
    themes = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    themes.mkdir(parents=True, exist_ok=True)
    with resources.as_file(resources.files("pbigen") / "resources" / "base_themes" / f"{BASE_THEME}.json") as src:
        shutil.copyfile(src, themes / f"{BASE_THEME}.json")
    write_platform(rp, spec.project, "Report")
    _dump(out_dir / f"{spec.project}.pbip", pbip_json(spec))
    return rp

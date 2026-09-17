"""Emisor PBIR: SpecLock -> carpeta `<proyecto>.Report/` + fichero `.pbip`.

Estructura y versiones de esquema tomadas de informes guardados por Power BI
Desktop y de la documentación pública de Microsoft (json-schemas/fabric).
Los nombres de página y visual se derivan del spec (ids deterministas).
"""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path

from .ids import hex_id
from .platform_file import write_platform
from .spec import FieldRef, PageSpec, SpecLock, VisualSpec

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric"
S_DEF_PROPS = f"{SCHEMA_BASE}/item/report/definitionProperties/2.0.0/schema.json"
S_VERSION = f"{SCHEMA_BASE}/item/report/definition/versionMetadata/1.0.0/schema.json"
S_REPORT = f"{SCHEMA_BASE}/item/report/definition/report/3.0.0/schema.json"
S_PAGES = f"{SCHEMA_BASE}/item/report/definition/pagesMetadata/1.0.0/schema.json"
S_PAGE = f"{SCHEMA_BASE}/item/report/definition/page/2.0.0/schema.json"
S_VISUAL = f"{SCHEMA_BASE}/item/report/definition/visualContainer/2.4.0/schema.json"
S_PBIP = f"{SCHEMA_BASE}/pbip/pbipProperties/1.0.0/schema.json"

BASE_THEME = "CY26SU08"  # copiado de Power BI Desktop 2.157; ver resources/base_themes


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _measure_field(ref: FieldRef) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": ref.table}}, "Property": ref.prop}}


def _position(v: VisualSpec, z: int) -> dict:
    return {"x": v.x, "y": v.y, "z": z, "height": v.h, "width": v.w, "tabOrder": z}


def _container_objects(v: VisualSpec) -> dict:
    objs: dict = {}
    if v.title:
        objs["title"] = [{"properties": {"show": _literal("true"), "text": _literal(f"'{v.title}'")}}]
    return objs


def visual_json(spec: SpecLock, page: PageSpec, v: VisualSpec, z: int) -> dict:
    name = hex_id(spec.project, page.name, v.stable_name)
    doc: dict = {"$schema": S_VISUAL, "name": name, "position": _position(v, z)}
    if v.type == "textbox":
        doc["visual"] = {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {"textRuns": [{"value": v.text, "textStyle": {"fontSize": f"{v.font_size_pt}pt"}}]}
                            ]
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "title": [{"properties": {"show": _literal("false")}}],
                "background": [{"properties": {"show": _literal("false")}}],
            },
        }
    elif v.type == "card":
        ref = FieldRef.parse(v.measure or "")
        doc["visual"] = {
            "visualType": "cardVisual",
            "query": {
                "queryState": {
                    "Data": {
                        "projections": [
                            {
                                "field": _measure_field(ref),
                                "queryRef": f"{ref.table}.{ref.prop}",
                                "nativeQueryRef": ref.prop,
                            }
                        ]
                    }
                },
                "sortDefinition": {"isDefaultSort": True},
            },
            "drillFilterOtherVisuals": True,
        }
        objs = _container_objects(v)
        if objs:
            doc["visual"]["visualContainerObjects"] = objs
    else:  # pragma: no cover - el modelo pydantic ya lo impide
        raise ValueError(f"tipo de visual no soportado: {v.type}")
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


def report_json() -> dict:
    # reportVersionAtImport: "versión máxima de visual/página/informe al importar el tema";
    # usamos las versiones de esquema que este emisor escribe.
    return {
        "$schema": S_REPORT,
        "themeCollection": {
            "baseTheme": {
                "name": BASE_THEME,
                "reportVersionAtImport": {"visual": "2.4.0", "page": "2.0.0", "report": "3.0.0"},
                "type": "SharedResources",
            }
        },
    }


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
        {
            "$schema": S_DEF_PROPS,
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{spec.project}.SemanticModel"}},
        },
    )
    _dump(d / "version.json", {"$schema": S_VERSION, "version": "2.0.0"})
    _dump(d / "report.json", report_json())
    page_ids = [hex_id(spec.project, p.name) for p in spec.report.pages]
    _dump(d / "pages" / "pages.json", {"$schema": S_PAGES, "pageOrder": page_ids, "activePageName": page_ids[0]})
    for p in spec.report.pages:
        # La carpeta de la página y la de cada visual se llaman como su `name` (id hexadecimal).
        pdir = d / "pages" / hex_id(spec.project, p.name)
        _dump(pdir / "page.json", page_json(spec, p))
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        for i, v in enumerate(p.visuals):
            doc = visual_json(spec, p, v, z=(i + 1) * 1000)
            _dump(pdir / "visuals" / doc["name"] / "visual.json", doc)
    write_platform(rp, spec.project, "Report")
    themes = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    themes.mkdir(parents=True, exist_ok=True)
    with resources.as_file(resources.files("pbigen") / "resources" / "base_themes" / f"{BASE_THEME}.json") as src:
        shutil.copyfile(src, themes / f"{BASE_THEME}.json")
    _dump(out_dir / f"{spec.project}.pbip", pbip_json(spec))
    return rp

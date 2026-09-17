"""Identidad de cliente -> tema JSON de Power BI.

`templates/brands/<id>/brand.yaml` describe colores y tipografía una vez por cliente; el
generador lo traduce a un tema de informe (`StaticResources/RegisteredResources/<nombre>.json`).
La identidad vive en el tema; los visuales solo llevan campos y posición (docs/01 §4.3.3).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .config import REPO_ROOT

THEME_SCHEMA = "https://raw.githubusercontent.com/microsoft/powerbi-desktop-samples/main/Report-Theme-JSON-Schema/reportThemeSchema-2.157.json"


class BrandColors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[str] = Field(min_length=1)
    background: str = "#FFFFFF"
    foreground: str = "#252423"
    secondary: str = "#605E5C"
    accent: str = "#118DFF"
    table_accent: str | None = None
    good: str = "#1AAB40"
    neutral: str = "#D9B300"
    bad: str = "#D64550"


class BrandFonts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str = "Segoe UI"
    family_bold: str | None = None
    title_size: int = 14
    label_size: int = 10
    callout_size: int = 32


class Brand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    colors: BrandColors
    fonts: BrandFonts = BrandFonts()
    card_radius: int = 6


def brands_dir() -> Path:
    return REPO_ROOT / "templates" / "brands"


def load_brand(brand_id: str) -> Brand:
    p = brands_dir() / brand_id / "brand.yaml"
    if not p.exists():
        raise FileNotFoundError(f"identidad {brand_id!r} no encontrada: {p}")
    return Brand.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))


def _theme_body(brand: Brand) -> dict:
    c, f = brand.colors, brand.fonts
    bold = f.family_bold or f"{f.family} Semibold"
    return {
        "dataColors": c.data,
        "background": c.background,
        "foreground": c.foreground,
        "foregroundNeutralSecondary": c.secondary,
        "accent": c.accent,
        "tableAccent": c.table_accent or c.accent,
        "good": c.good,
        "neutral": c.neutral,
        "bad": c.bad,
        "textClasses": {
            "title": {"fontFace": bold, "fontSize": f.title_size, "color": c.foreground},
            "header": {"fontFace": bold, "fontSize": f.label_size + 2, "color": c.foreground},
            "label": {"fontFace": f.family, "fontSize": f.label_size, "color": c.secondary},
            "callout": {"fontFace": bold, "fontSize": f.callout_size, "color": c.foreground},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "*": [{"fontFamily": f.family}],
                    "title": [{"show": True, "fontFamily": bold, "fontSize": f.title_size, "fontColor": {"solid": {"color": c.foreground}}}],
                    "background": [{"show": True, "color": {"solid": {"color": c.background}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": "#E1DFDD"}}, "radius": brand.card_radius}],
                    "visualHeader": [{"show": True}],
                }
            },
            "page": {"*": {"background": [{"color": {"solid": {"color": "#F5F5F5"}}, "transparency": 0}]}},
        },
    }


def build_theme(brand: Brand) -> tuple[str, dict]:
    """Devuelve (nombre de fichero, documento).

    El `name` interno debe ser igual al nombre del fichero (Desktop no carga el tema si difieren)
    y lleva un sufijo hash del contenido porque Desktop cachea los temas por nombre.
    """
    body = _theme_body(brand)
    digest = hashlib.sha1(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    file_name = f"{brand.id}-{digest}.json"
    return file_name, {"name": file_name, **body}  # sin $schema, igual que los temas base de Desktop

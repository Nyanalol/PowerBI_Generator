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
    title_size: int = 13
    label_size: int = 11  # ejes, leyendas y tablas: 10 pt se lee mal en pantalla grande
    callout_size: int = 32  # la cifra manda, pero a 40 pt aplastaba al resto de la página


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
                    # Esquinas redondeadas en contenedores y barras: el aspecto por defecto es de 2015
                    "*": [{"fontFamily": f.family, "wordWrap": False, "rectangleRoundedCurve": brand.card_radius, "roundEdge": 6}],
                    "title": [{"show": True, "fontFamily": bold, "fontSize": f.title_size, "fontColor": {"solid": {"color": c.foreground}}}],
                    "background": [{"show": True, "color": {"solid": {"color": c.background}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": "#E1DFDD"}}, "radius": brand.card_radius}],
                    "visualHeader": [{"show": True}],
                    # Menos aire alrededor del contenido: el visual ya tiene borde y título.
                    # `$id: default` es obligatorio en los objetos que declaran selector, o Desktop
                    # ignora la entrada del tema en silencio.
                    "padding": [{"$id": "default", "top": 6, "bottom": 6, "left": 10, "right": 10}],
                    # Los títulos de eje repiten lo que ya dice el título del visual y se truncan
                    "categoryAxis": [
                        {"showAxisTitle": False, "gridlineShow": False, "fontSize": f.label_size, "maxMarginFactor": 35}
                    ],
                    "valueAxis": [{"showAxisTitle": False, "gridlineStyle": "dotted", "fontSize": f.label_size}],
                    "legend": [{"fontSize": f.label_size, "showTitle": False}],
                    "labels": [{"fontSize": f.label_size}],
                }
            },
            # La tarjeta: cifra grande, sin marco interior ni relleno que roben espacio
            "cardVisual": {
                "*": {
                    "value": [{"fontSize": f.callout_size, "fontFamily": bold, "fontColor": {"solid": {"color": c.foreground}}}],
                    "label": [{"$id": "default", "fontSize": f.label_size + 1, "fontColor": {"solid": {"color": c.secondary}}}],
                    "cardCalloutArea": [{"paddingUniform": 0, "backgroundTransparency": 100}],
                    "layout": [{"$id": "default", "paddingUniform": 4, "borderWidth": 0, "customizeLines": False}],
                }
            },
            # La matriz gana filas visibles apretando el interlineado, y se lee mejor con filas
            # alternas, sin rejilla vertical y con la cabecera y el total marcados
            "pivotTable": {
                "*": {
                    "grid": [
                        {
                            "rowPadding": 3,  # con 5 la matriz perdia la ultima fila en una banda de 213 px
                            "textSize": f.label_size,
                            "gridVertical": False,
                            "gridHorizontal": True,
                            "gridHorizontalColor": {"solid": {"color": "#EDEBE9"}},
                            "gridHorizontalWeight": 1,
                            "outlineWeight": 0,
                        }
                    ],
                    "values": [
                        {
                            "fontSize": f.label_size,
                            "bandedRowHeaders": True,
                            "backColorSecondary": {"solid": {"color": "#FAFAFA"}},
                            "outlineWeight": 0,
                        }
                    ],
                    "columnHeaders": [
                        {
                            "fontSize": f.label_size,
                            "fontFamily": bold,
                            "fontColor": {"solid": {"color": c.foreground}},
                            "backColor": {"solid": {"color": "#F3F2F1"}},
                            "alignment": "Right",
                            "outlineWeight": 0,
                            # La matriz deja hueco a la derecha si las columnas solo miden su contenido
                            "columnAdjustment": "growToFit",
                            "autoSizeColumnWidth": True,
                        }
                    ],
                    "rowHeaders": [{"fontSize": f.label_size, "stepped": True, "outlineWeight": 0}],
                    "total": [{"fontSize": f.label_size, "bold": True, "fontColor": {"solid": {"color": c.foreground}}}],
                }
            },
            # La línea por defecto es fina y sin marcadores: con 16 puntos se lee mejor gruesa.
            # Sin borde: si todos los visuales llevan marco, la página parece una plantilla.
            "lineChart": {
                "*": {
                    "lineStyles": [{"strokeWidth": 3, "lineStyle": "solid", "showMarker": True, "markerShape": "circle", "markerSize": 4}],
                    "border": [{"show": False}],
                }
            },
            # Barras y columnas: más gruesas (menos hueco entre ellas) y sin borde
            "clusteredColumnChart": {
                "*": {
                    "categoryAxis": [{"innerPadding": 25, "maxMarginFactor": 35}],
                    "dataPoint": [{"borderShow": False}],
                    "labels": [{"fontSize": f.label_size, "labelPosition": "OutsideEnd", "enableBackground": False}],
                    "border": [{"show": False}],
                }
            },
            "clusteredBarChart": {
                "*": {
                    "categoryAxis": [{"innerPadding": 25, "maxMarginFactor": 35}],
                    "dataPoint": [{"borderShow": False}],
                    "labels": [{"fontSize": f.label_size, "labelPosition": "OutsideEnd", "enableBackground": False}],
                    "border": [{"show": False}],
                }
            },
            # El slicer es un control, no un gráfico: cabecera discreta y sin caja alrededor
            "slicer": {
                "*": {
                    "header": [{"show": True, "fontFamily": bold, "textSize": f.label_size, "fontColor": {"solid": {"color": c.secondary}}}],
                    "items": [{"textSize": f.label_size, "fontColor": {"solid": {"color": c.foreground}}, "padding": 4}],
                }
            },
            "page": {"*": {"background": [{"color": {"solid": {"color": "#F7F8FA"}}, "transparency": 0}]}},
        },
    }


def accent_colors(brand: Brand | None) -> dict[str, str]:
    """Nombres semánticos a HEX. Un informe usa pocos colores y cada uno significa algo."""
    if brand is None:
        return {
            "primary": "#118DFF",
            "secondary": "#12239E",
            "positive": "#1AAB40",
            "negative": "#D64550",
            "warning": "#D9B300",
            "neutral": "#605E5C",
        }
    c = brand.colors
    return {
        "primary": c.data[0],
        "secondary": c.data[1] if len(c.data) > 1 else c.accent,
        "positive": c.good,
        "negative": c.bad,
        "warning": c.neutral,
        "neutral": c.secondary,
        # Extras que usa el emisor para el cuadro de texto del título
        "title_text": c.foreground,
        "font": brand.fonts.family,
        "font_bold": brand.fonts.family_bold or f"{brand.fonts.family} Semibold",
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

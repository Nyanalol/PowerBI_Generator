"""Proyectos: `init` (esqueleto + brief), `purge` (borrar datos, salidas y caché)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

Classification = Literal["publica", "interna", "confidencial", "personal"]


class Brief(BaseModel):
    """`project.yaml`: lo que el usuario expresa en lenguaje natural. Todo lo demás se deriva de aquí."""

    model_config = ConfigDict(extra="forbid")

    cliente: str = ""
    modo: Literal["crear", "revisar"] = "crear"
    data_classification: Classification = "interna"
    identidad: str = ""  # id de templates/brands/<id>/ (Fase 2)
    audiencia: str = ""
    preguntas: list[str] = []
    kpis: list[str] = []
    definiciones: dict[str, str] = {}  # KPI -> definición exacta, grano, exclusiones
    restricciones: list[str] = []
    seguridad_rls: list[str] = []
    referencias: list[str] = []


BRIEF_TEMPLATE = """# Brief del proyecto (ver docs/01-analisis-viabilidad.md §4.0).
# Rellena lo que sepas; lo que falte lo preguntará el Analyst/Strategist antes del gate.
cliente: ""
modo: crear                    # crear | revisar
data_classification: interna   # publica | interna | confidencial | personal
identidad: ""                  # templates/brands/<id> (Fase 2)
audiencia: ""
preguntas: []                  # preguntas de negocio que el informe debe responder
kpis: []                       # KPIs prioritarios
definiciones: {}               # "Importe": "suma de líneas facturadas, sin abonos"
restricciones: []              # páginas máximas, visuales vetados, accesibilidad...
seguridad_rls: []              # requisitos de seguridad a nivel de fila
referencias: []                # PBIP o capturas de referencia
"""

SPEC_TEMPLATE = """# spec_lock.yaml — contrato máquina. Lo escribe el Analyst/Strategist (o una persona) y lo lee el código.
version: 0
project: {name}
locale: es-ES

sources:
  - id: datos
    type: excel
    path: sources/datos.xlsx

model:
  tables: []

report:
  pages: []
"""

PURGE_DIRS = ("sources", "pbip", "screenshots", "analysis", "exports")


def init_project(project_dir: Path, name: str | None = None) -> list[Path]:
    project_dir = project_dir.resolve()
    name = name or project_dir.name
    created: list[Path] = []
    for sub in ("sources", "tests", "analysis"):
        p = project_dir / sub
        if not p.exists():
            p.mkdir(parents=True)
            created.append(p)
    for fname, text in (("project.yaml", BRIEF_TEMPLATE), ("spec_lock.yaml", SPEC_TEMPLATE.format(name=name))):
        p = project_dir / fname
        if not p.exists():
            p.write_text(text, encoding="utf-8", newline="\n")
            created.append(p)
    gi = project_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("sources/\npbip/\nscreenshots/\nanalysis/\nexports/\n**/.pbi/\n", encoding="utf-8", newline="\n")
        created.append(gi)
    return created


def load_brief(project_dir: Path) -> Brief:
    p = project_dir / "project.yaml"
    if not p.exists():
        return Brief()
    return Brief.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def purge_project(project_dir: Path) -> list[Path]:
    """Borra datos, salidas generadas, capturas y caché. Conserva spec, brief y tests."""
    removed: list[Path] = []
    for sub in PURGE_DIRS:
        p = project_dir / sub
        if p.exists():
            shutil.rmtree(p)
            removed.append(p)
    return removed

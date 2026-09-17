"""Fichero `.platform` (metadatos de integración Git de Fabric) para informe y modelo.

Desktop lo genera al guardar y la CLI de validación de Microsoft lo exige. El
`logicalId` es un GUID determinista derivado del nombre del proyecto y del tipo.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

S_PLATFORM = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
_NS = uuid.UUID("6f1c7a4e-3b2d-4c5e-9a8f-0d1e2f3a4b5c")  # espacio de nombres fijo de pbigen


def logical_id(project: str, item_type: str) -> str:
    return str(uuid.uuid5(_NS, f"{item_type}:{project}"))


def write_platform(folder: Path, project: str, item_type: str) -> None:
    doc = {
        "$schema": S_PLATFORM,
        "metadata": {"type": item_type, "displayName": project},
        "config": {"version": "2.0", "logicalId": logical_id(project, item_type)},
    }
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".platform").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

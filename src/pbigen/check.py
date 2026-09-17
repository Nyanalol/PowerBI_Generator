"""Comprobaciones estáticas sobre la salida generada (`pbip/`), no sobre el spec.

Leen los ficheros como lo haría un tercero: bindings del informe contra objetos del TMDL,
solapes y límites del lienzo, medidas sin formato o descripción. Sirven tanto para lo
generado como, en la Fase 2b, para un PBIP ajeno.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

_MEASURE_RE = re.compile(r"^\tmeasure\s+(?:'((?:[^']|'')+)'|(\S+))\s*=", re.M)
_COLUMN_RE = re.compile(r"^\tcolumn\s+(?:'((?:[^']|'')+)'|(\S+))\s*$", re.M)
_TABLE_RE = re.compile(r"^table\s+(?:'((?:[^']|'')+)'|(\S+))\s*$", re.M)
_FORMAT_RE = re.compile(r"^\t\tformatString:", re.M)


@dataclass
class Finding:
    severity: str  # error | warning
    code: str
    message: str
    file: str = ""


def _name(m: re.Match[str]) -> str:
    return (m.group(1) or m.group(2)).replace("''", "'")


def read_model_objects(semantic_model_dir: Path) -> dict[str, dict[str, set[str]]]:
    """{tabla: {"columns": {...}, "measures": {...}}} leído de los .tmdl."""
    out: dict[str, dict[str, set[str]]] = {}
    for f in (semantic_model_dir / "definition" / "tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        tm = _TABLE_RE.search(text)
        if not tm:
            continue
        table = _name(tm)
        out[table] = {
            "columns": {_name(m) for m in _COLUMN_RE.finditer(text)},
            "measures": {_name(m) for m in _MEASURE_RE.finditer(text)},
        }
    return out


def _walk_fields(node: Any) -> Iterator[tuple[str, str, str]]:
    """Recorre un JSON PBIR y devuelve (kind, entity, property) de cada referencia Column/Measure."""
    if isinstance(node, dict):
        for kind in ("Column", "Measure"):
            ref = node.get(kind)
            if isinstance(ref, dict) and "Property" in ref:
                entity = ref.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if entity:
                    yield kind, entity, ref["Property"]
        for v in node.values():
            yield from _walk_fields(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_fields(v)


def check_report(report_dir: Path, semantic_model_dir: Path | None) -> list[Finding]:
    findings: list[Finding] = []
    model = read_model_objects(semantic_model_dir) if semantic_model_dir and semantic_model_dir.exists() else None
    pages_dir = report_dir / "definition" / "pages"
    for page_json in pages_dir.glob("*/page.json"):
        page = json.loads(page_json.read_text(encoding="utf-8"))
        width, height = page.get("width", 1280), page.get("height", 720)
        rects: list[tuple[str, float, float, float, float]] = []
        for vjson in (page_json.parent / "visuals").glob("*/visual.json"):
            rel = str(vjson.relative_to(report_dir)).replace("\\", "/")
            v = json.loads(vjson.read_text(encoding="utf-8"))
            pos = v.get("position", {})
            x, y, w, h = pos.get("x", 0), pos.get("y", 0), pos.get("width", 0), pos.get("height", 0)
            if x < 0 or y < 0 or x + w > width or y + h > height:
                findings.append(Finding("error", "VISUAL_OUT_OF_CANVAS", f"visual fuera del lienzo {width}x{height}: ({x},{y},{w},{h})", rel))
            rects.append((rel, x, y, w, h))
            if model is not None:
                for kind, entity, prop in _walk_fields(v.get("visual", {})):
                    objs = model.get(entity)
                    bucket = "columns" if kind == "Column" else "measures"
                    if objs is None:
                        findings.append(Finding("error", "BINDING_TABLE_MISSING", f"tabla {entity!r} no existe en el modelo", rel))
                    elif prop not in objs[bucket]:
                        findings.append(Finding("error", "BINDING_FIELD_MISSING", f"{kind} {entity}[{prop}] no existe en el modelo", rel))
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                if a[1] < b[1] + b[3] and b[1] < a[1] + a[3] and a[2] < b[2] + b[4] and b[2] < a[2] + a[4]:
                    findings.append(Finding("warning", "VISUAL_OVERLAP", f"solape entre {a[0]} y {b[0]}", str(page_json.parent.name)))
    if model is not None:
        findings += check_measures(semantic_model_dir)  # type: ignore[arg-type]
    return findings


def check_measures(semantic_model_dir: Path) -> list[Finding]:
    """Medidas sin `formatString` o sin descripción `///` (avisos)."""
    findings: list[Finding] = []
    for f in (semantic_model_dir / "definition" / "tables").glob("*.tmdl"):
        lines = f.read_text(encoding="utf-8").splitlines()
        rel = str(f.relative_to(semantic_model_dir)).replace("\\", "/")
        for i, line in enumerate(lines):
            m = _MEASURE_RE.match(line)
            if not m:
                continue
            name = _name(m)
            described = i > 0 and lines[i - 1].strip().startswith("///")
            block: list[str] = []
            for nxt in lines[i + 1 :]:
                if nxt.strip() == "" or (nxt.startswith("\t") and not nxt.startswith("\t\t")):
                    break
                block.append(nxt)
            if not any(b.strip().startswith("formatString:") for b in block):
                findings.append(Finding("warning", "MEASURE_NO_FORMAT", f"medida {name!r} sin formatString", rel))
            if not described:
                findings.append(Finding("warning", "MEASURE_NO_DESCRIPTION", f"medida {name!r} sin descripción (///)", rel))
    return findings

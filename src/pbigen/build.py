"""Orquestación: spec_lock.yaml -> carpeta pbip/ del proyecto."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .emit_pbir import write_report
from .emit_tmdl import write_semantic_model
from .spec import SpecLock, load_spec


@dataclass
class BuildResult:
    out_dir: Path
    semantic_model: Path
    report: Path
    pbip_file: Path


def _clean_output(out_dir: Path) -> None:
    """Vacía pbip/ fichero a fichero. En Windows una carpeta abierta por otro proceso (una shell,
    Desktop) impide borrarla entera; los ficheros sí se pueden reemplazar. Conserva `.pbi/`
    (caché y ajustes locales de Desktop), que no es salida del generador."""
    for f in sorted(out_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if ".pbi" in f.parts:
            continue
        try:
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                f.rmdir()
        except OSError:
            if f.is_file():
                raise
            # carpeta en uso: se reutiliza


def build_project(project_dir: Path, clean: bool = True) -> BuildResult:
    project_dir = project_dir.resolve()
    spec: SpecLock = load_spec(project_dir / "spec_lock.yaml")
    for s in spec.sources:
        if not (project_dir / s.path).exists():
            raise FileNotFoundError(f"origen {s.id!r}: no existe {project_dir / s.path}")
    data_folders = {(project_dir / s.path).parent.resolve() for s in spec.sources}
    if len(data_folders) != 1:
        raise ValueError("en la v0 todos los orígenes deben estar en la misma carpeta")
    out_dir = project_dir / "pbip"
    if clean and out_dir.exists():
        _clean_output(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sm = write_semantic_model(spec, out_dir, data_folders.pop())
    rp = write_report(spec, out_dir)
    return BuildResult(out_dir, sm, rp, out_dir / f"{spec.project}.pbip")

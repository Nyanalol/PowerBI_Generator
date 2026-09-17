"""Configuración de máquina: `config.yaml` en la raíz del repo (ignorado por git)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools_dir: str = ".tools"
    powerbi_desktop_exe: str = ""
    desktop_supported_family: str = "2.157"

    @property
    def tools_path(self) -> Path:
        p = Path(self.tools_dir)
        return p if p.is_absolute() else REPO_ROOT / p


def load_config() -> Config:
    for name in ("config.yaml", "config.example.yaml"):
        p = REPO_ROOT / name
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return Config.model_validate(data)
    return Config()

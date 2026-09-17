"""`pbigen doctor`: prerrequisitos verificables de la máquina (ver docs/01, §0)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .tools import cli_path, desktop_family, find_desktop, node_exe, run_cli


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def run_checks(cfg: Config, project_dir: Path | None = None) -> list[Check]:
    checks: list[Check] = []
    checks.append(Check("Python", sys.version_info >= (3, 12), sys.version.split()[0]))

    node = node_exe()
    checks.append(Check("Node (wheel)", node.exists(), str(node), "uv sync"))

    for name in ("powerbi-report-author", "powerbi-desktop"):
        p = cli_path(cfg.tools_path, name)
        ok = p.exists()
        detail = str(p)
        if ok:
            r = run_cli(cfg.tools_path, name, "--version")
            detail = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "?"
        checks.append(Check(f"CLI {name}", ok, detail, "pbigen install-tools"))

    d = find_desktop(cfg.powerbi_desktop_exe or None)
    if d is None:
        checks.append(Check("Power BI Desktop", False, "no encontrado", "instalar Desktop (Store o MSI)"))
    else:
        fam = desktop_family(d.version)
        ok = fam == cfg.desktop_supported_family
        checks.append(
            Check(
                "Power BI Desktop",
                ok,
                f"{d.version} en {d.exe}",
                "" if ok else f"familia soportada: {cfg.desktop_supported_family}.x (docs/01, riesgo T5)",
            )
        )

    bridge_ok, bridge_detail = _bridge_status(cfg)
    checks.append(
        Check(
            "Puente Desktop (external tool access)",
            bridge_ok,
            bridge_detail,
            "Desktop > Archivo > Opciones > Características de versión preliminar > "
            "'Enable external tool access to Power BI Desktop through secure local APIs'; reiniciar Desktop",
        )
    )

    if project_dir is not None:
        p = project_dir.resolve()
        long_ok = len(str(p)) <= 120
        checks.append(Check("Ruta corta (<=120, límite PBIP 260)", long_ok, f"{len(str(p))} caracteres: {p}"))
        sync = any(k in str(p).lower() for k in ("onedrive", "sharepoint"))
        checks.append(Check("Fuera de OneDrive/SharePoint", not sync, str(p), "mover el proyecto a una carpeta local"))
    return checks


def _bridge_status(cfg: Config) -> tuple[bool, str]:
    if not cli_path(cfg.tools_path, "powerbi-desktop").exists():
        return False, "CLI no instalada"
    r = run_cli(cfg.tools_path, "powerbi-desktop", "status")
    text = (r.stdout or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False, (text or r.stderr.strip())[:200]
    status = data.get("status") or data.get("bridgeStatus") or json.dumps(data)[:200]
    inst = data.get("instances") or []
    if inst:
        return True, f"{status}; instancias: {len(inst)}"
    return status not in ("not_connected", "error"), str(status)

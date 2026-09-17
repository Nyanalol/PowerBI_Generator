"""Herramientas externas: Node (vía wheel de Python), CLIs de Microsoft y Power BI Desktop.

Ninguna instalación necesita permisos de administrador: Node viene en
`nodejs-wheel-binaries` y las CLIs se instalan con npm en `tools_dir`.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MS_CLIS = ["@microsoft/powerbi-report-authoring-cli", "@microsoft/powerbi-desktop-bridge-cli"]


def node_dir() -> Path:
    import nodejs_wheel  # instalado como dependencia del paquete

    return Path(nodejs_wheel.__file__).parent


def node_exe() -> Path:
    return node_dir() / "node.exe"


def npm_cli() -> Path:
    return node_dir() / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(node_dir()) + os.pathsep + env.get("PATH", "")
    return env


def install_ms_clis(tools_dir: Path) -> subprocess.CompletedProcess[str]:
    tools_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(node_exe()), str(npm_cli()), "install", "--prefix", str(tools_dir), "--no-audit", "--no-fund"]
    cmd += [f"{p}@latest" for p in MS_CLIS]
    return subprocess.run(cmd, capture_output=True, text=True, env=_env())


_CLI_PACKAGES = {
    "powerbi-report-author": "@microsoft/powerbi-report-authoring-cli",
    "powerbi-desktop": "@microsoft/powerbi-desktop-bridge-cli",
}


def cli_path(tools_dir: Path, name: str) -> Path:
    """Script JS de entrada de la CLI (se lanza con node; los .cmd de npm dependen del PATH)."""
    pkg_dir = tools_dir / "node_modules" / _CLI_PACKAGES[name]
    manifest = pkg_dir / "package.json"
    if not manifest.exists():
        return pkg_dir / "dist" / "cli.js"  # ruta inexistente: sirve para `exists()` == False
    import json

    bin_entry = json.loads(manifest.read_text(encoding="utf-8")).get("bin")
    rel = bin_entry[name] if isinstance(bin_entry, dict) else bin_entry
    return pkg_dir / rel


def run_cli(tools_dir: Path, name: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    script = cli_path(tools_dir, name)
    if not script.exists():
        raise FileNotFoundError(f"{name} no está instalado en {tools_dir}; ejecuta `pbigen install-tools`")
    return subprocess.run([str(node_exe()), str(script), *args], capture_output=True, text=True, env=_env(), cwd=cwd)


@dataclass
class DesktopInfo:
    exe: Path
    version: str  # p. ej. 2.157.1354.0


_STORE_RE = re.compile(r"Microsoft\.MicrosoftPowerBIDesktop_(\d+\.\d+\.\d+\.\d+)_")


def find_desktop(explicit: str | None = None) -> DesktopInfo | None:
    """Localiza PBIDesktop.exe (Store o MSI). Devuelve None si no está."""
    if explicit:
        p = Path(explicit)
        return DesktopInfo(p, _file_version(p)) if p.exists() else None
    store_root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
    candidates: list[DesktopInfo] = []
    try:
        for d in store_root.iterdir():
            m = _STORE_RE.match(d.name)
            if m and (d / "bin" / "PBIDesktop.exe").exists():
                candidates.append(DesktopInfo(d / "bin" / "PBIDesktop.exe", m.group(1)))
    except (PermissionError, FileNotFoundError):
        pass
    msi = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Power BI Desktop" / "bin" / "PBIDesktop.exe"
    if msi.exists():
        candidates.append(DesktopInfo(msi, _file_version(msi)))
    if not candidates:
        return None
    return max(candidates, key=lambda c: tuple(int(x) for x in c.version.split(".")))


def _file_version(exe: Path) -> str:
    ps = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"(Get-Item '{exe}').VersionInfo.ProductVersion",
    ]
    try:
        out = subprocess.run(ps, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return "?"
    return out or "?"


def desktop_family(version: str) -> str:
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else version

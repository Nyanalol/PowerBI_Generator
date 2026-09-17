"""Motor Analysis Services local de Power BI Desktop: catálogo, actualización de datos y consultas DAX.

Usa el cliente ADOMD.NET oficial (paquete NuGet de librerías cliente de Analysis Services)
a través de un script PowerShell, porque el cliente es .NET Framework. Todo local: nada
sale de la máquina.
"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

ADOMD_NUGET_URL = "https://www.nuget.org/api/v2/package/Microsoft.AnalysisServices.AdomdClient.retail.amd64/"


def adomd_dll(tools_dir: Path) -> Path:
    return tools_dir / "adomd" / "lib" / "net45" / "Microsoft.AnalysisServices.AdomdClient.dll"


def install_adomd(tools_dir: Path) -> Path:
    """Descarga el paquete NuGet del cliente ADOMD y extrae la DLL en tools_dir/adomd. Sin administrador."""
    target = tools_dir / "adomd"
    target.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ADOMD_NUGET_URL, timeout=120) as resp:  # noqa: S310 - URL fija de nuget.org
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.startswith("lib/net45/") or name.endswith(".nuspec"):
                z.extract(name, target)
    return adomd_dll(tools_dir)


def _run(tools_dir: Path, mode: str, **kwargs: str) -> dict[str, Any]:
    dll = adomd_dll(tools_dir)
    if not dll.exists():
        raise FileNotFoundError(f"cliente ADOMD no instalado ({dll}); ejecuta `pbigen install-tools`")
    with resources.as_file(resources.files("pbigen") / "resources" / "engine.ps1") as script:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Dll", str(dll), "-Mode", mode]
        for k, v in kwargs.items():
            if v:
                cmd += [f"-{k}", str(v)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    text = (r.stdout or "").strip()
    try:
        data = json.loads(text.splitlines()[-1]) if text else {}
    except json.JSONDecodeError:
        data = {"error": text or r.stderr.strip()}
    if r.returncode != 0 or "error" in data:
        raise RuntimeError(data.get("error") or r.stderr.strip() or f"engine.ps1 salió con {r.returncode}")
    return data


def catalogs(tools_dir: Path, port: int = 0, desktop_pid: int = 0) -> dict[str, Any]:
    return _run(tools_dir, "catalogs", Port=str(port or ""), DesktopPid=str(desktop_pid or ""))


def refresh(tools_dir: Path, port: int = 0, catalog: str = "", desktop_pid: int = 0) -> dict[str, Any]:
    return _run(tools_dir, "refresh", Port=str(port or ""), Catalog=catalog, DesktopPid=str(desktop_pid or ""))


def query(tools_dir: Path, dax: str, port: int = 0, catalog: str = "", desktop_pid: int = 0) -> dict[str, Any]:
    return _run(tools_dir, "query", Port=str(port or ""), Catalog=catalog, Dax=dax, DesktopPid=str(desktop_pid or ""))

"""CLI `pbigen`. Verbos: doctor, install-tools, demo-data, build, validate, open, screenshot."""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from . import __version__
from .build import build_project
from .config import load_config
from .demo_data import generate_ventas
from .doctor import run_checks
from .spec import load_spec
from .tools import find_desktop, install_ms_clis, run_cli

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Generador de proyectos Power BI (PBIP).")


def _ok(msg: str) -> None:
    typer.secho(f"OK    {msg}", fg=typer.colors.GREEN)


def _bad(msg: str) -> None:
    typer.secho(f"FALTA {msg}", fg=typer.colors.RED)


@app.callback()
def _main() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(__version__)


@app.command()
def doctor(project_dir: Path | None = typer.Argument(None, help="Proyecto a comprobar (opcional)")) -> None:
    """Comprueba los prerrequisitos de la máquina."""
    cfg = load_config()
    checks = run_checks(cfg, project_dir)
    for c in checks:
        (_ok if c.ok else _bad)(f"{c.name}: {c.detail}" + (f"  ->  {c.fix}" if (not c.ok and c.fix) else ""))
    failed = [c for c in checks if not c.ok]
    raise typer.Exit(code=1 if failed else 0)


@app.command("install-tools")
def install_tools() -> None:
    """Instala las CLIs de Microsoft (npm, sin administrador) en tools_dir."""
    cfg = load_config()
    typer.echo(f"Instalando en {cfg.tools_path} ...")
    r = install_ms_clis(cfg.tools_path)
    typer.echo((r.stdout or "").strip()[-800:])
    if r.returncode != 0:
        typer.secho(r.stderr.strip()[-1500:], fg=typer.colors.RED)
        raise typer.Exit(code=r.returncode)
    _ok("CLIs instaladas")


@app.command("demo-data")
def demo_data(project_dir: Path, year: int = 2025) -> None:
    """Genera sources/ventas.xlsx sintético en el proyecto."""
    path = project_dir / "sources" / "ventas.xlsx"
    rows, total = generate_ventas(path, year=year)
    _ok(f"{path} ({rows} filas, importe total {total:,.2f})")


@app.command()
def build(project_dir: Path) -> None:
    """Genera pbip/ (modelo TMDL + informe PBIR) desde spec_lock.yaml."""
    r = build_project(project_dir)
    _ok(f"modelo   {r.semantic_model}")
    _ok(f"informe  {r.report}")
    _ok(f"pbip     {r.pbip_file}")


@app.command()
def validate(project_dir: Path) -> None:
    """Valida el spec (pydantic) y el informe PBIR (CLI de Microsoft)."""
    spec = load_spec(project_dir / "spec_lock.yaml")
    _ok(f"spec_lock.yaml válido ({len(spec.model.tables)} tablas, {len(spec.report.pages)} páginas)")
    cfg = load_config()
    report_dir = project_dir / "pbip" / f"{spec.project}.Report"
    if not report_dir.exists():
        _bad(f"{report_dir} no existe; ejecuta `pbigen build`")
        raise typer.Exit(code=1)
    r = run_cli(cfg.tools_path, "powerbi-report-author", "validate", str(report_dir))
    typer.echo((r.stdout or r.stderr).strip())
    raise typer.Exit(code=r.returncode)


@app.command("open")
def open_(project_dir: Path) -> None:
    """Abre el .pbip generado en Power BI Desktop."""
    spec = load_spec(project_dir / "spec_lock.yaml")
    pbip = (project_dir / "pbip" / f"{spec.project}.pbip").resolve()
    if not pbip.exists():
        _bad(f"{pbip} no existe; ejecuta `pbigen build`")
        raise typer.Exit(code=1)
    cfg = load_config()
    d = find_desktop(cfg.powerbi_desktop_exe or None)
    if d is None:
        _bad("Power BI Desktop no encontrado")
        raise typer.Exit(code=1)
    subprocess.Popen([str(d.launch_exe), str(pbip)])
    _ok(f"abriendo {pbip} con {d.launch_exe}")


@app.command()
def screenshot(project_dir: Path, out_dir: Path | None = None) -> None:
    """Captura todas las páginas vía el puente de Desktop (el informe debe estar abierto)."""
    cfg = load_config()
    out = (out_dir or project_dir / "screenshots").resolve()
    out.mkdir(parents=True, exist_ok=True)
    st = run_cli(cfg.tools_path, "powerbi-desktop", "status")
    typer.echo(st.stdout.strip() or st.stderr.strip())
    r = run_cli(cfg.tools_path, "powerbi-desktop", "screenshot-all", "--output-dir", str(out))
    typer.echo((r.stdout or r.stderr).strip())
    raise typer.Exit(code=r.returncode)

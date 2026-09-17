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


@app.command("spec-schema")
def spec_schema() -> None:
    """Imprime el JSON Schema del contrato spec_lock.yaml (lo que el emisor sabe serializar, ni más ni menos)."""
    import json

    from .spec import SpecLock

    typer.echo(json.dumps(SpecLock.model_json_schema(), indent=2, ensure_ascii=False))


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
    from .engine import adomd_dll, install_adomd

    if adomd_dll(cfg.tools_path).exists():
        _ok(f"cliente ADOMD ya presente: {adomd_dll(cfg.tools_path)}")
    else:
        typer.echo("Descargando cliente ADOMD (NuGet) ...")
        _ok(f"cliente ADOMD: {install_adomd(cfg.tools_path)}")


@app.command()
def init(project_dir: Path, name: str | None = typer.Option(None, help="Nombre del proyecto Power BI")) -> None:
    """Crea el esqueleto de un proyecto: project.yaml (brief), spec_lock.yaml, sources/, tests/, analysis/."""
    from .project import init_project

    created = init_project(project_dir, name)
    for p in created:
        _ok(f"creado {p}")
    if not created:
        typer.echo("nada que crear: el proyecto ya existe")


@app.command()
def profile(
    project_dir: Path,
    sample_rows: int = typer.Option(0, help="Filas de muestra en el perfil (solo proyectos publica/interna)"),
) -> None:
    """Perfila los orígenes (tipos, cardinalidad, nulos, rangos, claves) -> analysis/data_profile.json."""
    from .profile import profile_project
    from .project import load_brief

    spec = load_spec(project_dir / "spec_lock.yaml")
    brief = load_brief(project_dir)
    if sample_rows > 0 and brief.data_classification in ("confidencial", "personal"):
        _bad(f"proyecto clasificado {brief.data_classification}: no se incluyen filas de muestra")
        sample_rows = 0
    out = profile_project(project_dir, spec, sample_rows)
    _ok(f"perfil escrito en {out}")


@app.command()
def check(project_dir: Path) -> None:
    """Comprobaciones estáticas sobre pbip/: bindings contra el modelo, lienzo, solapes, medidas."""
    from .check import check_report

    spec = load_spec(project_dir / "spec_lock.yaml")
    rp = project_dir / "pbip" / f"{spec.project}.Report"
    sm = project_dir / "pbip" / f"{spec.project}.SemanticModel"
    if not rp.exists():
        _bad(f"{rp} no existe; ejecuta `pbigen build`")
        raise typer.Exit(code=1)
    findings = check_report(rp, sm if sm.exists() else None)
    for f in findings:
        (_bad if f.severity == "error" else typer.echo)(f"{f.severity.upper():7} {f.code}: {f.message}  [{f.file}]")
    errors = [f for f in findings if f.severity == "error"]
    (_ok if not errors else _bad)(f"{len(findings)} hallazgos, {len(errors)} errores")
    raise typer.Exit(code=1 if errors else 0)


@app.command()
def test(project_dir: Path) -> None:
    """Ejecuta tests/*.yaml: DAX contra el modelo abierto en Desktop frente a SQL (duckdb) sobre los orígenes."""
    from .daxtest import load_tests, run_tests

    spec = load_spec(project_dir / "spec_lock.yaml")
    cases = load_tests(project_dir)
    if not cases:
        _bad("no hay tests en tests/*.yaml")
        raise typer.Exit(code=1)
    cfg = load_config()
    results = run_tests(project_dir, spec, cfg.tools_path, cases)
    for r in results:
        (_ok if r.passed else _bad)(f"{r.name}" + (f"  {r.detail}" if r.detail else ""))
    failed = [r for r in results if not r.passed]
    typer.echo(f"{len(results) - len(failed)}/{len(results)} tests pasan")
    raise typer.Exit(code=1 if failed else 0)


@app.command()
def purge(project_dir: Path, yes: bool = typer.Option(False, "--yes", help="No pedir confirmación")) -> None:
    """Borra datos, salidas, capturas, análisis y caché del proyecto (conserva spec, brief y tests)."""
    from .project import PURGE_DIRS, purge_project

    if not yes:
        typer.confirm(f"Borrar {', '.join(PURGE_DIRS)} de {project_dir}?", abort=True)
    for p in purge_project(project_dir):
        _ok(f"borrado {p}")


@app.command("demo-data")
def demo_data(project_dir: Path) -> None:
    """Genera sources/ventas.xlsx sintético (Ventas 2024-2025, Productos, Clientes) en el proyecto."""
    path = project_dir / "sources" / "ventas.xlsx"
    rows, total = generate_ventas(path)
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
    for pid in _desktop_pids_with(cfg, pbip):
        # Un cambio de modelo (TMDL) solo se aplica reabriendo; el puente solo recarga el informe.
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        _ok(f"cerrada la instancia de Desktop {pid} que tenía abierto este PBIP")
    subprocess.Popen([str(d.launch_exe), str(pbip)])
    _ok(f"abriendo {pbip} con {d.launch_exe}")


def _last_json_object(text: str) -> dict:
    """Último objeto JSON de una salida que puede llevar varios (la CLI imprime status y resultado)."""
    import json

    start = len(text)
    while True:
        start = text.rfind("{", 0, start)
        if start < 0:
            return {}
        if start == 0 or text[start - 1] in "\r\n":
            try:
                return json.loads(text[start:])
            except json.JSONDecodeError:
                pass


def _desktop_pids_with(cfg, pbip: Path) -> list[int]:  # type: ignore[no-untyped-def]
    """PIDs de Desktop (según el puente) que tienen abierto exactamente este .pbip."""
    import json

    try:
        r = run_cli(cfg.tools_path, "powerbi-desktop", "status")
        data = json.loads(r.stdout.strip() or "{}")
    except Exception:  # noqa: BLE001
        return []
    want = str(pbip).lower()
    return [int(i["pid"]) for i in data.get("instances", []) if str(i.get("currentFilePath", "")).lower() == want]


@app.command()
def refresh(project_dir: Path) -> None:
    """Actualiza los datos del modelo abierto en Desktop (TMSL full refresh contra el motor local)."""
    from .engine import refresh as _refresh

    cfg = load_config()
    data = _refresh(cfg.tools_path)
    _ok(f"actualizado catálogo {data['catalog']} en {data['ms']} ms (puerto {data['port']})")


@app.command()
def query(project_dir: Path, dax: str) -> None:
    """Ejecuta una consulta DAX (EVALUATE ...) contra el modelo abierto en Desktop y muestra las filas."""
    from .engine import query as _query

    cfg = load_config()
    data = _query(cfg.tools_path, dax)
    rows = data.get("rows") or []
    for row in rows:
        typer.echo("  ".join(f"{k}={v}" for k, v in row.items()))
    _ok(f"{len(rows)} filas en {data['ms']} ms")


@app.command()
def reload(project_dir: Path) -> None:
    """Recarga en Desktop la definición del informe desde disco (puente). Para cambios de modelo usa `open`."""
    cfg = load_config()
    spec = load_spec(project_dir / "spec_lock.yaml")
    pbip = (project_dir / "pbip" / f"{spec.project}.pbip").resolve()
    pids = _desktop_pids_with(cfg, pbip)
    if not pids:
        _bad("ninguna instancia de Desktop tiene abierto este PBIP; ejecuta `pbigen open`")
        raise typer.Exit(code=1)
    r = run_cli(cfg.tools_path, "powerbi-desktop", "reload", "--pid", str(pids[0]))
    typer.echo((r.stdout or r.stderr).strip()[-300:])
    raise typer.Exit(code=r.returncode)


@app.command()
def screenshot(
    project_dir: Path,
    out_dir: Path | None = None,
    settle_ms: int = typer.Option(4000, help="Espera antes de capturar, para que los visuales terminen de renderizar"),
) -> None:
    """Captura todas las páginas vía el puente de Desktop (el informe debe estar abierto)."""
    import json

    cfg = load_config()
    spec = load_spec(project_dir / "spec_lock.yaml")
    out = (out_dir or project_dir / "screenshots").resolve()
    out.mkdir(parents=True, exist_ok=True)
    pids = _desktop_pids_with(cfg, (project_dir / "pbip" / f"{spec.project}.pbip").resolve())
    args = ["screenshot-all", "--output-dir", str(out), "--settle", str(settle_ms)]
    if pids:
        args += ["--pid", str(pids[0])]
    r = run_cli(cfg.tools_path, "powerbi-desktop", *args)
    data = _last_json_object((r.stdout or "").strip())
    for s in data.get("screenshots", []):
        _ok(f"{s.get('pageDisplayName')}: {s.get('outputPath')}")
    if data.get("status") != "ok":
        _bad((data.get("error", {}).get("message") if data else text[-600:]) or "captura fallida")
        for f in (data.get("error", {}).get("details", {}) or {}).get("failures", []):
            typer.echo(f"  {f.get('pageDisplayName')}: {f.get('error', {}).get('message')}")
        raise typer.Exit(code=1)

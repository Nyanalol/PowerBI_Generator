"""Fase 1: init, profile, check y helpers de tests DAX, sobre el productor real y sin Desktop."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pbigen.build import build_project
from pbigen.check import check_report, read_model_objects
from pbigen.daxtest import _norm, _rows_equal, load_tests
from pbigen.demo_data import generate_ventas
from pbigen.profile import profile_project
from pbigen.project import init_project, load_brief, purge_project
from pbigen.spec import load_spec

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "ventas-demo"


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    shutil.copy(EXAMPLE / "spec_lock.yaml", tmp_path / "spec_lock.yaml")
    shutil.copytree(EXAMPLE / "tests", tmp_path / "tests")
    generate_ventas(tmp_path / "sources" / "ventas.xlsx")
    return tmp_path


def test_init_creates_brief_and_spec(tmp_path: Path) -> None:
    created = init_project(tmp_path / "nuevo", name="Nuevo")
    names = {p.name for p in created}
    assert {"project.yaml", "spec_lock.yaml", "sources", "tests", "analysis", ".gitignore"} <= names
    brief = load_brief(tmp_path / "nuevo")
    assert brief.modo == "crear" and brief.data_classification == "interna"
    assert init_project(tmp_path / "nuevo") == []  # idempotente


def test_profile_reports_types_and_facts(project: Path) -> None:
    spec = load_spec(project / "spec_lock.yaml")
    out = profile_project(project, spec)
    data = json.loads(out.read_text(encoding="utf-8"))
    table = data["sources"][0]["tables"][0]
    types = {c["name"]: c["suggested_type"] for c in table["columns"]}
    assert types == {"Fecha": "dateTime", "ProductoId": "int64", "ClienteId": "int64", "Unidades": "int64", "Importe": "double"}
    assert table["rows"] == 6448 and table["date_columns"] == ["Fecha"]
    assert [t["name"] for t in data["sources"][0]["tables"]] == ["Ventas", "Productos", "Clientes"]
    productos = data["sources"][0]["tables"][1]
    assert {"ProductoId", "Producto"} <= set(productos["candidate_keys"])
    assert "sample" not in table, "sin filas de muestra por defecto"
    importe = next(c for c in table["columns"] if c["name"] == "Importe")
    assert abs(importe["sum"] - 12580440.12) < 0.01


def test_check_passes_on_generated_output_and_reads_model(project: Path) -> None:
    r = build_project(project)
    objs = read_model_objects(r.semantic_model)
    assert {"Importe Total", "Importe YTD", "Importe PY", "Ticket Medio"} <= objs["Ventas"]["measures"]
    assert "Importe" in objs["Ventas"]["columns"] and "AñoMes" in objs["Fechas"]["columns"]
    findings = check_report(r.report, r.semantic_model)
    assert findings == [], [f.message for f in findings]


def test_check_detects_broken_binding_and_overlap(project: Path) -> None:
    r = build_project(project)
    cards = [v for v in (r.report / "definition" / "pages").glob("*/visuals/*/visual.json") if json.loads(v.read_text(encoding="utf-8"))["visual"]["visualType"] == "cardVisual"]
    vis = cards[0]
    doc = json.loads(vis.read_text(encoding="utf-8"))
    doc["visual"]["query"]["queryState"]["Data"]["projections"][0]["field"]["Measure"]["Property"] = "NoExiste"
    doc["position"].update({"x": 0, "y": 0})  # solapa con el textbox del título
    vis.write_text(json.dumps(doc), encoding="utf-8")
    codes = {f.code for f in check_report(r.report, r.semantic_model)}
    assert {"BINDING_FIELD_MISSING", "VISUAL_OVERLAP"} <= codes


def test_daxtest_helpers_normalize_and_compare(project: Path) -> None:
    assert len(load_tests(project)) == 9
    assert _norm("1,234.5") == 1234.5 and _norm("2025-01-01 00:00:00") == "2025-01-01T00:00:00"
    assert _rows_equal([("Norte", 10.001)], [("Norte", 10.0)], tol=0.005)
    assert not _rows_equal([("Norte", 10.1)], [("Norte", 10.0)], tol=0.005)
    assert _rows_equal([("a", 1.0), ("b", 2.0)], [("b", 2.0), ("a", 1.0)], tol=0.0)


def test_purge_keeps_spec_and_tests(project: Path) -> None:
    build_project(project)
    removed = purge_project(project)
    assert {p.name for p in removed} >= {"sources", "pbip"}
    assert (project / "spec_lock.yaml").exists() and (project / "tests").exists()

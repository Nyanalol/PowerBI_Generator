"""Tests de la Fase 0: el productor real (`build_project`) sobre el ejemplo versionado."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from pbigen.build import build_project
from pbigen.demo_data import generate_ventas
from pbigen.spec import SpecLock, load_spec

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "ventas-demo"


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copia del ejemplo con su Excel generado por el productor real."""
    p = tmp_path_factory.mktemp("ventas-demo")
    shutil.copy(EXAMPLE / "spec_lock.yaml", p / "spec_lock.yaml")
    generate_ventas(p / "sources" / "ventas.xlsx")
    return p


def _tree_digest(root: Path) -> dict[str, str]:
    out = {}
    for f in sorted(root.rglob("*")):
        if f.is_file():
            out[str(f.relative_to(root))] = hashlib.sha1(f.read_bytes()).hexdigest()
    return out


def test_spec_loads_and_cross_refs_hold() -> None:
    spec = load_spec(EXAMPLE / "spec_lock.yaml")
    assert spec.project == "VentasDemo"
    assert {m.name for m in spec.model.tables[0].measures} >= {"Importe Total", "Unidades Totales"}


def test_spec_rejects_unknown_measure(tmp_path: Path) -> None:
    text = (EXAMPLE / "spec_lock.yaml").read_text(encoding="utf-8").replace("Ventas[Importe Total]", "Ventas[NoExiste]")
    (tmp_path / "spec_lock.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="NoExiste"):
        load_spec(tmp_path / "spec_lock.yaml")


def test_spec_rejects_unknown_keys() -> None:
    data = {"version": 0, "project": "X", "sources": [], "model": {"tables": []}, "report": {"pages": []}, "extra": 1}
    with pytest.raises(ValueError):
        SpecLock.model_validate(data)


def test_build_writes_expected_files(project: Path) -> None:
    r = build_project(project)
    files = {str(f.relative_to(r.out_dir)).replace("\\", "/") for f in r.out_dir.rglob("*") if f.is_file()}
    expected = {
        "VentasDemo.pbip",
        "VentasDemo.Report/.platform",
        "VentasDemo.Report/definition.pbir",
        "VentasDemo.Report/definition/version.json",
        "VentasDemo.Report/definition/report.json",
        "VentasDemo.Report/definition/pages/pages.json",
        "VentasDemo.SemanticModel/.platform",
        "VentasDemo.SemanticModel/definition.pbism",
        "VentasDemo.SemanticModel/definition/database.tmdl",
        "VentasDemo.SemanticModel/definition/model.tmdl",
        "VentasDemo.SemanticModel/definition/expressions.tmdl",
        "VentasDemo.SemanticModel/definition/tables/Ventas.tmdl",
    }
    assert expected <= files
    pages = json.loads((r.report / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    page_dir = r.report / "definition" / "pages" / pages["pageOrder"][0]
    assert (page_dir / "page.json").exists(), "la carpeta de página debe llamarse como su id"
    visuals = list((page_dir / "visuals").iterdir())
    assert len(visuals) == 3
    for vdir in visuals:
        doc = json.loads((vdir / "visual.json").read_text(encoding="utf-8"))
        assert doc["name"] == vdir.name


def test_build_is_deterministic(project: Path) -> None:
    first = _tree_digest(build_project(project).out_dir)
    second = _tree_digest(build_project(project).out_dir)
    assert first == second


def test_tmdl_partition_reads_excel_by_parameter(project: Path) -> None:
    r = build_project(project)
    tmdl = (r.semantic_model / "definition" / "tables" / "Ventas.tmdl").read_text(encoding="utf-8")
    assert 'Excel.Workbook(File.Contents(#"DataFolder" & "\\ventas.xlsx")' in tmdl
    assert "measure 'Importe Total' = SUM(Ventas[Importe])" in tmdl
    assert "\tpartition Ventas = m" in tmdl
    expr = (r.semantic_model / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert str(project / "sources").replace("/", "\\") in expr

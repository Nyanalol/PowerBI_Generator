"""Tests del emisor: el productor real (`build_project`) sobre el ejemplo versionado (spec v1)."""

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
    return {str(f.relative_to(root)): hashlib.sha1(f.read_bytes()).hexdigest() for f in sorted(root.rglob("*")) if f.is_file()}


def test_spec_loads_and_cross_refs_hold() -> None:
    spec = load_spec(EXAMPLE / "spec_lock.yaml")
    assert spec.project == "VentasDemo" and spec.version == 1
    assert spec.field_kind("Ventas[Importe Total]") == "Measure"
    assert spec.field_kind("Fechas[AñoMes]") == "Column"
    assert len(spec.model.relationships) == 3 and len(spec.report.pages) == 3


@pytest.mark.parametrize(
    "bad, msg",
    [
        ("Ventas[Importe Total]\", title: Importe total", "NoExiste"),
    ],
)
def test_spec_rejects_unknown_measure(tmp_path: Path, bad: str, msg: str) -> None:
    text = (EXAMPLE / "spec_lock.yaml").read_text(encoding="utf-8").replace('measure: "Ventas[Importe Total]"', 'measure: "Ventas[NoExiste]"', 1)
    (tmp_path / "spec_lock.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        load_spec(tmp_path / "spec_lock.yaml")


def test_spec_rejects_column_where_measure_expected(tmp_path: Path) -> None:
    text = (EXAMPLE / "spec_lock.yaml").read_text(encoding="utf-8").replace('measure: "Ventas[Importe Total]"', 'measure: "Ventas[Importe]"', 1)
    (tmp_path / "spec_lock.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="debe ser una medida"):
        load_spec(tmp_path / "spec_lock.yaml")


def test_spec_rejects_unknown_keys() -> None:
    data = {"version": 1, "project": "X", "sources": [], "model": {"tables": []}, "report": {"pages": []}, "extra": 1}
    with pytest.raises(ValueError):
        SpecLock.model_validate(data)


def test_grid_fits_slicer_minimum_height() -> None:
    from pbigen.spec import GridPos

    x, y, w, h = GridPos(col=8, row=0, cols=2, rows=1).to_px()
    assert h >= 76, "un slicer desplegable con cabecera necesita 76 px"
    assert x + w <= 1280 and y + h <= 720


def test_build_writes_expected_files(project: Path) -> None:
    spec = load_spec(project / "spec_lock.yaml")
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
        "VentasDemo.SemanticModel/definition/relationships.tmdl",
        "VentasDemo.SemanticModel/definition/tables/Ventas.tmdl",
        "VentasDemo.SemanticModel/definition/tables/Fechas.tmdl",
    }
    assert expected <= files
    themes = [f for f in files if f.startswith("VentasDemo.Report/StaticResources/RegisteredResources/demo-")]
    assert len(themes) == 1, "tema de cliente registrado con sufijo hash"
    report = json.loads((r.report / "definition" / "report.json").read_text(encoding="utf-8"))
    assert report["themeCollection"]["customTheme"]["name"] == Path(themes[0]).name
    pages = json.loads((r.report / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    for page_spec, page_id in zip(spec.report.pages, pages["pageOrder"]):
        page_dir = r.report / "definition" / "pages" / page_id
        assert (page_dir / "page.json").exists()
        visuals = list((page_dir / "visuals").iterdir())
        assert len(visuals) == len(page_spec.visuals)
        for vdir in visuals:
            doc = json.loads((vdir / "visual.json").read_text(encoding="utf-8"))
            assert doc["name"] == vdir.name


def test_visual_types_and_roles(project: Path) -> None:
    r = build_project(project)
    kinds: dict[str, set[str]] = {}
    for v in (r.report / "definition" / "pages").glob("*/visuals/*/visual.json"):
        doc = json.loads(v.read_text(encoding="utf-8"))["visual"]
        kinds.setdefault(doc["visualType"], set()).update(doc.get("query", {}).get("queryState", {}).keys())
    assert kinds["lineChart"] == {"Category", "Y"}
    assert kinds["clusteredColumnChart"] >= {"Category", "Y"} and "Series" in kinds["clusteredColumnChart"]
    assert kinds["pivotTable"] == {"Rows", "Columns", "Values"}
    assert kinds["slicer"] == {"Values"}
    assert kinds["cardVisual"] == {"Data"}
    assert "textbox" in kinds


def test_build_is_deterministic(project: Path) -> None:
    assert _tree_digest(build_project(project).out_dir) == _tree_digest(build_project(project).out_dir)


def test_tmdl_model_shape(project: Path) -> None:
    r = build_project(project)
    ventas = (r.semantic_model / "definition" / "tables" / "Ventas.tmdl").read_text(encoding="utf-8")
    assert 'Excel.Workbook(File.Contents(#"DataFolder" & "\\ventas.xlsx")' in ventas
    assert "\tmeasure 'Importe YTD' = TOTALYTD([Importe Total], Fechas[Fecha])" in ventas
    assert "\tcolumn ProductoId\n\t\tdataType: int64\n\t\tisHidden" in ventas
    fechas = (r.semantic_model / "definition" / "tables" / "Fechas.tmdl").read_text(encoding="utf-8")
    assert "\tdataCategory: Time" in fechas and "\t\tisKey" in fechas and "= calculated" in fechas
    assert "\t\tsortByColumn: MesNum" in fechas
    rels = (r.semantic_model / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    assert "\tfromColumn: Ventas.ProductoId\n\ttoColumn: Productos.ProductoId" in rels
    model = (r.semantic_model / "definition" / "model.tmdl").read_text(encoding="utf-8")
    assert "ref table Fechas" in model


def test_relationship_columns_with_spaces_are_quoted(tmp_path: Path) -> None:
    """Desktop rechaza `fromColumn: Pedidos.Fecha Pedido`; exige Pedidos.'Fecha Pedido' (visto en 2.157)."""
    from pbigen.emit_tmdl import relationships_tmdl
    from pbigen.spec import RelationshipSpec

    text = relationships_tmdl([RelationshipSpec(**{"from": "Pedidos[Fecha Pedido]", "to": "Fechas[Fecha]"})])
    assert "\tfromColumn: Pedidos.'Fecha Pedido'" in text
    assert "\ttoColumn: Fechas.Fecha" in text


def test_spec_rejects_measure_named_like_table_or_column(tmp_path: Path) -> None:
    """Desktop no abre un modelo con una medida llamada como su tabla o como una columna (visto con Superstore)."""
    base = (EXAMPLE / "spec_lock.yaml").read_text(encoding="utf-8")
    bad = base.replace("- { name: Importe Total, dax:", "- { name: Ventas, dax:", 1)
    (tmp_path / "spec_lock.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="igual que una tabla"):
        load_spec(tmp_path / "spec_lock.yaml")
    bad = base.replace("- { name: Importe Total, dax:", "- { name: Importe, dax:", 1)
    (tmp_path / "spec_lock.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="igual que una columna"):
        load_spec(tmp_path / "spec_lock.yaml")


def test_m_field_access_is_always_quoted() -> None:
    """`[Sub-Category]` rompe el motor M con "Identificador no válido": hay que usar [#"..."]."""
    from pbigen.emit_tmdl import table_tmdl
    from pbigen.spec import ColumnSpec, SourceSpec, TableSourceSpec, TableSpec

    table = TableSpec(
        name="Productos",
        source=TableSourceSpec(source="s", sheet="Hoja", distinct_key="Product ID", attributes=["Sub-Category"]),
        columns=[
            ColumnSpec(name="ProductoId", source_column="Product ID", type="string"),
            ColumnSpec(name="Subcategoría", source_column="Sub-Category", type="string"),
        ],
    )
    text = table_tmdl(table, SourceSpec(id="s", type="excel", path="sources/x.xlsx"))
    assert 'each List.First([#"Sub-Category"])' in text
    assert "List.First([Sub-Category])" not in text


def test_date_table_has_quarter_axis_and_sort_direction(project: Path) -> None:
    """4 años son 48 meses ilegibles en un eje; AñoTrimestre da 16 puntos. `sort_direction: asc`
    pone lo peor arriba en un ranking (así se ven las pérdidas)."""
    from pbigen.emit_pbir import visual_json
    from pbigen.spec import GridPos, VisualSpec

    r = build_project(project)
    fechas = (r.semantic_model / "definition" / "tables" / "Fechas.tmdl").read_text(encoding="utf-8")
    assert "\tcolumn AñoTrimestre" in fechas
    assert '"AñoTrimestre", FORMAT([Fecha], "yyyy") & "-T" & FORMAT([Fecha], "q")' in fechas

    spec = load_spec(project / "spec_lock.yaml")
    page = spec.report.pages[0]
    v = VisualSpec(
        type="bar",
        name="ranking",
        category="Productos[Producto]",
        values=["Ventas[Importe Total]"],
        sort_direction="asc",
        grid=GridPos(col=0, row=0, cols=4, rows=3),
    )
    doc = visual_json(spec, page, v, z=1000)
    assert doc["visual"]["query"]["sortDefinition"]["sort"][0]["direction"] == "Ascending"

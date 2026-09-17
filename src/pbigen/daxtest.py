"""Tests DAX con duckdb como oráculo independiente.

`tests/*.yaml` en el proyecto:

```yaml
- name: importe total
  dax: EVALUATE ROW("v", [Importe Total])
  sql: SELECT SUM(Importe) FROM Ventas          # sobre las hojas del Excel, cargadas en duckdb
- name: importe por región
  dax: EVALUATE SUMMARIZECOLUMNS(Ventas[Region], "Importe", [Importe Total])
  sql: SELECT Region, SUM(Importe) FROM Ventas GROUP BY Region
- name: filas
  dax: EVALUATE ROW("n", COUNTROWS(Ventas))
  value: 3267                                    # alternativa: valor literal
```

Se comparan filas como tuplas ordenadas por posición de columna; los números con
tolerancia; las fechas en ISO. Si DAX y SQL no coinciden, el modelo (o el test) está mal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from . import engine
from .profile import load_sheets
from .spec import SpecLock


@dataclass
class TestCase:
    name: str
    dax: str
    sql: str | None = None
    value: Any = None
    tolerance: float = 0.005


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""
    dax_rows: list[tuple] = field(default_factory=list)
    expected_rows: list[tuple] = field(default_factory=list)


def load_tests(project_dir: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    for f in sorted((project_dir / "tests").glob("*.yaml")):
        for item in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            cases.append(TestCase(**item))
    return cases


def _norm(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:19]
    s = str(v)
    try:
        return float(s.replace(",", ""))
    except ValueError:
        pass
    if len(s) >= 19 and s[4] == "-" and s[10] in "T ":
        return s[:19].replace(" ", "T")
    return s


def _rows_equal(a: list[tuple], b: list[tuple], tol: float) -> bool:
    if len(a) != len(b):
        return False
    key = lambda r: tuple(str(x) for x in r)  # noqa: E731
    for ra, rb in zip(sorted(a, key=key), sorted(b, key=key)):
        if len(ra) != len(rb):
            return False
        for x, y in zip(ra, rb):
            if isinstance(x, float) and isinstance(y, float):
                if not math.isclose(x, y, abs_tol=tol, rel_tol=1e-9):
                    return False
            elif x != y:
                return False
    return True


def _oracle(project_dir: Path, spec: SpecLock) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for src in spec.sources:
        for sheet, df in load_sheets(project_dir / src.path).items():
            con.register(sheet, df)
    return con


def run_tests(
    project_dir: Path, spec: SpecLock, tools_dir: Path, cases: list[TestCase] | None = None, desktop_pid: int = 0
) -> list[TestResult]:
    project_dir = project_dir.resolve()
    cases = cases if cases is not None else load_tests(project_dir)
    con = _oracle(project_dir, spec)
    results: list[TestResult] = []
    for c in cases:
        try:
            data = engine.query(tools_dir, c.dax, desktop_pid=desktop_pid)
            dax_rows = [tuple(_norm(v) for v in row.values()) for row in data.get("rows", [])]
            if c.sql:
                expected = [tuple(_norm(v) for v in row) for row in con.execute(c.sql).fetchall()]
            else:
                expected = [(_norm(c.value),)]
            ok = _rows_equal(dax_rows, expected, c.tolerance)
            detail = "" if ok else f"DAX={dax_rows[:5]} esperado={expected[:5]}"
            results.append(TestResult(c.name, ok, detail, dax_rows, expected))
        except Exception as e:  # noqa: BLE001
            results.append(TestResult(c.name, False, f"error: {e}"))
    return results

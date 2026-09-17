"""Perfilado de datos: hechos sobre los orígenes, extraídos por código (nunca por el LLM).

Escribe `analysis/data_profile.json`. Es lo que ven el Analyst y el Strategist: nombres,
tipos, cardinalidad, nulos, rangos y claves candidatas. Nunca filas, salvo `sample_rows > 0`
explícito (solo proyectos `publica` / `interna`; ver docs/01 §0.1).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .spec import SourceSpec, SpecLock

def _suggested_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "dateTime"
    if pd.api.types.is_integer_dtype(s):
        return "int64"
    if pd.api.types.is_float_dtype(s):
        return "double"
    if s.dtype == object and s.dropna().map(lambda v: isinstance(v, (datetime, pd.Timestamp))).all() and not s.dropna().empty:
        return "dateTime"
    return "string"


def _to_json(v: Any) -> Any:
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def profile_frame(name: str, df: pd.DataFrame, sample_rows: int = 0) -> dict[str, Any]:
    n = len(df)
    columns = []
    for col in df.columns:
        s = df[col]
        dtype = str(s.dtype)
        info: dict[str, Any] = {
            "name": str(col),
            "pandas_dtype": dtype,
            "suggested_type": _suggested_type(s),
            "nulls": int(s.isna().sum()),
            "distinct": int(s.nunique(dropna=True)),
        }
        info["is_unique"] = bool(n > 0 and info["distinct"] == n and info["nulls"] == 0)
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            info["min"] = _to_json(s.min()) if n else None
            info["max"] = _to_json(s.max()) if n else None
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            info["sum"] = _to_json(s.sum()) if n else None
            info["mean"] = _to_json(round(float(s.mean()), 4)) if n else None
        if info["suggested_type"] == "string" and info["distinct"] <= 20:
            info["values"] = [_to_json(v) for v in s.dropna().unique().tolist()[:20]]
        columns.append(info)
    out: dict[str, Any] = {
        "name": name,
        "rows": n,
        "columns": columns,
        "candidate_keys": [c["name"] for c in columns if c["is_unique"]],
        "date_columns": [c["name"] for c in columns if c["suggested_type"] == "dateTime"],
    }
    if sample_rows > 0:
        out["sample"] = json.loads(df.head(sample_rows).to_json(orient="records", date_format="iso"))
    return out


def load_sheets(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(path, sheet_name=None)


def profile_project(project_dir: Path, spec_or_sources: "SpecLock | list[SourceSpec]", sample_rows: int = 0) -> Path:
    project_dir = project_dir.resolve()
    sources = spec_or_sources.sources if isinstance(spec_or_sources, SpecLock) else spec_or_sources
    result: dict[str, Any] = {"generated_at": datetime.now().isoformat(timespec="seconds"), "sources": []}
    for src in sources:
        path = project_dir / src.path
        sheets = load_sheets(path)
        result["sources"].append(
            {
                "id": src.id,
                "type": src.type,
                "path": src.path,
                "tables": [profile_frame(sheet, df, sample_rows) for sheet, df in sheets.items()],
            }
        )
    out = project_dir / "analysis" / "data_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return out

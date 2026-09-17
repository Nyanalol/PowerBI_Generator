"""Excel sintético de ventas para las fases 0-2. Determinista (semilla fija)."""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

PRODUCTOS = ["Portátil", "Monitor", "Teclado", "Ratón", "Docking"]
REGIONES = ["Norte", "Sur", "Este", "Oeste", "Centro"]
PRECIOS = {"Portátil": 950.0, "Monitor": 240.0, "Teclado": 45.0, "Ratón": 25.0, "Docking": 180.0}


def generate_ventas(path: Path, year: int = 2025, seed: int = 7) -> tuple[int, float]:
    """Escribe una hoja `Ventas` con una fila por día×producto×región (muestreada).

    Devuelve (filas, importe total) para poder comprobar el modelo con un dato conocido.
    """
    rng = random.Random(seed)
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas"
    ws.append(["Fecha", "Producto", "Region", "Unidades", "Importe"])
    total = 0.0
    rows = 0
    day = date(year, 1, 1)
    while day.year == year:
        for producto in PRODUCTOS:
            for region in REGIONES:
                if rng.random() < 0.35:
                    unidades = rng.randint(1, 12)
                    importe = round(unidades * PRECIOS[producto] * rng.uniform(0.9, 1.1), 2)
                    ws.append([day, producto, region, unidades, importe])
                    total += importe
                    rows += 1
        day += timedelta(days=1)
    for cell in ws["A"][1:]:
        cell.number_format = "yyyy-mm-dd"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return rows, round(total, 2)

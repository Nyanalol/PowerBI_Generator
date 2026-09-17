# Strategist: de la propuesta al contrato, y el gate

Entrada: modelo (Analyst) + propuesta de páginas (Data Analyst). Salida: `spec_lock.yaml`
completo y `tests/medidas.yaml`. Antes de escribir el definitivo, el gate.

## El contrato

`uv run pbigen spec-schema` imprime el JSON Schema real. Lo esencial (v1):

```yaml
version: 1
project: NombreSinCaracteresRaros      # letras, números, espacio, guion, guion bajo
locale: es-ES
sources:
  - { id: datos, type: excel, path: sources/datos.xlsx }
model:
  date_table: { name: Fechas, start: 2024-01-01, end: 2025-12-31 }   # columnas fijas: Fecha, Año, MesNum, Mes, Trimestre, AñoMes
  relationships:
    - { from: "Hecho[ClaveDim]", to: "Dim[ClaveDim]" }              # muchos -> uno; cross_filter: single|both; active: true
  tables:
    - name: Hecho
      description: ...
      source: { source: datos, sheet: Hoja }        # o table: NombreTablaExcel
      columns:
        - { name: Fecha, type: dateTime, format: "dd/MM/yyyy" }
        - { name: ClaveDim, type: int64, hidden: true }
        - { name: Importe, type: double, summarize: sum, format: "#,##0.00" }
      measures:
        - { name: Importe Total, dax: "SUM(Hecho[Importe])", format: "#,##0 €", description: ..., folder: Importe }
report:
  theme: { brand: demo }                            # templates/brands/<id>/brand.yaml; omitir = tema base
  pages:
    - name: Resumen                                 # nombre estable; display_name opcional
      visuals:
        - { type: textbox, name: titulo, text: "...", font_size_pt: 22, grid: { col: 0, row: 0, cols: 8, rows: 1 } }
        - { type: slicer, name: f_anio, field: "Fechas[Año]", mode: dropdown, title: Año, grid: { col: 8, row: 0, cols: 2, rows: 1 } }
        - { type: card, name: kpi_1, measure: "Hecho[Importe Total]", title: Ventas, grid: { col: 0, row: 1, cols: 3, rows: 2 } }
        - { type: line, name: tendencia, title: ..., category: "Fechas[AñoMes]", values: ["Hecho[Importe Total]", "Hecho[Importe PY]"], grid: {...} }
        - { type: bar, name: por_region, title: ..., category: "Dim[Region]", values: ["Hecho[Importe Total]"], grid: {...} }
        - { type: column, name: por_mes, title: ..., category: "Fechas[Mes]", series: "Fechas[Año]", values: [...], sort: category, grid: {...} }
        - { type: matrix, name: tabla, title: ..., rows: ["Dim[Region]", "Dim[Cliente]"], columns: ["Dim2[Categoria]"], values: [...], grid: {...} }
```

Reglas duras que el validador del spec impone: `measure` y `values` son medidas; `category`,
`series`, `field`, `rows`, `columns` son columnas; toda referencia `Tabla[Campo]` debe existir;
nombres de visual únicos por página; `grid` dentro de 12×8 (o `x/y/w/h` en píxeles, no ambos).

## Rejilla 12×8 (1280×720, fila de 79 px)

- Fila 0: título (`cols` 8) + slicers (`cols` 2 cada uno, `rows` 1).
- Tarjetas: `rows: 2` (con menos no cabe el valor). Cuatro tarjetas = `cols: 3` cada una.
- Gráficos: `rows` ≥ 3. Matriz: `rows` ≥ 6.
- Sin solapes: `check` los detecta, pero es más barato no crearlos.

## Tests

Un `tests/medidas.yaml` con entradas `{name, dax, sql}` (o `value`), siguiendo `analyst.md`.
Las hojas del Excel se consultan en SQL por su nombre. Añade `tolerance` cuando el resultado
sea un ratio pequeño.

## El gate (⛔ bloqueante)

Presenta en el idioma del usuario, en este orden y sin jerga de fichero:

1. **Modelo**: tablas (hecho/dimensión), relaciones, tabla de fechas, medidas (nombre y qué
   calcula, agrupadas por carpeta).
2. **Informe**: páginas con su intención y sus visuales, slicers, tema.
3. **Supuestos** que has hecho y **preguntas** que quedan (definiciones de KPI, exclusiones).
4. **Pendiente de emisor v2**: lo que un buen informe llevaría y hoy no se puede generar.
5. Cierra con: "¿Adelante así, o cambio algo?" y **espera**.

Cambios del usuario → se aplican al spec y se vuelve a presentar solo lo cambiado. Con el
"adelante", escribe `spec_lock.yaml` y `tests/medidas.yaml` y pasa al Executor sin más
preguntas.

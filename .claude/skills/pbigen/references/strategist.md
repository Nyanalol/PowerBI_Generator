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
  filters:                                          # alcance de todo el informe, sin gastar lienzo
    - { field: "Dim[Pais]", values: ["España"] }    # `exclude: true` para invertirlo
  pages:
    - name: Resumen                                 # nombre estable; display_name opcional
      visuals:
        - { type: textbox, name: titulo, text: "...", subtitle: "...", font_size_pt: 26, x: 34, y: 14, w: 700, h: 82 }
        - { type: slicer, name: f_anio, field: "Fechas[Año]", mode: dropdown, title: Año, grid: { col: 8, row: 0, cols: 2, rows: 2 } }
        - { type: card, name: kpi_1, measure: "Hecho[Importe Total]", title: Ventas, accent: primary, emphasis: true, grid: { col: 0, row: 2, cols: 4, rows: 3 } }
        - { type: line, name: tendencia, title: ..., category: "Fechas[AñoMes]", values: ["Hecho[Importe Total]", "Hecho[Importe PY]"], grid: {...} }
        - { type: bar, name: por_region, title: ..., category: "Dim[Region]", values: ["Hecho[Importe Total]"], grid: {...} }
        - { type: column, name: por_mes, title: ..., category: "Fechas[Mes]", series: "Fechas[Año]", values: [...], sort: category, grid: {...} }
        - { type: matrix, name: tabla, title: ..., rows: ["Dim[Region]", "Dim[Cliente]"], columns: ["Dim2[Categoria]"], values: [...], grid: {...} }
        - { type: table, name: lista, title: ..., rows: ["Dim[Cliente]"], values: [...], grid: {...} }
        - { type: donut, name: reparto, title: ..., category: "Dim[Segmento]", values: [...], grid: {...} }
        - { type: treemap, name: peso, title: ..., category: "Dim[Producto]", values: [...], grid: {...} }
        - { type: waterfall, name: puente, title: ..., category: "Fechas[Mes]", values: [...], grid: {...} }
        - { type: scatter, name: relacion, title: ..., category: "Dim[Producto]", x_measure: "Hecho[Descuento Medio]", values: ["Hecho[Margen %]"], size_measure: "Hecho[Ventas]", grid: {...} }
        - { type: shape, name: acento, accent: primary, x: 16, y: 18, w: 4, h: 44 }   # barra de la cabecera
      # filtros de página: acotan sin ocupar lienzo
      filters:
        - { field: "Fechas[Año]", values: [2025] }
```

Extras del perímetro v2: `top_n: { n, by, agg, direction }` en un ranking (el `by` es una columna
numérica, no una medida: lo exige el motor), `color_measure` para colorear por una medida DAX que
devuelve un HEX, `accent` semántico, `data_labels`, `emphasis` en el KPI principal y `subtitle` y
`style: banner` en el cuadro de texto del título.

Reglas duras que el validador del spec impone: `measure` y `values` son medidas; `category`,
`series`, `field`, `rows`, `columns` son columnas; toda referencia `Tabla[Campo]` debe existir;
nombres de visual únicos por página; `grid` dentro de 12x16 (o `x/y/w/h` en píxeles, no ambos).

## Retícula 12x16 (1280x720, columna de 96 px, fila de 35,5 px)

Bandas fijas: cabecera filas 0-1 (79 px), KPIs filas 2-4 (114 px), zona principal filas 5-10
(249 px) y zona secundaria filas 11-15 (213 px).

- La cabecera se coloca en píxeles, no en la retícula: barra de acento en `x: 16, y: 18, w: 4,
  h: 44` y cuadro de texto en `x: 34, y: 14, w: 700, h: 82`. Los segmentadores sí van en retícula
  (`row: 0, rows: 2`), que es el mínimo de 76 px que necesitan.
- Tarjetas: `rows: 3`. Entre dos y cinco por página, repartiendo el ancho (3 columnas si son
  cuatro, 4 si son tres, 6 si son dos). Sin cuota fija.
- Un visual dominante por página con el 35-45 % del área analítica.
- Composición distinta entre páginas consecutivas: 8+4, 7+5, 6+6 o un bloque de 12.
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

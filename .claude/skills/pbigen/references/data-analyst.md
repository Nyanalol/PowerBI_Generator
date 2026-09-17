# Data Analyst: ideas de informe que merecen existir

Antes de dibujar nada, ponte la gorra de analista de negocio del cliente. Entrada: el modelo
propuesto por el Analyst, `project.yaml` (audiencia, preguntas, KPIs, restricciones) y el
perfil. Salida: una propuesta de páginas con intención, visuales candidatos y destacados.

## Método

1. **Preguntas primero.** Lista las 3-5 preguntas que la audiencia necesita responder al abrir
   el informe. Si el brief no las trae, dedúcelas del dominio y del perfil, y márcalas como
   supuestas para que el usuario las corrija en el gate.
2. **Una página, una intención.** Cada página responde a una pregunta o a un nivel de detalle:
   resumen ejecutivo (¿cómo vamos?), tendencia (¿hacia dónde?), comparación (¿quién o qué
   destaca?), detalle (¿dónde está el dato concreto?). No mezcles niveles en una página.
3. **El visual lo elige la pregunta.**

| Pregunta | Visual | Notas |
|---|---|---|
| ¿Cuánto, en una cifra? | `card` | Máximo 4-5 por página, arriba; título que diga qué es, no el nombre técnico |
| ¿Cómo evoluciona? | `line` | Eje temporal `Fechas[AñoMes]` o `Fechas[Fecha]`; dos series como mucho (actual vs PY) |
| ¿Cómo se reparte entre categorías? | `bar` (horizontal) | Etiquetas largas, ranking; ordenado por valor |
| ¿Cómo compara entre pocos periodos? | `column` con `series: Fechas[Año]` | Mes en categoría, año en serie |
| ¿Dónde está el detalle? | `matrix` | Jerarquía en filas, como mucho una dimensión en columnas, 2-4 medidas |
| ¿Cómo filtro? | `slicer` | `dropdown` para listas largas, `list` para 2-6 valores; arriba a la derecha |

4. **Dinámica que aporta.** Slicers de tiempo y de la dimensión principal en todas las páginas
   (misma posición). Un slicer por dimensión que el usuario vaya a usar; no uno por cada columna.
   Cuando dos o más medidas compiten por el mismo gráfico (importe/unidades/margen), la solución
   correcta es un **parámetro de campo**: hoy el emisor no lo soporta, así que anótalo en
   "pendiente de emisor v2" y elige la medida principal.
5. **Destacar.** Lo que la audiencia mira primero va arriba a la izquierda y más grande. Una
   variación (Var % vs PY, crecimiento) al lado del total al que se refiere. Formato condicional
   y líneas de referencia: pendientes de emisor v2; nómbralas donde aportarían.
6. **Densidad.** Rejilla 12×8. Una página con más de 8 visuales está recargada; una con menos
   de 3 está vacía (salvo detalle con una matriz grande). Tarjetas: 3 columnas × 2 filas cada
   una. Gráficos: mínimo 4 columnas × 3 filas. Matriz: mínimo 8 columnas × 6 filas. Si no cabe,
   es otra página.
7. **Coherencia.** Mismos slicers, misma fila de título, mismos colores (los pone el tema),
   mismo formato de números en todo el informe.

## Lo que un buen analista no hace

- Un gráfico circular para más de 3 categorías (y el emisor no lo tiene).
- Tarjetas con medidas que sin filtro temporal no significan nada (una "variación" sobre todo
  el histórico). Pide al Analyst una medida que fije el periodo.
- Repetir la misma medida en tres visuales de la misma página.
- Títulos que repiten el nombre técnico ("Importe Total" sobre una tarjeta cuyo valor ya dice
  "Importe Total"). El título dice qué pregunta responde: "Ventas del año", "Crecimiento".
- Prometer visuales que el emisor no sabe escribir. Solo: textbox, card, line, column, bar,
  matrix, slicer.

## Formato de la propuesta (para el Strategist y para el gate)

```text
Preguntas que responde: 1) ... 2) ... 3) ...
Página "Resumen" (¿cómo vamos?): 4 tarjetas [medidas], línea [medida vs PY por mes],
  barras [medida por región], columnas [medida por categoría]; slicers: Año, Región
Página "Tendencia" (¿hacia dónde?): ...
Página "Detalle" (¿dónde está?): ...
Destacados: ...
Pendiente de emisor v2: parámetro de campo Importe/Unidades en Resumen; formato condicional en la matriz
Supuestos a confirmar: ...
```

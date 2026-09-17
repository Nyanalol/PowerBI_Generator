# Data Analyst: ideas de informe que merecen existir

Antes de dibujar nada, ponte la gorra de analista de negocio del cliente. Entrada: el modelo
propuesto por el Analyst, `project.yaml` (audiencia, preguntas, KPIs, restricciones) y el
perfil. Salida: una propuesta de páginas con intención, visuales candidatos y destacados.

## Método

1. **Preguntas primero.** Lista las 3-5 preguntas que la audiencia necesita responder al abrir
   el informe. Si el brief no las trae, dedúcelas del dominio y del perfil, y márcalas como
   supuestas para que el usuario las corrija en el gate.
2. **Una página, una intención.** Cada página responde a una pregunta o cubre un nivel de detalle:
   resumen ejecutivo, tendencia, comparación, detalle. No mezcles niveles en una página. La
   pregunta guía el diseño; el título de la página es afirmativo (`Resumen de ventas`), nunca la
   pregunta en sí.
3. **El visual lo elige la pregunta.**

| Pregunta | Visual | Notas |
|---|---|---|
| ¿Cuánto, en una cifra? | `card` | Máximo 4-5 por página, arriba; título que diga qué es, no el nombre técnico |
| ¿Cómo evoluciona? | `line` | Hasta 24 puntos en el eje: `Fechas[AñoMes]` para 1-2 años, `Fechas[AñoTrimestre]` a partir de 3. Dos series como mucho (actual vs PY). Mínimo `rows: 3` o las etiquetas se truncan |
| ¿Cómo se reparte entre categorías? | `bar` (horizontal) | Etiquetas largas, ranking; ordenado por valor |
| ¿Cómo compara entre pocos periodos? | `column` con `series: Fechas[Año]` | Mes en categoría, año en serie |
| ¿Dónde está el detalle? | `matrix` | Jerarquía en filas, como mucho una dimensión en columnas, 2-4 medidas. No estira sus columnas: dale el ancho que ocupen sus datos (6 de 12) y pon un ranking al lado |
| ¿Cómo filtro? | `slicer` | `dropdown` para listas largas, `list` para 2-6 valores; arriba a la derecha |

4. **Filtros: de informe, de página o slicer.** Un slicer ocupa lienzo y solo vale si el usuario lo
   va a mover. Lo que acota el alcance del informe entero (un país, una línea de negocio, excluir
   anulados) es un **filtro de informe**; lo que solo aplica a una página (un año concreto en la
   página de tendencia) es un **filtro de página**. Ambos están pendientes de emisor v2: hoy se
   proponen en el gate y se anotan como pendientes, no se sustituyen por slicers de relleno.
5. **Dinámica que aporta.** Slicers de tiempo y de la dimensión principal en todas las páginas
   (misma posición). Un slicer por dimensión que el usuario vaya a usar; no uno por cada columna.
   Cuando dos o más medidas compiten por el mismo gráfico (importe/unidades/margen), la solución
   correcta es un **parámetro de campo**: hoy el emisor no lo soporta, así que anótalo en
   "pendiente de emisor v2" y elige la medida principal.
6. **Destacar.** Lo que la audiencia mira primero va arriba a la izquierda y más grande. Una
   variación (Var % vs PY, crecimiento) al lado del total al que se refiere. Formato condicional
   y líneas de referencia: pendientes de emisor v2; nómbralas donde aportarían.
7. **Orden que destaca lo importante.** Un ranking por valor esconde al final lo que suele importar
   (lo que pierde dinero, lo que tarda más). `sort_direction: asc` lo sube arriba.
8. **Presupuesto de filas.** La rejilla tiene 8 filas y se reparten así: 1 el título con los
   slicers, 2 la fila de tarjetas (menos no muestra el valor), y quedan **5 para el contenido**.
   Una matriz con totales necesita 3 filas; un gráfico con etiquetas de eje largas o rotadas,
   otras 3; uno de etiquetas cortas se apaña con 2. Es decir: caben dos bandas de contenido, no
   tres. Si no cabe, sobra un visual: quita el que menos señal aporte (una serie que siempre
   marca lo mismo no aporta ninguna), no encojas todo hasta que se corte.
9. **Densidad.** Rejilla 12×8. Una página con más de 8 visuales está recargada; una con menos
   de 3 está vacía (salvo detalle con una matriz grande). Tarjetas: 3 columnas × 2 filas cada
   una. Gráficos: mínimo 4 columnas × 3 filas. Matriz: mínimo 8 columnas × 6 filas. Si no cabe,
   es otra página.
10. **Coherencia.** Mismos slicers, misma fila de título, mismos colores (los pone el tema),
   mismo formato de números en todo el informe.

## Lo que un buen analista no hace

- Un gráfico circular para más de 3 categorías (y el emisor no lo tiene).
- Tarjetas con medidas que sin filtro temporal no significan nada (una "variación" sobre todo
  el histórico). Pide al Analyst una medida que fije el periodo.
- Repetir la misma medida en tres visuales de la misma página.
- Títulos que repiten el nombre técnico ("Importe Total" sobre una tarjeta cuyo valor ya dice
  "Importe Total"). El título dice de qué es la cifra: "Ventas del año", "Crecimiento".
- **Títulos con pregunta** ("¿Cómo vamos?") ni **rayas** (`—`). Un informe se consulta de forma
  periódica, no se presenta una vez: los títulos son afirmativos y descriptivos
  ("Ventas y rentabilidad", "Beneficio por subcategoría"). La pregunta que responde la página se
  queda en el brief y en la propuesta, nunca en el lienzo.
- Prometer visuales que el emisor no sabe escribir. Solo: textbox, card, line, column, bar,
  matrix, slicer.

## Formato de la propuesta (para el Strategist y para el gate)

```text
Preguntas que responde: 1) ... 2) ... 3) ...
Página "Resumen de ventas" (responde: cómo vamos): 4 tarjetas [medidas], línea [medida vs PY por mes],
  barras [medida por región], columnas [medida por categoría]; slicers: Año, Región
Página "Tendencia mensual" (responde: hacia dónde vamos): ...
Página "Detalle por cliente" (responde: dónde está el dato): ...
Destacados: ...
Pendiente de emisor v2: parámetro de campo Importe/Unidades en Resumen; formato condicional en la matriz
Supuestos a confirmar: ...
```

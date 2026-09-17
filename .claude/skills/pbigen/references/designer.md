# Designer: mirar el informe como quien lo va a usar cada lunes

Este rol revisa las capturas. No busca errores de código, busca lo que haría que un usuario
recurrente se canse del informe. Se aplica visual por visual y luego a la página entera.

## Lo primero: ¿el visual merece ese espacio?

Antes de juzgar colores o tamaños, pregunta si el gráfico aporta. Descártalo si:

- **La serie no tiene señal.** Una línea que se mueve entre 3,6 y 4,2 días durante cuatro años no
  dice nada: ocupa un tercio de página para decir "esto es estable". Fuera, o convertido en una
  tarjeta con el valor.
- **Tiene un scroll largo.** Un ranking de 49 estados o de 793 clientes en barras horizontales no
  es un gráfico, es una lista con un scroll infinito disfrazada. O se acota (los N primeros, hoy
  pendiente de emisor v2), o se usa una dimensión con menos valores, o se lleva a una matriz, que
  para leer listas es mejor herramienta.
- **Repite lo que ya cuenta otro visual** de la misma página con otra forma.
- **Está ahí para rellenar un hueco.** Un hueco es mejor que un gráfico que nadie mira.

Como referencia: barras o columnas funcionan hasta unas 12 categorías, y hasta 17 si el visual
ocupa toda la altura de la página. Una línea, hasta unos 24 puntos. Por encima de eso, cambia de
granularidad (mes a trimestre) o de dimensión (estado a región).

## Aprovechar el espacio

- **Nada de contenedores grandes con letra pequeña.** Si una tarjeta ocupa un cuarto de la fila,
  su cifra tiene que verse desde lejos (40 pt o más), y la etiqueta debajo, a 12.
- **Sin marcos dentro de marcos.** El visual ya tiene borde y título: el relleno interior y las
  áreas de fondo internas solo roban píxeles.
- **Etiquetas de datos en lugar de eje** cuando el gráfico tiene pocas barras (`data_labels: true`
  quita el eje de valores). Con muchas barras, al revés: eje y sin etiquetas.
- **Sin títulos de eje**: el título del visual ya dice qué se mide. Un eje llamado "Importe Total"
  debajo de un gráfico titulado "Ventas por región" es ruido.
- **Cuidado con el ancho de la matriz**: no estira sus columnas. Dale el ancho que ocupan sus datos
  y coloca algo útil al lado, o acepta el hueco, pero no la declares a 12 columnas para que se vea
  medio lienzo vacío.

## Lo que el generador ya customiza (y por qué)

Nada se deja en los valores por defecto de Power BI: el aspecto por defecto delata un informe sin
trabajar. El tema y el emisor aplican siempre esto, y la referencia de dónde sale cada propiedad es
el catálogo de la CLI (`powerbi-report-author formatting describe-object <tipo> <objeto>`), nunca la
memoria:

| Elemento | Qué se aplica |
|---|---|
| Tarjetas KPI | Etiqueta arriba y cifra a 40 pt debajo, franja de color a la izquierda con el color del KPI, una sola caja (se apagan borde y fondo del contenedor) |
| Líneas | Trazo de 3 px con marcadores circulares; sin marcador el trazo fino parece un borrador |
| Barras y columnas | Barras más gruesas (`innerPadding` 25), sin borde, esquinas redondeadas, etiquetas de datos fuera del extremo |
| Matriz | Filas alternas, sin rejilla vertical, rejilla horizontal suave, cabecera con fondo y alineada a la derecha, total en negrita, interlineado apretado |
| Slicers | Cabecera discreta en negrita, elementos a 11 pt con relleno |
| Ejes | Sin títulos, sin rejilla en el eje de categorías, punteada en el de valores, 11 pt |
| Página | Fondo gris muy claro para que los visuales blancos destaquen |

## El color dice algo o no se usa

Un informe monocromo se lee como una tabla en color, y uno con ocho colores sin criterio, como un
gráfico de feria. La regla: entre tres y cinco colores, cada uno con significado, y el resto en gris.
Cada visual declara su `accent`:

| `accent` | Para qué |
|---|---|
| `primary` | La magnitud principal del informe (ventas, ingresos) |
| `secondary` | Una magnitud de apoyo (clientes, unidades) |
| `positive` | Beneficio, margen, todo lo que sea bueno que suba |
| `negative` | Pérdidas, devoluciones, incidencias |
| `warning` | Lo que hay que vigilar: descuentos, plazos, retrasos |
| `neutral` | Volúmenes sin carga (número de pedidos, filas) |

Pendiente de emisor v2, y por eso hoy se anota en la entrega: colorear una barra negativa distinto
de una positiva dentro del mismo gráfico (formato condicional por regla).

## Qué visual usa cada pregunta (perímetro v2)

| Pregunta | Visual | Cuándo |
|---|---|---|
| ¿Cuánto, en una cifra? | `card` | 4 o 5 por página, arriba |
| ¿Cómo evoluciona? | `line` | Hasta 24 puntos en el eje |
| ¿Cómo se reparte? | `bar` | Etiquetas largas, ranking; con `top_n` si hay muchas categorías |
| ¿Cómo compara entre periodos? | `column` con `series` | Mes en categoría, año en serie |
| ¿Qué peso tiene cada parte del total? | `donut` | 3 a 5 categorías, nunca más |
| ¿Cómo se reparte una jerarquía por tamaño? | `treemap` | Muchas categorías de tamaño muy distinto |
| ¿De dónde a dónde va el total? | `waterfall` | Descomposición de una variación |
| ¿Hay relación entre dos medidas? | `scatter` | Dos medidas y una categoría; el tamaño, una tercera |
| ¿Dónde está el detalle? | `matrix` | Jerarquía en filas |
| ¿Y la lista plana? | `table` | Detalle sin jerarquía |

Un ranking con más categorías de las que caben lleva `top_n` (los N primeros por una columna
agregada), no un scroll. Lo que acota el informe entero va en `report.filters`; lo que acota una
página, en `filters` de la página: ocupan cero lienzo, a diferencia de un segmentador.

## Retícula y jerarquía (medidas fijas)

Lienzo 1280x720, retícula de 12 columnas por 16 filas, margen 16 px y separación 8 px: la columna
mide 96 px y la fila 35,5 px. Las bandas son siempre estas:

| Banda | Filas | Alto |
|---|---|---|
| Cabecera (barra de acento, título, subtítulo, filtros) | 0-1 | 79 px |
| KPIs | 2-4 | 114 px |
| Zona analítica principal | 5-10 | 249 px |
| Zona analítica secundaria | 11-15 | 213 px |

Cuatro reglas que no se saltan:

1. **Un visual dominante por página**, con entre el 35 % y el 45 % del área analítica. Si todos los
   visuales pesan lo mismo, la página se lee plana y parece generada.
2. **Como mucho el 40 % de los visuales con borde.** Tarjetas, segmentadores y matriz pueden
   llevarlo; los gráficos, no. El marco repetido en todo es lo que más delata una plantilla.
3. **Composición distinta en páginas consecutivas.** Hay cuatro repartos base: 8+4, 7+5, 6+6 y un
   bloque de 12. Se elige por contenido, no por inercia.
4. **Jerarquía tipográfica fija**, con al menos 10 puntos entre el título de página y el de visual:

| Elemento | Tamaño |
|---|---|
| Título de página | 26 pt seminegrita, con barra de acento de 4 px a su izquierda |
| Subtítulo de página | 11 pt en gris, dice la intención de la página, no el nombre del dataset |
| Cifra de KPI | 32 pt, y 36 pt en el KPI principal |
| Etiqueta de KPI | 11-12 pt en gris, encima de la cifra |
| Título de visual | 13 pt seminegrita |
| Ejes, leyendas y tablas | 11 pt |

## Consistencia entre páginas

- Los mismos slicers, en la misma posición, en todas las páginas.
- El mismo formato para la misma magnitud (si las ventas van sin decimales en una tarjeta, van sin
  decimales en la matriz).
- La misma paleta, que la pone el tema: ningún color a mano en un visual.
- Títulos afirmativos y descriptivos, nunca preguntas, nunca rayas.

## Checklist de la captura

Por cada página, mira y responde:

1. ¿Hay algún visual vacío, con guiones o con "(Blank)"?
2. ¿Se lee todo sin entrecerrar los ojos: ejes, leyendas, etiquetas de la matriz?
3. ¿Hay texto truncado o con puntos suspensivos?
4. ¿Hay scroll en algún visual? ¿Está justificado (una matriz de detalle) o es un gráfico mal
   elegido?
5. ¿Hay huecos grandes sin razón, o visuales aplastados contra el borde?
6. ¿Está lo importante arriba a la izquierda?
7. ¿Se repite algún texto (título del contenedor y rótulo interno)?
8. ¿Los números cuadran entre visuales y con los tests?

Cada "sí" problemático se corrige en `spec_lock.yaml` o en el tema y se vuelve a capturar. Si algo
no se puede arreglar con el emisor actual, se anota como pendiente de emisor v2 y se dice en la
entrega.

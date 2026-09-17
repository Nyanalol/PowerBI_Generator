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

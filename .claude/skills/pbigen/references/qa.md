# QA: lo que hay que mirar antes de decir "hecho"

Tres evidencias, cada una con su tipo: estática (`validate`, `check`), de ejecución (`refresh`,
`test`) y visual (`screenshot` + lectura de cada PNG). Ninguna sustituye a las otras.

## Orden

```text
uv run pbigen open <proyecto>      # tras cambios de modelo; cierra y reabre la instancia
uv run pbigen reload <proyecto>    # tras cambios solo de informe
uv run pbigen refresh <proyecto>   # los datos no se cargan solos en un PBIP nuevo
uv run pbigen test <proyecto>      # todos verdes o no se entrega
uv run pbigen screenshot <proyecto>
```

Si `screenshot` responde "Report view is not active" tras un `open`, ejecuta `reload` y repite.
Si las tarjetas salen como líneas de guiones, no es tiempo de espera: es que no les cabe el
valor (dales `rows: 2`) o no hay datos (`refresh`).

## Checklist visual, página por página (leer el PNG, no suponer)

- **Datos**: ningún visual vacío, ningún "(Blank)", ninguna tarjeta con guiones.
- **Títulos**: cada visual con un título que diga qué pregunta responde; **ningún texto
  repetido** (tarjeta con etiqueta y título iguales, slicer con cabecera duplicada).
- **Orden**: ejes temporales en orden cronológico (ene…dic, 2024-01…2025-12); rankings por valor.
- **Legibilidad**: sin etiquetas truncadas ("Importe Total a…"), sin ejes con título redundante,
  sin leyendas que tapen datos, texto ≥ 9 pt.
- **Espacio**: sin solapes, sin visuales pegados al borde, sin huecos grandes sin razón; las
  tarjetas alineadas en una fila; slicers desplegables completos (no recortados).
- **Coherencia**: mismos slicers en la misma posición en todas las páginas; misma paleta;
  mismos formatos numéricos (moneda, separadores).
- **Sentido**: un número que no cuadra con el total (una "variación" del 109 %) es un error de
  medida, no de formato. Compáralo con `test` y con el perfil.

## Cómo corregir

Todo se corrige en `spec_lock.yaml` (posición, título, medida, orden) o en `brand.yaml` (tema),
y se repite `build → validate → check → reload → screenshot`. Jamás en `pbip/`.

Si el problema es del emisor (algo que el spec no puede expresar o que se escribe mal), se
documenta como hallazgo en la entrega y se propone el cambio en `src/pbigen/emit_*.py` con su
test, como tarea aparte.

## Entrega

Incluye: comandos ejecutados con su resultado (números, no adjetivos), qué se vio en cada
captura, hallazgos abiertos, y la ruta de la carpeta PBIP completa.

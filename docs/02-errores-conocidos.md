# Errores conocidos y su guarda

Catálogo de todo lo que ha fallado al usar el generador contra el sistema real, con la guarda que
impide que vuelva. **Regla: ningún error se arregla sin dejar aquí su entrada y sin añadir la
guarda** (test, comprobación de `check`, validación del spec o aviso del `doctor`). Si un error no
se puede evitar por código, se documenta el síntoma para reconocerlo en un minuto.

Entorno de referencia: Windows 11, Power BI Desktop 2.157.1354.0 (Store), esquemas PBIR
`visualContainer 2.4.0` / `page 2.0.0` / `report 3.0.0`, CLIs de Microsoft 0.1.4 y 0.1.2.

## 1. Modelo semántico (TMDL y motor)

| # | Síntoma | Causa | Guarda |
|---|---|---|---|
| M1 | Desktop: `TMDL Format Error: InvalidName ... 'Pedidos.Fecha Pedido' input could not be fully consumed` | En `relationships.tmdl` cada parte de `Tabla.Columna` se entrecomilla por separado: `Pedidos.'Fecha Pedido'` | `_tmdl_col_ref` + test `test_relationship_columns_with_spaces_are_quoted` |
| M2 | Desktop: `M Engine error: Microsoft.Data.Mashup.Preview; Identificador no válido` | Acceso a campo en M con guion: `[Sub-Category]`. Los identificadores generalizados no admiten guiones | `_m_field` entrecomilla siempre (`[#"Sub-Category"]`) + test `test_m_field_access_is_always_quoted` |
| M3 | Al abrir, el modelo queda vacío; DAX responde `solo funcionan en bases de datos que tienen al menos una tabla` | Nombre de medida igual al de su tabla o al de una columna suya, o repetido en el modelo. Tabular rechaza el modelo entero | Validación en `SpecLock._cross_refs` + test `test_spec_rejects_measure_named_like_table_or_column` |
| M4 | Una tarjeta de "variación" marca un porcentaje absurdo (109,8 %) | Medida de comparación sin filtro temporal: compara todo el histórico contra un año | Regla en `analyst.md`; el patrón correcto fija el periodo (`Fechas[Año] = MAX(Fechas[Año])`) |
| M5 | Un PBIP recién generado no muestra datos (tarjetas con guiones) | Un PBIP nuevo no trae datos cargados; hay que actualizar | `pbigen refresh` (TMSL contra el motor local); recordado en `qa.md` |
| M6 | `se esperaba un motor local y hay 2` | Varias instancias de Desktop abiertas, cada una con su `msmdsrv` | `engine.ps1 -DesktopPid`: el motor es el `msmdsrv` hijo de esa instancia; el CLI resuelve el PID por el PBIP del proyecto |
| M7 | `hay 2 catálogos; indica -Catalog` | Una apertura fallida deja un catálogo vacío en el mismo motor | `engine.ps1` elige el catálogo que tiene tablas (`TMSCHEMA_TABLES`) |
| M8 | Tildes rotas en los resultados DAX (`Portátil` → `Port?til`) | PowerShell no emite UTF-8 por defecto | `engine.ps1` fuerza `[Console]::OutputEncoding = UTF8` |

## 2. Informe (PBIR) y validación

| # | Síntoma | Causa | Guarda |
|---|---|---|---|
| R1 | `PBIR_PLATFORM_MISSING` | Falta `.platform` en el informe y en el modelo | `platform_file.write_platform` en ambos emisores + test de ficheros esperados |
| R2 | `PBIR_PAGE_JSON_MISSING` / `PBIR_PAGE_DIR_NOT_IN_ORDER` | Las carpetas de página y de visual deben llamarse como su id hexadecimal, no como el nombre legible | `write_report` usa `hex_id` para las carpetas + test `test_build_writes_expected_files` |
| R3 | `PBIR_SCHEMA_VALIDATION_ERROR: baseTheme must have required property 'reportVersionAtImport'` | El tema base exige las versiones de esquema al importar | `VERSION_AT_IMPORT` en `report_json` |
| R4 | `PBIR_THEME_FILE_NAME_MISMATCH` | El `name` interno del tema debe ser idéntico al nombre del fichero | `build_theme` devuelve ambos del mismo valor |
| R5 | Un cambio de tema no se ve tras recargar | Desktop cachea los temas por nombre de fichero | Sufijo hash del contenido en el nombre (`demo-726174ca.json`) |
| R6 | `PBIR_THEME_SCHEMA_UNREACHABLE` (aviso) | `$schema` del tema apuntando a una URL que el validador no puede cargar | El tema se emite sin `$schema`, como los temas base de Desktop |
| R7 | `PBIR_SLICER_HEIGHT_BELOW_FLOOR`: 45,67 px < 76 px | Un slicer desplegable con cabecera necesita 76 px | Rejilla de 8 filas (79 px por fila) en `spec.py` + test `test_grid_fits_slicer_minimum_height` |
| R8 | La tarjeta muestra un esqueleto de guiones en vez del valor | Con título y callout de 32 pt no caben en menos de ~120 px | Aviso `CARD_TOO_SHORT` en `check`; las tarjetas usan `rows: 2` |
| R9 | El título aparece dos veces en slicers y tarjetas | Estos visuales tienen rótulo propio (`header` / `label`); el título del contenedor lo duplica | El emisor pone el título en el rótulo propio y oculta el del contenedor |
| R10 | Ejes temporales desordenados (2025-01 después de 2025-10) | Orden por valor en una categoría temporal | `sort: auto` ordena por categoría cuando el campo es de la tabla de fechas o `dateTime` |
| R11 | Barra de desplazamiento y etiquetas apiñadas en una línea temporal | Más de ~24 puntos en el eje: 4 años por mes son 48 | Columna `AñoTrimestre` en la tabla de fechas (16 puntos para 4 años); regla en `data-analyst.md` |
| R12 | Etiquetas del eje truncadas (`2015-...`) aunque el visual sea ancho | Con etiquetas rotadas, la altura manda: 2 filas de rejilla no bastan | Los gráficos con eje de categorías largas usan `rows: 3` como mínimo |
| R13 | Una matriz declarada a 12 columnas deja medio lienzo vacío | La matriz no estira sus columnas: ocupa lo que miden sus datos | Media página para la matriz y un ranking al lado; regla de densidad en `data-analyst.md` |
| R14b | La matriz corta su última fila o el ranking muestra 3 elementos | Tres bandas de contenido en una página que solo tiene 5 filas libres tras título y tarjetas | Presupuesto de filas en `data-analyst.md`: caben dos bandas; si no cabe, se quita el visual con menos señal |
| R15 | El tema no cambia nada en las tarjetas | Los objetos con selector (`label`, `layout`, `padding`) exigen `"$id": "default"` en el tema, y aun así la tarjeta ignora varios; PBIR además codifica los números como `40D` (decimal) y `4L` (entero) | El emisor escribe tamaño de cifra, relleno y etiqueta en el propio `visual.json` con literales verificados con `powerbi-report-author expr encode` |
| R16 | La tarjeta muestra dos marcos concéntricos | La tarjeta dibuja su propia caja (`cardCalloutArea`) además del borde y el fondo del contenedor | El emisor apaga borde y fondo del contenedor en las tarjetas |
| R17 | Un cambio de tema no se ve tras `pbigen reload` | El puente recarga la definición del informe, no el tema | `pbigen open` (cierra y reabre) cuando se toca `brand.yaml` o `theme.py` |
| R14 | Un ranking esconde lo importante al final de la lista | Orden descendente por defecto: las pérdidas quedan abajo, fuera del scroll | `sort_direction: asc` pone lo peor arriba |

## 3. Entorno, Desktop y puente

| # | Síntoma | Causa | Guarda |
|---|---|---|---|
| E1 | `winget install OpenJS.NodeJS.LTS` cancelado (código 1602) | El instalador pide elevación | Node se instala como dependencia Python (`nodejs-wheel-binaries`); sin administrador |
| E2 | `"node" no se reconoce como un comando` al llamar a las CLIs | Los `.cmd` que genera npm buscan `node` en el PATH | `run_cli` invoca `node <script.js>` con el Node del wheel |
| E3 | `pbigen open` no abría nada | El ejecutable bajo `WindowsApps` no arranca directamente | Se lanza por el alias `%LOCALAPPDATA%\Microsoft\WindowsApps\PBIDesktopStore.exe` |
| E4 | `Report view is not active` al capturar | Tras reabrir, el puente necesita un `reload` antes de la primera captura | Documentado en `qa.md`; `pbigen reload` antes de `screenshot` |
| E5 | `screenshot-all requires the selected Desktop instance to have a PBIP/PBIR current file` | La instancia elegida es una apertura fallida ("Untitled") | `screenshot` pasa `--pid` de la instancia que tiene este PBIP |
| E6 | `Multiple Power BI Desktop Bridge instances are available` | Varias instancias con puente | Igual que E5: selección por PID |
| E7 | Capturas con visuales a medio pintar | La captura llega antes de que terminen de renderizar | `--settle-ms` (4 s por defecto) |
| E8 | `PermissionError [WinError 32]` al reconstruir | En Windows no se puede borrar una carpeta abierta por otro proceso (Desktop o una shell) | `_clean_output` borra fichero a fichero y conserva `.pbi/` |
| E9 | Un cambio en el modelo no se refleja al recargar | El puente solo recarga la definición del **informe** | `pbigen open` cierra y reabre la instancia que tenga ese PBIP |
| E10 | `doctor` dice que el puente no está conectado aunque la preview esté activada | El puente solo responde con Desktop abierto | Mensaje del `doctor` y nota en la documentación |

## 4. Datos y perfilado

| # | Síntoma | Causa | Guarda |
|---|---|---|---|
| D1 | Una columna de fechas se perfila como `string` | El tipo de pandas no siempre es `datetime64[ns]` exacto (columnas `object` con `Timestamp`) | `_suggested_type` decide por el tipo real, no por su nombre + test del perfil |
| D2 | Una dimensión derivada de una hoja plana tiene claves repetidas | El origen trae el mismo id con varios nombres (32 productos en Superstore) | `distinct_key` + `attributes` agrupan en M con `List.First`; la incidencia se reporta al cliente |

## 5. Estilo del informe

| # | Síntoma | Causa | Guarda |
|---|---|---|---|
| S1 | Títulos con pregunta (`¿Cómo vamos?`) o con raya | Estilo de presentación de consultoría en un informe que se consulta de forma periódica | Regla en `data-analyst.md` y en `CLAUDE.md`: títulos afirmativos, sin rayas ni guiones dobles |

## Cómo añadir una entrada

1. Reproduce el error y copia el mensaje exacto (es lo que hace que se reconozca la próxima vez).
2. Arregla la causa en el emisor, el validador del spec o el CLI, nunca en la salida generada.
3. Añade la guarda: test de regresión si es del emisor, regla en `SpecLock` si es del contrato,
   comprobación en `check` si solo se ve en el resultado, o nota en la referencia del rol si es
   una decisión de diseño.
4. Escribe aquí la fila: síntoma, causa, guarda.

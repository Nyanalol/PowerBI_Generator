# PowerBI Generator: análisis de viabilidad y plan

Fecha: 2026-09-17. Estado: revisado tras dos rondas de auditoría cruzada. Ronda 1: licencia,
papel real de la CLI de Microsoft, formato por visual, plan B de capturas, unidad de entrega,
entrada PBIX. Ronda 2: etiquetas de confidencialidad, clases de artefacto y fuga de datos,
definiciones de negocio y RLS en el brief, familia de Desktop soportada, perímetro v1 del emisor,
separación diagnóstico/corrección en el modo revisar, evidencia por tipo de hallazgo, `doctor`.

## 0. Objetivo

Herramienta **productiva para el equipo y para trabajos futuros**, personalizable por cliente:
un consultor recibe el encargo de un cliente (de esta empresa o de cualquier otra) y obtiene un
resultado revisable, versionable y entregable, con calidad comprobada antes de enseñarlo. Dos
modos de uso, con la identidad y las reglas del cliente cargadas como configuración:

- **Crear**: datos + brief → proyecto Power BI nuevo (modelo + informe).
- **Revisar**: PBIP existente del cliente → informe de auditoría (modelo, DAX, rendimiento,
  layout, cumplimiento de identidad) y, si se pide, correcciones aplicadas sobre el mismo PBIP.

No es una prueba personal. Eso impone requisitos desde el día uno:

- **Instalable en cualquier máquina del equipo** con un comando, sin depender de plugins o rutas
  de una máquina concreta. Un script `doctor` comprueba los prerrequisitos **verificables**:
  familia de Desktop soportada (v1 = 2.157.x, no "2.157 o superior": los esquemas PBIR se
  versionan y suben con cada release), puente local activo, Node y CLIs, ruta del workspace fuera
  de OneDrive/SharePoint sincronizado y corta (límite de 260 caracteres en rutas PBIP), y fuentes
  tipográficas de la identidad instaladas (las fuentes no viajan dentro del informe).
- **Precondición de admisión del encargo:** PBIP no soporta etiquetas de confidencialidad. Un
  cliente cuya política exija conservarlas durante el desarrollo no puede entrar en este flujo; se
  comprueba antes de aceptar, no en la entrega.
- **Licencias limpias** para uso comercial en todas las dependencias.
- **Reproducible**: mismo spec y mismos datos, mismo resultado; el resultado se revisa en git.
- **Documentado para quien no lo escribió**: un README de uso y un ejemplo completo que funcione.
- **Sin secretos ni datos de cliente en el repo, y no basta con `.gitignore`.** Tres clases de
  artefacto con tratamiento distinto: (1) datos y caché, nunca versionados ni empaquetados
  (`sources/`, `.pbi/cache.abf`, que contiene una copia del modelo con datos); (2) PBIR y
  bookmarks, versionables pero **portadores potenciales de valores reales** (selecciones de
  filtros y slicers), que pasan por un escaneo antes de commit o entrega; (3) TMDL, tema y spec,
  seguros. El empaquetado de entrega es una lista blanca, no una copia recursiva de la carpeta.

### 0.1 Cumplimiento y datos sensibles (diseño, no bloqueo)

El generador acabará conectado a datos de clientes que pueden ser confidenciales o contener datos
personales. No es un impedimento para arrancar, pero sí condiciona decisiones que después son
caras de cambiar. Reglas de diseño desde la Fase 1:

| Regla | Qué significa en el código |
| --- | --- |
| **Clasificación por proyecto** | `project.yaml` lleva `data_classification`: `publica` / `interna` / `confidencial` / `personal`. Lo demás se deriva de ahí |
| **Los datos no salen de la máquina o del tenant del cliente** | Perfilado y tests DAX se ejecutan en local (duckdb, Desktop) o dentro de Fabric. Ningún dato viaja a un servicio externo por defecto |
| **El LLM ve metadatos, no filas** | A Analyst y Strategist se les pasa el perfil (nombres, tipos, cardinalidad, rangos, estadísticos). Las filas de muestra son opt-in y solo para `publica` / `interna`; para `confidencial` / `personal` van enmascaradas o no van |
| **Registro de lo enviado** | Cada llamada a un modelo de lenguaje deja en `analysis/llm_log.jsonl` qué se envió (hash y resumen) para poder auditarlo |
| **Sin secretos en ficheros generados** | Credenciales solo en `.env` o en el gestor del tenant; el TMDL usa parámetros y conexiones, nunca cadenas con contraseña |
| **Salida limpia** | El escaneo previo a commit/entrega (§0, clases de artefacto) busca valores literales en filtros PBIR y bloquea `.pbi/cache.abf`. Un comando `purge` borra datos, caché y capturas de un proyecto |
| **Etiquetas de confidencialidad** | Precondición de admisión (arriba). Cuando Microsoft las soporte en PBIP, pasa a ser un campo del brief |
| **RLS como parte del modelo** | Los roles se declaran en el spec y se prueban con tests DAX por rol (§4.0) |

Nada de esto exige infraestructura nueva; son convenciones del spec, dos comandos (`scan`,
`purge`) y una regla sobre qué recibe el LLM.

## 1. Veredicto

**Es factible.** Tres hechos verificados hoy lo sostienen:

1. **El formato de salida es texto con esquema público.** Desde marzo de 2026 Power BI Desktop guarda
   por defecto en PBIR (informe: un JSON por página y por visual, con JSON Schema publicado por
   Microsoft) y TMDL (modelo semántico: texto plano). Un proyecto PBIP es una carpeta git-friendly.
   GA de PBIR prevista para Q3 2026.
2. **Existe un renderizador local con puente para agentes.** Power BI Desktop 2.157 (instalado) expone
   una API local en preview ("external tool access") que permite recargar el informe desde disco y
   sacar capturas PNG por página. Eso cierra el bucle generar → validar → mirar sin publicar nada.
3. **El modelo es comprobable, no solo mirable.** Con el informe abierto en Desktop se pueden lanzar
   consultas DAX contra el motor local (ADOMD). Un test de medidas es una consulta con resultado
   esperado. Es una puerta de calidad objetiva que un generador de documentos no puede tener.

## 2. Principios de diseño

Se toma como referencia de destino el generador de presentaciones del equipo (pipeline por roles,
especificación confirmada antes de generar, contrato máquina, validación determinista). Lo que
cambia por ser Power BI:

| Principio | En PowerBI Generator |
| --- | --- |
| Pipeline serial por roles con gates | Analyst → Strategist → Executor → QA |
| Narrativa + contrato máquina | `report_spec.md` (para personas) + `spec_lock.yaml` (para el código) |
| Confirmación bloqueante antes de generar | Único gate humano obligatorio: el usuario aprueba modelo e informe propuestos |
| Librería de identidades / plantillas | Identidad corporativa → tema JSON de Power BI; plantillas de página reutilizables |
| Control de calidad determinista antes de entregar | Validación de esquema + tests DAX + capturas de pantalla revisadas |
| **Quién escribe el artefacto final** | **El código, no el LLM.** El `visual.json` es JSON estricto cuya superficie depende del tipo de visual, roles, selectores y versión de esquema. La skill de Microsoft enseña a escribirlo a mano pero, para construcciones completas, recomienda "un generador determinista que lea el brief aprobado y escriba el JSON"; la de data-goblin prohíbe editarlo a mano. El LLM escribe la *especificación* (modelo, DAX, layout) y un emisor determinista escribe los ficheros. El emisor soporta un conjunto tipado y creciente de construcciones y **falla si recibe algo que no sabe serializar**, en lugar de improvisar |
| Número de artefactos | **Dos, acoplados:** modelo semántico (datos → estrella → DAX) e informe (páginas → visuales enlazados a campos del modelo). El informe no se puede diseñar sin el modelo |
| Fuente | **Datos + brief.** Hace falta un paso de *perfilado de datos* (tipos, cardinalidad, claves, rangos de fechas) que alimenta el diseño del modelo |

## 3. Inventario de lo que ya existe en la máquina (verificado)

| Pieza | Estado | Uso previsto |
| --- | --- | --- |
| Power BI Desktop 2.157 (Store) | Instalado. Puente local **apagado** (hay que activar la preview y reiniciar) | Render + motor DAX local |
| Python 3.14 + pandas + duckdb + jsonschema | Instalado | Perfilado de datos, generadores, validación |
| `pbir` CLI (data-goblin) | Evaluado y **desinstalado**. Licencia "Custom Non-Commercial": la cláusula 3 nombra expresamente "prestar servicios de consultoría o desarrollo de pago" como uso comercial | **No se usa en ninguna fase.** Ver riesgo L1 |
| `@microsoft/powerbi-report-authoring-cli` + `@microsoft/powerbi-desktop-bridge-cli` | **No instalados: falta Node.js** (`winget install OpenJS.NodeJS.LTS`). Licencia MIT | Camino por defecto para validar PBIR y capturar Desktop |
| Plugins Claude `powerbi-authoring` (Microsoft) y `semantic-models`/`tabular-editor` (data-goblin) | Registrados en `installed_plugins.json` pero **la carpeta `plugins/cache` no existe**: no se están cargando | Reinstalar. Sus skills (`powerbi-report-planning`, `semantic-model-authoring`, `tmdl`, `dax`) son conocimiento que no hay que reescribir |
| Tabular Editor 2 | Instalado (`TabularEditor.exe`), sin `te` en PATH | Validación de modelo, BPA, scripting C# |
| `fab` CLI (ms-fabric-cli 0.1.10) | Instalado | Fase 4 (despliegue a Fabric) |

## 4. Arquitectura propuesta

### 4.0 Entradas de un proyecto (el brief)

Cada proyecto arranca con un `project.yaml` que el comando `init` pregunta o que el usuario
rellena. Es lo que hace el marco adaptable a cada cliente y encargo. La identidad se guarda
una vez por cliente y se reutiliza en todos sus proyectos; el modo (`crear` / `revisar`) decide
qué bloques son obligatorios:

| Bloque | Qué contiene | A qué alimenta |
| --- | --- | --- |
| **Empresa / identidad** | Nombre del cliente o equipo; paquete de marca: logo(s), paleta, tipografías, idioma, formato de fecha/moneda. Se guarda como `templates/brands/<empresa>/` reutilizable entre proyectos | Tema JSON de Power BI, cabeceras de página, locale del modelo |
| **Orígenes de datos** | Uno o varios orígenes, cada uno con su *adaptador*: ficheros locales (XLSX primero, CSV, Parquet), bases SQL, Lakehouse/Warehouse de Fabric, y **un modelo semántico ya publicado en Fabric** (en ese caso no se genera modelo: se lee su metadato por XMLA/REST y se genera un informe *thin* conectado a él). Ruta y credenciales por parámetro, nunca en el modelo | Perfilado, partitions M del modelo o, con modelo existente, catálogo de campos para el Strategist |
| **Objetivos** | Audiencia, preguntas de negocio a responder, KPIs prioritarios, decisiones que debe apoyar el informe | Analyst (qué medidas) y Strategist (qué páginas y visuales) |
| **Definiciones de negocio** | Definición exacta de cada KPI, grano de negocio (qué es una fila válida), reglas de exclusión, cortes temporales (año fiscal, cierre), salvedades conocidas de los datos. El perfilado descubre tipos y claves, **no** qué significa una venta válida | Analyst; se cierra **antes** del gate, porque cambiarlo después rehace medidas, dimensiones y tests |
| **Seguridad** | Requisitos de seguridad a nivel de fila (RLS): roles, criterio de filtrado, tablas afectadas. Forma parte del modelo y condiciona relaciones | Analyst (roles en TMDL) y tests DAX por rol |
| **Restricciones** | Número máximo de páginas, visuales permitidos o vetados, accesibilidad, nivel de detalle, destino (local / workspace) | Strategist y QA |
| **Ejemplos de referencia** | Opcional: PBIP existente o capturas de informes que gustan al cliente | Strategist, como referencia de estilo |
| **Objeto a revisar** (modo revisar) | Ruta al PBIP del cliente y alcance: solo diagnóstico, o diagnóstico + correcciones; qué está fuera de alcance | Auditor y, si procede, Executor sobre el PBIP existente |

El brief es el único sitio donde el usuario expresa intención en lenguaje natural; todo lo demás
se deriva de él y se confirma en el gate del Strategist.

### 4.1 Estructura de proyecto generado

```text
projects/<nombre>/
  project.yaml        brief: empresa/identidad, orígenes, objetivos, restricciones (§4.0)
  sources/            datos (CSV/XLSX/Parquet)
  analysis/           data_profile.json  (hechos extraídos por script, no por el LLM)
  report_spec.md      narrativa: audiencia, preguntas de negocio, páginas, KPIs, estilo
  spec_lock.yaml      contrato máquina: tablas, columnas, relaciones, medidas (DAX),
                      tabla de fechas, páginas, visuales con posición en rejilla, tema
  pbip/               SALIDA generada: <nombre>.SemanticModel/ (TMDL) + <nombre>.Report/ (PBIR)
  screenshots/        capturas por página (Desktop bridge)
  tests/              consultas DAX con resultado esperado (smoke tests del modelo)
  exports/            carpeta PBIP completa empaquetada (ZIP) / despliegue
```

El fichero `<nombre>.pbip` es **solo un puntero** a la carpeta del informe. La unidad de entrega
local es la carpeta completa (`.Report` + `.SemanticModel` + `.pbip` + `.gitignore`), nunca el
`.pbip` suelto.

```text
```

### 4.2 Roles y pipeline

```text
brief + datos → [1] Perfilado → [2] Analyst: propuesta de modelo (estrella, medidas)
             → [3] Strategist: propuesta de informe (páginas, visuales, tema)  ⛔ CONFIRMACIÓN
             → [4] Executor: genera TMDL + PBIR (scripts/CLI, no a mano)
             → [5] QA: validate → abrir en Desktop → tests DAX → capturas → revisión
             → [6] Entrega: .pbip local  |  (fase 4) despliegue a workspace Fabric
```

- **Perfilado** (`scripts/profile_data.py`): duckdb/pandas. Escribe `analysis/data_profile.json`.
  Produce hechos, no diseño.
- **Analyst** (LLM): lee el perfil y propone el modelo: hechos vs dimensiones, claves, tabla de
  fechas, medidas base (con DAX) y patrones (YTD, PY, variación). Escribe la sección `model` de
  `spec_lock.yaml`.
- **Strategist** (LLM): lee el brief + modelo y propone el informe. Escribe `report_spec.md` y la
  sección `report` de `spec_lock.yaml`. Gate bloqueante.
- **Executor** (scripts): `generate_model.py` (spec → TMDL vía plantillas Jinja) y
  `generate_report.py` (spec → modelo interno tipado → emisor PBIR propio). La CLI de Microsoft
  **no escribe informes**: sus comandos son catálogo de visuales, descubrimiento de propiedades,
  codificación de expresiones y `validate`. Se usa para consultar capacidades y validar, no para
  generar. Determinista: mismo spec, mismos ficheros.
- **QA** (`scripts/quality_check.py` + LLM para leer capturas): validación de esquema, campos
  referenciados existen en el modelo, solapes de visuales, tests DAX contra Desktop, capturas.

### 4.3 Decisiones de diseño que fijan el rumbo

1. **Capa de orígenes intercambiable desde el día uno.** El perfilado y el generador de modelo
   hablan con una interfaz `Source` (listar tablas, tipos, muestra, expresión M o conexión); cada
   origen es un adaptador. Fases 0-3 usan el adaptador de ficheros locales con modelo "thick" en
   modo import (PBIP con `.SemanticModel`, ruta por parámetro). Fase 4 añade SQL, Lakehouse y el
   adaptador de **modelo semántico existente en Fabric**, que salta la generación de modelo y
   produce un informe thin. Sin Fabric ni licencias hasta la fase 4, pero sin decisiones que lo
   impidan después.
2. **El LLM nunca escribe `visual.json` ni TMDL a mano.** Escribe `spec_lock.yaml`; el código
   escribe ficheros. Si el generador no cubre algo, se amplía el generador **entre fases, no
   durante una fase**. El perímetro de la v1 del emisor queda congelado antes de la Fase 1:
   `textbox`, `cardVisual`, `lineChart`, `clusteredColumnChart`/`clusteredBarChart`,
   `pivotTable` (matriz) y `slicer` (lista y rango); bindings a columna y medida; posición,
   ordenación, ejes, leyenda, etiquetas, colores por serie, cabeceras de matriz, configuración de
   slicer, texto, tema y los objetos de contenedor. Fuera de v1: bookmarks, drillthrough, mapas,
   parámetros de campo, visuales personalizados, navegación. Los identificadores de página y
   visual se derivan de forma determinista del spec (hash de nombre), nunca aleatorios, para que
   dos generaciones iguales den diffs vacíos.
3. **Tema primero, formato por visual cuando no hay otra opción.** La identidad va al tema JSON y
   los visuales llevan por defecto solo campos y posición. Pero hay propiedades de contenedor
   (`visualContainerObjects`: fondo, borde, padding, cabecera, y varias de cards) que la cascada de
   Power BI obliga a fijar por visual; el `spec_lock` admite una sección `format` por visual para
   exactamente esas, sin convertirse en un espejo de PBIR.
4. **Rejilla de layout declarativa** (12 columnas × filas sobre 1280×720) en el spec; el generador
   traduce a píxeles. Evita el "todo cards" y hace comparables las plantillas de página.
5. **Tests DAX como parte del proyecto**, no del framework: cada proyecto tiene `tests/*.yaml`
   con consulta y resultado esperado calculado por duckdb sobre los mismos CSV. Si el modelo y
   duckdb no coinciden, algo está mal en el modelo.

## 5. Plan por fases (de sencillo a complejo)

### Fase 0. Spike de desriesgo (1 sesión)

Objetivo: comprobar a mano los dos puntos que lo pueden tumbar todo.
- Instalar Node + CLIs de Microsoft; activar el puente en Desktop.
- Crear a mano (o con CLI) el PBIP mínimo: 1 CSV → 1 tabla import → 3 medidas → 1 página → 3 visuales.
- Criterio de salida: abre en Desktop sin errores; `powerbi-desktop screenshot` produce PNG;
  una consulta DAX contra el motor local devuelve el número esperado.
- **Nuevo criterio de salida, el que valida la arquitectura:** un `spec_lock.yaml` mínimo
  (1 Excel, 1 tabla, 1 medida, 1 visual) genera modelo e informe **con los mismos emisores que usará
  el producto**, sin LLM, y el resultado abre y se captura. Fase 0 no termina con un PBIP hecho a
  mano.
- Si el puente no funciona en esta máquina (Store, políticas corporativas), **el bucle autónomo
  local ha fallado** y hay que decidirlo aquí. La alternativa cloud (publicar y exportar PNG con
  `exportToFile`) exige workspace en capacidad Premium/Embedded/Fabric y licencia Pro para
  publicar; no vale con PPU. Es una opción del bloque con infraestructura (fase 4), no un
  sustituto gratuito.

**Resultado (2026-09-17): Fase 0 completada.** Los tres criterios se cumplen en esta máquina:
Desktop 2.157 abre el PBIP generado desde `spec_lock.yaml` sin errores; `pbigen refresh` carga
los datos del Excel a través del motor local (TMSL, 250 ms) y `pbigen query` devuelve por DAX el
importe total exacto del Excel (6.151.060,63 sobre 3.267 filas); `pbigen screenshot` captura la
página con las tarjetas renderizadas. Lo aprendido, ya incorporado al código:

- El ejecutable de Desktop de la Store no arranca desde `WindowsApps`; se lanza por el alias
  `%LOCALAPPDATA%\Microsoft\WindowsApps\PBIDesktopStore.exe`.
- Node no necesita instalador: `nodejs-wheel-binaries` lo trae dentro del entorno Python. Los
  `.cmd` de npm no encuentran `node`; las CLIs se invocan como `node <script.js>`.
- La CLI de validación de Microsoft exige `.platform` en informe y modelo, carpetas de página y
  visual nombradas por su id, y `reportVersionAtImport` en el tema base.
- Un PBIP recién generado no tiene datos: Desktop muestra "--" hasta actualizar. La actualización
  se puede lanzar desde fuera con un comando TMSL `refresh` contra el motor local; no hace falta
  tocar la interfaz. El cliente ADOMD se descarga de NuGet sin administrador.
- El puente de Desktop solo responde con Desktop abierto; `doctor` lo indica como "no conectado"
  si no hay ninguna instancia, aunque la preview esté activada.

### Fase 1. Esqueleto del generador

- `project_manager.py init/validate`, `profile_data.py`, `spec_lock.yaml` v1 (una tabla, N medidas,
  1 página), `generate_model.py`, `generate_report.py`, `quality_check.py` (esquema + campos).
- Criterio: desde un Excel y un `spec_lock.yaml` escrito a mano, salir un PBIP que abre y se captura.

**Resultado (2026-09-17): Fase 1 completada.** `pbigen init` crea el esqueleto con el brief
(`project.yaml`, con clasificación de datos); `profile` escribe `analysis/data_profile.json`
(tipos, cardinalidad, nulos, rangos, claves candidatas, sin filas salvo opt-in y nunca en
proyectos confidenciales o personales); `check` verifica sobre la salida generada que cada
binding del informe existe en el TMDL, los límites del lienzo, los solapes y las medidas sin
formato o descripción; `test` ejecuta `tests/*.yaml` como DAX contra Desktop y SQL con duckdb
sobre el mismo Excel (5 de 5 en el ejemplo, incluido un desglose por región); `purge` borra
datos, salidas, capturas y caché conservando spec, brief y tests. Dos correcciones surgidas al
ejecutarlo: detección de fechas en el perfil por tipo real de pandas, y salida UTF-8 forzada en
el puente PowerShell del motor (las tildes de los valores DAX llegaban mal codificadas).

### Fase 2. Modelo real y librerías

- Estrella multi-tabla, tabla de fechas generada, relaciones, patrones de medidas (time intelligence).
- Multi-página, slicers, tema desde identidad corporativa (librería propia de temas; se puede
  arrancar importando las paletas ya definidas en el generador de presentaciones).
- Tests DAX automáticos (duckdb como oráculo). Plantillas de página (overview ejecutivo, tendencia,
  detalle tabla).
- Criterio: un Excel sintético de ventas (3 hojas: ventas, productos, clientes) → informe de 3 páginas sin tocar JSON a mano.

**Resultado (2026-09-17): Fase 2 completada.** Excel de tres hojas y dos años → estrella con
tabla de fechas calculada y marcada, tres relaciones, medidas de time intelligence (YTD, PY,
crecimiento anual), tres páginas sobre rejilla 12×8 con textbox, tarjetas, líneas, columnas,
barras, matriz y slicers, y tema generado desde `templates/brands/demo/brand.yaml`. Validación
de Microsoft en verde, `check` sin hallazgos, 10 de 10 tests DAX contra duckdb (incluidos YTD a
una fecha, PY de un mes y crecimiento 2025 vs 2024), capturas de las tres páginas revisadas.
Lo aprendido, ya incorporado al código o a `check`:

- El `name` interno del tema debe ser igual al nombre del fichero, y Desktop cachea temas por
  nombre: el fichero lleva sufijo hash del contenido. Sin `$schema`, como los temas de Desktop.
- Un slicer desplegable con cabecera necesita 76 px; de ahí la rejilla de 8 filas (79 px). Una
  tarjeta con título y callout de 32 pt necesita unos 120 px o muestra un esqueleto de guiones
  (`check` avisa: `CARD_TOO_SHORT`).
- El slicer ya tiene cabecera: el título va ahí, no en el contenedor (si no, sale duplicado).
- Categorías temporales se ordenan por categoría; el resto por valor (`sort: auto`).
- Un cambio de modelo (TMDL) no se aplica con `reload` del puente: `open` cierra y reabre la
  instancia que tenga el PBIP. Tras reabrir, el puente puede responder "Report view is not
  active" hasta el primer `reload`. Las capturas necesitan unos segundos de asentamiento.
- Hallazgo de analista, no de código: "Variación vs año anterior" sin filtro temporal comparaba
  dos años contra uno (109,8 %). Es el tipo de error que el rol Data Analyst de la Fase 3 debe
  detectar; de momento la tarjeta usa `Crecimiento Anual %` (último año contra el previo).

### Fase 2b. Modo revisar, solo diagnóstico (en paralelo a la Fase 2; no depende del emisor)

- Lector de PBIP existente (TMDL + PBIR) → inventario: tablas, medidas, relaciones, páginas,
  visuales, campos usados y huérfanos.
- Comprobaciones estáticas: reglas de buenas prácticas de modelo (Tabular Editor BPA),
  validación PBIR con la CLI de Microsoft, **cada binding de PBIR apunta a una tabla, columna o
  medida que existe en TMDL** (una referencia rota sobrevive a la validación de esquema), solapes,
  cumplimiento del tema del cliente, medidas sin formato ni descripción, riesgos estáticos de
  rendimiento (cardinalidad, columnas calculadas, medidas con patrones caros).
- Evidencia en ejecución, con el PBIP abierto en Desktop: capturas por página (visuales vacíos,
  truncados, ilegibles) y **medición** de tiempo de consulta por visual vía DAX contra el motor
  local. Sin medición no se afirma "este visual tarda demasiado".
- Salida: informe de auditoría (Markdown/Word con la plantilla del cliente) con hallazgos
  priorizados por consecuencia. Cada hallazgo lleva la evidencia que le corresponde: fichero y
  ubicación estructural para lo estático, captura para lo visual, medición para lo de ejecución.
- Criterio: auditar un PBIP real de un cliente y que ningún hallazgo carezca de evidencia de su
  tipo.
- **Las correcciones no van aquí.** Aplicar cambios a un PBIP ajeno exige o bien el emisor (solo
  para construcciones del subconjunto soportado) o bien operaciones de parche que preserven lo
  que el generador no entiende. Eso pertenece a la Fase 3.

### Fase 3. Roles LLM y experiencia

- Skill de Claude Code para el equipo con el flujo Analyst → Strategist (confirmación en chat o
  en una página local) → Executor → QA con revisión de capturas.
- **Rol Data Analyst** (añadido 2026-09-17): antes de proponer páginas, se pone la gorra de
  analista y genera ideas de informe a partir del perfil y el brief: qué preguntas responde cada
  página, qué KPIs merecen tarjeta, qué comparaciones aportan (tendencia, año contra año,
  ranking, concentración, variación), qué dinámica conviene (slicers, parámetros de campo para
  cambiar medida o dimensión cuando hay varias candidatas, drill), y qué destacar (formato
  condicional, líneas de referencia). Elige el visual por la pregunta, no por costumbre; reparte
  la densidad (una página no puede ir recargada mientras otra va vacía) y aplica la rejilla. Sus
  propuestas se presentan al usuario y, confirmadas, se traducen a `spec_lock.yaml`.
- **Buenas prácticas de M y DAX como criterio de calidad**, no como sugerencia: plegado de
  consultas y tipos fijados en M; medidas sobre columnas base, variables, `DIVIDE`, sin columnas
  calculadas donde valga una medida, sin `FILTER` sobre tablas enteras, tablas de fechas
  marcadas, claves ocultas, formato y descripción en toda medida. Se comprueban con las reglas
  BPA de Tabular Editor y con `check`, y las que sean medibles (tiempo por consulta) con `test`.
- **Perímetro v2 del emisor**, por orden de demanda real. Es lo que falta para que la base sea
  potente de verdad; cada cliente solo debería tener que aportar su identidad y sus datos:
  1. **Filtros de informe y de página** (hoy todo se hace con slicers, que ocupan lienzo).
  2. **Roles RLS** con sus tests por rol.
  3. **Formato condicional por regla**: una barra negativa en rojo dentro de un gráfico, semáforos
     en la matriz, barras de datos en celdas.
  4. **Más tipos de visual**: KPI con objetivo, anillo, treemap, dispersión, cascada, embudo, tabla
     (`tableEx`), medidor y mapa. Y, cuando el contexto lo pida de verdad, **visuales
     personalizados** (Deneb o `.pbiviz` certificados), con su fichero registrado en el informe.
  5. **Top N y filtros por visual** para que un ranking no se convierta en una lista con scroll.
  6. **Parámetros de campo** para alternar medida o dimensión en un mismo gráfico.
  7. Líneas de referencia, tooltips de página, botones y marcadores de navegación.
  8. Sinónimos por objeto para Copilot.
  Siempre entre fases, nunca a mitad de una.
- Modo revisar con correcciones: catálogo cerrado de operaciones de parche sobre un PBIP ajeno
  (cambiar tema, añadir descripción y formato a medidas, corregir un binding roto, añadir una
  página generada) que preservan byte a byte lo que no tocan. Nada de reescribir el PBIP entero.
- Entrada = PBIP existente ("re-tematizar", "auditar", "añadir página"). Un PBIX **no** es entrada
  automatizable: Microsoft no permite convertir PBIX↔PBIP por programa, solo con *Guardar como* en
  Desktop. La precondición documentada para PBIX es convertirlo antes a PBIP.
- Empaquetado para el equipo: instalación con un comando, `doctor` de prerrequisitos, ejemplo
  completo, guía de uso.

**Resultado (2026-09-17): Fase 3, primera entrega.** Skill de equipo versionada en el repo
(`.claude/skills/pbigen/`): `SKILL.md` con el pipeline serial y el gate, y referencias por rol
(`analyst.md`: reglas de modelo y DAX; `data-analyst.md`: preguntas → visuales, densidad,
destacados, qué queda para el emisor v2; `strategist.md`: contrato y formato del gate; `qa.md`:
checklist visual con lo aprendido en las fases 0-2). `pbigen spec-schema` expone el JSON Schema
del contrato para que el LLM no adivine. Pendiente en esta fase: página local de confirmación,
emisor v2 (parámetros de campo, formato condicional, líneas de referencia, filtros de página,
roles RLS) y empaquetado de entrega por lista blanca.

**Prueba de punta a punta (2026-09-17): dataset público Superstore.** 9.994 líneas de pedido en un
Excel plano de una sola hoja, el caso que más se parece a lo que entrega un cliente. La skill
recorrió el flujo completo: perfilado, modelo en estrella con dos dimensiones **derivadas** de la
hoja plana (`distinct_key` + `attributes`, agrupando en M), tabla de fechas, 16 medidas, 4 páginas y
tema de cliente. Resultado: validación de Microsoft en verde, `check` sin hallazgos, **14 de 14
tests DAX** contra duckdb, y cuatro páginas revisadas con el rol de diseñador. Lo que salió de esa
revisión, ya incorporado como reglas: fuera los rankings con scroll (49 estados, 793 clientes van a
la matriz), eje trimestral en vez de mensual cuando hay más de dos años, etiquetas de datos en lugar
de eje en gráficos de pocas barras, presupuesto de filas por página, y tarjetas con una sola caja y
cifra grande. Los fallos de emisor que destapó el dataset real (comillas en relaciones TMDL,
identificadores M con guion, nombres de medida que chocan con tablas o columnas) están en
`docs/02-errores-conocidos.md` con su test de regresión.

### Fase 4. Fabric

- Adaptadores SQL, Lakehouse / Direct Lake y modelo semántico existente (informe thin).
- Despliegue con `fabric-cicd` o `fab`; capturas vía export API
  para máquinas sin Desktop; informes "thin" contra modelos publicados.

## 6. Riesgos y decisiones abiertas

| # | Riesgo | Impacto | Mitigación |
| --- | --- | --- | --- |
| L1 | `pbir-cli` es no comercial y su licencia cuenta la consultoría de pago como uso comercial | Legal | Excluido de todas las fases, incluido el spike. Base: CLIs MIT de Microsoft (catálogo + validación + puente Desktop) + JSON Schema oficial + emisor propio |
| T1 | El puente de Desktop es preview y puede fallar por políticas de la máquina corporativa | Sin bucle visual local | Se prueba en Fase 0; plan B = publicar + export API |
| T2 | PBIR y el propio guardado PBIP siguen marcados *preview* en la documentación (17-sep-2026); el esquema puede cambiar entre versiones de Desktop | Regeneraciones rotas | Fijar versión de esquema en `spec_lock`; validar contra el JSON Schema de la versión instalada |
| T3 | Rutas absolutas en M para ficheros locales | PBIP no portable | Parámetro `DataFolder` en el modelo; el generador lo rellena |
| T4 | Solo Windows (Desktop) | Sin CI en Linux | Aceptado en local; la fase 4 desacopla con Fabric |
| T5 | Dos consultores con versiones distintas de Desktop: los esquemas PBIR y de tema se versionan por release; no hay matriz oficial de compatibilidad hacia atrás | Un PBIP validado en una máquina falla o se ve distinto en otra | `doctor` exige la familia soportada (v1: 2.157.x); el spec registra la versión de esquema con la que se generó |
| T6 | Rutas largas (límite 260) y carpetas sincronizadas con OneDrive/SharePoint rompen el guardado de PBIP; fuentes no instaladas cambian el render | Falla en una máquina y no en otra | `doctor` valida ubicación y fuentes de la identidad |
| C1 | PBIP no soporta etiquetas de confidencialidad | Encargo inviable si el cliente las exige durante el desarrollo | Precondición de admisión (§0) |
| D1 | PBIR y bookmarks pueden contener valores reales (filtros, slicers); `.pbi/cache.abf` contiene datos | Fuga de datos de cliente por commit o por empaquetado recursivo | Clases de artefacto (§0), escaneo previo a commit/entrega, empaquetado por lista blanca |
| P1 | Plugins registrados pero no cargados (`plugins/cache` ausente) | Se pierde conocimiento ya instalado | Reinstalar antes de la Fase 0 |

**Decisiones que tomar antes de la Fase 1:** (a) Node + CLIs de Microsoft como base, sí/no;
(b) formato del `spec_lock`: YAML (propuesto) frente a Markdown; (c) dataset de
referencia para las fases 1-2: Excel sintético de ventas generado por script (decidido).

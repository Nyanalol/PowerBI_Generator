# PowerBI Generator — análisis de viabilidad y plan

Fecha: 2026-09-17. Estado: propuesta inicial, pendiente de auditoría cruzada.

## 1. Veredicto

**Es factible, y está mejor posicionado de lo que estaba ppt-master al nacer.**
Tres hechos verificados hoy lo sostienen:

1. **El formato de salida es texto con esquema público.** Desde marzo de 2026 Power BI Desktop guarda
   por defecto en PBIR (informe: un JSON por página y por visual, con JSON Schema publicado por
   Microsoft) y TMDL (modelo semántico: texto plano). Un proyecto PBIP es una carpeta git-friendly.
   GA de PBIR prevista para Q3 2026.
2. **Existe un renderizador local con puente para agentes.** Power BI Desktop 2.157 (instalado) expone
   una API local en preview ("external tool access") que permite recargar el informe desde disco y
   sacar capturas PNG por página. Eso cierra el bucle generar → validar → mirar, que en ppt-master
   resolvía el preview SVG en el navegador.
3. **El modelo es comprobable, no solo mirable.** Con el informe abierto en Desktop se pueden lanzar
   consultas DAX contra el motor local (ADOMD). Un test de medidas es una consulta con resultado
   esperado. Es una puerta de calidad que ppt-master no tiene.

## 2. Qué se hereda de ppt-master y qué NO

| Principio ppt-master | En PowerBI Generator |
|---|---|
| Pipeline serial por roles con gates | **Se hereda.** Analyst → Strategist → Executor → QA |
| `design_spec.md` (narrativa) + `spec_lock` (contrato máquina) | **Se hereda.** `report_spec.md` + `spec_lock.yaml` |
| Confirmación bloqueante del Strategist antes de generar | **Se hereda.** Es el único gate humano obligatorio |
| Librería de brands / layouts / charts | **Se hereda y se reutiliza.** Un brand de ppt-master se traduce a un tema JSON de Power BI |
| Quality checker determinista antes de exportar | **Se hereda,** con más dientes: validación de esquema + tests DAX + capturas |
| **El Executor escribe el SVG a mano, prohibido generar por script** | **Se invierte.** El visual.json es JSON estricto con cientos de propiedades; escribirlo a mano es el antipatrón que las dos librerías de skills (Microsoft y data-goblin) prohíben. Aquí el LLM escribe la *especificación* (modelo, DAX, layout) y un generador/CLI determinista escribe los ficheros |
| Un artefacto (el deck) | **Dos artefactos acoplados:** modelo semántico (datos → estrella → DAX) e informe (páginas → visuales enlazados a campos del modelo). El informe no se puede diseñar sin el modelo |
| Fuente = documento (PDF/DOCX) | **Fuente = datos + brief.** Hace falta un paso nuevo de *perfilado de datos* (tipos, cardinalidad, claves, rangos de fechas) que alimenta el diseño del modelo |

## 3. Inventario de lo que ya existe en la máquina (verificado)

| Pieza | Estado | Uso previsto |
|---|---|---|
| Power BI Desktop 2.157 (Store) | Instalado. Puente local **apagado** (hay que activar la preview y reiniciar) | Render + motor DAX local |
| Python 3.14 + pandas + duckdb + jsonschema | Instalado | Perfilado de datos, generadores, validación |
| `pbir` CLI 0.9.32 (data-goblin) | Instalado hoy. **Licencia "Custom Non-Commercial"** | Prototipar en Fase 0. Ver riesgo L1 |
| `@microsoft/powerbi-report-authoring-cli` + `@microsoft/powerbi-desktop-bridge-cli` | **No instalados: falta Node.js** (`winget install OpenJS.NodeJS.LTS`). Licencia MIT | Camino por defecto para validar PBIR y capturar Desktop |
| Plugins Claude `powerbi-authoring` (Microsoft) y `semantic-models`/`tabular-editor` (data-goblin) | Registrados en `installed_plugins.json` pero **la carpeta `plugins/cache` no existe**: no se están cargando | Reinstalar. Sus skills (`powerbi-report-planning`, `semantic-model-authoring`, `tmdl`, `dax`) son conocimiento que no hay que reescribir |
| Tabular Editor 2 | Instalado (`TabularEditor.exe`), sin `te` en PATH | Validación de modelo, BPA, scripting C# |
| `fab` CLI (ms-fabric-cli 0.1.10) | Instalado | Fase 4 (despliegue a Fabric) |

## 4. Arquitectura propuesta

### 4.1 Estructura de proyecto generado

```
projects/<nombre>/
  sources/            datos (CSV/XLSX/Parquet) + brief.md del usuario
  analysis/           data_profile.json  (hechos extraídos por script, no por el LLM)
  report_spec.md      narrativa: audiencia, preguntas de negocio, páginas, KPIs, estilo
  spec_lock.yaml      contrato máquina: tablas, columnas, relaciones, medidas (DAX),
                      tabla de fechas, páginas, visuales con posición en rejilla, tema
  pbip/               SALIDA generada: <nombre>.SemanticModel/ (TMDL) + <nombre>.Report/ (PBIR)
  screenshots/        capturas por página (Desktop bridge)
  tests/              consultas DAX con resultado esperado (smoke tests del modelo)
  exports/            .pbip empaquetado / despliegue
```

### 4.2 Roles y pipeline

```
brief + datos → [1] Perfilado → [2] Analyst: propuesta de modelo (estrella, medidas)
             → [3] Strategist: propuesta de informe (páginas, visuales, tema)  ⛔ CONFIRMACIÓN
             → [4] Executor: genera TMDL + PBIR (scripts/CLI, no a mano)
             → [5] QA: validate → abrir en Desktop → tests DAX → capturas → revisión
             → [6] Entrega: .pbip local  |  (fase 4) despliegue a workspace Fabric
```

- **Perfilado** (`scripts/profile_data.py`): duckdb/pandas. Escribe `analysis/data_profile.json`.
  Equivale a `source_to_md.py`: hechos, no diseño.
- **Analyst** (LLM): lee el perfil y propone el modelo: hechos vs dimensiones, claves, tabla de
  fechas, medidas base (con DAX) y patrones (YTD, PY, variación). Escribe la sección `model` de
  `spec_lock.yaml`.
- **Strategist** (LLM): lee el brief + modelo y propone el informe. Escribe `report_spec.md` y la
  sección `report` de `spec_lock.yaml`. Gate bloqueante, como en ppt-master.
- **Executor** (scripts): `generate_model.py` (spec → TMDL vía plantillas Jinja) y
  `generate_report.py` (spec → PBIR vía CLI de Microsoft o generación directa validada contra
  el JSON Schema oficial). Determinista: mismo spec, mismos ficheros.
- **QA** (`scripts/quality_check.py` + LLM para leer capturas): validación de esquema, campos
  referenciados existen en el modelo, solapes de visuales, tests DAX contra Desktop, capturas.

### 4.3 Decisiones de diseño que fijan el rumbo

1. **Modelo "thick" local en fases 0-3** (PBIP con `.SemanticModel` en modo import leyendo ficheros
   locales por parámetro de ruta). Sin Fabric ni licencias hasta la fase 4.
2. **El LLM nunca escribe `visual.json` ni TMDL a mano.** Escribe `spec_lock.yaml`; el código
   escribe ficheros. Si el generador no cubre algo, se amplía el generador.
3. **Tema antes que formato por visual.** La identidad (brand) va al tema JSON; los visuales solo
   llevan enlaces a campos y posición. Es lo que recomiendan ambas librerías y lo que hace el
   spec_lock pequeño.
4. **Rejilla de layout declarativa** (12 columnas × filas sobre 1280×720) en el spec; el generador
   traduce a píxeles. Evita el "todo cards" y hace comparables las plantillas de página.
5. **Tests DAX como parte del proyecto**, no del framework: cada proyecto tiene `tests/*.yaml`
   con consulta y resultado esperado calculado por duckdb sobre los mismos CSV. Si el modelo y
   duckdb no coinciden, algo está mal en el modelo.

## 5. Plan por fases (de sencillo a complejo)

### Fase 0 — Spike de desriesgo (1 sesión)
Objetivo: comprobar a mano los dos puntos que lo pueden tumbar todo.
- Instalar Node + CLIs de Microsoft; activar el puente en Desktop.
- Crear a mano (o con CLI) el PBIP mínimo: 1 CSV → 1 tabla import → 3 medidas → 1 página → 3 visuales.
- Criterio de salida: abre en Desktop sin errores; `powerbi-desktop screenshot` produce PNG;
  una consulta DAX contra el motor local devuelve el número esperado.
- Si el puente no funciona en esta máquina (Store, políticas corporativas), el plan B es
  exportar capturas tras publicar en un workspace; se decide aquí, no en la fase 3.

### Fase 1 — Esqueleto del generador
- `project_manager.py init/validate`, `profile_data.py`, `spec_lock.yaml` v1 (una tabla, N medidas,
  1 página), `generate_model.py`, `generate_report.py`, `quality_check.py` (esquema + campos).
- Criterio: desde un CSV y un `spec_lock.yaml` escrito a mano, salir un PBIP que abre y se captura.

### Fase 2 — Modelo real y librerías
- Estrella multi-tabla, tabla de fechas generada, relaciones, patrones de medidas (time intelligence).
- Multi-página, slicers, tema desde brand (reutilizar `templates/brands` de ppt-master).
- Tests DAX automáticos (duckdb como oráculo). Plantillas de página (overview ejecutivo, tendencia,
  detalle tabla).
- Criterio: un dataset tipo ventas (3 CSV) → informe de 3 páginas sin tocar JSON a mano.

### Fase 3 — Roles LLM y experiencia
- Skill `pbi-master` con el flujo Analyst → Strategist (confirmación, posible reutilización del
  `confirm_ui` de ppt-master) → Executor → QA con revisión de capturas.
- Entrada = PBIP/PBIX existente ("re-tematizar", "auditar", "añadir página"), equivalente al
  beautify de ppt-master.

### Fase 4 — Fabric
- Despliegue con `fabric-cicd` o `fab`; fuentes Lakehouse / Direct Lake; capturas vía export API
  para máquinas sin Desktop; informes "thin" contra modelos publicados.

## 6. Riesgos y decisiones abiertas

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| L1 | `pbir-cli` es no comercial; el uso en SoftwareOne/clientes lo excluye como dependencia | Legal | Prototipar con él en Fase 0 si acelera; construir sobre las CLIs MIT de Microsoft + JSON Schema oficial |
| T1 | El puente de Desktop es preview y puede fallar por políticas de la máquina corporativa | Sin bucle visual local | Se prueba en Fase 0; plan B = publicar + export API |
| T2 | PBIR aún no GA: el esquema puede cambiar entre versiones de Desktop | Regeneraciones rotas | Fijar versión de esquema en `spec_lock`; validar contra el JSON Schema de la versión instalada |
| T3 | Rutas absolutas en M para ficheros locales | PBIP no portable | Parámetro `DataFolder` en el modelo; el generador lo rellena |
| T4 | Solo Windows (Desktop) | Sin CI en Linux | Aceptado en local; la fase 4 desacopla con Fabric |
| P1 | Plugins registrados pero no cargados (`plugins/cache` ausente) | Se pierde conocimiento ya instalado | Reinstalar antes de la Fase 0 |

**Decisiones que tomar antes de la Fase 1:** (a) Node + CLIs de Microsoft como base, sí/no;
(b) formato del `spec_lock`: YAML (propuesto) frente a Markdown como ppt-master; (c) dataset de
referencia para las fases 1-2 (propuesta: ventas sintéticas generadas por script, 3 CSV).

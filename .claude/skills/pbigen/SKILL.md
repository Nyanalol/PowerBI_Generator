---
name: pbigen
description: Genera o revisa proyectos Power BI (PBIP: modelo TMDL + informe PBIR) con el generador del repo. Úsala cuando el usuario pida "crea un informe Power BI con estos datos", "genera un PBIP", "hazme un dashboard de ventas", "propón un informe para este Excel", o "revisa este PBIP". Orquesta los roles Analyst → Data Analyst → Strategist (gate de confirmación) → Executor → QA sobre los comandos `pbigen`, sin escribir nunca TMDL ni PBIR a mano.
---

# pbigen: del brief al PBIP comprobado

Pipeline serial por roles. El LLM diseña y decide; el código escribe los ficheros y comprueba.
Regla de oro: **si `spec_lock.yaml` no puede expresarlo, no se genera**. Se anota como
limitación y se propone ampliar el emisor entre fases, nunca parcheando JSON.

```text
brief + datos → [1] init + profile → [2] Analyst: modelo → [3] Data Analyst: ideas de informe
→ [4] Strategist: spec_lock.yaml  ⛔ CONFIRMACIÓN → [5] Executor: build, validate, check
→ [6] QA: open/reload, refresh, test, screenshot, revisión visual → [7] entrega
```

## Disciplina de ejecución

1. **Serial.** Cada paso consume la salida del anterior. Sin adelantar trabajo de pasos posteriores.
2. **Un solo gate humano** (paso 4): presentar modelo + informe propuestos y **esperar** la
   confirmación explícita. Antes del gate no se genera nada; después, los pasos 5-7 corren solos.
3. **El LLM ve metadatos, no filas.** Lee `analysis/data_profile.json`. Solo pide filas de
   muestra (`profile --sample-rows`) si `project.yaml` clasifica el proyecto como `publica` o
   `interna` y hace falta para entender un campo.
4. **Nunca escribir `visual.json`, `page.json` ni `.tmdl`.** Solo `spec_lock.yaml`,
   `project.yaml` y `tests/*.yaml`. El contrato exacto: `uv run pbigen spec-schema`.
5. **Desktop es el juez.** Un PBIP no está terminado hasta que abre, carga datos, pasa los tests
   DAX y las capturas se han mirado. Reportar lo que falló tal cual, con la salida del comando.
6. **Idioma**: el del usuario para todo lo visible; nombres de tablas y medidas en el idioma del
   cliente (por defecto español), identificadores de código en inglés.

## Paso 1. Proyecto y perfil

```text
uv run pbigen doctor <proyecto>                 # si falla algo, decirlo y parar en lo que dependa de ello
uv run pbigen init <proyecto> --name <Nombre>   # solo si no existe
uv run pbigen profile <proyecto>                # requiere spec_lock.yaml con `sources` y los ficheros en sources/
```

Si el proyecto es nuevo, antes de perfilar hay que declarar los orígenes en `spec_lock.yaml`
(`sources:` con `id`, `type: excel`, `path`) y copiar los datos a `sources/`. Rellena
`project.yaml` con lo que el usuario haya dicho; lo que falte de la lista de §4.0 de
`docs/01-analisis-viabilidad.md` (definiciones de KPI, grano, exclusiones, RLS) se pregunta
**antes** del gate, agrupado en una sola tanda de preguntas, no una a una.

## Paso 2. Analyst (modelo). Leer `references/analyst.md`

Entrada: `analysis/data_profile.json` + `project.yaml`. Salida: la sección `model` de
`spec_lock.yaml` (tablas, columnas con tipo y formato, claves ocultas, relaciones, tabla de
fechas, medidas con DAX, descripción, formato y carpeta). Aplica las reglas de M/DAX de la
referencia como obligatorias, no como consejo.

## Paso 3. Data Analyst (ideas). Leer `references/data-analyst.md`

Con la gorra de analista de negocio: qué preguntas responde el informe, qué KPIs merecen
tarjeta, qué comparaciones aportan (tendencia, año contra año, ranking, concentración,
variación), qué interacción conviene (slicers, drill), qué destacar. Elige el visual por la
pregunta, no por costumbre. Reparte la densidad entre páginas. Produce una lista de páginas con
intención y visuales candidatos, y una lista corta de ideas que **no** caben en el emisor actual
(parámetros de campo, formato condicional, líneas de referencia) marcadas como "pendiente de
emisor v2", para que el usuario sepa que existen sin prometerlas.

## Paso 4. Strategist (spec y gate). Leer `references/strategist.md`

Traduce el modelo y las ideas a `spec_lock.yaml` completo (rejilla 12×8, tema, páginas,
visuales) y a `tests/medidas.yaml` (cada medida con su SQL de oráculo). Presenta al usuario un
resumen en su idioma: tablas y relaciones, medidas (nombre, qué calcula), páginas (intención y
visuales), tema, y las ideas pendientes de emisor v2. **⛔ Espera confirmación o cambios.** Solo
tras el "adelante" se escribe el spec definitivo.

## Paso 5. Executor

```text
uv run pbigen build <proyecto>
uv run pbigen validate <proyecto>     # 0 errores o no se sigue: corregir el spec, no la salida
uv run pbigen check <proyecto>        # errores bloquean; avisos se leen y se decide
```

Si `validate` o `check` fallan, la causa está en el spec o en el emisor. Corregir el spec si es
un error de diseño; si es una limitación del emisor, documentarla y proponer la ampliación.
Nunca editar `pbip/` a mano.

## Paso 6. QA y diseño. Leer `references/qa.md` y `references/designer.md`

```text
uv run pbigen open <proyecto>         # primera vez o tras cambiar el modelo (cierra y reabre)
uv run pbigen reload <proyecto>       # tras cambios solo de informe
uv run pbigen refresh <proyecto>      # carga los datos
uv run pbigen test <proyecto>         # DAX vs duckdb; todos deben pasar
uv run pbigen screenshot <proyecto>   # y LEER cada PNG con la checklist de qa.md
```

Tras reabrir Desktop, si `screenshot` dice "Report view is not active", ejecutar `reload` y
repetir. **Las capturas se revisan con el rol de diseñador de Power BI** (`references/designer.md`),
no de pasada: se juzga si cada visual merece su espacio, si se aprovecha el ancho y si algo tiene un
scroll que delata un gráfico mal elegido. Cada hallazgo se corrige en el spec o en el tema y se
repite 5-6. Máximo tres vueltas; si algo no se resuelve, se entrega con el hallazgo documentado.

## Paso 7. Entrega

Resumen final para el usuario: qué se generó (ruta de la carpeta PBIP completa, nunca solo el
`.pbip`), resultado de validate/check/test con números, capturas revisadas y qué se vio, ideas
pendientes de emisor v2, y siguiente paso sugerido. Recordar que `pbip/`, `sources/` y
`screenshots/` no se versionan y que la entrega al cliente es la carpeta PBIP por lista blanca.

## Modo revisar (PBIP ajeno)

Todavía sin lector de PBIP ajeno (Fase 2b). Si el usuario lo pide: explicar que hoy solo se
puede auditar un PBIP generado por este repo (`check`, `test`, `screenshot`), y que la Fase 2b
está en el plan. No improvisar una revisión leyendo JSON a mano y opinando.

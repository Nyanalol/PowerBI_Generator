# PowerBI Generator — guía para agentes

Generador de proyectos Power BI (carpeta PBIP: modelo semántico en TMDL + informe en PBIR) a partir
de una especificación declarativa. Uso previsto: equipo de consultoría, varios clientes, varias
máquinas Windows. Lee `docs/01-analisis-viabilidad.md` antes de proponer cambios de arquitectura:
ahí están las decisiones tomadas, sus razones y los riesgos aceptados.

## Reglas que no se negocian

1. **El artefacto final lo escribe el código, nunca el LLM.** `visual.json`, `page.json` y los
   `.tmdl` salen de los emisores (`src/pbigen/emit_pbir.py`, `emit_tmdl.py`) a partir de
   `spec_lock.yaml`. Si el spec no puede expresar algo, se amplía el modelo tipado (`spec.py`) y el
   emisor, entre fases. No se parchea JSON a mano ni se generan ficheros "de momento".
2. **El emisor falla ante lo que no conoce.** Nada de valores por defecto inventados para
   propiedades PBIR o TMDL. Ante la duda, consultar el catálogo con
   `powerbi-report-author formatting describe-object` / `catalog describe` y la documentación pública
   de esquemas (`https://github.com/microsoft/json-schemas/tree/main/fabric`).
3. **Identificadores deterministas.** Páginas y visuales derivan su nombre hexadecimal del spec
   (`ids.hex_id`). Dos generaciones del mismo spec producen ficheros idénticos.
4. **Licencias limpias para uso comercial.** Solo dependencias MIT/BSD/Apache o equivalentes. En
   particular, `pbir-cli` (data-goblin) tiene licencia no comercial y está excluido en todas las
   fases; no lo instales ni lo cites como opción.
5. **Sin datos de cliente en el repo.** `**/sources/`, `**/pbip/`, `**/screenshots/`, `**/.pbi/`
   y `projects/` están ignorados. Los ficheros PBIR pueden contener valores reales (filtros,
   slicers): revisar antes de proponer un commit de un PBIP ajeno. El empaquetado de entrega es una
   lista blanca, nunca una copia recursiva.
6. **Nada de instalaciones con administrador.** Node viene en `nodejs-wheel-binaries` y las CLIs de
   Microsoft se instalan con `pbigen install-tools` en `.tools/`. Lo único que requiere acción
   manual es activar en Desktop la preview "external tool access".
7. **Cumplimiento por diseño.** Los datos de un proyecto no salen de la máquina ni del tenant del
   cliente. Un modelo de lenguaje recibe metadatos y perfiles, nunca filas, salvo opt-in explícito
   en proyectos clasificados como públicos o internos. Las credenciales van en `.env` o en el
   tenant, jamás en TMDL ni en el spec. Ver `docs/01-analisis-viabilidad.md` §0.1.
8. **Verificar contra el sistema vivo.** Desktop es el juez: un PBIP "válido" que Desktop no abre
   no está terminado. Ante una afirmación sobre el formato, comprobarla con la CLI de validación o
   abriendo el resultado, no con memoria.

## Flujo de trabajo

```text
uv sync --extra dev
uv run pbigen doctor [examples/ventas-demo]      # prerrequisitos verificables
uv run pbigen install-tools                      # CLIs de Microsoft (npm, sin admin)
uv run pbigen demo-data examples/ventas-demo     # Excel sintético en sources/
uv run pbigen build examples/ventas-demo         # -> examples/ventas-demo/pbip/
uv run pbigen validate examples/ventas-demo      # pydantic + powerbi-report-author validate
uv run pbigen open examples/ventas-demo          # abre en Power BI Desktop (alias de la Store)
uv run pbigen refresh examples/ventas-demo       # carga los datos en el modelo abierto (TMSL vía ADOMD)
uv run pbigen query examples/ventas-demo 'EVALUATE ROW("t", [Importe Total])'   # DAX contra el motor local
uv run pbigen screenshot examples/ventas-demo    # capturas vía puente (Desktop abierto)
uv run pytest
```

## Estructura

```text
src/pbigen/
  cli.py         verbos Typer
  spec.py        modelo pydantic de spec_lock.yaml (contrato; extra=forbid)
  emit_tmdl.py   spec -> <proyecto>.SemanticModel/ (TMDL)
  emit_pbir.py   spec -> <proyecto>.Report/ (PBIR) + <proyecto>.pbip
  build.py       orquestación
  doctor.py      prerrequisitos
  tools.py       Node (wheel), npm, CLIs de Microsoft, localización de Desktop
  engine.py      motor AS local de Desktop: catálogos, refresh TMSL, consultas DAX (ADOMD vía PowerShell)
  demo_data.py   Excel sintético
  resources/     tema base copiado de Desktop
examples/        proyectos de ejemplo (solo spec_lock.yaml versionado)
docs/            análisis, decisiones, plan por fases
tests/           pytest; los tests llaman al código de producción, no a copias
```

## Al cambiar el formato de salida

- Anota en `docs/` la versión de esquema PBIR y la familia de Desktop contra la que se probó.
- Añade o actualiza un test que genere el ejemplo y compare con la salida esperada.
- Ejecuta `pbigen validate` y abre el resultado en Desktop antes de dar el cambio por bueno.

## Estilo

- Español en documentación y mensajes de usuario; inglés en identificadores de código.
- Commits pequeños, un cambio por commit, mensaje en español.
- Los tests usan el productor real (`build_project`, `generate_ventas`), nunca fixtures inventadas.

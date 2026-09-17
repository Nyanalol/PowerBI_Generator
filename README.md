# PowerBI Generator

Generador de proyectos Power BI (PBIP: modelo semántico TMDL + informe PBIR) para uso de un
equipo de consultoría: pipeline por roles, especificación confirmada antes de generar,
generación determinista y control de calidad (validación, tests DAX, capturas) antes de entregar.

Estado: Fases 0, 1 y 2 completadas. Desde un Excel y un `spec_lock.yaml` se genera un proyecto con
estrella, tabla de fechas, time intelligence, tres páginas y tema de cliente; se valida, se abre en
Desktop, se cargan los datos, se prueban las medidas por DAX contra duckdb y se capturan las páginas,
todo por comando. Ver [docs/01-analisis-viabilidad.md](docs/01-analisis-viabilidad.md) para
el análisis, las decisiones y el plan por fases, y [CLAUDE.md](CLAUDE.md) para las reglas de
trabajo en el repositorio.

## Requisitos

- Windows con Power BI Desktop 2.157.x (Store o MSI). Activar en Desktop la característica de
  versión preliminar "Enable external tool access to Power BI Desktop through secure local APIs".
- Python 3.12 o superior y [uv](https://docs.astral.sh/uv/).
- Nada que requiera administrador: Node y las CLIs de Microsoft se instalan dentro del proyecto.

## Primeros pasos

```text
uv sync --extra dev
uv run pbigen doctor
uv run pbigen install-tools
uv run pbigen demo-data examples/ventas-demo
uv run pbigen profile examples/ventas-demo
uv run pbigen build examples/ventas-demo
uv run pbigen validate examples/ventas-demo
uv run pbigen check examples/ventas-demo
uv run pbigen open examples/ventas-demo
uv run pbigen refresh examples/ventas-demo
uv run pbigen query examples/ventas-demo 'EVALUATE ROW("t", [Importe Total])'
uv run pbigen test examples/ventas-demo
uv run pbigen screenshot examples/ventas-demo
```

## Autoría

Proyecto concebido, creado y mantenido por **Miguel Ángel González-Albo Campillo** desde el
17 de septiembre de 2026, a título personal: desarrollado con una suscripción personal de Claude,
en tiempo propio y sin uso de licencias, suscripciones ni recursos de ninguna empresa. El historial
de git (cuenta personal, correo personal, fechas) es el registro de autoría. Licencia MIT, con el
autor como titular del copyright (ver [LICENSE](LICENSE)).

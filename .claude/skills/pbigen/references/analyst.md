# Analyst: del perfil de datos al modelo

Entrada: `analysis/data_profile.json` (hechos) y `project.yaml` (intención, definiciones,
seguridad). Salida: sección `model` de `spec_lock.yaml`. Nunca filas de datos.

## Cómo leer el perfil

- `rows`, `columns[].suggested_type`, `distinct`, `nulls`, `min`/`max`, `values` (solo si ≤ 20
  distintos), `candidate_keys`, `date_columns`.
- Una hoja con muchas filas, fechas y cantidades es un **hecho**. Una hoja corta con una clave
  candidata y atributos es una **dimensión**. Una columna del hecho cuyo nombre y cardinalidad
  coinciden con la clave de una dimensión es la **relación** (muchos → uno).
- Si dos hojas comparten nombre de columna pero no cardinalidad compatible, no inventes la
  relación: pregunta.

## Reglas del modelo (obligatorias)

1. **Estrella.** Hechos en el centro, dimensiones alrededor, relaciones muchos-a-uno, filtro en
   una dirección. `cross_filter: both` solo con una razón escrita en `description`.
2. **Tabla de fechas siempre** que haya una fecha en un hecho: `model.date_table` con `start` y
   `end` que cubran los datos con margen de año completo (de 1 de enero a 31 de diciembre).
   Relaciona la fecha del hecho con `Fechas[Fecha]`. Toda time intelligence usa `Fechas[Fecha]`.
3. **Claves ocultas** (`hidden: true`) en hechos y dimensiones. El usuario no filtra por ids.
4. **Tipos fijados en el spec** (`int64`, `double`, `dateTime`, `string`, `boolean`, `decimal`).
   El emisor los escribe en M (`Table.TransformColumnTypes`), que es lo que mantiene el plegado
   y evita columnas de texto disfrazadas de número.
5. **Formato en columnas numéricas y en toda medida** (`format`). Moneda con símbolo del cliente.
6. **`summarize: sum`** solo en cantidades sumables del hecho; `none` en claves, atributos y
   columnas de dimensión (evita sumas absurdas de ids o precios).
7. **`sort_by`** para etiquetas que deban ordenarse por otra columna (mes por número de mes).
8. **Nombres** legibles para el usuario final, en el idioma del cliente, con espacios
   (`Importe Total`, no `ImporteTotal`), consistentes entre tablas.

## Reglas DAX (obligatorias)

- Medidas base sobre columnas (`SUM(Ventas[Importe])`); el resto sobre medidas base, nunca
  repitiendo la columna (`[Importe Total] - [Importe PY]`).
- `DIVIDE` en toda división. Nunca `/`.
- Time intelligence solo con `Fechas[Fecha]`: `TOTALYTD`, `SAMEPERIODLASTYEAR`, `DATEADD`.
- Una medida que **sin filtro temporal** compare periodos debe fijar el periodo ella misma
  (`Fechas[Año] = MAX(Fechas[Año])`), o su tarjeta engañará (visto: 109,8 % de "variación").
- Variables (`VAR`) para no recalcular; sin `FILTER` sobre tablas enteras cuando basta un filtro
  de columna; sin columnas calculadas cuando vale una medida; sin `EARLIER`.
- **`description` en toda medida** (qué calcula y en qué unidad) y `folder` para agruparlas
  (`Importe`, `Unidades`, `Clientes`...). `check` avisa si faltan.
- Formato: importes `#,##0 €`, porcentajes `0.0%`, enteros `#,##0`, ratios `#,##0.00`.

## Medidas que casi siempre aportan

| Pregunta | Medidas |
|---|---|
| ¿Cuánto? | Total, Unidades, Ticket medio (`DIVIDE(total, filas)`) |
| ¿Cómo va el año? | YTD (`TOTALYTD`), PY (`SAMEPERIODLASTYEAR`), Var % vs PY (`DIVIDE(total - PY, PY)`) |
| ¿Crecemos? (sin filtro) | Último año, Año previo, Crecimiento anual % |
| ¿Quién pesa? | % del total (`DIVIDE(total, CALCULATE(total, ALL(dim)))`), ranking (`RANKX`) |
| ¿Cuántos? | Clientes activos (`DISTINCTCOUNT`), Pedidos |

## Seguridad (RLS)

Si `project.yaml.seguridad_rls` no está vacío, el modelo necesita roles. El emisor v1 **no**
escribe roles: anótalo como limitación bloqueante en la propuesta y no sigas al gate sin que
el usuario decida (aceptar sin RLS en esta entrega, o esperar al emisor v2).

## Tests que debes proponer (`tests/medidas.yaml`)

Uno por medida base (total, filas), uno por relación (agregado por un atributo de cada
dimensión con `JOIN ... USING`), uno por medida de tiempo con filtro explícito (YTD a una fecha,
PY de un mes) y uno por medida derivada. El SQL corre en duckdb sobre las hojas del Excel con su
nombre; no reimplementes la regla en Python ni copies el número esperado a mano.

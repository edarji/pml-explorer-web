# Guatemala Price Explorer: contrato del paquete gt-1

App separada de PML Explorer: `gt_app.py`, con `gt_datos.py` y `gt_ticker.py`. Lee solo `gt/`; no lee `data/` ni `pnd/`. Parte de edarji/edarji.net#8.

## Paquete (`gt/`, escrito solo por power-market-lab `scripts/gt_publico.py`)
| Archivo | Columnas |
|---|---|
| `poe_horario.parquet` | `fecha, hora (0–23, inicio del intervalo, America/Guatemala), poe_usd_mwh, generador_marginal` |
| `poe_diario.parquet` | `fecha, horas_validas, promedio, mediana, minimo, maximo` |
| `poe_mensual.parquet` | `mes, dias_con_dato, horas_validas, promedio, minimo, maximo` |
| `metadata.json` | `version_esquema = "gt-1"`, `generado_utc`, `desde`, `hasta`, `dias_sin_dato`, `fuente {nombre, url, nota}` y `archivos {nombre: {filas, sha256}}` |

- **Fuente:** AMM, Posdespacho Diario, hoja `POE`. Es un dato preliminar; los valores oficiales de liquidación son los del ITE.
- **Lectura** (`gt_datos.leer`): rechaza un esquema distinto, archivos ausentes, sha256 o filas que no coinciden. Con el paquete inválido no se muestra ninguna cifra.
- **Caché:** sha256 de `metadata.json` + versión de la app. Una corrección con la misma fecha final invalida la caché.
- **Agregados:** promedios simples sobre las horas con dato. El mensual se calcula sobre las horas, no como promedio de los promedios diarios. Nada se rellena.

## Ticker
POE promedio del último día publicado (D) frente al día calendario anterior (D−1), más el mínimo y el máximo horario de D, en USD/MWh.

- Si falta D−1 → «sin comparación».
- Si alguno de los dos días está incompleto → comparación sin color ni flecha.
- Sin porcentajes.

## Despliegue
Segunda app de Streamlit Community Cloud sobre este repositorio:

- rama `main`;
- archivo principal `gt_app.py`;
- Python 3.14.

La app de México (`app.py`) no cambia.

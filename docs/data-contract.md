# Contrato de datos públicos — esquema v1

Contrato recibido de Claude por Lalo, fechado **2026-10-25**. Reemplaza la propuesta anterior de `data/public/`. El lector implementa este esquema; falta recibir y validar los archivos reales del pipeline. El ejemplo de metadata suministrado describe el formato y **no acredita una entrega ni sus conteos**.

Fuente: **CENACE SW-PML, MDA, SIN**. Unidades: **MXN/MWh**. Parquet con compresión **zstd**, filas ordenadas por `nodo`.

**`data/` solo lo escribe el pipeline del Mac mini, autor `pml-bot`.** El visor y el validador no crean, editan ni borran archivos ahí.

## Archivos

- `hourly/AAAA-MM-DD.parquet`: un archivo por día, ventana de los últimos 365 días.
- `daily/AAAA-MM.parquet`: un archivo por mes desde 2023-01; el mes en curso se reescribe cada día.
- `nodes.parquet`: catálogo de nodos y fechas observadas.
- `metadata.json`: rangos, conteos y SHA-256; el pipeline lo escribe al final.

Los nombres del manifiesto son relativos a `data/`, sin rutas locales, equipos ni usuarios. Cada archivo del paquete debe estar enumerado en `archivos`, incluyendo `nodes.parquet`. La lista debe coincidir con las particiones de los rangos declarados; un extracto ilustrativo del JSON no es un manifiesto completo.

## Esquemas Parquet

| Archivo | Columna | Tipo |
| --- | --- | --- |
| hourly | `fecha` | DATE |
| hourly | `hora` | INTEGER, 1..24 |
| hourly | `nodo` | VARCHAR |
| hourly | `pml` | DOUBLE |
| daily | `fecha` | DATE |
| daily | `nodo` | VARCHAR |
| daily | `horas_validas` | INTEGER, 0..24 |
| daily | `suma_pml` | DOUBLE |
| daily | `suma_pml_cuadrado` | DOUBLE |
| daily | `pml_min` | DOUBLE |
| daily | `pml_max` | DOUBLE |
| daily | `horas_negativas` | INTEGER |
| nodes | `nodo` | VARCHAR |
| nodes | `primera_fecha` | DATE |
| nodes | `ultima_fecha` | DATE |

La correspondencia Arrow que verifica el lector es DATE=date32, INTEGER=int32, VARCHAR=string y DOUBLE=float64. Se comprueban las columnas exactas; no se aceptan alias de otra versión.

La hora es **hora final**: hora 1 representa 00:00–01:00. La gráfica conserva la coordenada inicial del intervalo (`fecha + hora - 1`) de la vista validada. No es una conversión a UTC.

Una fila horaria por `(nodo, fecha, hora)` y una diaria por `(nodo, fecha)`. No hay columna de promedio: se deriva de suma y horas válidas. Los precios horarios conservan los valores publicados por CENACE. No se redondean previamente las sumas ni las sumas de cuadrados.

Un nodo solo tiene filas desde que existe. Una fila faltante significa sin dato, nunca precio cero. Una fila diaria con cero horas tampoco aporta observaciones: el lector la excluye de agregados y extremos. El validador exige en ese caso cero horas negativas, sumas cero o nulas y extremos nulos, para no representar precios inexistentes. Para filas con horas válidas, todos los acumuladores y extremos deben ser finitos y no nulos.

`primera_fecha` y `ultima_fecha` son el primer/último día **con dato**, no altas/bajas oficiales. El catálogo debe tener claves únicas y coincidir con las fechas observadas del histórico diario.

## Esquema v2: componentes del PML (2026-10-30)

Aditivo sobre v1, con `version_esquema = "2"`. El lector acepta v1 y v2; con v1 la vista 3 muestra «pendiente».

| Archivo | Columna | Tipo | Significado |
| --- | --- | --- | --- |
| hourly | `energia`, `perdidas`, `congestion` | DOUBLE | Componentes publicados por CENACE (`pml_ene`, `pml_per`, `pml_cng`), con su signo |
| daily | `suma_energia`, `suma_perdidas`, `suma_congestion` | DOUBLE | Sumas sobre las mismas `horas_validas` que `suma_pml` |
| daily | `horas_congestion_positiva`, `horas_congestion_negativa` | INTEGER | Horas con congestión > 0 y < 0 |
| daily | `descuadre_max` | DOUBLE | Máximo de \|PML − (energía + pérdidas + congestión)\| en el día |
| daily | `horas_descuadre` | INTEGER | Horas con descuadre redondeado a 6 decimales > 0.02 MXN/MWh |

Toda hora con PML debe traer los tres componentes, finitos y no nulos: misma base de observaciones. Los validadores cuadran en todo el solapamiento las sumas, los conteos y el descuadre máximo diario contra el horario.

## Metadata

| Campo | Valor o significado |
| --- | --- |
| `version_esquema` | Cadena `"1"` o `"2"` (v2 con componentes) |
| `generado_utc` | Instante ISO 8601 con zona UTC de generación del paquete |
| `fuente` | `CENACE SW-PML, MDA, SIN` |
| `unidades` | `MXN/MWh` |
| `convencion_hora` | `1-24 hora final` |
| `horario_desde`, `horario_hasta` | Fechas ISO inclusivas de la ventana horaria |
| `diario_desde`, `diario_hasta` | Fechas ISO inclusivas del histórico diario |
| `nodos` | Número de nodos del catálogo |
| `archivos` | Mapa de ruta relativa → `filas` (entero) y `sha256` (64 dígitos hexadecimales) |

La interfaz obtiene **todas las fechas del rango de metadata**, sin fechas fijas en código ni inferencia desde el reloj. Muestra `generado_utc` convertido con la zona IANA `America/Mexico_City`. Por ejemplo, el instante ilustrativo `2026-10-26T05:00:12Z` corresponde a `2026-10-25 23:00:12 CST`. Esa es la actualización del paquete; no se presenta como el instante de extracción original de CENACE.

## Reglas de consulta

- Rango completo dentro de `horario_desde..horario_hasta`: usar hourly; todas las estadísticas de la vista 1.
- Cualquier otro rango dentro del histórico diario: usar daily; solo gráfica diaria/mensual; mediana, P10 y P90 requieren datos horarios.
- `n = SUM(horas_validas)`; promedio `SUM(suma_pml)/n`; extremos `MIN(pml_min)` y `MAX(pml_max)`; negativas `SUM(horas_negativas)`.
- Desviación muestral: `SQRT((SUM(suma_pml_cuadrado)-SUM(suma_pml)^2/n)/(n-1))`, definida para n > 1.
- Cobertura: `n / ((fin-inicio+1)*24)`, presentada como porcentaje.
- Serie diaria: suma/horas; serie mensual: suma de acumuladores/suma de horas por mes. No se promedian promedios diarios.

La lista de nodos viene de `nodes.parquet`. Nunca se unen ambas fuentes para contar dos veces el solapamiento. Los cuantiles no se estiman desde el diario.

## Verificación de solo lectura

Al cargar una nueva versión, `inspeccionar_paquete` comprueba metadata v1, inventario completo, SHA-256, conteos de filas/nodos, columnas, tipos y compresión. Una discrepancia detiene la vista. La caché incluye metadata y la lista/tamaño/fecha de modificación de los archivos; los hashes se comprueban cuando esa versión se carga.

`scripts/validar_datos.py` añade comprobación de filas: orden por nodo, claves, fechas, horas, valores finitos, acumuladores, primeras/últimas observaciones y cuadre de horario contra diario en todo el solapamiento. Los hashes verifican consistencia con el manifiesto, no autentican por sí solos la procedencia oficial.

Claude publica un paquete consistente, con metadata al final, en un único commit. Conserva exportación, revisión de seguridad, deploy key, commit/push y automatización. Work mantiene el visor. La prueba integral y de paquete dañado debe ejecutarse sobre la entrega real antes del despliegue aprobado por Lalo.

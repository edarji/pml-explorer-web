# Validaciones y aceptación pendiente

## 2026-11-20 · PND v0.7.0: AC-13 local (rendimiento con el paquete real)

Medición **local** con el paquete PND real de esta rama (`pnd/`, 2023-01-01 a 2026-11-19, 1418 archivos horarios, 101 zonas, `dias_sin_dato` = 2026-05-08) y el paquete PML del repo. Equipo: MacBook Pro Apple M5 Pro, 24 GB, macOS 27.2.1; Python 3.14.8, Streamlit 1.66.1, DuckDB 1.5.6, pyarrow 24.0.0, pandas 3.0.6. Zona: MONTERREY. Cada escenario corre en su propio proceso (`scripts/medir_ac13_pnd.py`); RSS = `ru_maxrss` del proceso. Mediana de 3 corridas.

| Escenario | Primera corrida | Con caché | RSS máximo |
| --- | ---: | ---: | ---: |
| App, inicio PML (referencia, sin modalidad PND en la URL) | 0.99 s | 0.08 s | 229 MiB |
| App, PND mensual, rango completo | 1.61 s | 0.09 s | 275 MiB |
| App, PND diaria, rango completo | 1.54 s | 0.09 s | 276 MiB |
| App, PND horaria, 366 días (2025-11-19 a 2026-11-19) | 1.21 s | 0.13 s | 281 MiB |
| App, PND solo 2026-05-08 (día sin dato: «Sin datos», 0 métricas) | 0.94 s | 0.06 s | 225 MiB |

| Función de `pnd.py` (sin Streamlit) | Resultado | Tiempo | RSS máximo |
| --- | --- | ---: | ---: |
| `inspeccionar_pnd()` (manifiesto, SHA-256 de 1419 archivos, esquema, zstd) | 2023-01-01 a 2026-11-19, 101 zonas | 0.24 s | 75 MiB |
| `serie_pnd` mensual, rango completo | 47 filas | 0.54 s | 180 MiB |
| `serie_pnd` diaria, rango completo | 1418 filas | 0.55 s | 181 MiB |
| `serie_pnd` horaria, 366 días | 8760 filas (365 días × 24; 2026-05-08 sin dato) | 0.33 s | 163 MiB |
| `estadisticas_pnd`, rango completo | 34,032 horas con dato | 0.50 s | 174 MiB |

Lectura: con el paquete real, PND agrega unos 0.2–0.6 s a la primera corrida de AppTest y unos 50 MiB de RSS sobre el inicio PML. Las corridas con caché quedan por debajo de 0.15 s. En las cinco corridas de la app no hubo ninguna excepción.

Son mediciones locales de procesos concretos (AppTest y funciones), **no de Community Cloud**: la memoria, el arranque en frío y el tiempo de consulta en la nube siguen pendientes hasta desplegar, lo que requiere aprobación específica.

## 2026-10-30 · Entrega 3: componentes (vista 3) y contrato v2

`vista3.py` reutiliza la consulta validada de `power-market-lab/scripts/vista3.py` en la ventana horaria (umbral de descuadre 0.02 MXN/MWh; el conteo compara el descuadre redondeado a 6 decimales para no contar ruido de coma flotante). Fuera de la ventana usa los acumuladores v2 sobre las mismas `horas_validas` del PML.

*Estado al 2026-11-01: el paquete público es v2 desde el 2026-10-31 (`c62aa39`) y la vista 3 está activa; el párrafo siguiente describe la situación del 2026-10-30.* En esa fecha **el paquete público aún era v1**, así que la vista mostraba «pendiente» (prueba `test_vista3_pendiente_con_paquete_v1`). La plomería v2 se probó en un entorno aislado con PML real y componentes **sintéticos** (nunca versionados ni publicados), 3 nodos, 2026-09-01 a 2026-10-30:

| Comprobación | Resultado |
| --- | --- |
| Export v2 + `validar_publico.py` (privado) + `scripts/validar_datos.py` | Sin errores |
| Vista 3 pública vs SQL privado, horaria/diaria/mensual y resumen | Idénticos en 3 nodos |
| Acumuladores diarios vs horario | Conteos y descuadre idénticos; promedios ±0.01 |
| Congestión negativa, descuadre 0.03 en 30 horas | Signos conservados; aviso «30 horas con descuadre mayor a 0.02» |
| Sin datos / horaria fuera de ventana | Sin cifras / bloqueada |
| Componente diario alterado con SHA-256 recalculado | `NO APTO`: «Los componentes diarios no cuadran» |
| Migración v1 → v2 | El exportador rehace solo los archivos v1 |

`tests/test_vista3.py` repetirá estas comprobaciones con los datos reales en cuanto `pml-bot` publique v2.

## 2026-10-30 · Entrega 2: spread entre nodos (vista 2)

`vista2.py` reutiliza la consulta validada de `power-market-lab/scripts/vista2.py` dentro de la ventana horaria (JOIN por fecha y hora antes de agregar). Fuera de la ventana usa los acumuladores diarios solo en días con 24 horas en ambos nodos, donde todas las horas coinciden y el promedio es exacto; los días incompletos se excluyen y se cuentan (en el paquete al 2026-10-30 no hay ninguno).

`tests/test_vista2.py` con el paquete real, A = 01AAN-85, B = 03TLJ-230 (nace el 2026-09-11), últimos 90 días de la ventana:

| Propiedad | Resultado |
| --- | --- |
| A = A → cero (horario y diario) | Promedio, mínimo, máximo y horas con A más caro = 0; cobertura 100 % |
| Intercambiar A/B | Signo invertido en las tres resoluciones; mínimo y máximo intercambiados |
| Solo horas coincidentes | Horas coincidentes = horas de B; ningún periodo antes del alta de B |
| Diario = horario en la ventana | Series diaria/mensual iguales a ±0.01 (un centavo en fronteras de redondeo), mismas horas |
| Sin horas comunes | 0 horas, promedio nulo; la interfaz no muestra cifras |
| Interfaz | Cobertura común escasa, mediana «—» fuera de ventana, bloqueo A = A, horaria fuera de ventana bloqueada |

Tiempos locales: histórico completo 0.39 s; año horario 0.63 s.

## 2026-10-30 · Entrega 1: interfaz pública (auditoría de Lalo)

Pruebas: `PML_REFERENCE_GLOB="$PWD/data/hourly/*.parquet" python -m unittest discover -s tests` con el paquete al 2026-10-30 (14 pruebas, OK). `tests/test_app_publica.py` recorre la interfaz con el paquete real versionado:

| Caso | Resultado esperado y comprobado |
| --- | --- |
| 03TLJ-230, 2023-01-01–2026-10-29, mensual | Aviso «Cobertura escasa» (3.5 %), rango con observaciones desde la primera fecha del nodo; septiembre marcado parcial (480 de 720 h) |
| 01AAN-85, 2026-10-29–30, mensual | Octubre marcado «29–30 oct: 2 de 31 días» |
| 01AAN-85, histórico completo, diaria | KPI «Promedio/Mediana/Mínimo/Máximo horario», «Horas con PML < 0»; dos decimales iguales en KPI y tabla; sin nombres internos |
| 03TLJ-230, 2023-01-01–02 | Sin cifras; aviso con las fechas observadas del nodo y «no equivale a precio cero» |
| Horaria fuera de ventana | Bloqueo con las fechas de la ventana |

Revisión visual en 1280×720 y 390×844 (Chromium local): la mediana fuera de ventana se muestra «—» con explicación, sin recortes.


Fecha de revisión: **2026-10-25**. **Actualización: el paquete real recibido pasó la [validación de entrega](validation-delivery-2026-10-25.md), incluidos nueve casos de referencia y nueve recorridos de interfaz.** Las comprobaciones de preparación siguientes se conservan como antecedente. No se han escrito archivos en `data/` ni modificado el laboratorio privado. No se ha desplegado el visor.

## Comprobaciones realizadas

| Comprobación | Resultado |
| --- | --- |
| Existencia/visibilidad GitHub | `edarji/pml-explorer-web`, público, rama `main`, comprobado con API pública |
| Sintaxis Python y configuración TOML | Correctas |
| SQL horario de `serie`/`estadisticas` | Misma consulta original, normalizando únicamente la ruta parametrizada |
| Pruebas automatizadas con fuente horaria real | 8 pruebas pasan; incluyen comparación en tres nodos seleccionados por primera observación, uno de historia posterior |
| Agregado diario en memoria frente a horario | Promedio, mínimo, máximo, horas válidas/negativas, desviación muestral, cobertura y series diaria/mensual coinciden al redondeo de la vista |
| Cuantiles fuera de ventana | Valores ausentes en la consulta diaria; resolución horaria rechazada fuera de ventana; límites inclusivos comprobados |
| Interfaz diaria con observaciones reales en memoria | Fechas desde los límites declarados, aviso de cuantiles y actualización en Ciudad de México; transporte del paquete sustituido para la prueba, pendiente el paquete exportado |
| Arranque Streamlit AppTest sin paquete | Aviso sin excepciones ni métricas, desde un directorio distinto al del código; sin servidor |
| Contrato v1 y fecha de actualización | Aceptación de metadata v1; rechazo de versión, unidades, zona UTC, rangos o rutas incompatibles; conversión del ejemplo a 23:00:12 del día anterior en Ciudad de México |
| SHA-256 y conteos alterados | Rechazados en pruebas aisladas con flujos de bytes y encabezados simulados, sin guardar archivos ni crear precios; falta probar el paquete real |
| Validador con paquete ausente | Rechazo con salida 1 y mensaje `NO APTO para publicación` |
| Reglas Git de derivados | Admiten solo particiones con nombres previstos, `nodes.parquet` y `metadata.json`; rechazan otras rutas y secretos |
| Revisión de archivos de publicación | Sin coincidencias de tokens, claves privadas o rutas personales en la revisión por patrones |
| Límites de escritura | Huellas de todos los archivos de `data/` y de las fuentes privadas comparadas antes/después: sin cambios |

La comparación numérica leyó la referencia horaria real autorizada del laboratorio, con consultas de solo lectura y tablas temporales en RAM. **No exportó un paquete público ni probó los Parquet diarios del pipeline.** El esquema diario de esa prueba se construyó en memoria exclusivamente a partir de precios reales. No se generaron precios ficticios ni archivos de datos.

La tolerancia de comparación de las cifras es medio centavo (0.005 MXN/MWh) tras el redondeo de SQL, sin tolerancia relativa. La prueba preserva la equivalencia de los estadísticos reconstruibles y exige que los cuantiles diarios no estén disponibles. La definición de `STDDEV` sigue siendo muestral, no poblacional.

## Reproducir sin generar datos

```bash
python -m unittest discover -s tests -v
```

Sin fuente real, la prueba numérica se omite explícitamente: no se crea un sustituto. Para ejecutar también esa comparación, usar una ruta de solo lectura a observaciones horarias auténticas autorizadas:

```bash
PML_REFERENCE_GLOB='/ruta/autorizada/horarios/*.parquet' python -m unittest discover -s tests -v
```

Al recibir los derivados de Claude, ejecutar además:

```bash
python scripts/validar_datos.py --data-dir /ruta/al/paquete-temporal
```

La biblioteca permite pasar `data_dir` a las consultas para leer esa carpeta temporal sin copiarla al repositorio. La app pública usará la carpeta `data/` versionada por `pml-bot`.

## Estado de los pendientes de integración

1. Contrato físico v1 recibido e implementado: `pml_min`/`pml_max`, fechas de catálogo, rangos desde metadata y `generado_utc` convertido a Ciudad de México. Este pendiente queda cerrado; la aceptación del paquete real se completó según el informe enlazado.
2. **Cerrado para la entrega identificada en el informe:** paquete real y nueve casos de referencia, incluidos tres nodos y uno de alta posterior.
3. **Cerrado para esta entrega:** validación completa aprobada; copia dañada de Claude rechazada por SHA-256.
4. **Cerrado para esta entrega:** nueve recorridos de interfaz con Parquet reales y fecha de actualización correcta.
5. Revisión de seguridad de Claude y aprobación para el primer push de datos conforme al reparto acordado.

## Pendientes para publicar

Tras cerrar lo anterior: pedir aprobación a Lalo para el primer despliegue público, comprobar instalación y ejecución real en Linux/Community Cloud, medir memoria/tiempo con todo el paquete y confirmar la URL real. Después, Claude verifica tres actualizaciones diarias de `pml-bot` y prepara el enlace desde edarji.net mediante PR.

No se requiere acceso entrante al Mac mini ni introducir credenciales en el repositorio. Esta preparación no configura automatizaciones, deploy keys ni permisos nuevos del servicio.

# Validaciones y aceptación pendiente

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

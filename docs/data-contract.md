# Integración con el pipeline de Claude

Revisión: 2026-10-25. Este documento reemplaza la propuesta anterior de `data/public/`. **La estructura y las reglas económicas están acordadas; el esquema físico completo todavía no se ha recibido.** No se debe interpretar la preparación del lector como aceptación de un paquete no entregado.

## Acuerdo localizado

La respuesta de Claude del 25 de octubre de 2026 establece:

- `data/hourly/AAAA-MM-DD.parquet`: un día por archivo, ventana móvil de 365 días.
- `data/daily/AAAA-MM.parquet`: un mes por archivo, histórico diario desde 2023-01.
- `data/nodes.parquet`: catálogo público.
- `data/metadata.json`: incluye `horario_desde` y `horario_hasta`.
- Promedio = `SUM(suma_pml)/SUM(horas_validas)`; el diario incluye además `horas_negativas` y `suma_pml_cuadrado`.
- La cobertura horaria suficiente exige que el rango completo sea inclusivamente interior a las fechas de metadata.
- Solo el pipeline de Claude / `pml-bot` escribe en `data/`. Work mantiene el visor y la documentación.

La ventana puede ampliarse por el pipeline solo tras un nuevo acuerdo; este lector rechaza más de 365 días. No hay otra partición horaria/mensual oculta ni unión de ambas fuentes que duplique observaciones.

## Interfaz preparada del lector — pendiente de cotejo físico

| Archivo | Columnas que espera el lector | Origen de la decisión |
| --- | --- | --- |
| Horario | `nodo`, `fecha`, `hora`, `pml` | Esquema de la vista 1 original |
| Diario | `nodo`, `fecha`, `horas_validas`, `suma_pml`, `suma_pml_cuadrado`, `horas_negativas` | Claves originales y acumuladores acordados |
| Diario | **`min_pml`, `max_pml`** | Nombres provisionales del adaptador; Claude debe confirmar los nombres reales |
| Nodos | `nodo` | Clave original; confirmar el esquema completo de `nodes.parquet` |
| Metadata | `horario_desde`, `horario_hasta` | Nombres confirmados por Claude |

Los dos nombres provisionales se concentran en `MIN_DIARIO` y `MAX_DIARIO`, en `vista1.py`. **No se pide al pipeline que cambie su contrato para ajustarse a ellos.** Al recibirlo, Work ajustará el lector si difieren. No se reconocen alias silenciosamente.

Tipos de lectura: `nodo` texto; `fecha` DATE o TIMESTAMP sin zona, a medianoche; `hora`, `horas_validas` y `horas_negativas` enteros; precios y acumuladores numéricos finitos, sin nulos. Los dos límites horarios deben poder leerse como fechas ISO. La aplicación admite columnas adicionales del pipeline, sujetas a su revisión de seguridad.

Una fila horaria por `(nodo, fecha, hora)` y una diaria por `(nodo, fecha)`; horas 1..24; de 1 a 24 horas válidas por fila diaria. No generar filas de cero horas para completar fechas. El archivo solo contiene fechas de la partición indicada. Los días sin un nodo no se inventan ni se completan. Las claves del catálogo deben ser únicas y cubrir los datos. No se equipara el catálogo observado a un catálogo oficial de vigencias.

Los acumuladores se calculan sobre todas las horas válidas del día, **sin redondeo previo de sumas ni de cuadrados**. `min_pml`/`max_pml` designan el menor/mayor precio horario, nunca el mínimo/máximo de promedios diarios. La suma de cuadrados conserva precisión suficiente para la desviación muestral. El tipo físico y las tolerancias finales requieren cotejo con Claude.

## Metadata pendiente

Además de los límites horarios conocidos, falta recibir el contrato de:

- Fuente/procedencia CENACE, mercado MDA, sistema SIN y unidades MXN/MWh.
- Fecha real de extracción/actualización, con zona horaria y significado preciso.
- Cobertura diaria efectiva, número de filas/nodos y controles realizados.
- Versionado del esquema y mecanismo de consistencia del paquete, si los define el pipeline.

No se han inventado nombres de campos para estas propiedades ni creado un `metadata.json`. Por ahora el visor muestra el corte efectivo diario leído del paquete y la ventana horaria declarada; **ese corte no es el instante de extracción**. Integrar su fecha real de actualización en pantalla queda pendiente del contrato.

## Validación y publicación

`inspeccionar_paquete` comprueba presencia, nombres, esquema físico, particiones esperadas y coherencia de límites. La caché usa el contenido de metadata y la lista/tamaño/fecha de modificación de los archivos, por lo que un nuevo paquete invalida las consultas. No es una verificación criptográfica de procedencia.

`scripts/validar_datos.py` recorre las filas sin escribir datos, rechaza nulos/no finitos/duplicados, comprueba catálogo, horas, fechas de partición y acumuladores básicos. Compara además horario y diario en todo el solapamiento. Un archivo ilegible o ausente devuelve código 1 y bloquea la aceptación.

Faltan ejecutar esas comprobaciones sobre el paquete final, acordar tolerancias con los tipos reales y probar que una copia deliberadamente dañada del paquete temporal también es rechazada. Esa copia y cualquier exportación son responsabilidad del pipeline; Work no escribe ni siquiera archivos de prueba dentro de `data/`.

El pipeline debe publicar un paquete consistente en un único commit, incluyendo metadata. Claude conserva exportación, deploy key, revisión de seguridad, commit/push, `launchd` y actualización de datos. No se incorpora ninguna credencial al visor.

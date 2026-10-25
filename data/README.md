# Contrato del paquete público

**No se incluyen datos todavía.** Esta carpeta no es una copia del almacenamiento operativo. No se distribuyen ejemplos de precios ni datos sintéticos.

## Formato compatible con la vista actual

Archivos Parquet revisados dentro de `data/public/`, con el mismo esquema entre archivos y solo estas columnas necesarias:

| Columna | Tipo requerido | Significado |
| --- | --- | --- |
| `fecha` | DATE o TIMESTAMP sin zona, a medianoche | Día de operación CENACE |
| `hora` | entero de 1 a 24 | Etiqueta horaria de la fuente |
| `nodo` | texto no vacío | Identificador NodoP |
| `pml` | numérico finito, no nulo | PML MDA SIN en MXN/MWh |

Una fila por `(fecha, hora, nodo)`, sin duplicados entre archivos. No incluir columnas privadas, identificadores personales, credenciales, rutas del equipo ni componentes innecesarios para esta vista. Mantener valores oficiales, ceros y negativos; no imputar horas ausentes. Fecha inicial prevista: 2023-01-01; nunca presentar una cobertura que el paquete no contenga.

El paquete debe generarse como una exportación pública deliberada, con procedencia CENACE comprobada, separada de las bases y descargas de trabajo. La creación de este repositorio no aprueba ningún archivo operativo para publicación. No se copió el histórico local.

## Metadatos obligatorios antes del lanzamiento con datos

Crear `data/public/manifest.json` con los valores reales, sin ejemplos inventados:

- `source_url`, `market` (MDA), `system` (SIN), `unit` (MXN/MWh).
- `extracted_at`: instante ISO 8601 con zona de la extracción de la fuente.
- `published_at`: instante ISO 8601 con zona de la publicación del paquete.
- `operation_date_min`, `operation_date_max`, `valid_hourly_rows`, `node_count` calculados del paquete.
- `files`: nombres exactos de los Parquet, tamaño en bytes y SHA-256.
- `historical_catalog_notes`: evidencia de altas/bajas o aclaración de que no hay vigencias verificadas.
- `quality_notes`: fechas ausentes, duplicados/errores detectados y su resolución, tratamiento de recálculos/republicaciones y validaciones realizadas.

El manifiesto sirve como trazabilidad documental; esta versión de la aplicación no lo interpreta ni verifica automáticamente. Actualizar también la fecha de datos en `docs/methodology.md`.

## Revisión previa a incluir archivos

1. Verificar fuente, mercado, sistema, unidades, fechas y claves con CENACE.
2. Comprobar unicidad, tipos, PML finitos/no nulos, horas y catálogo histórico. Informar cobertura sin completar valores.
3. Revisar todas las columnas y metadatos del Parquet, tamaño por archivo y huella total. Medir memoria y tiempo de consulta en Community Cloud. No se ha probado el histórico completo en la nube.
4. Revisar ausencia de secretos y archivos privados.
5. Añadir excepciones **por nombre exacto** a `.gitignore` para cada derivado aprobado y el manifiesto. No usar `git add -f` ni una excepción global de Parquet.
6. Validar la vista con el paquete aprobado antes de anunciarla desde edarji.net.

Solo promedios diarios/mensuales no satisfacen este contrato. La resolución horaria, mediana y percentiles de rangos arbitrarios requieren conservar observaciones horarias válidas.

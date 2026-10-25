# Metodología pública — PML Explorer v0.1

Última actualización de este documento: **2026-10-25**.
Última actualización de los datos públicos: **pendiente; no hay un paquete público publicado**. La fecha del documento no es la fecha de corte de los precios. Al incorporar datos se registrarán fecha de extracción y último día de operación disponible en `data/public/manifest.json` y se actualizará este apartado.

## Fuente y alcance

Fuente oficial: Centro Nacional de Control de Energía (CENACE), [Precios de Energía y Servicios Conexos MDA](https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreEnerServConMDA.aspx), a través del servicio público SW-PML. Referencia técnica: [Manual SW-PML](https://www.cenace.gob.mx/DocsMEM/2020-01-14%20Manual%20T%C3%A9cnico%20SW-PML.pdf).

Se analizan los **PML del Mercado del Día en Adelanto (MDA) del Sistema Interconectado Nacional (SIN)**, en MXN/MWh, con cobertura histórica prevista desde enero de 2023. No se incluyen MTR, BCA ni BCS. Cada consulta corresponde a un nodo; no representa un promedio de todos los nodos del SIN. La plataforma es un análisis independiente de información de CENACE.

La cobertura efectiva depende del paquete público y de la existencia histórica del nodo. No se afirma que todos los nodos tengan observaciones desde 2023. CENACE puede recalcular o republicar reportes: un paquete es una instantánea de las observaciones disponibles cuando se extrajo, no una garantía de última revisión permanente.

## Observación horaria y resoluciones

La unidad de observación es `(fecha de operación, hora, nodo)`. El código actual ubica la hora como `fecha + (hora - 1) horas`; requiere etiquetas de hora enteras de 1 a 24. Esta coordenada de gráfica no constituye una conversión a UTC. Las fechas Desde/Hasta son inclusivas.

- **Horaria:** una observación válida por nodo y hora. El agrupamiento horario conserva su PML, redondeado a dos decimales.
- **Diaria:** promedio simple de las observaciones horarias válidas del día incluido en el rango.
- **Mensual:** promedio simple de las observaciones horarias válidas de cada mes, limitado al rango elegido. Si el rango corta un mes, el punto representa solo la parte seleccionada.

Para un conjunto de horas válidas H, el promedio es `sum(PML_h) / count(H)`. No se pondera por demanda, volumen ni duración distinta de una hora. El promedio mensual se calcula directamente sobre horas; no es un promedio no ponderado de promedios diarios. El promedio del rango también se calcula sobre sus horas. Un periodo incompleto no se rellena para promediar.

## Estadísticas y restricciones

La mediana y los percentiles P10/P90 se calculan sobre **PML horarios originales del rango y nodo seleccionados**, incluso cuando la gráfica es diaria o mensual. DuckDB usa `MEDIAN` y `QUANTILE_CONT` (interpolación continua). No describen la distribución de los puntos diarios/mensuales de la gráfica.

No se pueden obtener medianas o percentiles exactos de un rango arbitrario promediando medianas o percentiles diarios/mensuales. Tampoco pueden reconstruirse únicamente a partir de promedio y número de horas. El contrato actual necesita datos horarios. Un paquete solo agregado requeriría acordar otra interfaz de cálculo; no es compatible con esta vista sin cambios explícitos.

Se muestran mínimo, máximo, promedio y número de horas con PML negativo. La tabla ampliada incluye desviación estándar muestral (`STDDEV`), mediana y percentiles. Con una sola observación la desviación muestral no está definida. Promedio, mediana, desviación y percentiles se redondean a dos decimales en SQL; el indicador principal Promedio se presenta sin decimales, tal como en la vista existente.

## Faltantes y cobertura

No se imputan precios, no se arrastran observaciones y no se convierten faltantes en cero. Los ceros y precios negativos que sí publique la fuente se conservan. Un periodo sin filas no produce un punto agregado; no debe interpretarse una línea entre puntos como evidencia de observaciones intermedias.

El código heredado calcula `horas_con_dato = COUNT(*)` y el denominador como `24 × días calendario del rango`. Por tanto, el paquete público debe tener **una sola fila por nodo/fecha/hora y PML numérico, finito y no nulo**. DuckDB omite nulos al promediar, pero `COUNT(*)` los contaría: admitirlos haría incoherente la cobertura. Rechazar duplicados y filas inválidas es un requisito del paquete, no una limpieza que ya realice esta aplicación.

El denominador de 24 horas diarias es una convención del prototipo. Si las etiquetas oficiales de un día requieren una interpretación distinta, el paquete y el cálculo deben revisarse antes de publicarlo; no se corrigen silenciosamente horas para aparentar cobertura completa. Cuando no hay observaciones en el rango, la vista muestra un aviso.

## Catálogo histórico de nodos

El catálogo varía con el tiempo. El selector web se obtiene de los identificadores efectivamente presentes en los derivados públicos, sin depender de un archivo local de configuración. No se infiere continuidad entre claves diferentes ni se fusionan nodos por semejanza de nombre.

La ausencia anterior al alta de un nodo o posterior a su baja no equivale automáticamente a un fallo de descarga. Primera/última observación no prueban por sí solas la vigencia oficial. La vista heredada conserva su cobertura sobre todo el rango calendario: **todavía no distingue en pantalla horas fuera de vigencia y horas faltantes dentro de vigencia**. No debe presentarse ese porcentaje como tasa de integridad del nodo. El paquete deberá documentar vigencias verificadas o su ausencia; corregir esta limitación queda pendiente de validación técnica, sin rediseñar aquí la vista.

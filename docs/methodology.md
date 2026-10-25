# Metodología — PML Explorer v0.1

Documento actualizado: **2026-10-25**. El paquete derivado público y su fecha de extracción están pendientes. La fecha de este documento no es un corte de precios.

## Fuente y alcance

Fuente: Centro Nacional de Control de Energía (CENACE), [Precios de Energía y Servicios Conexos MDA](https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreEnerServConMDA.aspx), mediante el [servicio SW-PML](https://www.cenace.gob.mx/DocsMEM/2020-01-14%20Manual%20T%C3%A9cnico%20SW-PML.pdf). El manual describe precios por hora, día de operación y NodoP, y distingue MDA de MTR. La versión pública de este visor cubre exclusivamente **MDA del SIN**, en **MXN/MWh**; no incluye MTR, BCA, BCS, demanda ni agrupaciones regionales.

El análisis es independiente de CENACE. Se publican derivados de sus observaciones, no precios ficticios ni una base operativa. CENACE puede revisar o republicar información; la versión disponible es la instantánea del pipeline, sin garantía de incorporar una revisión posterior hasta la siguiente actualización.

## Dos resoluciones de almacenamiento

- **Horario:** ventana móvil de hasta 365 días; un Parquet por fecha de operación.
- **Diario:** acumuladores por nodo/día de todo el histórico previsto desde 2023-01-01; un Parquet por mes.

La cobertura efectiva depende del paquete recibido y de la existencia histórica del nodo. El histórico diario no permite recuperar la trayectoria de las horas anteriores a la ventana móvil. El rango de consulta es inclusivo y siempre usa una sola fuente: horario si cabe completo en la ventana declarada, diario en caso contrario. No se suman fuentes solapadas ni se combinan cuantiles de ventanas parciales.

La coordenada de gráfica horaria heredada es `fecha + (hora - 1) horas`, para etiquetas de 1 a 24. No implica conversión a UTC. El denominador heredado de cobertura es 24 horas por día calendario. Si una etiqueta oficial exigiera otra interpretación, requiere validación en el laboratorio y no se corrige silenciosamente.

## Promedios y gráfica

Para N observaciones horarias válidas, `promedio = S/N`, con `S = suma(PML_h)`. Cada hora tiene el mismo peso; no hay ponderación por demanda o volumen. Se conservan ceros y precios negativos.

Dentro de la ventana, las consultas horarias originales usan `AVG(pml)`. En el histórico diario, el equivalente para cualquier rango es `SUM(suma_pml)/SUM(horas_validas)`. **Nunca se calcula un promedio simple de promedios diarios.** Los meses incompletos se calculan solo con los días elegidos. La gráfica diaria/mensual representa esos promedios; la horaria requiere el rango completo en la ventana disponible.

El SQL redondea el resultado a dos decimales. El indicador principal de promedio se muestra sin decimales, como en la vista validada; los acumuladores del pipeline no deben redondearse antes de la consulta.

## Estadísticas de los precios horarios

| Indicador | Rango íntegramente horario | Rango que excede la ventana |
| --- | --- | --- |
| Promedio | `AVG(pml)` | `SUM(suma_pml)/SUM(horas_validas)` |
| Mínimo y máximo | Extremos de las horas | Menor mínimo/mayor máximo horario diario |
| Horas negativas | Conteo de `pml < 0` | Suma de `horas_negativas` |
| Desviación estándar muestral | `STDDEV(pml)` | Reconstrucción con N, S y Q |
| Mediana | `MEDIAN(pml)` | No disponible |
| P10/P90 | `QUANTILE_CONT(pml, 0.10/0.90)` | No disponibles |

Para `Q = suma(PML_h²)`, la desviación muestral es `sqrt((Q - S²/N)/(N-1))`, con N > 1. Con cero o una observación no está definida; no se reemplaza por cero. El lector protege de pequeños residuos negativos de coma flotante; el validador rechaza acumuladores materialmente inconsistentes. La precisión numérica de los tipos físicos y el redondeo a dos decimales deben contrastarse con la entrega final; equivalencia matemática no promete identidad binaria entre métodos de acumulación.

La mediana y los percentiles describen la distribución de **todas las horas del rango**, aunque la gráfica sea diaria o mensual. `QUANTILE_CONT` interpola continuamente. No se obtienen cuantiles horarios exactos con promedios, medianas o percentiles diarios agregados. Por eso se muestran como **“No disponible”** si el rango no cae completo dentro de `horario_desde..horario_hasta`, sin estimarlos ni calcularlos sobre una parte del rango.

Los acumuladores permiten conservar los estadísticos reconstruibles de las observaciones válidas; la prueba final debe confirmar los mismos resultados que la vista original, incluidos rangos parciales, signos y redondeo.

## Faltantes, cobertura y catálogo

No se imputan horas, no se arrastran precios y un faltante nunca se convierte en cero. Se rechazan precios nulos/no finitos y claves duplicadas en el paquete; son requisitos para que los conteos y las sumas sean coherentes. Si un nodo no tiene datos en el rango, el visor muestra un aviso, sin cifras sustitutivas. Una línea entre puntos no acredita que existan todas las horas intermedias.

`horas_con_dato` es el conteo horario válido o la suma de `horas_validas`. `horas_del_rango = 24 × días calendario inclusivos`. La cobertura es `100 × horas_con_dato/horas_del_rango`, a un decimal; no se reduce el denominador para ocultar faltantes.

El catálogo cambia con el tiempo. Un nodo puede incorporarse después de enero de 2023 y no se inventan observaciones anteriores a su alta. La vista conserva el porcentaje sobre el rango calendario completo y lo advierte en pantalla: **no es una tasa de integridad dentro de la vigencia del nodo**. Primera/última observación tampoco prueban una alta/baja oficial. El selector usa `nodes.parquet`; no fusiona claves similares ni inventa regiones o zonas. Las vigencias oficiales requieren evidencia del catálogo NodosP, pendiente de entrega.

## Trazabilidad y límites pendientes

La pantalla muestra el rango efectivo diario y la ventana horaria de metadata. La fecha de extracción debe provenir del contrato final del pipeline; todavía no se ha recibido y no se infiere del reloj del servidor ni de la fecha de Git. El [contrato de integración](data-contract.md) distingue las decisiones acordadas de los nombres físicos pendientes.

Antes del lanzamiento: validar los derivados finales, cotejar tres nodos (uno de alta posterior), revisar las advertencias en pantalla y medir tiempo/RAM en Community Cloud. No se ha validado todavía el paquete público ni el servicio desplegado. Los cambios de cálculo se aprueban y validan primero en `power-market-lab`; esta preparación no lo modifica.

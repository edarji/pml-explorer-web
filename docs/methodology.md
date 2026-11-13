# Metodología — PML Explorer

Documento revisado: **2026-11-13**. Describe el comportamiento de la aplicación pública vigente. La fecha de este documento no es un corte de precios.

| Concepto | Valor vigente | Dónde se comprueba |
| --- | --- | --- |
| Versión de la aplicación | **v0.6.2 beta**: vista 1 (PML histórico), vista 2 (spread entre nodos) y vista 3 (componentes), con enlaces compartibles, selector por ubicación y descarga CSV | Pie de la aplicación («PML Explorer v0.6.2 beta · Datos: esquema v2 · …») |
| Esquema de datos | **v2** (v1 + componentes del PML), publicado por `pml-bot` desde el 2026-10-31 (commit `c62aa39`) | `version_esquema` en `data/metadata.json`; [contrato de datos](data-contract.md) |
| Fecha del paquete | Cambia cada noche; no la fija este documento | «Actualización del paquete» en el pie de la aplicación (`generado_utc` convertido a Ciudad de México) |

## Fuente y alcance

Fuente: Centro Nacional de Control de Energía (CENACE), [Precios de Energía y Servicios Conexos MDA](https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreEnerServConMDA.aspx), mediante el [servicio SW-PML](https://www.cenace.gob.mx/DocsMEM/2020-01-14%20Manual%20T%C3%A9cnico%20SW-PML.pdf). El manual describe precios por hora, día de operación y NodoP, y distingue MDA de MTR. La versión pública de este visor cubre exclusivamente **MDA del SIN**, en **MXN/MWh**; no incluye MTR, BCA, BCS, demanda ni agrupaciones regionales.

El análisis es independiente de CENACE. Se publican derivados de sus observaciones, no precios ficticios ni una base operativa. CENACE puede revisar o republicar información; la versión disponible es la instantánea del pipeline, sin garantía de incorporar una revisión posterior hasta la siguiente actualización.

## Dos resoluciones de almacenamiento

- **Horario:** ventana móvil de hasta 365 días; un Parquet por fecha de operación.
- **Diario:** acumuladores por nodo/día de todo el histórico previsto desde 2023-01-01; un Parquet por mes.

La cobertura efectiva depende del paquete recibido y de la existencia histórica del nodo. El histórico diario no permite recuperar la trayectoria de las horas anteriores a la ventana móvil. El rango de consulta es inclusivo y siempre usa una sola fuente: horario si cabe completo en la ventana declarada, diario en caso contrario. No se suman fuentes solapadas ni se combinan cuantiles de ventanas parciales.

La hora es final: la etiqueta 1 corresponde a 00:00–01:00. La coordenada de gráfica horaria heredada, que marca el inicio del intervalo, es `fecha + (hora - 1) horas`, para etiquetas de 1 a 24. No implica conversión a UTC. El denominador heredado de cobertura es 24 horas por día calendario. Si una etiqueta oficial exigiera otra interpretación, requiere validación en el laboratorio y no se corrige silenciosamente.

## Promedios y gráfica

Para N observaciones horarias válidas, `promedio = S/N`, con `S = suma(PML_h)`. Cada hora tiene el mismo peso; no hay ponderación por demanda o volumen. Se conservan ceros y precios negativos.

Dentro de la ventana, las consultas horarias originales usan `AVG(pml)`. En el histórico diario, el equivalente para cualquier rango es `SUM(suma_pml)/SUM(horas_validas)`. **Nunca se calcula un promedio simple de promedios diarios.** Los meses incompletos se calculan solo con los días elegidos. La gráfica diaria/mensual representa esos promedios; la horaria requiere el rango completo en la ventana disponible.

El SQL redondea el resultado a dos decimales y la aplicación muestra precios, indicadores y tablas con dos decimales. Los acumuladores del pipeline no se redondean antes de la consulta.

## Estadísticas de los precios horarios

| Indicador | Rango íntegramente horario | Rango que excede la ventana |
| --- | --- | --- |
| Promedio | `AVG(pml)` | `SUM(suma_pml)/SUM(horas_validas)` |
| Mínimo y máximo | Extremos de las horas | Menor mínimo/mayor máximo horario diario |
| Horas negativas | Conteo de `pml < 0` | Suma de `horas_negativas` |
| Desviación estándar muestral | `STDDEV(pml)` | Reconstrucción con N, S y Q |
| Mediana | `MEDIAN(pml)` | No disponible |
| P10/P90 | `QUANTILE_CONT(pml, 0.10/0.90)` | No disponibles |

Para `Q = suma(PML_h²)`, la desviación muestral es `sqrt((Q - S²/N)/(N-1))`, con N > 1. Con cero o una observación no está definida; no se reemplaza por cero. El lector protege de pequeños residuos negativos de coma flotante; el validador rechaza acumuladores materialmente inconsistentes. Equivalencia matemática no promete identidad binaria entre métodos de acumulación.

La mediana y los percentiles describen la distribución de **todas las horas del rango**, aunque la gráfica sea diaria o mensual. `QUANTILE_CONT` interpola continuamente. No se obtienen cuantiles horarios exactos con promedios, medianas o percentiles diarios agregados. Por eso se muestran como **“No disponible”** si el rango no cae completo dentro de `horario_desde..horario_hasta`, sin estimarlos ni calcularlos sobre una parte del rango.

Los acumuladores permiten conservar los estadísticos reconstruibles de las observaciones válidas; la prueba final debe confirmar los mismos resultados que la vista original, incluidos rangos parciales, signos y redondeo.

## Faltantes, cobertura y catálogo

No se imputan horas, no se arrastran precios y un faltante nunca se convierte en cero. Se rechazan precios horarios nulos/no finitos y claves duplicadas en el paquete; son requisitos para que los conteos y las sumas sean coherentes. Las filas diarias con cero horas válidas no aportan precios ni extremos. Si un nodo no tiene datos en el rango, el visor muestra un aviso, sin cifras sustitutivas. Una línea entre puntos no acredita que existan todas las horas intermedias.

`horas_con_dato` es el conteo horario válido o la suma de `horas_validas`. `horas_del_rango = 24 × días calendario inclusivos`. La cobertura es `100 × horas_con_dato/horas_del_rango`, a un decimal; no se reduce el denominador para ocultar faltantes.

El catálogo cambia con el tiempo. Un nodo puede incorporarse después de enero de 2023 y no se inventan observaciones anteriores a su alta. La vista conserva el porcentaje sobre el rango calendario completo y lo advierte en pantalla: **no es una tasa de integridad dentro de la vigencia del nodo**. Primera/última observación tampoco prueban una alta/baja oficial. El selector usa `nodes.parquet`, que incluye `primera_fecha` y `ultima_fecha` observadas; no fusiona claves similares. Desde v0.6.0, nombres, regiones y zonas vienen solo del Catálogo de NodosP de CENACE (`referencia/`), nunca de la clave. Esas fechas no acreditan vigencias oficiales del catálogo NodosP.

## Spread entre nodos (vista 2)

Spread = **PML_A − PML_B**, hora por hora, solo en las horas en que los dos nodos tienen dato; después se promedia por día o mes. La cobertura común es horas coincidentes ÷ (24 × días del rango). Fuera de la ventana horaria se usan los días en que ambos nodos tienen las 24 horas; un día incompleto en algún nodo se excluye y se avisa.

## Componentes del PML (vista 3)

PML = energía + pérdidas + congestión, con los signos publicados por CENACE (pérdidas y congestión pueden ser negativas). Todos los componentes se promedian sobre las mismas horas que el PML. El descuadre es |PML − (energía + pérdidas + congestión)| por hora; viene del redondeo de CENACE y se avisa cuando supera 0.02 MXN/MWh.

## Uso de la interfaz

- **Vista y filtros:** vista, nodo(s), fechas y resolución están en el panel «Vista y filtros», cerrado al abrir la aplicación. Cerrarlo no cambia la selección.
- **Fechas por defecto:** «Desde» y «Hasta» inician en el día de la consulta (fecha de Ciudad de México), en resolución horaria. Si el paquete todavía no incluye ese día, se usa el último día disponible. Los límites seleccionables siguen saliendo de `metadata.json`.
- **Nodos (v0.6.0):** se buscan por clave NodoP o por nombre oficial (por ejemplo `06ESC` o «Escobedo» encuentran `06ESC-115 · Escobedo`). Cada opción se muestra como «Clave · Nombre», pero el valor elegido, la URL y los cálculos usan solo la clave: un nombre puede repetirse en varias claves. Antes del nodo, «Región de Control», «Estado» y «Zona de carga» (opcionales, «Todas» por defecto) acotan la lista; el estado es la entidad federativa (clave INEGI) donde CENACE ubica cada nodo y se aplica nodo por nodo, porque una zona de carga puede abarcar varios estados; no cambian el nodo elegido: si queda fuera del filtro se conserva con un aviso, y «Limpiar ubicación» vuelve a «Todas». En la vista 2, Nodo A y Nodo B tienen filtros independientes. La clasificación es la de la versión del catálogo indicada al pie y no se aplica hacia atrás; los 7 nodos de interconexión internacional aparecen como «sin clasificación verificada». Si el catálogo falta o no pasa su validación, la aplicación funciona solo con claves, como en v0.5.1. Región, estado y zona no se guardan en los enlaces.
- **Rangos rápidos (v0.4.1):** tres botones encima de «Desde/Hasta», compartidos por las tres vistas. Se anclan en `diario_hasta` de `metadata.json` (la última fecha de operación del paquete, igual para todos los nodos), no en el reloj. *Último día* = `diario_hasta`; *Últimos 7 días* = `diario_hasta − 6` a `diario_hasta`; *Mes en curso* = día 1 del mes de `diario_hasta` a `diario_hasta`. Si el inicio calculado queda antes de `diario_desde`, se recorta. Solo escriben las dos fechas: nodo, resolución, fórmulas, signos, agregaciones y faltantes no cambian. Un nodo con menos datos muestra el aviso de cobertura habitual.
- **Enlaces compartibles (v0.5.1):** la URL guarda la vista y los filtros, nunca los datos. Parámetros: `vista` (`historico`, `comparacion` o `componentes`), `nodo` (vistas 1 y 3) o `nodo_a` y `nodo_b` (vista 2), `desde` y `hasta` en formato `AAAA-MM-DD`, y `resolucion` (`horaria`, `diaria` o `mensual`). Las fechas siempre son absolutas, también después de un rango rápido: un enlace no cambia de periodo cuando llega el paquete nocturno. Ejemplo: `?vista=comparacion&nodo_a=01AAN-85&nodo_b=01AGU-230&desde=2026-10-30&hasta=2026-11-05&resolucion=diaria`. La URL solo se lee al abrir la aplicación; cada cambio de filtro la actualiza. Un enlace con una vista, nodo, fecha o resolución inválidos, con un parámetro repetido o con un periodo fuera del paquete no se corrige en silencio: se explica el problema y no se muestran cifras hasta que el usuario cambie un filtro o pulse «Continuar con la configuración mostrada». Si faltan parámetros, se usan los valores predeterminados y se avisa. El botón «Atrás» del navegador no deshace cambios de filtro: la aplicación vuelve a escribir en la URL la configuración que está a la vista, así que URL, filtros y resultados siempre coinciden (para salir de la aplicación puede hacer falta pulsarlo más de una vez).
- **Recuadro de la gráfica (v0.5.1):** al pasar el mouse (o tocar en móvil) se marca el punto más cercano y un recuadro pequeño muestra nodo (o «A − B» en el spread), fecha, hora en convención CENACE —la hora 1 es 00:00–01:00— solo en resolución horaria, el valor en MXN/MWh y, en diaria o mensual, las horas con dato. Solo muestra valores ya calculados.
- **Pestañas en móvil (v0.5.1):** en pantallas de 640 px o menos la barra de pestañas ocupa dos filas, para que las tres vistas estén siempre visibles sin desplazarse.
- **Mensajes de control:** fechas invertidas, resolución horaria fuera de la ventana y rangos sin datos muestran un aviso y ninguna cifra sustitutiva.

## Exportación CSV (v0.6.2)

Cada vista tiene «Descargar CSV» debajo de la gráfica. El archivo contiene **la serie que dibuja la gráfica**, en la resolución elegida, con los mismos valores que la aplicación: no se recalcula nada ni se añade detalle horario a una consulta diaria o mensual. Los indicadores de la ficha (mediana, percentiles, extremos) no se exportan porque se calculan sobre horas aunque la gráfica sea diaria o mensual.

- **Formato:** coma como separador, punto decimal, UTF-8 con BOM, una fila de encabezados en `snake_case`. Se abre directamente con `pandas.read_csv`. En Excel con configuración regional de México se abre con doble clic; con una región que usa coma decimal (por ejemplo España), Excel espera `;` y conviene usar Datos → Desde texto/CSV.
- **Tiempo:** horaria = `fecha_operacion` + `hora_cenace` (1–24, hora final); diaria = `fecha_operacion`; mensual = `mes`, `fecha_desde`, `fecha_hasta` (parte del mes dentro de la consulta). Diaria y mensual añaden `horas_con_dato` (vista 2: `horas_comunes`), `horas_posibles` y `periodo_parcial`.
- **Valores:** vista 1 `nodo`, `pml`; vista 2 `nodo_a`, `nodo_b`, `pml_a`, `pml_b`, `spread_a_menos_b`; vista 3 `nodo`, `pml`, `energia`, `perdidas`, `congestion`, `descuadre_promedio` (con signo, 4 decimales). En la vista 2, `pml_a` y `pml_b` se promedian sobre las **mismas horas comunes** que el spread (no son las curvas de la gráfica, que usan todas las horas de cada nodo); como el spread se redondea después de restar, `pml_a − pml_b` puede diferir de él en ±0.01.
- **Faltantes:** un periodo sin dato no tiene fila; una celda vacía significa sin valor, nunca cero.
- **Contexto:** columnas constantes `vista`, `resolucion`, `consulta_desde`, `consulta_hasta`, `observado_desde`, `observado_hasta`, `cobertura_consulta_pct`, `unidad`, `fuente`, `mercado`, `sistema`, `paquete_generado_utc` (cuándo se generó el paquete, no una fecha de operación), `esquema_datos` y `version_app`. La URL no va en el archivo: sus parámetros son esas columnas, y junto al botón está «Enlace de esta consulta» para copiarla.
- **Nombre:** `pml_<historico|spread|componentes>_<nodos>_<desde>[_<hasta>]_<resolucion>.csv` con las fechas de la consulta.
- Un texto que Excel leería como fórmula (empieza con `= + - @`) se guarda precedido de `'`; los números negativos no se tocan.

## Trazabilidad y límites

La pantalla obtiene los límites diarios y horarios de `metadata.json`. Muestra `generado_utc`, instante de generación del paquete, convertido a `America/Mexico_City`; no lo infiere del reloj del servidor ni de Git, ni lo confunde con la extracción original de CENACE. El [contrato de datos](data-contract.md) fija el esquema, las unidades, la convención horaria y el manifiesto con conteos y SHA-256. El lector comprueba ese manifiesto antes de mostrar cifras.

La aplicación está publicada en Streamlit Community Cloud (https://pml-explorer.streamlit.app/) y `pml-bot` actualiza el paquete cada noche. **No hay mediciones verificadas** de memoria, tiempo de arranque en frío ni tiempo de consulta en Community Cloud; tampoco de la duración de la publicación nocturna con el esquema v2. Los cambios de cálculo se aprueban y validan primero en `power-market-lab`.

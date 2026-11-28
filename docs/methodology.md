# Metodología — PML Explorer

Documento revisado: **2026-11-28** (v0.10.0 · Operación · Demanda, panel derecho con la demanda del día por región). Describe el comportamiento de la aplicación pública vigente. La fecha de este documento no es un corte de precios.

| Concepto | Valor vigente | Dónde se comprueba |
| --- | --- | --- |
| Versión de la aplicación | **v0.6.5 beta** (identidad visual Dark Trading con pulido UX): vista 1 (PML histórico), vista 2 (spread entre nodos) y vista 3 (componentes), con enlaces compartibles, selector por ubicación y descarga CSV | Pie de la aplicación («PML Explorer v0.6.5 beta · Datos: esquema v2 · …») |
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

## Chaly's Bebop · vista estacional (vista 4, v0.9.0)

Un año calendario (Y) de un NodoP frente a su propia historia. Solo PML y solo el paquete **diario** (`data/daily`): una lectura de Y−5 a Y del nodo, recortada al inicio del paquete.

- **Precio de cada día:** promedio diario `suma_pml / horas_validas` (días con `horas_validas > 0`), redondeado a 2 decimales, igual que la serie diaria de la vista 1. Un día sin dato queda vacío: no es cero y la línea no lo cruza.
- **Líneas:**
  - Y en ámbar, hasta el último día de operación publicado; no se completa el resto del año.
  - Y−1 en azul apagado y Y−2 en gris, ambas tenues.
- **Banda Mín–Máx 5Y:** por fecha de calendario (mes-día), el mínimo y el máximo de los **promedios diarios** de Y−5 a Y−1 de ese nodo.
  - Nunca incluye Y.
  - No es un intervalo de confianza ni usa extremos horarios.
  - Cada fecha usa solo los años con dato ese día; el recuadro dice cuántos y cuáles.
  - Con menos de 2 años no se dibuja banda, porque una sola observación no es un rango.
  - El paquete empieza el 2023-01-01: para Y = 2026 la banda tiene hasta 3 de 5 años (2023 a 2025) y la vista lo rotula así. No se inventan años anteriores.
- **29 de febrero:** no aparece en esta vista, porque no tiene par en los años no bisiestos.
  - El calendario tiene 365 fechas y el 1 de marzo de un año bisiesto sigue siendo el 1 de marzo.
  - Las demás vistas y sus CSV lo conservan.
- **Fuera de banda:** una franja angosta bajo la gráfica marca cada día de Y por encima del máximo (rojo) o por debajo del mínimo (verde). Solo cuentan las fechas con banda.
- **Resumen:**
  - Días sobre y bajo la banda, y años en la banda.
  - Promedio de Y frente a Y−1, ponderado por horas (acumuladores) sobre las fechas de calendario con dato en los dos años. No promedia promedios.
- **Controles:**
  - El año Y se elige en la vista; si el nodo no tiene ese año, se toma el más reciente con dato.
  - 1D, 7D, Mes, YTD y «Fechas» no cambian esta vista.
- **Enlace y CSV:**
  - Enlace: `?vista=estacional&nodo=…&anio=AAAA`.
  - CSV propio `pml_bebop_<nodo>_<año>.csv`, con una fila por fecha de calendario: `fecha_calendario`, `pml_<Y>`, `horas_<Y>`, `pml_<Y−1>`, `pml_<Y−2>`, `banda_min`, `banda_max`, `banda_n_anios`, `banda_anios`, `fuera_de_banda`.
  - Una celda vacía es «sin dato».

## Uso de la interfaz

- **Ensemble y Solo (v0.8.0):** la aplicación abre en **ENSEMBLE**, un tablero compacto del día de referencia («Hasta», acotado a cada paquete) con dos secciones separadas: **PML · NodoP** (todos los nodos) y **PND · Zona de carga** (todas las zonas). Cada sección muestra cuántos elementos tienen dato, el más caro y el más barato, cuántos tuvieron alguna hora negativa, una gráfica compacta de distribución y los 5 más caros y 5 más baratos. Elegir un nodo o una zona en el panel derecho (o tocar una fila de los rankings) abre **SOLO**: las vistas de siempre con ese elemento como protagonista (desde v0.8.1, arriba del tablero; ver «Solista al frente»). «Cerrar detalle» (antes «Volver al mercado») deja solo el tablero con las mismas fechas, resolución, modalidad y selección. Desde SOLO PML, «Comparar nodos» usa al protagonista como nodo A.
  - **Sin cálculo nuevo:** el promedio del día de cada elemento es el mismo valor que su vista SOLO para ese día (promedio simple de sus horas con dato; fuera de la ventana horaria PML, suma ÷ horas válidas del diario). El tablero solo **ordena** esos valores y **cuenta** elementos: no hay promedios entre nodos, índices ni ponderaciones. La distribución agrupa esos mismos promedios por intervalo de precio para dibujarlos.
  - **PML y PND no se mezclan:** cada sección usa su paquete y su propio día de referencia (si el día PND no tiene dato, se usa el último anterior con dato y se dice). Ninguna gráfica, tabla o indicador combina PML con PND.
  - **Faltantes:** un nodo o una zona sin horas con dato ese día no entra al ranking ni se trata como cero; se cuenta como «sin dato». Un elemento con menos de 24 horas lo indica en su fila.
  - **Enlaces:** un enlace con `vista`, `nodo`, `nodo_a`, `nodo_b`, `modalidad` o `zona` abre SOLO con exactamente el mismo análisis que en v0.7.0 (incluidos sus avisos). Sin esos parámetros abre ENSEMBLE; su URL guarda solo `desde`, `hasta` y `resolucion`.
  - **Panel derecho (watchlist):** filtro de **tensión** (400 kV al abrir; 230, 115 o Todas), búsqueda por clave o nombre, ubicación (Región de Control, Estado, Zona de carga) y una lista corta de nodos con su PML promedio del día de referencia (6 filas y «Mostrar más»: no se dibujan miles de opciones). La tensión es la columna `tension_kv` del Catálogo de NodosP de CENACE, no se deduce del sufijo de la clave; «Todas» incluye también 69, 85, 138 kV y otras. Si el nodo elegido no cumple el filtro, se conserva y se avisa. En PND, la lista son las zonas de carga, con filtro de región. Los filtros no se guardan en la URL ni intervienen en ningún cálculo.
  - **SOLO (v0.8.0):** la línea principal lleva un degradado debajo y, en el histórico PML y en PND, **barras de congestión del mismo periodo** con eje cero (azul > 0, gris < 0), alineadas en el tiempo con la línea. En PML son la congestión de la consulta de componentes (la de la vista 3); en PND, la congestión del propio paquete PND (`pz_cng`). No se combinan entre sí.
  - **Paleta «Graphite híbrido»:** fondo gris tipo Apple Bolsa y tarjetas claras. Desde v0.8.1 el detalle también es claro (ya no hay panel grafito): ámbar para PML y azul para PND. Solo presentación.
  - **Solista al frente (v0.8.1):** una sola página. Sin selección se ve solo ENSEMBLE. Al elegir un nodo o una zona, su detalle (las mismas vistas y cifras de SOLO) aparece **arriba** y el mismo ENSEMBLE sigue **debajo**, usable: tocar otra fila o usar «Buscar otro nodo» cambia solo el protagonista y conserva fechas, resolución y filtros; la fila del solista se resalta. «Cerrar detalle» deja solo el mercado. Un enlace con nodo, zona, vista o modalidad abre el mismo análisis de antes dentro del detalle, con ENSEMBLE debajo. Con el detalle abierto, fechas, ubicación y precio se cambian en «Vista y filtros» del detalle; el panel derecho del tablero solo conserva la tensión, una búsqueda propia y la lista. Si el detalle no puede mostrar cifras (sin datos, fechas invertidas, enlace inválido), lo dice y el tablero sigue visible. En PND, las barras de congestión positivas van en grafito porque la línea ya es azul.
  - **Terminal persistente (v0.8.2):** la **barra superior** queda fija al desplazarse: marca compacta, precio (PML por nodo o PND por zona), los rangos **1D · 7D · Mes · YTD**, «Fechas» (Desde, Hasta y resolución, un solo juego de selectores para toda la página), el solista activo y el último día publicado del paquete (MDA, no tiempo real). **«Elige otro solista»** es una columna derecha fija, con su propio desplazamiento, desde el detalle hasta el final del tablero: tensión, búsqueda, ubicación y la lista con el promedio del día; sus filtros son propios de la lista (no cambian el selector del detalle). En 1024 px o menos la lista no queda fija (taparía la gráfica): va después del tablero y la barra muestra «Cambiar nodo», que lleva a ella. La gráfica del solista es más compacta (270 px de precio y 130 px de congestión con título y eje) y los indicadores van debajo, en rejilla; los valores no cambian.
  - **Rail izquierdo (v0.8.3):** «Elige el solista» pasa a la **izquierda** con unos 172–200 px de ancho y dos pestañas en el mismo panel: **Nodos** (PML por NodoP: tensión, búsqueda, ubicación y lista) y **Zonas** (PND por zona de carga: región, búsqueda y lista). Las pestañas y el selector «Precio» de la barra son el mismo estado: cambiar uno cambia el otro, y PML y PND siguen sin mezclarse. Cada fila muestra la clave o zona arriba y el promedio del día abajo (mismo valor que antes); un nombre largo se recorta con «…» y se lee completo en la ayuda. En 1024 px o menos el rail va después del tablero y la barra muestra «Cambiar nodo» o «Cambiar zona».
  - **Ticker PND (v0.8.5):** una cinta dentro de la barra fija, debajo de los controles, con el **PND promedio del último día publicado** del paquete PND (día D) de una selección de zonas de carga y su **cambio en MXN/MWh contra el día calendario anterior** (D−1). Rojo ▲ si subió, verde ▼ si bajó, gris «=» si es igual: el color solo dice si el precio es mayor o menor, no si es bueno o malo. Rótulo: «PND · Zonas de carga · promedio diario (MXN/MWh)», las dos fechas y «Datos publicados por CENACE · MDA · no tiempo real».
    - **Mismo valor que ENSEMBLE y SOLO PND:** cada precio es el promedio simple de las horas con dato de la zona ese día (`ensemble.ranking_pnd`, `ROUND(AVG(pnd), 2)`); el cambio es la resta de esos dos valores ya redondeados. No es un promedio de NodosP ni mezcla PML. Dos lecturas pequeñas por paquete (D y D−1), en caché hasta que cambia el paquete.
    - **Faltantes:** si D−1 no tiene dato publicado (o la zona no tiene precio ese día) se muestra «s/c vs ayer» sin flecha ni color; **nunca se compara con un día más antiguo**. Si la zona no tiene precio en D, «sin dato». Si alguno de los dos días tiene menos de 24 horas con dato, se muestra la diferencia **sin color ni flecha** con «parcial h/h». Sin porcentajes (el precio base puede ser cero o negativo). Sin paquete PND, o si falla, la cinta no aparece y PML sigue igual.
    - **Siempre el último día publicado de PND**, aunque se esté viendo otro rango o un NodoP; la cinta no cambia fechas, resolución, el día de referencia de ENSEMBLE ni la URL.
    - **Selección editorial (`ticker.ZONAS_TICKER`, editable sin tocar la interfaz):** una zona por cada Gerencia de Control Regional del SIN, la de su ciudad principal, más Querétaro porque Occidental es la región con más zonas (26 de 101): VDM CENTRO (Central), MONTERREY (Noreste), GUADALAJARA y QUERETARO (Occidental), PUEBLA (Oriental), MERIDA (Peninsular), CHIHUAHUA (Norte) y HERMOSILLO (Noroeste). Nombres exactos de `pnd/zonas.parquet`; la región, del Catálogo de NodosP de CENACE. No hay zonas de Baja California porque el paquete es solo del SIN. No es un ranking de popularidad.
    - **Interacción:** se desplaza sola (CSS, sin animar los números) y se detiene con el cursor encima. Con teclado cada zona se recorre una vez y la cinta se detiene y se vuelve desplazable. Con «reducir movimiento» no se mueve sola y se desliza a mano; en 640 px o menos tampoco se mueve sola: se desliza con el dedo. Tocar una zona abre su **detalle PND** arriba con ENSEMBLE debajo (igual que la lista; si las fechas elegidas quedan fuera del paquete PND se ajustan como al pasar a PND). La barra mide su alto con la cinta, así que el rail y el detalle quedan debajo de las dos.
  - **Drill-down del histograma PND (v0.8.7):** en ENSEMBLE con PND, tocar una barra de «Distribución del PND promedio del día entre zonas de carga» muestra debajo el rango y sus zonas: «a–b MXN/MWh · N zonas de carga», de mayor a menor PND promedio del día, con su valor. Tocar una zona abre su **detalle PND** arriba con ENSEMBLE debajo (igual que la lista del rail). «Quitar selección» o cambiar de día la borra. El mismo rango se elige sin gráfica en «Ver zonas de un rango» (teclado y lectores de pantalla).
    - **Intervalos exactos:** los límites no se adivinan del dibujo: `ensemble.intervalos` replica el algoritmo `bin` de Vega-Lite (máx. 30 intervalos, límites «redondos»), y la gráfica dibuja esos mismos intervalos ya calculados (`bin="binned"`). Cada intervalo es [a, b): un valor igual al límite superior cuenta en la barra siguiente, salvo en la última, que incluye su límite. Así, la altura de la barra es siempre el número de zonas de la lista.
    - **Mismo valor que ENSEMBLE:** el promedio de cada zona es el del ranking PND del día (`ensemble.ranking_pnd`, promedio simple de las horas con dato). Una zona sin dato ese día no entra en ninguna barra; si una zona tiene menos de 24 horas con dato se indica «· h h» y una nota lo explica. Solo zonas de carga, no NodosP; la distribución PML no cambia (sin drill-down por ahora).
  - **YTD (v0.8.2):** del 1 de enero del año del último día publicado del paquete de la modalidad elegida (PML o PND) hasta ese día, recortado al inicio del paquete. Los días sin dato siguen sin dato (no se rellenan) y la cobertura lo dice. Desde v0.9.1 abre en horaria, como los demás rangos (antes, v0.8.2 a v0.9.0, pasaba a diaria). Queda en la URL como `desde`/`hasta`, así que el enlace es reproducible.
  - **Comparar YoY (v0.8.9):** interruptor «YoY» en la barra, solo con el detalle de **PML histórico** o de **PND** abierto (no en spread, componentes ni ENSEMBLE: no hay control que no haga nada). Compara el rango elegido con **las mismas fechas un año antes** (2026-10-25 a 2026-11-24 contra 2025-10-25 a 2025-11-24; un 29 de febrero pasa al 28).
    - **Cifras:** el promedio de cada periodo es el mismo indicador «Promedio horario» de la vista (promedio simple de las horas con dato, con las mismas consultas) y la diferencia es su resta en MXN/MWh, con dos decimales. Rojo ▲ si subió y verde ▼ si bajó, como el ticker. Sin porcentajes (el precio base puede ser cero o negativo).
    - **Cobertura:** se muestran las dos coberturas. Si alguna no es del 100 %, la diferencia va sin color ni flecha («parcial»). Si un año antes no hay ninguna hora con dato (por ejemplo antes del inicio del paquete), se dice «Sin dato publicado» y no se compara.
    - **Curva:** en resolución diaria o mensual, la serie del año anterior se dibuja en gris punteado con sus fechas movidas un año, y el recuadro del cursor muestra «Un año antes». Se parte en los días sin dato como la línea actual; un 29 de febrero sin par no se dibuja; nada se interpola. En horaria solo se compara el promedio.
    - **Enlace:** `yoy=1` en la URL; sin el parámetro, apagado (no se avisa como faltante). Los indicadores, la tabla y el CSV del periodo elegido no cambian.
  - En pantallas de 1024 px o menos, el panel del solista (búsqueda y lista) va primero y el tablero debajo, ambos a todo el ancho; ubicación y fechas van plegadas.
- **Vista y filtros:** vista y nodo(s) están en el panel «Vista y filtros» del detalle, cerrado al abrir la aplicación; desde v0.8.2, fechas y resolución están en «Fechas» de la barra superior. Cerrarlo no cambia la selección.
- **Granularidad de la gráfica (v0.9.1):** las pastillas **Horaria · Diaria · Mensual** van sobre los rangos 1D · 7D · Mes · YTD y dependen de la longitud del rango (Desde a Hasta, incluidos los dos): con **1 día**, solo horaria; de **2 a 7 días**, horaria o diaria; con **8 días o más** (Mes, YTD o fechas a mano), las tres. Cada botón de rango abre en **horaria**. La horaria además exige que el rango quepa en la horaria publicada (PML: ventana `horario_desde` a `horario_hasta`; PND: hasta 366 días); si no cabe, va desactivada y la gráfica usa la primera permitida (diaria). Una pastilla desactivada explica el motivo al pasar el mouse. Si un enlace o unas fechas a mano piden una granularidad que el rango no admite (por ejemplo, 1 día en mensual), la gráfica pasa a la permitida y un aviso lo dice; así 1D siempre muestra sus 24 horas y no un solo punto. Solo cambia la gráfica y su CSV: los indicadores siguen siendo horarios y los cálculos de cada resolución no cambian.
- **Fechas por defecto:** «Desde» y «Hasta» inician en el día de la consulta (fecha de Ciudad de México), en resolución horaria. Si el paquete todavía no incluye ese día, se usa el último día disponible. Los límites seleccionables siguen saliendo de `metadata.json`.
- **Nodos (v0.6.0):** se buscan por clave NodoP o por nombre oficial (por ejemplo `06ESC` o «Escobedo» encuentran `06ESC-115 · Escobedo`). Cada opción se muestra como «Clave · Nombre», pero el valor elegido, la URL y los cálculos usan solo la clave: un nombre puede repetirse en varias claves. Antes del nodo, «Región de Control», «Estado» y «Zona de carga» (opcionales, «Todas» por defecto) acotan la lista; el estado es la entidad federativa (clave INEGI) donde CENACE ubica cada nodo y se aplica nodo por nodo, porque una zona de carga puede abarcar varios estados; no cambian el nodo elegido: si queda fuera del filtro se conserva con un aviso, y «Limpiar ubicación» vuelve a «Todas». En la vista 2, Nodo A y Nodo B tienen filtros independientes. La clasificación es la de la versión del catálogo indicada al pie y no se aplica hacia atrás; los 7 nodos de interconexión internacional aparecen como «sin clasificación verificada». Si el catálogo falta o no pasa su validación, la aplicación funciona solo con claves, como en v0.5.1. Región, estado y zona no se guardan en los enlaces.
- **Rangos rápidos (v0.4.1):** tres botones encima de «Desde/Hasta», compartidos por las tres vistas. Se anclan en `diario_hasta` de `metadata.json` (la última fecha de operación del paquete, igual para todos los nodos), no en el reloj. *Último día* = `diario_hasta`; *Últimos 7 días* = `diario_hasta − 6` a `diario_hasta`; *Mes en curso* = día 1 del mes de `diario_hasta` a `diario_hasta`. Si el inicio calculado queda antes de `diario_desde`, se recorta. Solo escriben las dos fechas: nodo, resolución, fórmulas, signos, agregaciones y faltantes no cambian. Un nodo con menos datos muestra el aviso de cobertura habitual.
- **Enlaces compartibles (v0.5.1):** la URL guarda la vista y los filtros, nunca los datos. Parámetros: `vista` (`historico`, `comparacion` o `componentes`), `nodo` (vistas 1 y 3) o `nodo_a` y `nodo_b` (vista 2), `desde` y `hasta` en formato `AAAA-MM-DD`, y `resolucion` (`horaria`, `diaria` o `mensual`). Las fechas siempre son absolutas, también después de un rango rápido: un enlace no cambia de periodo cuando llega el paquete nocturno. Ejemplo: `?vista=comparacion&nodo_a=01AAN-85&nodo_b=01AGU-230&desde=2026-10-30&hasta=2026-11-05&resolucion=diaria`. La URL solo se lee al abrir la aplicación; cada cambio de filtro la actualiza. Un enlace con una vista, nodo, fecha o resolución inválidos, con un parámetro repetido o con un periodo fuera del paquete no se corrige en silencio: se explica el problema y no se muestran cifras hasta que el usuario cambie un filtro o pulse «Continuar con la configuración mostrada». Si faltan parámetros, se usan los valores predeterminados y se avisa. El botón «Atrás» del navegador no deshace cambios de filtro: la aplicación vuelve a escribir en la URL la configuración que está a la vista, así que URL, filtros y resultados siempre coinciden (para salir de la aplicación puede hacer falta pulsarlo más de una vez).
- **Recuadro de la gráfica (v0.5.1):** al pasar el mouse (o tocar en móvil) se marca el punto más cercano y un recuadro pequeño muestra nodo (o «A − B» en el spread), fecha, hora en convención CENACE —la hora 1 es 00:00–01:00— solo en resolución horaria, el valor en MXN/MWh y, en diaria o mensual, las horas con dato. Solo muestra valores ya calculados.
- **Línea limpia (v0.8.8):** las líneas de precio (PML histórico, spread, componentes y PND) ya no llevan un punto en cada periodo: es una línea continua delgada con su degradado. Al acercar el cursor (o tocar) aparece el punto del periodo más cercano con su recuadro, como antes. Los **periodos parciales** (diaria y mensual) conservan un triángulo ▼ discreto y el aviso de abajo los enumera. **Faltantes:** la línea no une dos periodos separados por uno o más periodos sin dato (se parte en tramos); un periodo aislado entre faltantes se dibuja como punto para que no desaparezca. «Más fluida» es menos ruido visual: no se interpola, no se suaviza, no se agregan filas y los valores, el recuadro y el CSV son los mismos.
- **Espacio y cabecera (v0.8.8):** el contenido usa hasta 1640 px de ancho con márgenes laterales de 20–32 px (antes un máximo de 1240 px): en 1440 px la gráfica del detalle pasa de 798 a 1,094 px y en 1920 de 785 a 1,281 px. La barra fija tiene un poco más de aire (16 px más de alto en escritorio y 9 en móvil). Al elegir otro nodo o zona, la página solo se desplaza al detalle si no está a la vista (por ejemplo, al elegir desde ENSEMBLE más abajo); si el detalle ya se ve o se está leyendo su gráfica, no se mueve. Con «reducir movimiento», el desplazamiento es inmediato.
- **Eje de tiempo (v0.8.6):** en resolución **diaria** de hasta 62 días el eje marca días enteros y los rotula con la fecha («13 nov»): una marca por día hasta 10 días, cada 2 días hasta 20 y cada 7 hasta 62; antes, con pocos días, aparecían marcas intermedias de horas («12 PM», «06 AM») aunque cada punto es un día. En resolución **mensual** marca meses enteros («sep 2026»; cada 2, 3, 6 o 12 meses si hay más de 12), en vez de semanas. La serie horaria y los rangos diarios largos (más de 62 días, como YTD) conservan las marcas automáticas. Aplica a PML (las tres vistas) y a PND, a la línea y a sus barras de congestión. Solo cambia el rótulo del eje: valores, recuadro y CSV son los mismos.
- **Pestañas en móvil (v0.5.1):** en pantallas de 640 px o menos la barra de pestañas ocupa dos filas, para que las tres vistas estén siempre visibles sin desplazarse.
- **Mensajes de control:** fechas invertidas, resolución horaria fuera de la ventana y rangos sin datos muestran un aviso y ninguna cifra sustitutiva.

## Exportación CSV (v0.6.2)

Cada vista tiene «Descargar CSV» debajo de la gráfica. El archivo contiene **la serie que dibuja la gráfica**, en la resolución elegida, con los mismos valores que la aplicación: no se recalcula nada ni se añade detalle horario a una consulta diaria o mensual. Los indicadores de la ficha (mediana, percentiles, extremos) no se exportan porque se calculan sobre horas aunque la gráfica sea diaria o mensual.

- **Formato:** coma como separador, punto decimal, UTF-8 con BOM, una fila de encabezados en `snake_case`. Se abre directamente con `pandas.read_csv`. En Excel con configuración regional de México se abre con doble clic; con una región que usa coma decimal (por ejemplo España), Excel espera `;` y conviene usar Datos → Desde texto/CSV.
- **Columnas (mínimas, decisión del 2026-11-13):** tiempo = `fecha_operacion` + `hora_cenace` (1–24, hora final) en horaria, `fecha_operacion` en diaria, `mes` (AAAA-MM) en mensual. Después, vista 1 `nodo`, `pml`; vista 2 `nodo_a`, `nodo_b`, `pml_a`, `pml_b`, `spread_a_menos_b`; vista 3 `nodo`, `pml`, `energia`, `perdidas`, `congestion`, `descuadre_promedio` (con signo, 4 decimales). Todos los precios en MXN/MWh. En la vista 2, `pml_a` y `pml_b` se promedian sobre las **mismas horas comunes** que el spread (no son las curvas de la gráfica, que usan todas las horas de cada nodo); como el spread se redondea después de restar, `pml_a − pml_b` puede diferir de él en ±0.01.
- **Faltantes:** un periodo sin dato no tiene fila; una celda vacía significa sin valor, nunca cero. El archivo no incluye horas con dato ni periodos parciales: esa información está en la tabla de la aplicación.
- **Contexto:** no hay columnas de contexto. Vista, nodos, fechas de la consulta y resolución van en el nombre del archivo, y «Enlace de esta consulta», junto al botón, abre la misma vista. Fuente (CENACE SW-PML, MDA, SIN), unidad y fecha del paquete son las del pie de la aplicación.
- **Nombre:** `pml_<historico|spread|componentes>_<nodos>_<desde>[_<hasta>]_<resolucion>.csv` con las fechas de la consulta.
- Un texto que Excel leería como fórmula (empieza con `= + - @`) se guarda precedido de `'`; los números negativos no se tocan.

## Trazabilidad y límites

La pantalla obtiene los límites diarios y horarios de `metadata.json`. Muestra `generado_utc`, instante de generación del paquete, convertido a `America/Mexico_City`; no lo infiere del reloj del servidor ni de Git, ni lo confunde con la extracción original de CENACE. El [contrato de datos](data-contract.md) fija el esquema, las unidades, la convención horaria y el manifiesto con conteos y SHA-256. El lector comprueba ese manifiesto antes de mostrar cifras.

La aplicación está publicada en Streamlit Community Cloud (https://pml-explorer.streamlit.app/) y `pml-bot` actualiza el paquete cada noche. **No hay mediciones verificadas** de memoria, tiempo de arranque en frío ni tiempo de consulta en Community Cloud; tampoco de la duración de la publicación nocturna con el esquema v2. Los cambios de cálculo se aprueban y validan primero en `power-market-lab`.

## Precio de zona de carga · PND (v0.7.0, en revisión)

- **Qué es.** Es el precio de zona de carga que CENACE publica en SW-PEND (campo `pz`) para el MDA del SIN. Según el manual técnico de SW-PEND, es el PML de los nodos de la zona **ponderado** por su factor de distribución de carga, así que la app lo toma tal cual y no lo recalcula.
- **Promedios.** Igual que en PML: un promedio simple de las horas con dato. El diario y el mensual se calculan sobre las horas (quedan ponderados por las horas válidas), nunca promediando promedios. Energía, pérdidas y congestión se promedian sobre las mismas horas.
- **Cobertura.** Se calcula como horas con dato ÷ (24 × días del rango elegido), incluidos los días declarados sin dato.
  - Un día sin dato no tiene fila ni cifra y no cuenta como cero.
  - Si el rango elegido solo contiene días sin dato, la app responde «sin datos».
- **Resolución horaria.** Se permite hasta 366 días por rango. No hay ventana horaria: el paquete PND es horario desde 2023.
- **Chaly's Bebop PND (v0.9.2, Issue #46).** Pestaña junto al histórico de la zona, con las mismas reglas que la vista estacional PML (sección «Chaly's Bebop»): año Y contra la banda Mín–Máx de **Y−5 a Y−1** (nunca Y), Y−1 y Y−2 tenues, banda solo con 2 o más años con dato en la fecha, 29 de febrero fuera de esta vista, sin interpolar.
  - **Precio del día:** el PND promedio diario de la zona con la misma fórmula del histórico diario (`ROUND(AVG(pnd), 2)` sobre las horas con dato); coincide exactamente con `serie_pnd(..., "diaria")` en todas las fechas y zonas probadas. Nunca usa datos PML ni otras zonas.
  - **Historia real:** el paquete empieza el 2023-01-01, así que para Y = 2026 la banda usa a lo sumo 2023–2025 (3 de 5 años). El 2026-05-08 (sin dato en la consulta verificada) es un hueco y se dice.
  - **Colores:** Y en el azul PND; Y−1 y Y−2 en grises, banda gris neutra. Nada en ámbar PML.
  - **Lectura:** una consulta DuckDB de la zona sobre los archivos horarios de Y−5 a Y (unos 1,400 hoy), en caché por zona, año y huella del paquete. Sin paquete derivado ni cambios al pipeline.
  - **Enlace:** `?modalidad=pnd&zona=…&vista=estacional&anio=AAAA`. Un enlace PND sin `vista` sigue abriendo el histórico. **CSV:** `pnd_bebop_<zona>_<año>.csv`, con las mismas columnas que el PML (`pnd_<año>` en lugar de `pml_<año>`).
- **Pendiente (no forma parte de esta entrega).**
  - AC-03: registrado el 2026-11-20 contra los reportes oficiales de CENACE del 17 al 19 de noviembre de 2026: 29,088 valores, 0 diferencias ([validación](validation.md)).
  - AC-13: la medición local con el paquete real ya está hecha ([validación](validation.md), 2026-11-20). Falta medir en Community Cloud, después de un despliegue aprobado.

## Operación · Demanda (v0.10.0, Issue #32)

- **Fuente.** La [Gráfica de Demanda](https://www.cenace.gob.mx/graficademanda.aspx) pública del CENACE. El Mac mini del proyecto la lee cada hora (a los :10, de la 1 a las 23, y a las 23:55) y publica la última lectura en la rama `datos-demanda` de este repositorio: un CSV por día y `metadata.json` (contrato «demanda v1», en `power-market-lab/docs/demanda-contrato.md`). **La app nunca consulta al CENACE.** Solo lee esa publicación desde `raw.githubusercontent.com`, con caché de 10 minutos y 8 s de espera máxima por archivo.
- **Otra línea de tiempo.** Es la operación del **día en curso**, en MW. No es el MDA ni corresponde a las fechas del gráfico de precios, y el panel lo dice.
- **Qué muestra, por región** (SIN por omisión; SEN, BCA, BCS y las 7 regiones del SIN):
  - **Demanda real · hora N:** la última hora con demanda real de esa región. El pronóstico y el desvío (real − pronóstico, en MW y en % del pronóstico) son de **esa misma hora**. No se compara con la máxima pronosticada.
  - **Máxima real:** la mayor demanda real del día hasta esa lectura, con su hora. **Máxima pronosticada:** el mayor pronóstico de las 24 horas, con su hora. Las dos vienen de la misma gráfica, en la misma unidad.
  - **Horas con dato** y una gráfica de 24 horas con la demanda real (línea continua, solo horas con dato) y el pronóstico (punteado). No se interpola ni se proyecta.
- **Hora CENACE.** 1–24, hora final (la 1 es 00:00–01:00), Ciudad de México.
- **SEN = SIN + BCA + BCS.** El SIN no incluye Baja California ni Baja California Sur. El SEN se suma por hora **solo** cuando las tres tienen el valor; si falta una, esa hora queda sin SEN.
- **Faltantes.** Una celda vacía es «sin dato», nunca 0; un 0 publicado no es demanda real. «Pendiente» = la hora aún no termina.
- **Frescura.** El panel siempre dice la hora de la última lectura y cuánto hace. Si pasó más de 90 minutos, la marca como atrasada. Si el último día publicado no es hoy (en Ciudad de México), avisa que no hay lectura de hoy y muestra el día publicado con su fecha.
- **Si la publicación falla o no cumple el contrato** (columnas, estados, gerencias, horas, un 0 marcado como demanda), el panel no muestra ninguna cifra y deja el enlace a la gráfica oficial.
- **Revisiones.** El CENACE revisa la demanda real durante el día; cada lectura reemplaza a la anterior.
- **Aviso.** Información indicativa de la operación, no para liquidación.
- **Diseño.** En escritorio ancho (1360 px o más) es la tercera columna, de 228 a 264 px y fija al desplazarse; el centro conserva al menos 850 px (909 px a 1440). Por debajo de 1360 px no hay tres columnas: el panel queda al final, debajo del contenido, y el botón «Demanda» de la barra lleva a él. Nunca tapa la gráfica ni la selección.


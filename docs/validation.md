# Validaciones y aceptación pendiente

## 2026-11-27 · v0.9.1 Granularidad Horaria · Diaria · Mensual sobre los rangos (Issue #40, seguimiento)

Servidor local; paquete PML del 2023-01-01 al 2026-11-27; `main` = v0.9.0 (`56a3910`).

- Bug de Lalo: con diaria o mensual elegida (en YTD o YoY) y regreso a 1D, la gráfica quedaba en un solo punto. Ahora 1D solo admite horaria: YTD → Diaria o Mensual → 1D vuelve a 24 horas (AppTest, PML histórico, spread, componentes y PND; también con YoY encendido).
- Reglas por rango en `rangos.resoluciones_permitidas`: 1 día → horaria; 2–7 días → horaria o diaria; 8+ días → las tres; la horaria se desactiva fuera de la ventana horaria PML o por encima de 366 días en PND. Cada botón de rango abre en horaria. `tests/test_resolucion.py` reescrito (14 pruebas).
- Enlaces viejos: un enlace de 1 día con `resolucion=diaria` o `mensual` abre en horaria con un aviso; un enlace válido se respeta sin aviso.
- Regresión contra `main`: los 14 enlaces de referencia dan las mismas cifras, tablas, textos y URL (AppTest, procesos separados) y los 12 CSV son idénticos byte a byte (nombre y sha256).
- Navegador (1440 y 390 px): YTD en horaria tarda unos 3.8 s del clic al dibujo; Mensual → 1D deja `resolucion=horaria`; sin desplazamiento horizontal.
- Pruebas: 290 pasan, 4 omitidas (suite completa).
- Capturas antes/después en `docs/capturas/v0.9.1-granularidad/`.

## 2026-11-27 · v0.9.0 Chaly's Bebop 🎷, vista estacional PML (Issue #42)

Servidor local; paquete PML del 2023-01-01 al 2026-11-27; `main` = v0.8.10 (`63b7021`).

- **Historia disponible:** para Y = 2026, 2,400 nodos tienen 3 años de referencia (2023 a 2025), 23 tienen 2, 16 tienen 1 y los nodos nuevos de 2026 ninguno. No hay días parciales en el paquete.
- **01LCP-400, Y = 2026:**
  - Banda con 2023, 2024 y 2025, rotulada «3 de 5 años», sin 2021 ni 2022.
  - Y llega hasta el 27 de noviembre.
  - 83 días sobre la banda y 130 bajo ella.
  - Promedio 2026: 801.92 contra 788.75 de 2025 en las mismas 331 fechas.
  - El promedio diario de cada fecha es igual al de la serie diaria de la vista 1 (prueba).
- **Pruebas:** 287 passed, 4 skipped. Nuevas en `tests/test_estacional.py` (19):
  - mínimo y máximo exactos por mes-día con negativos y extremos;
  - Y fuera de su banda; Y−1 y Y−2;
  - 365 fechas sin 29 de febrero, sin desplazar el 1 de marzo;
  - n < 2 sin banda; día parcial; huecos sin unir;
  - promedio ponderado por horas en fechas comunes; CSV con años reales;
  - enlace con `anio` (ida y vuelta, inválido, opcional);
  - en la app: banda solo con años publicados, Y hasta el último día, cambio de año, nodo con un año de historia y año ausente que pasa al más reciente;
  - las otras vistas no cambian.
- **Tiempos:** una lectura de 47 archivos mensuales en 1.5 s la primera vez (0.04 s con el sistema de archivos ya leído) y 0.07 s de cálculo; después, en caché por nodo, año y paquete. Página completa en Chromium local: unos 5 s.
- **Navegador (Chromium 1440, 1920 y 390):** sin desplazamiento horizontal. El recuadro muestra Y, Y−1 y Y−2 con sus años, mínimo, máximo, número de años y día parcial.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` y 12/12 CSV idénticos (sha256).
- Capturas en `docs/capturas/v0.9.0-bebop/`.

## 2026-11-27 · v0.8.10 YTD ya no deja la gráfica atrapada en diaria (Issue #40)

Servidor local; paquete PML al 2026-11-27 y PND al 2026-11-19; `main` = v0.8.9 (`215a67c`).

- **Bug reproducido en `main`:** horaria → YTD (pasa a diaria) → 1D se quedaba en diaria (CSV «resolución diaria, 1 filas»). Con el arreglo, 1D vuelve a horaria: 24 puntos en la gráfica y CSV «resolución horaria, 24 filas».
- **Pruebas:** 268 passed, 4 skipped. Nuevas en `tests/test_resolucion.py` (11). Transiciones puras: horaria→YTD→1D/Mes/7D; YTD dos veces; diaria o mensual explícitas se respetan; ventana horaria PML fuera de rango (sigue en diaria con aviso); tope de 366 días en PND. En la app (AppTest): PML histórico, spread, componentes y PND vuelven a tener un punto por hora (no solo la radio); mensual elegida durante YTD se mantiene al pulsar 1D; un enlace nuevo con `resolucion=diaria` no se cambia. Las pruebas de la app fallan en `main` y pasan en la rama.
- **Navegador (Chromium 1440 y 390):** marca «automática (YTD)» en la línea de estado de la barra (escritorio) y nota en «Fechas» (también en móvil); desaparece al volver a horaria. Sin desplazamiento horizontal.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` y 12/12 CSV idénticos (sha256): un enlace abierto no cambia.
- Capturas antes/después en `docs/capturas/v0.8.10-resolucion/`.

## 2026-11-26 · v0.8.9 Comparar YoY (Issue #27, fase 2)

Servidor local; paquete PML al 2026-11-25 y PND al 2026-11-19; `main` = v0.8.8 (`6b9d1d4`).

- **Cifras (paquete real):** 01AAN-85, 2026-10-25 a 2026-11-24: 908.47 contra 757.03 un año antes, ▲ +151.44 MXN/MWh, cobertura 100 % y 100 %. PND Monterrey, mayo de 2026: 479.91 contra 772.46, −292.55 sin color (parcial: 96.8 % por el 08 de mayo sin dato). PND enero–marzo de 2023: «Sin dato publicado» (el paquete empieza en 2023). Cada promedio es igual a `estadisticas` / `estadisticas_pnd` del periodo (prueba).
- **Pruebas:** 257 passed, 4 skipped. Nuevas en `tests/test_yoy.py` (14): fechas un año antes y 29 de febrero, curva movida un año sin el 29, solo diaria/mensual, comparable/parcial/sin dato, negativos sin %, enlace `yoy=1` opcional (sin aviso de faltante, valor inválido avisado, solo en histórico y PND), en la app los mismos promedios que las estadísticas, horaria sin curva, PND sin dato un año antes, apagado sin cambios y sin interruptor en spread ni ENSEMBLE.
- **Navegador (Chromium 1440 y 390):** interruptor en la barra junto a YTD; franja YoY sobre la gráfica; curva gris punteada con «Un año antes» en el recuadro; el hueco del 08 de mayo de 2026 queda en blanco. Apagar el interruptor quita la franja y `yoy` de la URL. Sin desplazamiento horizontal.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` y 12/12 CSV idénticos (sin `yoy`, nada cambia).
- Capturas en `docs/capturas/v0.8.9-yoy/`.

## 2026-11-25 · v0.8.8 Pulido visual: línea limpia, cabecera con aire, canvas más ancho y sin salto (Issue #31, P0)

Servidor local; paquete PML al 2026-11-24 y PND al 2026-11-19; `main` = v0.8.7 (`bce1112`).

- **Puntos:** en diaria y mensual cada periodo tenía un círculo (`mark_point(size=50)`, hasta 400 periodos). Ahora solo quedan ▼ en parciales, un punto en periodos aislados entre faltantes y el punto del cursor (opacidad condicional) con el mismo recuadro. Comprobado en el spec real de PML histórico (horaria, diaria, mensual), spread, componentes y PND.
- **Faltantes:** antes la línea unía en silencio el 2026-05-07 con el 2026-05-09 en PND (el 08 no tiene archivo); ahora son dos tramos, sin fila inventada (14 filas, ninguna nula). Ningún valor se interpola ni se suaviza.
- **Canvas (Chromium):** contenido 1240 → 1640 px máx.; márgenes 32 px por lado en 1440 (antes 100 + relleno) y 140 en 1920. Gráfica del detalle: 798 → 1,094 px en 1440; 785 → 1,281 px en 1920; 786 → 901 px en 1024. Rail 187 px en 1440 y 200 en 1920 (sin cambio). Sin desplazamiento horizontal en 320, 390, 768, 1024, 1440 y 1920 px.
- **Cabecera:** alto de la barra 140 → 156 px en 1440 y 1920, 162 → 156 en 1024, 184 → 207 en 768 y 235 → 244 en 390; sigue fija y `--alto-barra` la mide (detalle a 17 px bajo la barra al elegir).
- **Sin salto (Chromium, posición del contenedor que se desplaza):** con el detalle abierto y la gráfica a la vista, elegir otra fila del rail en `main` subía la página de 693 a 126 px; ahora se queda en 709. Desde ENSEMBLE más abajo sigue habiendo un solo desplazamiento hasta el detalle (17 px bajo la barra en 1440, 12 en 390). En 390, elegir desde la lista al final lleva al detalle igual que antes. Con «reducir movimiento», sin animación.
- **Pruebas:** 243 passed, 4 skipped. Nuevas en `tests/test_pulido.py` (10): tramos (consecutivos, hueco, aislado, horaria, mensual con cambio de año, vacío), sin puntos permanentes en el spec de PML horaria/diaria/mensual, spread y componentes con recuadro y `detail` por tramo, hueco PND de 2026-05-08 en dos tramos sin filas nulas y canvas de 1640 px.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` (métricas, textos, avisos, tablas y URL) y 12/12 CSV idénticos (nombre y sha256).
- **Rendimiento local** (mediana de corridas 2–5; entre paréntesis `main`): carga con caché 1.52 s (1.51 s), tablero → detalle 0.96 s (0.95 s), cerrar detalle 0.24 s (0.24 s).
- Capturas antes/después en `docs/capturas/v0.8.8-pulido/`: PML mes diaria, 3 días horaria, 12 meses mensual, PND con el hueco del 08 de mayo y spread, en 1440 y 390 px; cabecera en 1920, 1440 y 390 px.
- **Pendiente (P1 de #31, no incluido):** microtransición (fundido corto del contenido nuevo). Se priorizó la transición sin salto, como pide la Issue.

## 2026-11-25 · v0.8.7 Drill-down del histograma PND (Issue #36)

Servidor local; paquete PML al 2026-11-24 y PND al 2026-11-19; `main` = v0.8.5 (`10abaab`); después se integró `main` con v0.8.6 (eje de fechas, #33).

- **Intervalos idénticos a Vega-Lite:** límites y conteos de `ensemble.intervalos` comparados con los que calcula Vega (vl-convert) en 190 días reales (180 PND y 10 PML) y en casos borde (valor en un límite, máximo en el borde, negativos, un solo valor, valores iguales, decimales): 190/190 iguales.
- **Conteo = lista (Chromium 1440, PND 2026-11-19):** 400–500 → 10 zonas, 700–800 → 24 y 1,900–2,000 → 1 (Riviera Maya): la altura de cada barra tocada es el número de zonas de su lista. «Ver zonas de un rango» con 500–600 → 13. Tocar Minas abre «PND · Minas» arriba con ENSEMBLE debajo y la selección del histograma se conserva; «Quitar selección» la borra. En iPhone 13 (390 px), lo mismo con el dedo.
- **Pruebas:** 228 passed, 4 skipped. Nuevas en `tests/test_histograma.py` (9): réplica de Vega en casos borde, límites [a, b) con el máximo en la última barra, zona sin dato fuera de las barras, orden de la lista, conteo = lista en 45 días del paquete real, elegir rango → título, zonas y apertura del detalle PND, quitar, cambiar de día borra la selección, horas parciales marcadas y sin PND no hay controles.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` (métricas, textos, avisos, tablas y URL) y 12/12 CSV idénticos (nombre y sha256). La distribución PML y los cálculos no cambian.
- **Sin desplazamiento horizontal** en 320, 390, 768, 1440 y 1920 px. Capturas en `docs/capturas/v0.8.7-histograma/` (selección, tras tocar una zona y cierre, en 1440 y 390 px).
- **Rendimiento local** (mediana; entre paréntesis `main`): carga con caché 1.53 s (1.45 s), tablero → detalle 1.04 s (1.00 s), cerrar detalle 0.23 s (0.22 s). Tocar una barra → lista ≈ 0.8 s (una recarga de Streamlit; sin consultas nuevas: usa el ranking del día ya en caché).

## 2026-11-24 · v0.8.6 Eje de fechas por resolución (seguimiento de la revisión de v0.8.2, Issue #19)

Servidor local; paquete PML al 2026-11-24 y PND al 2026-11-19; `main` = v0.8.3 (`95f8872`); actualizado sobre v0.8.5 (`10abaab`, ticker PND) sin cambios de eje.

- **Problema reproducido:** con serie diaria de pocos días el eje X rotulaba horas entre fechas: «12 PM | vie 13 | 12 PM | sáb 14 …» a 900 px (PND y PML 7D, spread y componentes; con 3 días también «06 AM/06 PM»), y en mensual de 3 meses marcaba semanas («ago 23 | ago 30 | sep 06 …»). Los domingos el formato automático decía «nov 15» junto a «vie 13».
- **Cambio:** `eje_tiempo()` en `app.py` fija las marcas en días enteros (diaria hasta 62 días: cada 1, 2 o 7 días, rótulo «13 nov») o meses enteros (mensual: «sep 2026», cada 1, 2, 3, 6 o 12 meses). Horaria y diaria de más de 62 días (YTD) no cambian. Línea y barras de congestión usan el mismo eje.
- **Regresión de escalas** (spec real de 10 escenas vía AppTest, renderizado a 900 y 330 px): PND 7D, PML 3D/7D/mes, spread y componentes 7D muestran solo fechas; mensual 3 meses y YTD mensual solo meses; 1D horaria y YTD diaria idénticas a `main`. Fuera de `axis.tickCount`/`axis.format`, los specs y sus datos son idénticos a `main` (solo cambia el nombre interno de la vista, que es un hash del spec).
- **Pruebas:** 212 passed, 4 skipped. Nuevas en `tests/test_ejes.py` (5): PND 7D sin «12 PM», PML 7D y spread, mes diario cada 2 días, mensual por meses, horaria y YTD sin cambio. Sin el cambio fallan 4 de 5.
- `data/`, `pnd/`, `scripts/`, rangos, consultas y `exportar.py` no cambian: cifras, avisos y CSV son los mismos. Capturas antes/después (1440 y 390 px) en `docs/capturas/v0.8.4-eje/`.

## 2026-11-24 · v0.8.5 Ticker PND en la barra fija (Issue #34)

Servidor local; paquete PML al 2026-11-24 y PND al 2026-11-19; `main` = v0.8.3 (`95f8872`). Rama desde `main`, independiente de #33 (eje de fechas).

- **Cifras (paquete real):** D = 2026-11-19 y D−1 = 2026-11-18, ambos con dato. VDM CENTRO 1,008.17 ▲ +239.08; MONTERREY 584.06 ▼ −7.46; GUADALAJARA 778.38 ▲ +97.39; QUERETARO 755.34 ▲ +98.01; PUEBLA 1,101.58 ▲ +315.26; MERIDA 1,188.26 ▲ +329.80; CHIHUAHUA 470.67 ▼ −29.50; HERMOSILLO 463.11 ▼ −15.31. Cada precio es igual al ranking PND de ENSEMBLE y al promedio de SOLO PND del día (prueba).
- **Pruebas:** 219 passed, 4 skipped. Nuevas en `tests/test_ticker.py` (12): sube/baja/igual, parcial (sin color), D−1 sin archivo sin buscar un día más antiguo, zona sin precio hoy o ayer, negativos sin %, paquete vacío, zonas de la selección presentes en el paquete, igualdad con ENSEMBLE/SOLO, cinta en ENSEMBLE con fechas y rótulo, «sin dato publicado» de D−1, tocar una zona abre el detalle PND con ENSEMBLE debajo, la cinta no cambia las fechas de un enlace y sin PND no hay cinta.
- **Regresión:** 14/14 enlaces con detalle idéntico a `main` (métricas, textos, avisos, tablas y URL) y 12/12 CSV idénticos (nombre y sha256).
- **Barra fija (Chromium 1440):** la cinta queda dentro de la barra (60–200 px al desplazarse sobre ENSEMBLE y sobre la gráfica); el rail y el detalle quedan a 217 px, 17 px bajo la barra. `--alto-barra` incluye la cinta. Alto de la barra: 140 px en 1440 (`main` 78 px), 235 px en 390 (`main` 146 px).
- **Movimiento:** pista de dos copias de 1,518 px (-50 % exacto, sin salto); 48 s por vuelta (≈ 32 px/s). Se detiene con el cursor. Tocar una zona no reinicia la animación (su tiempo sigue: 4.07 s → 7.05 s). Con teclado: 8 paradas (la copia visual tiene `aria-hidden` y `tabindex=-1`), la cinta se detiene y se desplaza a la ficha enfocada. Con «reducir movimiento»: sin animación y desplazable a mano. En ≤ 640 px: sin animación, se desliza con el dedo; tocar MERIDA en iPhone 13 abre «PND · Merida».
- **Sin desplazamiento horizontal** en 320, 390, 768, 1024, 1440 y 1920 px. Capturas en `docs/capturas/v0.8.5-ticker/`.
- **Rendimiento local** (mediana de corridas 2–5; entre paréntesis `main`): carga en frío 3.58 s (3.93 s), con caché 1.56 s (1.64 s), tablero → detalle 1.03 s (1.07 s), cerrar detalle 0.26 s (0.25 s). La consulta de la cinta tarda 0.26 s la primera vez y 0.03 s después; en la app queda en caché por paquete.

## 2026-11-23 · v0.8.3 Rail izquierdo compacto: Nodos y Zonas, más aire para Ensemble (Issue #29)

Servidor local; paquete PML al 2026-11-23 y PND al 2026-11-19; `main` = v0.8.2 (`8ee8b79`).

- **Pruebas:** 207 passed, 4 skipped. Nuevas en `RailIzquierdo`: un solo selector de modalidad y sin claves repetidas (ENSEMBLE, detalle PML y PND); «Zonas» en el rail cambia la cabecera a PND y la lista a zonas (sin filas PML); la cabecera mueve las pestañas del rail; con detalle PML, «Zonas» abre PND, la fila elegida muestra el mismo precio que su detalle y volver a «Nodos» conserva el nodo; quitar la pestaña activa no cambia la modalidad. Se adaptaron 2 pruebas (etiqueta de dos líneas de la lista; el primer expander de la página ya es «Ubicación» del rail).
- **Regresión:** en 14 enlaces (10 PML de las tres vistas y tres resoluciones, 3 PND, 1 ENSEMBLE) las métricas, avisos, URL, gráficas (huella de la especificación) y las 13 descargas CSV (huella de contenido y nombre) son idénticas a `main`. `data/`, `pnd/`, `scripts/`, rangos y módulos de cálculo no cambian.
- **Rail (Chromium):** 187 px en 1440 (antes 245), 200 px en 1920, mínimo 172 px; el área principal pasa de 771 a 875 px en 1440. El rail queda fijo bajo la barra (156 px) al desplazarse sobre la gráfica y sobre ENSEMBLE, sin superponerse. La búsqueda abre su lista a 350 px para leer clave y nombre completos.
- **Aire:** de la barra fija al contenido, 49 px en 1440 (antes 31) y 44–45 px en ≤ 1024 (antes ≈ 30). Elegir deja el detalle a 156 px, 17 px bajo la barra (139 px).
- **Sincronía PML ↔ PND:** rail → cabecera y cabecera → rail en ENSEMBLE y con detalle abierto; el chip dice «Cambiar zona» en PND.
- **Móvil/tablet:** en ≤ 1024 px el rail va después del tablero; «Cambiar nodo/zona» lo deja a 209 px, justo bajo la barra (206 px) en iPhone 13. Sin desplazamiento horizontal en 320, 390, 768, 1024, 1440 y 1920 px. Capturas en `docs/capturas/v0.8.3-rail/`.
- **Rendimiento local** (mediana; entre paréntesis `main`): carga en frío 3.02 s (3.41 s), con caché 1.34 s (1.38 s), lista → detalle 0.93 s (0.96 s), cerrar detalle 0.18 s (0.19 s).

## 2026-11-22 · v0.8.2 Terminal persistente: barra y lista fijas, solista compacto, YTD (Issue #27, fase P0)

Mismo entorno y método que las entradas anteriores (servidor local; paquete PML al 2026-11-21 y PND al 2026-11-19; `main` = v0.8.1, `79710cd`).

- **Pruebas:** 202 passed, 4 skipped. Nuevas: YTD en `tests/test_rangos.py` (1 ene del año del último dato; 1 de enero = un solo día; paquete que empieza a mitad de año) y `TerminalPersistente` (fechas, resolución, rangos y lista una sola vez en ENSEMBLE, detalle y spread; YTD deja `desde`=1 ene, `hasta`=último día, resolución diaria, y su enlace abre las mismas cifras). Se adaptaron 3 pruebas que usaban el selector `nodo` del panel derecho: ahora la lista tiene su propia búsqueda (`buscar_pml`).
- **Regresión (A7):** en los 14 enlaces, el contenido del detalle (métricas, textos, avisos, tablas y URL) es idéntico al de `main`. Las 12 descargas CSV tienen el mismo nombre y SHA-256. `data/`, `pnd/`, `scripts/` y los módulos de cálculo no cambian.
- **Fijos al desplazarse (A1, A2), Chromium:** en 1440 px la barra (71 px) y la lista quedan en su lugar arriba, a media página sobre la gráfica y sobre el tablero. Elegir en la lista con la página desplazada deja el detalle justo bajo la barra y conserva fechas y resolución en la URL. En iPhone 13 (390 px) la barra mide 137 px, «Cambiar nodo» lleva a la lista justo bajo la barra y elegir regresa al detalle; sin desplazamiento horizontal.
- **Responsive (A6):** sin desplazamiento horizontal en 320, 390, 768, 1024 y 1440 px. Capturas en `docs/capturas/v0.8.2-terminal/`.
- **Rendimiento local:** 5 sesiones nuevas por versión tras reiniciar los servidores; corridas 2–5 por mediana.
  - Carga del tablero: 3.57 s en frío y 1.42 s con caché (`main`: 4.07 s y 1.47 s).
  - Tablero → detalle: 1.05 s (`main`: 0.97 s).
  - Cerrar detalle: 0.25 s (`main`: 0.34 s).
- **YoY:** queda para una fase 2 (consulta y reglas de cobertura propias). No hay ningún control YoY en esta versión.
- **Pendiente:** revisión de ChatGPT, validación visual de Eduardo y prueba en Community Cloud, que requiere despliegue autorizado.

## 2026-11-22 · v0.8.1 Solista al frente, Ensemble siempre visible (Issue #25)

Mismo entorno y método que las entradas de v0.8.0 (servidor local, paquete público PML al 2026-11-21 y PND al 2026-11-19; `main` = v0.8.0, `1b0d37f`).

- **Pruebas:** 199 passed, 4 skipped. Nuevas (`SolistaAlFrente`, 6): sin selección solo mercado (A1); enlace con nodo muestra detalle y tablero sin claves repetidas (A2); cambiar de solista desde el ranking conserva fechas y resolución, resalta la fila y «Cerrar detalle» deja solo el tablero (A3); la búsqueda del tablero cambia solo el protagonista y vuelve a quedar vacía (A3); una zona desde el detalle PML abre el detalle PND sin indicadores PML y con las dos secciones separadas debajo (A4); un detalle sin datos conserva su aviso y el tablero (A6).
- **Regresión (A6):** en los 14 enlaces, el contenido del detalle en v0.8.1 (métricas, textos, avisos, tablas y URL) es idéntico al de SOLO en `main`. Las 12 descargas CSV tienen el mismo nombre y SHA-256. `data/`, `pnd/`, `scripts/` y los módulos de cálculo no cambian.
- **Responsive (A7):** sin desplazamiento horizontal en 320, 390, 768, 1024 y 1440 px para «antes de seleccionar», PML histórico, spread, componentes y PND al frente con el tablero debajo (25 capturas en `docs/capturas/v0.8.1-solista/`, más `foco-pml-*` y `foco-pnd-*`: elegir desde el tablero lleva la vista al detalle, que queda arriba de la pantalla, en 1440 y 390 px).
- **Rendimiento local (A8):** 5 sesiones nuevas por versión tras reiniciar el servidor; corridas 2–5 por mediana.
  - Carga del tablero: 3.64 s en frío y 1.43 s con caché (`main`: 3.72 s y 1.48 s).
  - Tablero → detalle: 1.07 s (`main`, ENSEMBLE → SOLO: 0.69 s). Es más lento porque ahora el tablero se vuelve a dibujar debajo del detalle; el tiempo en el servidor es casi igual (0.41 s contra 0.38 s) y la diferencia está en el navegador.
  - Cerrar detalle: 0.30 s (`main`, volver al mercado: 0.48 s).
- **Pendiente:** validación visual de Eduardo y prueba en Community Cloud, que requiere despliegue autorizado.

## 2026-11-20 · v0.8.0, segunda iteración visual (Graphite híbrido, watchlist con tensión, congestión en SOLO)

Atiende la dirección de producto de los comentarios en #19 y #24. Mismo entorno y método que la entrada siguiente.

- **Pruebas:** 193 passed, 4 skipped. Nuevas: tensión inicial 400 kV contra la columna oficial `tension_kv` del catálogo (las 53 opciones son de 400 kV, el nodo elegido se conserva con aviso y no se pierde al cambiar el filtro) y una fila de la watchlist que abre SOLO con el mismo precio.
- **Regresión:** los 14 enlaces dan en `main` y en esta rama las mismas métricas, textos, avisos, tablas y URL. Las 12 descargas CSV tienen el mismo nombre y SHA-256. `data/`, `pnd/`, `scripts/` y los módulos de cálculo no cambian. `.streamlit/config.toml` sí cambia, solo en la paleta del tema.
- **Responsive:** sin desplazamiento horizontal en 320, 390, 768, 1024 y 1440 px. Hay 25 capturas en `docs/capturas/v0.8.0-graphite-2/`; las de la iteración anterior quedan en `docs/capturas/v0.8.0-graphite/` como «antes».
- **Rendimiento local:** se midieron 5 sesiones nuevas tras reiniciar el servidor; las corridas 2–5 se resumen con su mediana.
  - Carga de ENSEMBLE: 3.81 s en frío y 1.44 s con caché.
  - ENSEMBLE → SOLO: 0.73 s.
  - SOLO → ENSEMBLE: 0.51 s.

## 2026-11-20 · v0.8.0 Graphite Trading | Ensemble & Solo: regresión, pruebas y rendimiento (local)

Rama `graphite-ensemble-solo`, PR en borrador. Plan y criterios AC-G01 a AC-G14 en la Issue #19. Entorno: contenedor Linux, Python 3.13, Streamlit 1.66.1, DuckDB 1.5.6, pyarrow 24.0.0, pandas 3.0.6, con los paquetes `data/` y `pnd/` de `main` (`7bf7621`).

- **Pruebas:** 191 passed, 4 skipped (`main`: 166 passed, 4 skipped). Nuevas: `tests/test_escena.py` (8) y `tests/test_ensemble.py` (17). Las pruebas de vistas que abrían la app sin enlace ahora fijan la escena SOLO antes de correr (sin enlace, la app abre ENSEMBLE); sus aserciones no cambiaron, salvo la versión del pie (v0.8.0 beta).
- **Mismo cálculo que SOLO (AC-G06):** para el día de referencia, el promedio, horas, mínimo, máximo y horas negativas del ranking coinciden exactamente con `estadisticas()` (dentro y fuera de la ventana horaria) y `estadisticas_pnd()` en una muestra de 19 nodos por día y 19 zonas.
- **Regresión de enlaces (AC-G02, AC-G03):** 14 enlaces (4 de la vista 1, 3 de la vista 2, 2 de la vista 3, 3 de PND, uno con nodo inexistente y uno incompleto) dan en `main` y en esta rama las mismas métricas, subtítulos, textos, avisos, tablas y URL (AppTest). Solo se excluyen lo que esta versión agrega a propósito: el encabezado del solista y el pie con la versión.
- **CSV (AC-G09):** 12 descargas reales (Chromium) de las 4 vistas: nombre de archivo y SHA-256 idénticos a `main`.
- **Archivos sin cambios (AC-G10):** `git diff main` vacío en `data/`, `pnd/`, `scripts/`, `exportar.py`, `vista1.py`, `vista2.py`, `vista3.py`, `pnd.py`, `enlaces.py`.
- **Responsive (AC-G11):** sin desplazamiento horizontal en 320, 390, 768, 1024 y 1440 px para ENSEMBLE, SOLO vistas 1–3 y SOLO PND (25 capturas en `docs/capturas/v0.8.0-graphite/`).
- **Rendimiento (AC-G12), navegador real, 5 sesiones nuevas tras reiniciar el servidor:**

| Medición | Corrida 1 (servidor en frío) | Corridas 2–5 (mediana) |
| --- | ---: | ---: |
| Carga de ENSEMBLE hasta terminar de dibujar | 3.59 s | 1.45 s |
| ENSEMBLE → SOLO (tocar un ranking) | 0.98 s | 0.68 s |
| SOLO → ENSEMBLE («Volver al mercado») | 0.54 s | 0.46 s |
| Referencia `main` v0.7.0, carga inicial (mismo método) | 4.36 s | 1.79 s |

La meta de 3 s en frío no se cumple por 0.6 s; ese tiempo es sobre todo la carga del paquete que `main` también hace (4.36 s con el mismo método). Las transiciones no tienen animaciones: son un solo rerun con consultas en caché. Son tiempos **locales**, no de Community Cloud.

## 2026-11-20 · PND v0.7.0: AC-03 contra reportes oficiales de CENACE

Verificación independiente de Eduardo, 2026-11-20 (comparación verificada a las 12:27:24Z), sobre el paquete de `9cbd5b3`. Los Parquet son los mismos en el paquete actual: después solo cambió `metadata.json`, en `a2d279b`. La evidencia completa está en el [comentario del PR #23](https://github.com/edarji/pml-explorer-web/pull/23#issuecomment-7039719618).

- **Reporte oficial:** ZIP descargado de [PreEnerServConMDA](https://www.cenace.gob.mx/Paginas/SIM/Reportes/PreEnerServConMDA.aspx) con *Precios en Nodos Distribuidos MDA, Diaria, SIN, 17/11/2026–19/11/2026*. Trae 3 CSV de 2424 filas cada uno (101 zonas × 24 h). SHA-256:
  - 17 nov: `f3d61c376c6dd9cc3b1c55158aab2b52651884672942be90fb697ec7fda78127`
  - 18 nov: `ca581a15bd02e52d23cdcceaa737424234a9c350e74f321f7e75bb3354afd8f7`
  - 19 nov: `f90c6fd4cfac847f29e5c5c8fa15396b5214400c88b0b435b9d3e8e51791daba`
- **Servicio:** `SWPEND/SIM/SIN/MDA/2026/11/17/2026/11/19/JSON` respondió HTTP 200, 1,455,466 bytes, SHA-256 `bbb683956164a65775589a30b06db4e9de5201d30e16ce8cb4eb11111889ce92`.
- **Comparación exacta (Decimal)** por fecha, zona y hora de `pz`, `pz_ene`, `pz_per` y `pz_cng` contra los Parquet del paquete: 7272 filas y 29,088 valores, **0 diferencias**.
- **App:** las estadísticas y el CSV de MONTERREY, VDM CENTRO y CENTRO ORIENTE del 17 al 19 de noviembre (216 h) coinciden con el reporte. Promedios horarios (17/18/19):
  - MONTERREY 603.3220833 / 591.5229167 / 584.05875
  - VDM CENTRO 1019.26875 / 769.09 / 1008.165
  - CENTRO ORIENTE 766.2854167 / 682.8266667 / 796.87
- **Día sin dato:** en MONTERREY, mayo de 2026 da 479.91 con 720 de 744 h (96.8 %). El 2026-05-08 no tiene filas.
- **Medición local de Eduardo** (macOS, Python 3.14.8, DuckDB 1.5.6; no es Community Cloud ni caché del sistema vacía):
  - inspección 0.1392 s;
  - diaria, mensual y estadísticas de 3 zonas para 2023–2025: 0.1816–0.2188 s por operación;
  - histórico completo: 0.2426–0.2828 s;
  - RSS máximo acumulado del proceso: 250,413,056 bytes (~239 MiB).

Alcance: AC-03 queda registrado para el 17–19 nov de 2026 con esta evidencia. Los demás días los respalda el contrato (descuadre ≤ 0.02, 24 h, zonas = referencia), no una comparación uno a uno.

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

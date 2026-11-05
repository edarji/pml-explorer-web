"""Entrada pública de PML Explorer."""
import base64
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from rangos import RANGOS_RAPIDOS, rango_rapido
from vista2 import diferencial, resumen
from vista3 import componentes, resumen_componentes
from vista1 import (DATA_DIR, RESOLUCIONES, UMBRAL_DESCUADRE, DatosNoDisponibles, actualizado_cdmx, catalogo,
                    cobertura_horaria, estadisticas, huella_paquete,
                    inspeccionar_paquete, marcar_periodos, observado, serie)

REPO = "https://github.com/edarji/pml-explorer-web/blob/main"
COBERTURA_ESCASA = 80  # % de horas con dato bajo el cual se advierte explícitamente
SITIO_MERCADOS = "https://edarji.net/mercados/"
ZONA_MERCADO = ZoneInfo("America/Mexico_City")
AYUDA_NODO = ("Escribe la clave NodoP o parte de ella, por ejemplo 06ESC. El paquete público "
              "solo contiene claves: no incluye nombres de localidad ni regiones.")
SIN_RESULTADOS = ("¿Sin resultados? Busca por clave, no por nombre (por ejemplo 06ESC, no Escobedo). "
                  "Pulsa Esc o borra el texto para conservar el nodo elegido.")
# H03: los st.caption de Streamlit 1.66 usan opacidad 0.6 (≈3.70:1 sobre blanco). Con 0.8 el texto
# queda en ≈6.67:1 sobre blanco y ≈6.19:1 sobre gris claro, por debajo del texto principal (12.53:1).
ESTILOS = """<style>
[data-testid='stCaptionContainer']{opacity:0.8}
.block-container{max-width:1240px}
/* v0.5 · Pestañas: el radio de vistas se dibuja como barra de pestañas subrayada. */
.st-key-pestanas div[role=radiogroup]{gap:0;border-bottom:1px solid #E4DDD0;flex-wrap:nowrap;overflow-x:auto}
.st-key-pestanas div[role=radiogroup] label{padding:.5rem 1.1rem .55rem;margin:0;border-bottom:3px solid transparent;
  white-space:nowrap}
.st-key-pestanas div[role=radiogroup] label > div > div:first-child{display:none}
.st-key-pestanas div[role=radiogroup] label p{font-size:1.02rem}
.st-key-pestanas label[data-selected=true]{box-shadow:inset 0 -3px 0 #1B1B1B}
.st-key-pestanas label[data-selected=true] p{font-weight:600}
/* Botones de rango: pastillas pequeñas; la activa en gris oscuro. */
.st-key-rangos button{min-height:2rem;padding:.1rem .85rem;border:1px solid #D9D2C5;background:#FFFFFF}
.st-key-rangos button p{font-size:.85rem}
.st-key-rangos button[kind=primary]{background:#3A3A3A;border-color:#3A3A3A;color:#fff}
/* Encabezado tipo ficha de mercado. */
.precio{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35rem .8rem;margin:-.4rem 0 .2rem}
.precio .valor{font-size:2.6rem;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.precio .unidad{font-size:1rem;font-weight:600;color:#555}
.precio .cambio{font-size:1.25rem;font-weight:600}
.precio .fecha{font-size:.85rem;color:#6B6B6B}
.sube{color:#2E7D32}.baja{color:#C62828}.igual{color:#6B6B6B}
.linea-meta{font-size:.85rem;color:#4A4A4A;margin-bottom:.4rem}
/* Tarjeta de gráfica + ficha de indicadores. */
.st-key-tarjeta{background:#F5F1EA;border-radius:.8rem;padding:1rem 1.1rem .6rem}
.st-key-ficha [data-testid=stMetric]{padding:0}
.st-key-ficha [data-testid=stMetricLabel]{min-height:0;margin:0}
.st-key-ficha [data-testid=stMetric] > div{display:flex;justify-content:space-between;align-items:baseline;gap:.5rem}
.st-key-ficha [data-testid=stMetricLabel] p{font-size:.88rem}
.st-key-ficha [data-testid=stMetricValue], .st-key-ficha [data-testid=stMetricValue] p{font-size:.92rem;font-weight:500;line-height:1.6;height:auto;min-height:0}
.st-key-ficha [data-testid=stVerticalBlock]{gap:.1rem}
.fila{display:flex;justify-content:space-between;font-size:.88rem;line-height:1.75}
.rango{margin:.1rem 0 .7rem}.rango .et{font-size:.88rem}
.rango .barra{position:relative;height:3px;background:#CFC8BB;margin:.55rem 0 .3rem;border-radius:2px}
.rango .barra span{position:absolute;top:-4px;width:11px;height:11px;border-radius:50%;background:#555;
  transform:translateX(-50%)}
.rango .ext{display:flex;justify-content:space-between;font-size:.75rem;color:#555}
</style>"""
ASSETS = Path(__file__).resolve().parent / "assets"
NARANJA = "#E8772E"
# Fechas de los ejes en español (Vega-Lite usa inglés por defecto: «Thu 29», «November»).
LOCALE_ES = {"time": {
    "dateTime": "%A, %e de %B de %Y, %X", "date": "%d/%m/%Y", "time": "%H:%M:%S", "periods": ["AM", "PM"],
    "days": ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
    "shortDays": ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
    "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre"],
    "shortMonths": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]},
    "number": {"decimal": ".", "thousands": ",", "grouping": [3], "currency": ["$", ""]}}
ETIQUETAS_RANGO = {"Último día": "1D", "Últimos 7 días": "7D", "Mes en curso": "Mes"}


def logo():
    """Logo animado del saxofón (mismo diseño que la app del laboratorio); al pasar el mouse crece y brilla."""
    svg = base64.b64encode((ASSETS / "logo_animado.svg").read_bytes()).decode()
    st.markdown(
        f'<img class="logo-pml" alt="PML Explorer: logo del saxofón" src="data:image/svg+xml;base64,{svg}">'
        "<style>.logo-pml {width: 84px; max-width: 22vw; display: block; transition: transform .3s, filter .3s;}"
        ".logo-pml:hover {transform: scale(1.12) rotate(-3deg); filter: drop-shadow(0 0 10px #FFB000);}"
        "@media (prefers-reduced-motion: reduce) {.logo-pml, .logo-pml:hover {transition: none; transform: none;}}</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_paquete(data_dir, version):
    return inspeccionar_paquete(data_dir), catalogo(data_dir), observado(data_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas(nodo, inicio, fin, data_dir, version):
    return estadisticas(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie(nodo, inicio, fin, resolucion, data_dir, version):
    return serie(nodo, inicio, fin, resolucion, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_resumen(nodo_a, nodo_b, inicio, fin, data_dir, version):
    return resumen(nodo_a, nodo_b, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_diferencial(nodo_a, nodo_b, inicio, fin, resolucion, data_dir, version):
    return diferencial(nodo_a, nodo_b, inicio, fin, resolucion, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_resumen_componentes(nodo, inicio, fin, data_dir, version):
    return resumen_componentes(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_componentes(nodo, inicio, fin, resolucion, data_dir, version):
    return componentes(nodo, inicio, fin, resolucion, data_dir)


def mxn(valor):
    """Precio con la misma precisión en indicadores y tablas: dos decimales."""
    return "—" if pd.isna(valor) else f"{valor:,.2f}"


def grafica(df, y, titulo_y, resolucion, color=None):
    """Línea con puntos; los periodos parciales se marcan con ▼ y se explican en el tooltip."""
    base = alt.Chart(df).encode(
        x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor="#CFC8BB")),
        y=alt.Y(f"{y}:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor="#E4DDD0", tickCount=5)),
        tooltip=[alt.Tooltip("etiqueta:N", title="Periodo"),
                 alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.2f"),
                 alt.Tooltip("horas:Q", title="Horas con dato", format=",")],
    )
    linea = base.mark_line(color=color or NARANJA, strokeWidth=1.8)
    capas = [linea]
    # Con muchos periodos solo se dibujan los puntos parciales, para no saturar la gráfica.
    puntos = base if len(df) <= 400 else base.transform_filter("datum.parcial")
    if resolucion != "horaria":
        capas.append(puntos.mark_point(size=50, filled=True, color=color or NARANJA).encode(
            shape=alt.Shape("parcial:N", title="Periodo",
                            scale=alt.Scale(domain=[False, True], range=["circle", "triangle-down"]),
                            legend=alt.Legend(labelExpr="datum.value ? 'parcial' : 'completo'")),
        ))
    st.altair_chart(alt.layer(*capas).properties(background="transparent")
                    .configure_view(stroke=None).configure(locale=LOCALE_ES),
                    width="stretch")


def avisos_parciales(df, resolucion):
    parciales = df[df["parcial"]]
    if resolucion == "horaria" or parciales.empty:
        return
    lista = "; ".join(parciales["etiqueta"].head(6))
    extra = f" y {len(parciales) - 6} más" if len(parciales) > 6 else ""
    st.caption(f"▼ Periodos parciales (el promedio usa solo las horas con dato del rango elegido): {lista}{extra}.")


def metodologia():
    with st.expander("Metodología y definiciones"):
        st.markdown(f"""
- **Fuente:** CENACE, servicio SW-PML, Mercado del Día en Adelanto (MDA), Sistema Interconectado Nacional (SIN). Unidades: MXN/MWh.
- **Promedio:** promedio **simple** de las horas con dato (cada hora pesa igual; no se pondera por demanda ni volumen). Diario y mensual se calculan con la suma y el número de horas, nunca promediando promedios.
- **Indicadores (Promedio, Mediana, Mínimo, Máximo, Horas con PML < 0):** se calculan siempre sobre **las horas** del rango elegido, aunque la gráfica muestre promedios diarios o mensuales.
- **Convención horaria:** hora 1–24 de CENACE, hora final: la hora 1 es 00:00–01:00 del día de operación. En la gráfica horaria cada punto se dibuja al inicio de su hora. No hay conversión a UTC.
- **Faltantes:** una hora sin dato **no es un precio cero**; no se imputa ni se arrastra. La cobertura es horas con dato ÷ (24 × días del rango).
- **Periodos parciales:** un mes o día que el rango no cubre completo, o que tiene horas sin dato, se marca con ▼ y su promedio usa solo las horas disponibles.
- **Spread (vista 2):** PML_A − PML_B hora por hora, solo en las horas en que los dos nodos tienen dato; después se promedia por día o mes. Fuera de la ventana horaria se usan los días en que ambos nodos tienen las 24 horas (ahí todas las horas coinciden y el cálculo es exacto); un día incompleto en algún nodo se excluye.
- **Componentes (vista 3):** PML = energía + pérdidas + congestión, con sus signos (pérdidas y congestión pueden ser negativas). Todos se promedian sobre las mismas horas que el PML. El **descuadre** es |PML − (energía + pérdidas + congestión)| por hora y viene del redondeo de CENACE; se avisa cuando supera {UMBRAL_DESCUADRE} MXN/MWh.
- **Histórico horario y diario:** mediana y percentiles requieren que todo el rango esté dentro de la ventana horaria (último año). Fuera de ella se usan acumuladores diarios exactos para promedio, extremos, desviación y horas negativas.
- **Rangos rápidos:** se anclan en la última fecha de operación del paquete (igual para todos los nodos). *Último día* = ese día; *Últimos 7 días* = ese día y los 6 anteriores; *Mes en curso* = del día 1 de ese mes hasta ese día, por eso el mes aparece como parcial (▼). Solo cambian «Desde» y «Hasta».
- **Fechas:** “Desde/Hasta” son **fechas de operación** del mercado. “Actualización” es cuándo se generó el paquete público, no cuándo CENACE publicó cada día.
- **Precisión:** precios con dos decimales; la desviación estándar es muestral.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def dia_de_consulta(limites):
    """Fecha de operación por defecto: hoy en Ciudad de México, acotada al rango del paquete.

    Solo elige el valor inicial de los selectores; los límites siguen saliendo de metadata.
    """
    hoy = datetime.now(ZONA_MERCADO).date()
    return min(max(hoy, limites["desde"]), limites["hasta"])


def aplicar_rango(opcion, limites):
    """Callback de los botones: Streamlit lo ejecuta antes de volver a dibujar la página."""
    st.session_state["desde"], st.session_state["hasta"] = rango_rapido(opcion, limites)


def controles_rango(limites):
    """Fechas y resolución, compartidas entre vistas. Por defecto, el día de la consulta en resolución horaria."""
    dia = dia_de_consulta(limites)
    # v0.4.1: rangos rápidos. El botón solo escribe «Desde» y «Hasta» en session_state antes del siguiente
    # dibujo; nodo, resolución y cálculos no cambian. El ancla es la última fecha del paquete.
    # El valor inicial va en session_state y no como argumento del widget: así Streamlit no avisa de
    # «valor por defecto y Session State a la vez» cuando un botón de rango rápido cambia las fechas.
    st.session_state.setdefault("desde", dia)
    st.session_state.setdefault("hasta", dia)
    c1, c2, c3 = st.columns(3)
    inicio = c1.date_input("Desde", min_value=limites["desde"], max_value=limites["hasta"], key="desde")
    fin = c2.date_input("Hasta", min_value=limites["desde"], max_value=limites["hasta"], key="hasta")
    resolucion = c3.radio("Resolución de la gráfica", list(RESOLUCIONES), index=0, key="resolucion", horizontal=True,
                          help="Solo cambia la gráfica. Los indicadores siempre son horarios.")
    return inicio, fin, resolucion


def botones_rango(limites):
    """v0.5: rangos rápidos como pastillas (1D, 7D, Mes) sobre el contenido; la activa va resaltada."""
    actual = (st.session_state.get("desde"), st.session_state.get("hasta"))
    with st.container(key="rangos", horizontal=True, horizontal_alignment="right", gap="small"):
        for opcion in RANGOS_RAPIDOS:
            st.button(ETIQUETAS_RANGO[opcion], key=f"rango_{opcion}", on_click=aplicar_rango, args=(opcion, limites),
                      type="primary" if rango_rapido(opcion, limites) == actual else "secondary",
                      help=f"{opcion} (ancla: último día del paquete, {limites['hasta']})")


def flecha(cambio):
    return "sube" if cambio > 0 else "baja" if cambio < 0 else "igual"


def barra_rango(etiqueta, minimo, maximo, marca):
    """Barra mínimo–máximo con un punto en `marca` (como el «52 Week Range» de una ficha bursátil)."""
    pos = 50 if maximo == minimo else max(0, min(100, (marca - minimo) / (maximo - minimo) * 100))
    return (f'<div class="rango"><div class="et">{etiqueta}</div><div class="barra"><span style="left:{pos:.1f}%">'
            f'</span></div><div class="ext"><span>{mxn(minimo)}</span><span>{mxn(maximo)}</span></div></div>')


def cabecera(valor_del_dia, dia, limites, texto, porcentaje=True):
    """v0.5 · Número grande del último día con dato y su cambio contra el día anterior.

    `valor_del_dia(fecha)` devuelve el valor de ese día o None si no hay horas con dato. El día anterior puede
    quedar fuera del rango elegido; si no hay dato ese día, no se muestra cambio (nunca se compara contra cero).
    `porcentaje=False` para el spread: un % sobre una base cercana a cero no significa nada.
    """
    valor = valor_del_dia(dia)
    previo = valor_del_dia(dia - timedelta(days=1)) if dia - timedelta(days=1) >= limites["desde"] else None
    cambio_html = ""
    if valor is not None and previo is not None:
        cambio = valor - previo
        pct = f" ({cambio / abs(previo):+.2%})" if porcentaje and previo else ""
        cambio_html = f'<span class="cambio {flecha(cambio)}">{cambio:+,.2f}{pct}</span>'
    st.markdown(
        f'<div class="precio"><span class="valor">{mxn(valor)}</span><span class="unidad">MXN/MWh</span>'
        f'{cambio_html}<span class="fecha">{texto} del {dia} vs. día anterior</span></div>',
        unsafe_allow_html=True)
    return valor


def grafica_series(df, columnas, colores):
    """Varias curvas con el mismo estilo que `grafica` (eje derecho, sin rejilla vertical, fechas en español)."""
    largo = df.melt(id_vars=["periodo"], value_vars=columnas, var_name="serie", value_name="valor").dropna()
    st.altair_chart(alt.Chart(largo).mark_line(strokeWidth=1.6).encode(
        x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor="#CFC8BB")),
        y=alt.Y("valor:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor="#E4DDD0", tickCount=5)),
        color=alt.Color("serie:N", title=None, sort=columnas, scale=alt.Scale(domain=columnas, range=colores),
                        legend=alt.Legend(orient="top-left", direction="horizontal")),
        tooltip=[alt.Tooltip("periodo:T", title="Periodo"), alt.Tooltip("serie:N", title="Serie"),
                 alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f")],
    ).properties(background="transparent").configure_view(stroke=None).configure(locale=LOCALE_ES), width="stretch")


def fila(etiqueta, valor):
    return f'<div class="fila"><span>{etiqueta}</span><span>{valor}</span></div>'


def selector_nodo(nodos, etiqueta, key, defecto):
    """Selector con búsqueda por clave NodoP (H05). No hay nombres oficiales en el paquete público."""
    return st.selectbox(etiqueta, nodos, index=nodos.index(defecto) if defecto in nodos else 0, key=key,
                        placeholder="Clave, p. ej. 06ESC", help=AYUDA_NODO)


def vista_1(limites, nodos, fechas_nodo, version, panel):
    """Vista 1: PML histórico de un nodo."""
    with panel:
        st.caption(SIN_RESULTADOS)  # encima: la lista «No results» de Streamlit taparía un texto inferior
        nodo = selector_nodo(nodos, "Buscar por clave de nodo", "nodo", "01AAN-85")
        inicio, fin, resolucion = controles_rango(limites)
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")

    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()

    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        e = consultar_estadisticas(nodo, inicio, fin, str(DATA_DIR), version).iloc[0]
        df = consultar_serie(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if e["horas_con_dato"] == 0:
        detalle = (f" {nodo} tiene datos del {primera} al {ultima}; ninguna de esas fechas cae en el rango elegido."
                   if primera else "")
        st.warning(f"Sin observaciones para {nodo} entre {inicio} y {fin}.{detalle} "
                   "No se muestra ninguna cifra: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo}: {inicio} a {fin}")
    con_dato, del_rango = int(e["horas_con_dato"]), int(e["horas_del_rango"])
    desde_obs, hasta_obs = e["primera_fecha"].date(), e["ultima_fecha"].date()

    # v0.5 · Cabecera tipo ficha: el «precio» es el PML promedio del último día con dato del rango.
    def pml_del_dia(d):
        x = consultar_estadisticas(nodo, d, d, str(DATA_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["promedio"]
    cabecera(pml_del_dia, hasta_obs, limites, "PML promedio")
    dia = consultar_estadisticas(nodo, hasta_obs, hasta_obs, str(DATA_DIR), version).iloc[0]
    st.markdown(f"MDA · SIN · CENACE | **Cobertura:** {e['cobertura_pct']}% ({con_dato:,} de {del_rango:,} horas "
                f"con dato) | **Rango con observaciones:** {desde_obs} a {hasta_obs}")
    if e["cobertura_pct"] < COBERTURA_ESCASA:
        motivo = (f" El nodo tiene datos desde {primera}." if primera and primera > inicio else "")
        st.warning(f"Cobertura escasa: los indicadores describen solo {con_dato:,} horas, entre {desde_obs} y "
                   f"{hasta_obs}, no todo el rango elegido.{motivo} Las horas sin dato no se tratan como cero.")
    elif e["cobertura_pct"] < 100:
        st.caption("Hay horas sin dato en el rango; los indicadores usan solo las horas con dato.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    titulo = {"horaria": "PML horario", "diaria": "PML promedio diario",
              "mensual": "PML promedio mensual"}[resolucion]
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown(f"**{titulo} (MXN/MWh)**")
            grafica(df, "pml_promedio", "MXN/MWh", resolucion)
        with der, st.container(key="ficha"):
            st.markdown(barra_rango("Rango horario del periodo", e["minimo"], e["maximo"], e["promedio"])
                        + (barra_rango(f"Rango del {hasta_obs}", dia["minimo"], dia["maximo"], dia["promedio"])
                           if dia["horas_con_dato"] else ""), unsafe_allow_html=True)
            st.metric("Promedio horario", mxn(e["promedio"]), help="Promedio simple de las horas con dato.")
            st.metric("Mediana horaria", mxn(e["mediana"]) if horario_completo else "—",
                      help=None if horario_completo else
                      f"Requiere datos horarios: disponible solo si todo el rango está entre "
                      f"{limites['horario_desde']} y {limites['horario_hasta']}.")
            st.metric("Mínimo horario", mxn(e["minimo"]), help="Menor PML de una hora en el rango.")
            st.metric("Máximo horario", mxn(e["maximo"]), help="Mayor PML de una hora en el rango.")
            st.metric("Horas con PML < 0", f"{int(e['horas_negativas']):,}")
            st.markdown(fila("Desv. estándar", mxn(e["desv_std"]))
                        + fila("Percentil 10", mxn(e["p10"]) if horario_completo else "—")
                        + fila("Percentil 90", mxn(e["p90"]) if horario_completo else "—")
                        + fila("Cobertura", f"{e['cobertura_pct']}%"), unsafe_allow_html=True)
    st.caption(f"Indicadores calculados sobre las {con_dato:,} horas con dato, en MXN/MWh"
               + ("." if resolucion == "horaria" else f", aunque la gráfica sea {resolucion}."))
    if not horario_completo:
        st.caption("— Mediana, P10 y P90 requieren datos horarios: el rango excede la ventana horaria "
                   f"({limites['horario_desde']} a {limites['horario_hasta']}). No se estiman.")
    avisos_parciales(df, resolucion)

    with st.expander("Todas las estadísticas"):
        filas = [
            ("Horas con dato", f"{con_dato:,}", "h"),
            ("Horas del rango (24 × días)", f"{del_rango:,}", "h"),
            ("Cobertura", f"{e['cobertura_pct']}", "%"),
            ("Primera fecha con dato", str(desde_obs), ""),
            ("Última fecha con dato", str(hasta_obs), ""),
            ("Promedio horario", mxn(e["promedio"]), "MXN/MWh"),
            ("Desviación estándar muestral", mxn(e["desv_std"]), "MXN/MWh"),
            ("Mínimo horario", mxn(e["minimo"]), "MXN/MWh"),
            ("Percentil 10 horario", mxn(e["p10"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Mediana horaria", mxn(e["mediana"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Percentil 90 horario", mxn(e["p90"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Máximo horario", mxn(e["maximo"]), "MXN/MWh"),
            ("Horas con PML < 0", f"{int(e['horas_negativas']):,}", "h"),
        ]
        st.dataframe(pd.DataFrame(filas, columns=["Indicador", "Valor", "Unidad"]),
                     hide_index=True, width="stretch")
        tabla = df[["etiqueta", "pml_promedio", "horas", "horas_posibles"]].rename(columns={
            "etiqueta": "Periodo", "pml_promedio": "PML promedio (MXN/MWh)",
            "horas": "Horas con dato", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={"PML promedio (MXN/MWh)": st.column_config.NumberColumn(format="%.2f")})


def vista_2(limites, nodos, fechas_nodo, version, panel):
    """Vista 2: spread A − B, solo en las horas en que los dos nodos tienen dato."""
    with panel:
        defecto_b = "01AGU-230" if "01AGU-230" in nodos else nodos[min(1, len(nodos) - 1)]
        st.caption(SIN_RESULTADOS)
        ca, cb = st.columns(2)
        with ca:
            nodo_a = selector_nodo(nodos, "Nodo A · buscar por clave", "nodo_a", "01AAN-85")
        with cb:
            nodo_b = selector_nodo(nodos, "Nodo B · buscar por clave", "nodo_b", defecto_b)
        inicio, fin, resolucion = controles_rango(limites)
        for n in (nodo_a, nodo_b):
            if n in fechas_nodo:
                st.caption(f"{n} tiene datos del {fechas_nodo[n][0]} al {fechas_nodo[n][1]}.")

    st.markdown("**Spread = PML_A − PML_B** (MXN/MWh). Positivo: A más caro que B. "
                "Solo se comparan las horas en que los dos nodos tienen dato; después se agrega por día o mes.")
    if nodo_a == nodo_b:
        st.error("Elige dos nodos distintos.")
        st.stop()
    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        r = consultar_resumen(nodo_a, nodo_b, inicio, fin, str(DATA_DIR), version).iloc[0]
        d = consultar_diferencial(nodo_a, nodo_b, inicio, fin, resolucion, str(DATA_DIR), version)
        a = consultar_serie(nodo_a, inicio, fin, resolucion, str(DATA_DIR), version)
        b = consultar_serie(nodo_b, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if r["horas_coincidentes"] == 0:
        fechas = "; ".join(f"{n}: {fechas_nodo[n][0]} a {fechas_nodo[n][1]}" for n in (nodo_a, nodo_b) if n in fechas_nodo)
        st.warning(f"{nodo_a} y {nodo_b} no tienen horas con dato en común entre {inicio} y {fin}. "
                   f"Datos observados: {fechas}. No se calcula spread: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo_a} − {nodo_b}: {inicio} a {fin}")
    comunes, del_rango = int(r["horas_coincidentes"]), int(r["horas_del_rango"])
    desde_obs, hasta_obs = r["primera_fecha"].date(), r["ultima_fecha"].date()

    # v0.5 · Cabecera: spread promedio del último día común, cambio en MXN/MWh (sin %).
    def spread_del_dia(dia):
        x = consultar_resumen(nodo_a, nodo_b, dia, dia, str(DATA_DIR), version).iloc[0]
        return None if x["horas_coincidentes"] == 0 else x["promedio"]
    cabecera(spread_del_dia, hasta_obs, limites, "Spread A − B promedio", porcentaje=False)
    st.markdown(f"Positivo: {nodo_a} más caro que {nodo_b} | **Cobertura común:** {r['cobertura_pct']}% ({comunes:,} de "
                f"{del_rango:,} horas con dato en los dos nodos) | **Rango común con observaciones:** {desde_obs} a {hasta_obs}")
    if r["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura común escasa: el spread describe solo {comunes:,} horas, entre {desde_obs} y {hasta_obs}. "
                   "Las horas en que falta alguno de los dos nodos se excluyen, no se imputan.")
    if r["dias_no_comparables"]:
        st.warning(f"{int(r['dias_no_comparables']):,} días con horas incompletas en algún nodo se excluyeron: "
                   "fuera de la ventana horaria no se puede saber qué horas coinciden.")

    curvas = pd.merge(a[["periodo", "pml_promedio"]].rename(columns={"pml_promedio": nodo_a}),
                      b[["periodo", "pml_promedio"]].rename(columns={"pml_promedio": nodo_b}),
                      on="periodo", how="outer")
    d = marcar_periodos(d, inicio, fin, resolucion)
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown("**Spread A − B (MXN/MWh)** · solo horas coincidentes")
            grafica(d, "dif_promedio", "Spread A − B (MXN/MWh)", resolucion)
            st.markdown("**PML de cada nodo (MXN/MWh)** · cada curva con todas sus horas con dato")
            grafica_series(curvas, [nodo_a, nodo_b], [NARANJA, "#2F6FB0"])
        with der, st.container(key="ficha"):
            if pd.notna(r["minimo"]) and pd.notna(r["maximo"]):
                st.markdown(barra_rango("Rango horario del spread", r["minimo"], r["maximo"], r["promedio"]),
                            unsafe_allow_html=True)
            st.metric("Spread promedio", mxn(r["promedio"]),
                      help="Promedio horario simple de PML_A − PML_B en las horas coincidentes.")
            st.metric("Mediana horaria", mxn(r["mediana"]))
            st.metric("Mínimo horario", mxn(r["minimo"]))
            st.metric("Máximo horario", mxn(r["maximo"]))
            st.metric("Horas con A más caro", "—" if pd.isna(r["pct_a_mas_caro"]) else f"{r['pct_a_mas_caro']}%")
            st.markdown(fila("Horas coincidentes", f"{comunes:,}") + fila("Cobertura común", f"{r['cobertura_pct']}%")
                        + fila("Días excluidos", f"{int(r['dias_no_comparables'] or 0):,}"), unsafe_allow_html=True)
    if not horario_completo:
        st.caption("Fuera de la ventana horaria el spread se calcula con los días en que ambos nodos tienen las 24 horas. "
                   f"Mediana, mínimo, máximo y % de horas con A más caro requieren el rango entre "
                   f"{limites['horario_desde']} y {limites['horario_hasta']}.")
    avisos_parciales(d, resolucion)

    with st.expander("Tabla del spread"):
        tabla = d[["etiqueta", "dif_promedio", "horas", "horas_posibles"]].rename(columns={
            "etiqueta": "Periodo", "dif_promedio": "Spread A − B (MXN/MWh)",
            "horas": "Horas coincidentes", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={"Spread A − B (MXN/MWh)": st.column_config.NumberColumn(format="%.2f")})


def vista_3(limites, nodos, fechas_nodo, version, panel):
    """Vista 3: PML descompuesto en energía, pérdidas y congestión, con su signo."""
    with panel:
        st.caption(SIN_RESULTADOS)  # encima: la lista «No results» de Streamlit taparía un texto inferior
        nodo = selector_nodo(nodos, "Buscar por clave de nodo", "nodo", "01AAN-85")
        inicio, fin, resolucion = controles_rango(limites)
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")

    st.markdown("**PML = energía + pérdidas + congestión** (MXN/MWh). La energía es igual en todos los nodos a la "
                "misma hora; pérdidas y congestión son lo propio del nodo y pueden ser negativas.")
    if not limites.get("componentes"):
        st.info("Los componentes del PML todavía no están en el paquete público. Esta vista se activa sola "
                "cuando el pipeline publique la versión 2 de los datos.")
        st.stop()
    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        r = consultar_resumen_componentes(nodo, inicio, fin, str(DATA_DIR), version).iloc[0]
        df = consultar_componentes(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if r["horas_con_dato"] == 0:
        detalle = f" {nodo} tiene datos del {primera} al {ultima}." if primera else ""
        st.warning(f"Sin observaciones para {nodo} entre {inicio} y {fin}.{detalle} "
                   "No se muestra ninguna cifra: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo}: componentes del PML, {inicio} a {fin}")
    con_dato = int(r["horas_con_dato"])
    hasta_obs = r["ultima_fecha"].date()

    # v0.5 · Cabecera: PML promedio del último día con dato, igual que en la vista 1.
    def pml_del_dia(dia):
        x = consultar_resumen_componentes(nodo, dia, dia, str(DATA_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["pml"]
    cabecera(pml_del_dia, hasta_obs, limites, "PML promedio")
    st.markdown(f"MDA · SIN · CENACE | **Cobertura:** {r['cobertura_pct']}% ({con_dato:,} de "
                f"{int(r['horas_del_rango']):,} horas con dato) | **Rango con observaciones:** "
                f"{r['primera_fecha'].date()} a {hasta_obs}")
    if r["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura escasa: los promedios describen solo {con_dato:,} horas. Las horas sin dato no se tratan como cero.")
    if r["horas_descuadre"] > 0:
        st.warning(f"{int(r['horas_descuadre']):,} horas con descuadre mayor a {UMBRAL_DESCUADRE} MXN/MWh.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    nombres = {"energia": "Energía", "perdidas": "Pérdidas", "congestion": "Congestión"}
    colores = [NARANJA, "#2F6FB0", "#8E8E8E"]
    largo = df.melt(id_vars=["periodo", "etiqueta"], value_vars=list(nombres), var_name="componente", value_name="valor")
    largo["componente"] = largo["componente"].map(nombres)
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown("**Componentes del PML (barras apiladas, MXN/MWh)** · los negativos quedan debajo del cero")
            st.altair_chart(alt.Chart(largo).mark_bar().encode(
                x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor="#CFC8BB")),
                y=alt.Y("valor:Q", title=None, stack="zero",
                        axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor="#E4DDD0", tickCount=5)),
                color=alt.Color("componente:N", title=None, sort=list(nombres.values()),
                                scale=alt.Scale(domain=list(nombres.values()), range=colores),
                                legend=alt.Legend(orient="top-left", direction="horizontal")),
                tooltip=[alt.Tooltip("etiqueta:N", title="Periodo"), alt.Tooltip("componente:N", title="Componente"),
                         alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f")])
                .properties(background="transparent").configure_view(stroke=None).configure(locale=LOCALE_ES),
                width="stretch")
            st.markdown("**Pérdidas y congestión (MXN/MWh)** · la parte propia del nodo, a su escala")
            grafica_series(df.rename(columns={"perdidas": "Pérdidas", "congestion": "Congestión"}),
                           ["Pérdidas", "Congestión"], colores[1:])
        with der, st.container(key="ficha"):
            st.metric("PML promedio", mxn(r["pml"]))
            st.metric("Energía", mxn(r["energia"]))
            st.metric("Pérdidas", mxn(r["perdidas"]))
            st.metric("Congestión", mxn(r["congestion"]))
            st.metric("Horas con congestión > 0", f"{int(r['horas_congestion_positiva']):,}")
            st.metric("Horas con congestión < 0", f"{int(r['horas_congestion_negativa']):,}")
            st.metric("Descuadre máximo", f"{r['descuadre_max']:,.4f}",
                      help="Máximo de |PML − (energía + pérdidas + congestión)| en una hora. Viene del redondeo de CENACE.")
            st.markdown(fila("Cobertura", f"{r['cobertura_pct']}%"), unsafe_allow_html=True)
    st.caption(f"Promedios horarios simples sobre las mismas {con_dato:,} horas para el PML y cada componente."
               + ("" if r["horas_descuadre"] > 0 else f" Ninguna hora con descuadre mayor a {UMBRAL_DESCUADRE} MXN/MWh."))
    avisos_parciales(df, resolucion)

    with st.expander("Tabla de componentes y descuadre"):
        tabla = df[["etiqueta", "pml", "energia", "perdidas", "congestion", "descuadre", "horas"]].rename(columns={
            "etiqueta": "Periodo", "pml": "PML", "energia": "Energía", "perdidas": "Pérdidas",
            "congestion": "Congestión", "descuadre": "Descuadre promedio", "horas": "Horas con dato"})
        formato = {c: st.column_config.NumberColumn(format="%.2f") for c in ("PML", "Energía", "Pérdidas", "Congestión")}
        formato["Descuadre promedio"] = st.column_config.NumberColumn(format="%.4f")
        st.dataframe(tabla, hide_index=True, width="stretch", column_config=formato)


st.set_page_config(page_title="PML Explorer", page_icon=str(ASSETS / "logo.svg"), layout="wide",
                   initial_sidebar_state="collapsed")
st.html(ESTILOS)
# H01: regreso explícito al sitio editorial, fuera de cualquier panel para que se vea en las tres vistas.
st.markdown(f"[← Mercados · edarji.net]({SITIO_MERCADOS})")
col_logo, col_titulo = st.columns([1, 9], vertical_alignment="center")
with col_logo:
    logo()
with col_titulo:
    st.title("PML Explorer")
    st.caption("Precio Marginal Local · Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh")

if not (DATA_DIR / "metadata.json").is_file():
    st.info("Los derivados públicos de CENACE todavía no están disponibles en esta publicación.")
    st.stop()

try:
    version = huella_paquete()
    limites, nodos, fechas_nodo = cargar_paquete(str(DATA_DIR), version)
except (DatosNoDisponibles, duckdb.Error):
    st.error("El paquete público está incompleto o su esquema no es compatible. La integración debe validarse antes de publicar cifras.")
    st.stop()

if not nodos:
    st.warning("El paquete público no contiene nodos con datos.")
    st.stop()


VISTAS = {"1. PML histórico": vista_1, "2. Comparar nodos (spread)": vista_2, "3. Componentes del PML": vista_3}
# H07: vista y filtros en un panel con texto visible dentro del contenido, cerrado al iniciar, en vez de la
# barra lateral (en móvil quedaba sobre los resultados o como un icono sin texto). Cerrarlo no borra la selección.
# v0.5: las vistas son una barra de pestañas visible arriba; nodo, fechas y resolución siguen en el panel.
col_pestanas, col_rangos = st.columns([3, 1], vertical_alignment="bottom")
with col_pestanas, st.container(key="pestanas"):
    vista = st.radio("Vista", list(VISTAS), key="vista", horizontal=True, label_visibility="collapsed",
                     format_func=lambda v: v.split(". ", 1)[1])
with col_rangos:
    botones_rango(limites)
panel = st.expander("Vista y filtros", expanded=False)
# El contenido va en un contenedor creado antes que el pie: si una vista se detiene con st.stop()
# (sin datos, fechas invertidas), metodología y fechas disponibles siguen visibles debajo.
contenido = st.container()
metodologia()
st.caption(f"Fechas de operación disponibles: {limites['desde']} a {limites['hasta']} (diario); "
           f"{limites['horario_desde']} a {limites['horario_hasta']} (horario). "
           f"Actualización del paquete: {actualizado_cdmx(limites['generado_utc'])}, Ciudad de México.")
with contenido:
    VISTAS[vista](limites, nodos, fechas_nodo, version, panel)

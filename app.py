"""Entrada pública de PML Explorer."""
import base64
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

import catalogo as cat_nodos
import ensemble as ens
import exportar
import pnd as pnd_zonas

from enlaces import PARAMETROS, VISTAS_URL, construir_enlace, leer_enlace
from escena import ENSEMBLE, SOLO, enlace_ensemble, escena_de_enlace
from rangos import RANGOS_RAPIDOS, rango_rapido
from vista2 import diferencial, resumen
from vista3 import componentes, resumen_componentes
from vista1 import (DATA_DIR, RESOLUCIONES, UMBRAL_DESCUADRE, DatosNoDisponibles, actualizado_cdmx, catalogo,
                    cobertura_horaria, estadisticas, huella_paquete,
                    inspeccionar_paquete, marcar_periodos, metadata, observado, serie)

VERSION_APP = "v0.8.0 beta"  # versión de la aplicación; el esquema de datos y la fecha vienen del paquete
REPO = "https://github.com/edarji/pml-explorer-web/blob/main"
COBERTURA_ESCASA = 80  # % de horas con dato bajo el cual se advierte explícitamente
SITIO_MERCADOS = "https://edarji.net/mercados/"
URL_APP = "https://pml-explorer.streamlit.app/"  # base del enlace copiable junto a «Descargar CSV»
ZONA_MERCADO = ZoneInfo("America/Mexico_City")
AYUDA_NODO = ("Escribe la clave NodoP (por ejemplo 06ESC) o parte del nombre oficial. La clave identifica "
              "el nodo; el nombre solo ayuda a encontrarlo y puede repetirse en varias claves.")
SIN_RESULTADOS = ("¿Sin resultados? Prueba con la clave (por ejemplo 06ESC) o revisa Región, Estado y Zona. "
                  "Pulsa Esc o borra el texto para conservar el nodo elegido.")
# v0.6.0 · Sin catálogo de referencia válido la app vuelve al comportamiento de v0.5.1: solo claves.
AYUDA_SOLO_CLAVE = ("Escribe la clave NodoP o parte de ella, por ejemplo 06ESC. El catálogo de nombres y "
                    "ubicaciones no está disponible en esta publicación.")
TODAS = "Todas"
UBICACION = {}  # se llena al cargar el paquete: {"union": DataFrame, "nombres": dict, "manifiesto": dict}
# v0.7.0 · Precio de zona de carga. Se llena solo si la carpeta pública pnd/ pasa su contrato; si no, la app es
# exactamente la de PML (sin selector de modalidad). {"limites", "zonas", "regiones", "version"}
PND = {}
MODALIDADES = {"pml": "PML · NodoP", "pnd": "PND · Zona de carga"}
ZONA_DEFECTO = "MONTERREY"
PND_HORARIA_MAX_DIAS = 366  # la gráfica horaria de más de un año no se lee y pesa en el navegador
# H03: los st.caption de Streamlit 1.66 usan opacidad 0.6 (≈3.70:1 sobre blanco). Con 0.8 el texto
# queda en ≈6.67:1 sobre blanco y ≈6.19:1 sobre gris claro, por debajo del texto principal (12.53:1).
ESTILOS = """<style>
/* v0.6.3 · Dark Trading (Bloomberg Black + Apple Bolsa). Solo colores y tipografía; la estructura es la de v0.5–v0.6.2.
   Paleta: negro #000, superficies #111113/#1C1C1E, bordes #2C2C2E, texto #F2F2F7, secundario #A1A1A6,
   ámbar #FFB000 (logo sax), azul #0A84FF, verde #30D158 / rojo #FF453A solo para cambios. */
[data-testid='stCaptionContainer']{opacity:0.8}
.block-container{max-width:1240px}
/* Cifras con ancho fijo por dígito, como en una pantalla de cotizaciones: las columnas no bailan. */
.precio,.st-key-ficha,.fila,.rango,[data-testid=stMetricValue],[data-testid=stDataFrame]{font-variant-numeric:tabular-nums}
/* v0.5 · Pestañas: el radio de vistas se dibuja como barra de pestañas subrayada (activa en ámbar). */
.st-key-pestanas div[role=radiogroup]{gap:0;border-bottom:1px solid #2C2C2E;flex-wrap:nowrap;overflow-x:auto}
.st-key-pestanas div[role=radiogroup] label{padding:.5rem 1.1rem .55rem;margin:0;border-bottom:3px solid transparent;
  white-space:nowrap}
.st-key-pestanas div[role=radiogroup] label > div > div:first-child{display:none}
.st-key-pestanas div[role=radiogroup] label p{font-size:1.02rem;color:#A1A1A6}
.st-key-pestanas label[data-selected=true]{box-shadow:inset 0 -3px 0 #FFB000}
.st-key-pestanas label[data-selected=true] p{font-weight:600;color:#F2F2F7}
/* v0.5.1 · Móvil: las tres pestañas no caben en una fila (≈526 px) y «Componentes» quedaba fuera de la
   pantalla. En pantallas angostas la barra pasa a dos filas en vez de desplazarse: todas siempre visibles. */
@media (max-width:640px){
.st-key-pestanas div[role=radiogroup]{flex-wrap:wrap;overflow-x:visible}
.st-key-pestanas div[role=radiogroup] label{padding:.45rem .6rem .5rem}
.st-key-pestanas div[role=radiogroup] label p{font-size:.92rem}
}
/* v0.6.2 · Descarga: en pantallas angostas el botón y el enlace ocupan todo el ancho, uno bajo otro. */
@media (max-width:640px){
.st-key-descarga{flex-direction:column;align-items:stretch}
.st-key-descarga button{width:100%}
}
/* v0.5.1 · Recuadro al pasar el mouse: pequeño para no tapar la gráfica; v0.6.3 en grafito. */
#vg-tooltip-element{font-size:11px;padding:4px 7px;background:#1C1C1E;color:#F2F2F7;border:1px solid #3A3A3C;
  box-shadow:0 4px 14px rgba(0,0,0,.6)}
#vg-tooltip-element td.key{padding-right:6px;color:#A1A1A6}
/* Botones de rango: pastillas pequeñas (como 1D/1S/1M de Bolsa); la activa en ámbar. */
.st-key-rangos button{min-height:2rem;padding:.1rem .85rem;border:1px solid #3A3A3C;background:#1C1C1E;
  border-radius:999px;color:#F2F2F7}
.st-key-rangos button p{font-size:.85rem;font-weight:600}
.st-key-rangos button[kind=primary]{background:#FFB000;border-color:#FFB000;color:#000}
/* Encabezado tipo cotización: cifra grande blanca y cambio en pastilla verde/roja (Apple Bolsa). */
.precio{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35rem .8rem;margin:-.4rem 0 .2rem}
.precio .valor{font-size:2.6rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:#FFFFFF}
.precio .unidad{font-size:1rem;font-weight:600;color:#A1A1A6}
.precio .cambio{font-size:1.15rem;font-weight:700;padding:.05rem .5rem;border-radius:.35rem}
.precio .cambio.sube{background:#30D158;color:#000}.precio .cambio.baja{background:#FF453A;color:#000}
.precio .cambio.igual{background:#3A3A3C;color:#F2F2F7}
.precio .fecha{font-size:.85rem;color:#A1A1A6}
.sube{color:#30D158}.baja{color:#FF453A}.igual{color:#A1A1A6}
.linea-meta{font-size:.85rem;color:#A1A1A6;margin-bottom:.4rem}
/* Tarjeta de gráfica + ficha de indicadores: superficie grafito con borde fino (terminal). */
.st-key-tarjeta{background:#111113;border:1px solid #2C2C2E;border-radius:.8rem;padding:1rem 1.1rem .6rem}
.st-key-ficha{border-left:1px solid #2C2C2E;padding-left:1rem}
.st-key-ficha [data-testid=stMetric]{padding:0}
.st-key-ficha [data-testid=stMetricLabel]{min-height:0;margin:0}
.st-key-ficha [data-testid=stMetric] > div{display:flex;justify-content:space-between;align-items:baseline;gap:.5rem}
.st-key-ficha [data-testid=stMetricLabel] p{font-size:.88rem;color:#A1A1A6}
.st-key-ficha [data-testid=stMetricValue], .st-key-ficha [data-testid=stMetricValue] p{font-size:.92rem;font-weight:600;line-height:1.6;height:auto;min-height:0;color:#F2F2F7}
.st-key-ficha [data-testid=stVerticalBlock]{gap:.1rem}
.fila{display:flex;justify-content:space-between;font-size:.88rem;line-height:1.75;border-top:1px solid #1C1C1E}
.fila span:first-child{color:#A1A1A6}
.rango{margin:.1rem 0 .7rem}.rango .et{font-size:.88rem;color:#A1A1A6}
.rango .barra{position:relative;height:3px;background:#3A3A3C;margin:.55rem 0 .3rem;border-radius:2px}
.rango .barra span{position:absolute;top:-4px;width:11px;height:11px;border-radius:50%;background:#FFB000;
  transform:translateX(-50%)}
.rango .ext{display:flex;justify-content:space-between;font-size:.75rem;color:#A1A1A6}
/* En una columna (móvil) la ficha va debajo de la gráfica: el separador pasa de vertical a horizontal. */
@media (max-width:640px){
.st-key-ficha{border-left:none;padding-left:0;border-top:1px solid #2C2C2E;padding-top:.6rem}
}
/* v0.6.4 · Pulido UX. Segunda tarjeta (vista 2: curvas de cada nodo) con el mismo estilo. */
.st-key-tarjeta_curvas{background:#111113;border:1px solid #2C2C2E;border-radius:.8rem;padding:1rem 1.1rem .6rem}
/* Marca: logo y título en una fila también en móvil (antes el logo ocupaba su propia fila). */
.st-key-marca{flex-wrap:nowrap}
.st-key-marca h1{padding:.2rem 0 0}
/* Foco visible con teclado en pestañas y pastillas. */
.st-key-pestanas label:has(input:focus-visible){outline:2px solid #FFB000;outline-offset:-2px;border-radius:.3rem}
.st-key-rangos button:focus-visible{outline:2px solid #FFB000;outline-offset:2px}
.st-key-rangos button{min-height:2.25rem;min-width:3.2rem}
@media (max-width:640px){
/* Primera pantalla compacta: marca, pestañas y pastillas ocupan menos alto para llegar antes a la cifra y la gráfica. */
.st-key-marca .logo-pml{width:52px}
.st-key-marca h1{font-size:1.75rem}
.block-container h3{font-size:1.2rem}
.precio .valor{font-size:2.1rem}
.precio .cambio{font-size:1rem}
/* Pastillas cómodas al tacto: 44 px de alto (guía de Apple). */
.st-key-rangos button{min-height:44px;min-width:56px}
}
/* v0.8.0 · Graphite Trading | Ensemble & Solo. Misma paleta Dark Trading (decisión D4); sin animaciones. */
.st-key-seccion_pml,.st-key-seccion_pnd,.st-key-atril{background:#111113;border:1px solid #2C2C2E;border-radius:.8rem;
  padding:.9rem 1rem .5rem}
.seccion-et{display:flex;flex-wrap:wrap;align-items:baseline;gap:.15rem .6rem;font-size:1.02rem}
.seccion-et span:last-child{font-size:.82rem;color:#A1A1A6}
.seccion-et .marca{width:.6rem;height:.6rem;border-radius:2px;align-self:center}
.marca.pml{background:#FFB000}.marca.pnd{background:#0A84FF}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:.3rem 0 .2rem}
.kpi{background:#1C1C1E;border:1px solid #2C2C2E;border-radius:.55rem;padding:.5rem .65rem;min-width:0}
.kpi .et{font-size:.78rem;color:#A1A1A6}
.kpi .v{font-size:1.35rem;font-weight:700;color:#F2F2F7;font-variant-numeric:tabular-nums;line-height:1.3}
.kpi .nota{font-size:.75rem;color:#A1A1A6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mini-et,.lista-et{font-size:.8rem;color:#A1A1A6;margin:.35rem 0 -.2rem}
[class*=st-key-rk_] [data-testid=stVerticalBlock]{gap:.3rem}
[class*=st-key-rk_] button{justify-content:flex-start;min-height:2.25rem;padding:.2rem .7rem;background:#1C1C1E;
  border:1px solid #2C2C2E;font-variant-numeric:tabular-nums;text-align:left}
[class*=st-key-rk_] button p{font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*=st-key-rk_] button:hover{border-color:#FFB000}
.st-key-rk_pnd_caras button:hover,.st-key-rk_pnd_baratas button:hover{border-color:#0A84FF}
.st-key-volver button{min-height:2.25rem;padding:.1rem .8rem;border:1px solid #3A3A3C;background:#1C1C1E;border-radius:999px}
.solista{display:flex;flex-wrap:wrap;align-items:baseline;gap:.1rem .7rem;margin:.1rem 0 .3rem;padding-left:.7rem;
  border-left:3px solid #FFB000}
.solista.pnd{border-left-color:#0A84FF}
.solista .et{flex-basis:100%;font-size:.74rem;letter-spacing:.06em;color:#A1A1A6}
.solista .nombre{font-size:1.7rem;font-weight:700;color:#FFFFFF;letter-spacing:-.01em}
.solista .nombre .vs{font-size:1rem;color:#A1A1A6;font-weight:600}
.solista .detalle{font-size:.86rem;color:#A1A1A6}
/* Tableta (641–1024 px): el panel derecho pasa arriba a todo el ancho; los indicadores, 2 × 2. */
@media (max-width:1024px){
.st-key-ensemble > div > [data-testid=stHorizontalBlock],
.st-key-ensemble > [data-testid=stHorizontalBlock]{flex-direction:column-reverse}
.st-key-ensemble > div > [data-testid=stHorizontalBlock] > [data-testid=stColumn],
.st-key-ensemble > [data-testid=stHorizontalBlock] > [data-testid=stColumn]{width:100% !important;flex:1 1 100% !important}
.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:640px){
.solista .nombre{font-size:1.4rem}
.kpi .v{font-size:1.15rem}
[class*=st-key-rk_] button{min-height:44px}
.st-key-volver button{min-height:44px}
}
</style>"""
ASSETS = Path(__file__).resolve().parent / "assets"
NARANJA = "#FFB000"  # v0.6.3: ámbar del logo sax (nombre conservado: es la serie principal en las tres vistas)
AZUL = "#0A84FF"
GRIS = "#8E8E93"
FONDO = "#000000"  # contorno del punto resaltado, para que se separe de la línea
EJE = "#3A3A3C"     # marcas del eje X
REJILLA = "#1F1F22"  # rejilla horizontal, tenue sobre negro
CERO = "#8E8E93"     # v0.6.4: línea de referencia en cero (spread, pérdidas y congestión)
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
# v0.8.0 · Graphite Trading | Ensemble & Solo.
ALTO_SOLO = 380        # px de la gráfica principal en SOLO (antes, el alto por omisión de Vega-Lite: 300)
ALTO_DISTRIBUCION = 150  # px de las gráficas compactas de ENSEMBLE
RANKING_N = 5          # filas de «Más caros» y «Más baratos»


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


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_pnd(pnd_dir, version):
    """v0.7.0 · Límites y zonas del paquete PND. Lanza PndNoDisponible si no cumple el contrato."""
    return pnd_zonas.inspeccionar_pnd(pnd_dir), pnd_zonas.zonas(pnd_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas_pnd(zona, inicio, fin, pnd_dir, version):
    return pnd_zonas.estadisticas_pnd(zona, inicio, fin, pnd_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie_pnd(zona, inicio, fin, resolucion, pnd_dir, version):
    return pnd_zonas.serie_pnd(zona, inicio, fin, resolucion, pnd_dir)


@st.cache_data(max_entries=16, show_spinner=False)
def consultar_ranking_pml(dia, data_dir, version):
    """v0.8.0 · ENSEMBLE: promedio del día de cada nodo (misma fórmula que SOLO), del más caro al más barato."""
    return ens.ranking_pml(dia, data_dir)


@st.cache_data(max_entries=16, show_spinner=False)
def consultar_ranking_pnd(dia, pnd_dir, version):
    """v0.8.0 · ENSEMBLE: promedio del día de cada zona de carga (misma fórmula que SOLO PND)."""
    return ens.ranking_pnd(dia, pnd_dir)


def mxn(valor):
    """Precio con la misma precisión en indicadores y tablas: dos decimales."""
    return "—" if pd.isna(valor) else f"{valor:,.2f}"


def campos_recuadro(df, resolucion, nodo):
    """Columnas de texto para el recuadro que aparece al pasar el mouse. No tocan los valores.

    Convención de CENACE (hora final): el punto de las 00:00 es la hora 1, de 00:00 a 01:00.
    """
    df = df.copy()
    df["nodo_txt"] = nodo
    if resolucion == "horaria":
        horas = pd.to_datetime(df["periodo"]).dt.hour
        df["fecha_txt"] = pd.to_datetime(df["periodo"]).dt.strftime("%Y-%m-%d")
        df["hora_txt"] = [f"{h + 1} ({h:02d}:00–{h + 1:02d}:00)" for h in horas]
    else:
        df["fecha_txt"] = df["etiqueta"]  # día, o mes con su nota de periodo parcial
    return df


def grafica(df, y, titulo_y, resolucion, color=None, nodo="", cero=False, titulo_serie=None):
    """Línea con puntos; los periodos parciales se marcan con ▼.

    v0.5.1: al pasar el mouse cerca de la línea se marca el punto más cercano y aparece un recuadro pequeño
    con nodo, valor, fecha y hora (horaria) u horas con dato (diaria y mensual).
    """
    df = campos_recuadro(df, resolucion, nodo)
    recuadro = [alt.Tooltip("nodo_txt:N", title=titulo_serie or ("Nodos" if " − " in nodo else "Nodo")),
                alt.Tooltip("fecha_txt:N", title="Fecha")]
    if resolucion == "horaria":
        recuadro.append(alt.Tooltip("hora_txt:N", title="Hora"))
    recuadro.append(alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.2f"))
    if resolucion != "horaria":
        recuadro.append(alt.Tooltip("horas:Q", title="Horas con dato", format=","))
    base = alt.Chart(df).encode(
        x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
        y=alt.Y(f"{y}:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5)),
    )
    linea = base.mark_line(color=color or NARANJA, strokeWidth=1.8)
    # v0.6.4 · `cero=True` (spread): línea de referencia en 0 para leer el signo de un vistazo.
    capas = ([alt.Chart(df).mark_rule(color=CERO, strokeWidth=1, strokeDash=[4, 3]).encode(y=alt.datum(0))]
             if cero else []) + [linea]
    # Con muchos periodos solo se dibujan los puntos parciales, para no saturar la gráfica.
    puntos = base if len(df) <= 400 else base.transform_filter("datum.parcial")
    if resolucion != "horaria":
        capas.append(puntos.mark_point(size=50, filled=True, color=color or NARANJA).encode(
            shape=alt.Shape("parcial:N", title="Periodo",
                            scale=alt.Scale(domain=[False, True], range=["circle", "triangle-down"]),
                            legend=alt.Legend(labelExpr="datum.value ? 'parcial' : 'completo'")),
        ))
    # Punto más cercano al mouse: invisible hasta que se acerca el cursor, y lleva el recuadro.
    cerca = alt.selection_point(on="pointerover", nearest=True, fields=["periodo"], empty=False,
                                clear="pointerout")
    capas.append(base.mark_point(size=70, filled=True, color=color or NARANJA, stroke=FONDO, strokeWidth=1.5)
                 .encode(opacity=alt.condition(cerca, alt.value(1), alt.value(0)), tooltip=recuadro)
                 .add_params(cerca))
    # v0.8.0 · SOLO: la gráfica principal gana alto (protagonista); los datos y las marcas no cambian.
    st.altair_chart(alt.layer(*capas).properties(background="transparent", height=ALTO_SOLO)
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
- **Descargar CSV (v0.6.2):** la serie de la gráfica en la resolución elegida, con los mismos valores: fecha (y hora CENACE si es horaria), nodo y precios en MXN/MWh. Coma como separador y punto decimal; una celda vacía no es cero. En la vista 2, PML A y PML B se promedian sobre las mismas horas comunes que el spread.
- **Nombres y ubicación (v0.6.0):** nombre oficial, Región de Control y Zona de carga vienen del [Catálogo de NodosP de CENACE](https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx), en la versión indicada al pie. CENACE aclara que la versión no es la vigencia de cada nodo: la clasificación corresponde a esa versión y no se aplica hacia atrás. Sirve para **localizar** nodos; no determina el nodo de liquidación de una instalación. El **estado** es la entidad federativa (clave INEGI) donde CENACE ubica cada nodo; se filtra nodo por nodo, porque una zona de carga puede abarcar varios estados, y no indica dónde está una instalación ni su nodo de liquidación. Los nodos de interconexión internacional no tienen región, zona ni estado («sin clasificación verificada»). Región, zona y estado no intervienen en ningún cálculo.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def metodologia_pnd():
    """v0.7.0 · Metodología de la modalidad PND (decisión D: PEND/pz solo aquí y en los metadatos)."""
    with st.expander("Metodología y definiciones · PND"):
        st.markdown(f"""
- **Qué es:** el **precio de zona de carga (PND)** que publica CENACE para cada zona de carga del SIN en el Mercado del Día en Adelanto (MDA). Es el precio con que se liquida la demanda de la zona, no el de un nodo. Unidades: MXN/MWh.
- **Fuente:** CENACE, servicio SW-PEND (Precios de Energía en Nodos Distribuidos), campo `pz` (y `pz_ene`, `pz_per`, `pz_cng` para energía, pérdidas y congestión). Según el manual técnico de SW-PEND, es el promedio de los PML de los nodos de la zona **ponderado** por su factor de distribución de carga: no es un promedio simple de nodos, por eso la app lo toma tal cual lo publica CENACE y no lo recalcula.
- **Componentes:** PND = energía + pérdidas + congestión, con sus signos. Se revisa que |PND − suma| no supere 0.02 MXN/MWh antes de publicar.
- **Promedio:** promedio **simple** de las horas con dato, igual que en el PML. Diario y mensual se calculan sobre las horas, nunca promediando promedios.
- **Convención horaria:** hora 1–24 de CENACE, hora final (la hora 1 es 00:00–01:00 del día de operación). Sin conversión a UTC.
- **Faltantes:** una hora o un día sin dato **no es un precio cero**; no se imputa ni se arrastra. Si el servicio de CENACE no devolvió un día en una consulta verificada, el paquete lo declara «sin dato disponible» con la fecha y el resultado de esa consulta, y se vuelve a pedir en cada actualización. La cobertura es horas con dato ÷ (24 × días del rango), incluidos esos días.
- **Correcciones:** si CENACE corrige un día ya publicado, el paquete toma la versión nueva y el día queda listado como corregido; el original se conserva en el respaldo del laboratorio.
- **Zonas y regiones:** la lista de zonas viene del paquete; la Región de Control para filtrar viene del [Catálogo de NodosP de CENACE](https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx) (una zona puede estar en dos regiones). Solo ayuda a encontrar la zona; no interviene en ningún cálculo.
- **PML y PND no se mezclan:** cada modalidad tiene su propio paquete, sus fechas y su CSV.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def ajustar_fechas_modalidad():
    """Callback del selector de modalidad: acota «Desde» y «Hasta» a las fechas del paquete elegido.

    PML y PND tienen paquetes distintos; un date_input con un valor fuera de sus límites fallaría.
    """
    limites = PND["limites"] if st.session_state.get("modalidad") == "pnd" else PND["limites_pml"]
    for clave in ("desde", "hasta"):
        if clave in st.session_state:
            st.session_state[clave] = min(max(st.session_state[clave], limites["desde"]), limites["hasta"])


def dia_de_consulta(limites):
    """Fecha de operación por defecto: hoy en Ciudad de México, acotada al rango del paquete.

    Solo elige el valor inicial de los selectores; los límites siguen saliendo de metadata.
    """
    hoy = datetime.now(ZONA_MERCADO).date()
    return min(max(hoy, limites["desde"]), limites["hasta"])


def aplicar_rango(opcion, limites):
    """Callback de los botones: Streamlit lo ejecuta antes de volver a dibujar la página."""
    st.session_state["desde"], st.session_state["hasta"] = rango_rapido(opcion, limites)


def controles_rango(limites, en_columnas=True):
    """Fechas y resolución, compartidas entre vistas. Por defecto, el día de la consulta en resolución horaria.

    v0.8.0: `en_columnas=False` las apila (panel derecho de ENSEMBLE, angosto). Mismas claves y valores.
    """
    dia = dia_de_consulta(limites)
    # v0.4.1: rangos rápidos. El botón solo escribe «Desde» y «Hasta» en session_state antes del siguiente
    # dibujo; nodo, resolución y cálculos no cambian. El ancla es la última fecha del paquete.
    # El valor inicial va en session_state y no como argumento del widget: así Streamlit no avisa de
    # «valor por defecto y Session State a la vez» cuando un botón de rango rápido cambia las fechas.
    st.session_state.setdefault("desde", dia)
    st.session_state.setdefault("hasta", dia)
    c1, c2, c3 = st.columns(3) if en_columnas else (st.container(), st.container(), st.container())
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


def leer_url(nodos, limites):
    """v0.5.1 · Una sola vez por sesión y antes de dibujar los filtros: copia el enlace recibido a session_state.

    Los widgets toman su valor de session_state por su clave, así que basta con escribirlo antes de crearlos.
    Lo inválido no se copia: queda anotado en «enlace_avisos» para explicarlo al usuario.
    """
    if "enlace_leido" in st.session_state:
        return
    st.session_state["enlace_leido"] = True
    parametros = {clave: st.query_params.get_all(clave) for clave in st.query_params}
    estado, problemas, faltantes = leer_enlace(parametros, nodos, limites, PND.get("zonas"), PND.get("limites"))
    # v0.8.0 · Un enlace con nodo, zona, vista o modalidad abre SOLO (igual que en v0.7.0); sin ellos, ENSEMBLE.
    st.session_state.setdefault("escena", escena_de_enlace(parametros))
    st.session_state.update(estado)
    st.session_state["enlace_avisos"] = (problemas, faltantes)
    st.session_state["panel_abierto"] = bool(problemas)  # fijo en la sesión: el panel no se cierra solo


def descartar_avisos():
    """Callback del botón «Continuar»: el usuario acepta la configuración que ve en el panel."""
    st.session_state["enlace_avisos"] = ([], [])


def actualizar_url(vista):
    """v0.5.1 · Refleja los filtros actuales en la URL. Se llama después del panel, antes de los avisos de la vista.

    Escribir st.query_params no provoca un rerun, y la URL solo se lee al abrir la sesión: no hay ciclos.
    Si el enlace recibido tenía problemas, la vista se detiene aquí sin cifras (y sin tocar la URL original)
    hasta que el usuario cambie un filtro o pulse «Continuar».
    """
    enlace = construir_enlace({clave: st.session_state.get(clave) for clave in PARAMETROS} | {"vista": vista})
    problemas, faltantes = st.session_state.get("enlace_avisos", ([], []))
    if problemas or faltantes:
        if enlace != st.session_state.setdefault("enlace_inicial", enlace):
            problemas, faltantes = [], []  # el usuario ya cambió un filtro: el aviso cumplió su función
            descartar_avisos()
    if problemas:
        st.error("Este enlace no se puede abrir tal cual:\n\n" + "\n".join(f"- {p}" for p in problemas)
                 + "\n\nNo se muestra ninguna cifra para no presentar un análisis distinto del compartido. "
                 "Corrige los filtros en «Vista y filtros» o continúa con la configuración que se ve ahí.")
        st.button("Continuar con la configuración mostrada", on_click=descartar_avisos)
        st.stop()
    if faltantes:
        st.info(f"El enlace no indicaba: {', '.join(faltantes)}. Se usan los valores predeterminados que ves "
                "en «Vista y filtros».")
    actual = st.query_params.to_dict()
    nuevo = {k: v for k, v in actual.items() if k not in PARAMETROS} | enlace  # conserva parámetros ajenos
    if nuevo != actual:
        st.query_params.from_dict(nuevo)


def descarga_csv(vista_url, tabla, nodos_csv, inicio, fin, resolucion, ayuda=None):
    """v0.6.2 · «Descargar CSV» y el enlace de la consulta, debajo de la tarjeta de cada vista.

    `tabla` sale de los DataFrames que la vista ya dibujó (exportar.tabla_*), así que el archivo trae los
    mismos valores sin consultas nuevas. El CSV se entrega ya armado (bytes): con `data` como función
    Streamlit Cloud respondía «Failed to generate file for download» (v0.6.2, 2026-11-13); armarlo cuesta
    milisegundos y pocos cientos de KB. La descarga no vuelve a ejecutar la página (`on_click="ignore"`):
    pestaña, filtros y URL no cambian.
    Solo se llama cuando la vista ya mostró resultados; una vista sin datos se detiene antes.
    """
    nombre = exportar.nombre_archivo(vista_url, nodos_csv, inicio, fin, resolucion)
    enlace = construir_enlace({clave: st.session_state.get(clave) for clave in PARAMETROS}
                              | {"vista": st.session_state.get("vista", VISTAS_URL["historico"])})
    with st.container(key="descarga", horizontal=True, vertical_alignment="center", gap="small"):
        st.download_button("Descargar CSV", data=exportar.a_csv(tabla), file_name=nombre,
                           mime="text/csv", on_click="ignore", icon=":material/download:", key=f"csv_{vista_url}",
                           help=ayuda or "Los datos de esta gráfica: fecha, hora (si es horaria), nodo y precios en MXN/MWh.")
        with st.popover("Enlace de esta consulta"):
            st.code(URL_APP + "?" + urlencode(enlace), language=None, wrap_lines=True)
            st.caption("Copia el enlace con el botón de la esquina. Abre esta misma vista con estos filtros.")
    st.caption(f"{nombre} · resolución {resolucion}, {len(tabla):,} filas · precios en MXN/MWh · coma como "
               "separador, punto decimal, UTF-8. Un periodo sin dato no tiene fila; una celda vacía no es cero.")


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


def grafica_series(df, columnas, colores, resolucion, titulo_serie="Serie", nodo=None, cero=False):
    """Varias curvas con el mismo estilo que `grafica` (eje derecho, sin rejilla vertical, fechas en español).

    v0.5.1: el mismo recuadro pequeño al pasar el mouse (punto más cercano de cada curva).
    """
    largo = df.melt(id_vars=["periodo"], value_vars=columnas, var_name="serie", value_name="valor").dropna()
    largo["etiqueta"] = pd.to_datetime(largo["periodo"]).dt.strftime("%Y-%m" if resolucion == "mensual" else "%Y-%m-%d")
    largo = campos_recuadro(largo, resolucion, nodo or "")
    recuadro = ([alt.Tooltip("nodo_txt:N", title="Nodo")] if nodo else []) + [
        alt.Tooltip("serie:N", title=titulo_serie), alt.Tooltip("fecha_txt:N", title="Fecha")]
    if resolucion == "horaria":
        recuadro.append(alt.Tooltip("hora_txt:N", title="Hora"))
    recuadro.append(alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f"))
    base = alt.Chart(largo).encode(
        x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
        y=alt.Y("valor:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5)),
        color=alt.Color("serie:N", title=None, sort=columnas, scale=alt.Scale(domain=columnas, range=colores),
                        legend=alt.Legend(orient="top", direction="horizontal", title=None)),
        # v0.6.4 · No depender solo del color: la segunda curva va punteada (la leyenda muestra color y trazo).
        strokeDash=alt.StrokeDash("serie:N", title=None, sort=columnas,
                                  scale=alt.Scale(domain=columnas, range=[[1, 0], [6, 3], [2, 2]][:len(columnas)]),
                                  legend=alt.Legend(orient="top", direction="horizontal", title=None)),
    )
    cerca = alt.selection_point(on="pointerover", nearest=True, fields=["periodo", "serie"], empty=False,
                                clear="pointerout")
    puntos = (base.mark_point(size=70, filled=True, stroke=FONDO, strokeWidth=1.5)
              .encode(opacity=alt.condition(cerca, alt.value(1), alt.value(0)), tooltip=recuadro).add_params(cerca))
    capas = ([alt.Chart(largo).mark_rule(color=CERO, strokeWidth=1, strokeDash=[4, 3]).encode(y=alt.datum(0))]
             if cero else []) + [base.mark_line(strokeWidth=1.6), puntos]
    st.altair_chart(alt.layer(*capas).properties(background="transparent")
                    .configure_view(stroke=None).configure(locale=LOCALE_ES), width="stretch")


def fila(etiqueta, valor):
    return f'<div class="fila"><span>{etiqueta}</span><span>{valor}</span></div>'


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_ubicacion(nodos, firma):
    """v0.6.0 · Catálogo de referencia unido a la lista de nodos (left join: no se pierde ninguno).

    `firma` (tamaño y fecha del archivo) solo sirve para que la caché se renueve si cambia el catálogo.
    Devuelve {} si el catálogo falta o no pasa su validación: la app sigue funcionando solo con claves.
    """
    try:
        df, manifiesto = cat_nodos.cargar()
    except (cat_nodos.CatalogoInvalido, OSError, ValueError):
        return {}
    union = cat_nodos.unir(nodos, df)
    return {"union": union, "nombres": dict(zip(union["nodo"], union["nombre"])), "manifiesto": manifiesto}


def firma_catalogo():
    ruta = cat_nodos.REFERENCIA_DIR / cat_nodos.ARCHIVO
    return f"{ruta.stat().st_size}:{ruta.stat().st_mtime_ns}" if ruta.is_file() else ""


def limpiar_ubicacion(key):
    """Callback de «Limpiar ubicación»: vuelve Región, Estado y Zona a «Todas» sin tocar el nodo elegido."""
    for filtro in ("region", "estado", "zona"):
        st.session_state[f"{key}_{filtro}"] = TODAS


def _elegir(etiqueta, opciones, clave):
    """Selectbox de un filtro; si su valor anterior ya no existe con los otros filtros, vuelve a «Todas»."""
    opciones = [TODAS] + opciones
    if st.session_state.get(clave, TODAS) not in opciones:
        st.session_state[clave] = TODAS
    valor = st.selectbox(etiqueta, opciones, key=clave)
    return None if valor == TODAS else valor


def filtros_ubicacion(key, nodos, en_columnas):
    """v0.6.0 · Región de Control, Estado y Zona de carga (catálogo CENACE) antes del selector de nodo.

    Solo acotan la lista de opciones. Nunca cambian el nodo elegido: si queda fuera del filtro se
    conserva al inicio de la lista con un aviso (decisión aprobada 2026-11-12). No van en la URL.
    El estado es un filtro paralelo (fase 2, aprobado 2026-11-12): se aplica nodo por nodo, porque
    una zona de carga puede abarcar varios estados.
    """
    union = UBICACION["union"]
    c1, c2, c3 = st.columns(3) if en_columnas else (st.container(), st.container(), st.container())
    with c1:
        region = _elegir("Región de Control", cat_nodos.regiones(union), f"{key}_region")
    with c2:
        estado = _elegir("Estado", cat_nodos.estados(union, region), f"{key}_estado")
    with c3:
        zona = _elegir("Zona de carga", cat_nodos.zonas(union, region, estado), f"{key}_zona")
    if region is None and estado is None and zona is None:
        return nodos
    filtrados = cat_nodos.filtrar(union, region, zona, estado)
    actual = st.session_state[key]
    if actual not in filtrados:
        st.caption(f"{actual} está fuera de este filtro; se conserva hasta que elijas otro nodo.")
        filtrados = [actual] + filtrados
    st.button("Limpiar ubicación", key=f"{key}_limpiar", on_click=limpiar_ubicacion, args=(key,))
    return filtrados


def ubicacion_de(nodo):
    """Texto bajo el selector: región, zona y estado del nodo, o «sin clasificación verificada»."""
    fila = UBICACION["union"].set_index("nodo").loc[nodo]
    if not fila["clasificado"]:
        return f"{nodo}: {cat_nodos.SIN_CLASIFICACION.lower()} en el catálogo CENACE; disponible por su clave."
    texto = f"Región {fila['region_control'].title()} · Zona de carga {fila['zona_carga'].title()}"
    return texto + (f" · {fila['estado'].title()}" if isinstance(fila["estado"], str) else "")


def selector_nodo(nodos, etiqueta, key, defecto, en_columnas=True, al_cambiar=None):
    """Selector de NodoP: búsqueda directa por clave o nombre y, si hay catálogo, filtros de ubicación.

    El valor del widget es siempre la clave (la URL y los cálculos no cambian); el nombre solo se muestra.
    """
    # v0.5.1: el valor inicial va en session_state, como las fechas, porque un enlace compartido puede haberlo
    # escrito antes; con `index=` Streamlit avisaría de «valor por defecto y Session State a la vez».
    st.session_state.setdefault(key, defecto if defecto in nodos else nodos[0])
    if not UBICACION:
        return st.selectbox(etiqueta, nodos, key=key, placeholder="Clave, p. ej. 06ESC", help=AYUDA_SOLO_CLAVE,
                            on_change=al_cambiar)
    opciones = filtros_ubicacion(key, nodos, en_columnas)
    nombres = UBICACION["nombres"]
    nodo = st.selectbox(etiqueta, opciones, key=key, format_func=lambda n: cat_nodos.etiqueta(n, nombres),
                        placeholder="Clave o nombre, p. ej. 06ESC", help=AYUDA_NODO, on_change=al_cambiar)
    st.caption(ubicacion_de(nodo))
    return nodo


def vista_1(limites, nodos, fechas_nodo, version, panel):
    """Vista 1: PML histórico de un nodo."""
    with panel:
        st.caption(SIN_RESULTADOS)  # encima: la lista «No results» de Streamlit taparía un texto inferior
        nodo = selector_nodo(nodos, "Nodo · clave o nombre", "nodo", "01AAN-85")
        inicio, fin, resolucion = controles_rango(limites)
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo)

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
            grafica(df, "pml_promedio", "PML (MXN/MWh)", resolucion, nodo=nodo)
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
    descarga_csv("historico", exportar.tabla_historico(df, nodo, resolucion), [nodo], inicio, fin, resolucion)
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
            nodo_a = selector_nodo(nodos, "Nodo A · clave o nombre", "nodo_a", "01AAN-85", en_columnas=False)
        with cb:
            nodo_b = selector_nodo(nodos, "Nodo B · clave o nombre", "nodo_b", defecto_b, en_columnas=False)
        inicio, fin, resolucion = controles_rango(limites)
        for n in (nodo_a, nodo_b):
            if n in fechas_nodo:
                st.caption(f"{n} tiene datos del {fechas_nodo[n][0]} al {fechas_nodo[n][1]}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo_a, nodo_b)

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
    # v0.6.4 · Quién es más caro, en palabras: solo lee el signo del spread promedio ya calculado.
    if pd.notna(r["promedio"]) and r["promedio"] != 0:
        caro, barato = (nodo_a, nodo_b) if r["promedio"] > 0 else (nodo_b, nodo_a)
        st.markdown(f'<div class="linea-meta">En promedio del periodo, <b>{caro}</b> fue más caro que {barato} por '
                    f'<b>{mxn(abs(r["promedio"]))} MXN/MWh</b>.</div>', unsafe_allow_html=True)
    if UBICACION:
        nombres = UBICACION["nombres"]
        st.caption(f"A: {cat_nodos.etiqueta(nodo_a, nombres)} · B: {cat_nodos.etiqueta(nodo_b, nombres)}")
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
            grafica(d, "dif_promedio", "Spread A − B (MXN/MWh)", resolucion, nodo=f"{nodo_a} − {nodo_b}", cero=True)
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
    # v0.6.4 · Las curvas de cada nodo pasan a una segunda tarjeta, debajo: en móvil ya no compiten con el spread
    # por la primera pantalla y la ficha del spread queda justo después de su gráfica.
    with st.container(key="tarjeta_curvas"):
        st.markdown("**PML de cada nodo (MXN/MWh)** · A continua, B punteada · cada curva con todas sus horas con dato")
        grafica_series(curvas, [nodo_a, nodo_b], [NARANJA, AZUL], resolucion, titulo_serie="Nodo")
    descarga_csv("comparacion", exportar.tabla_spread(d, nodo_a, nodo_b, resolucion), [nodo_a, nodo_b], inicio, fin,
                 resolucion)
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
        nodo = selector_nodo(nodos, "Nodo · clave o nombre", "nodo", "01AAN-85")
        inicio, fin, resolucion = controles_rango(limites)
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo)

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
    colores = [NARANJA, AZUL, GRIS]
    largo = df.melt(id_vars=["periodo", "etiqueta"], value_vars=list(nombres), var_name="componente", value_name="valor")
    largo["componente"] = largo["componente"].map(nombres)
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown("**Componentes del PML (barras apiladas, MXN/MWh)** · los negativos quedan debajo del cero")
            st.altair_chart((alt.Chart(largo).mark_bar().encode(
                x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
                y=alt.Y("valor:Q", title=None, stack="zero",
                        axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5)),
                color=alt.Color("componente:N", title=None, sort=list(nombres.values()),
                                scale=alt.Scale(domain=list(nombres.values()), range=colores),
                                legend=alt.Legend(orient="top", direction="horizontal", title=None)),
                tooltip=[alt.Tooltip("etiqueta:N", title="Periodo"), alt.Tooltip("componente:N", title="Componente"),
                         alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f")])
                + alt.Chart(largo).mark_rule(color=CERO, strokeWidth=1).encode(y=alt.datum(0)))
                .properties(background="transparent").configure_view(stroke=None).configure(locale=LOCALE_ES),
                width="stretch")
            st.markdown("**Pérdidas y congestión (MXN/MWh)** · la parte propia del nodo, a su escala")
            grafica_series(df.rename(columns={"perdidas": "Pérdidas", "congestion": "Congestión"}),
                           ["Pérdidas", "Congestión"], colores[1:], resolucion, titulo_serie="Componente", nodo=nodo,
                           cero=True)
        with der, st.container(key="ficha"):
            st.metric("PML promedio", mxn(r["pml"]))
            st.metric("Energía", mxn(r["energia"]))
            st.metric("Pérdidas", mxn(r["perdidas"]))
            st.metric("Congestión", mxn(r["congestion"]))
            st.markdown(fila("Cobertura", f"{r['cobertura_pct']}%"), unsafe_allow_html=True)
            # v0.6.4 · Detalle técnico plegado: el resumen principal es PML + sus tres componentes. El aviso de
            # descuadre sobre el umbral sigue arriba, fuera de este bloque.
            with st.expander("Detalle técnico"):
                st.metric("Horas con congestión > 0", f"{int(r['horas_congestion_positiva']):,}")
                st.metric("Horas con congestión < 0", f"{int(r['horas_congestion_negativa']):,}")
                st.metric("Descuadre máximo", f"{r['descuadre_max']:,.4f}",
                          help="Máximo de |PML − (energía + pérdidas + congestión)| en una hora. Viene del redondeo de CENACE.")
    descarga_csv("componentes", exportar.tabla_componentes(df, nodo, resolucion), [nodo], inicio, fin, resolucion)
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


def selector_zona(zonas, al_cambiar=None):
    """v0.7.0 · Zona de carga con filtro opcional de Región de Control (decisión E: sin filtro de estado).

    Igual que con los nodos, el filtro solo acota la lista; nunca cambia la zona elegida.
    """
    st.session_state.setdefault("zona", ZONA_DEFECTO if ZONA_DEFECTO in zonas else zonas[0])
    opciones = zonas
    if PND["regiones"]:
        c1, c2 = st.columns([1, 2])
        with c1:
            region = _elegir("Región de Control", sorted(PND["regiones"]), "zona_region")
        if region is not None:
            opciones = [z for z in PND["regiones"][region] if z in zonas]
            if st.session_state["zona"] not in opciones:
                st.caption(f"{st.session_state['zona']} está fuera de esta región; se conserva hasta que elijas otra zona.")
                opciones = [st.session_state["zona"]] + opciones
        destino = c2
    else:
        destino = st.container()
    with destino:
        zona = st.selectbox("Zona de carga", opciones, key="zona", format_func=str.title, on_change=al_cambiar,
                            help="Zona de carga del SIN según CENACE. El PND es el precio de la zona, no de un nodo.")
    regiones = [r for r, zs in PND["regiones"].items() if zona in zs]
    if regiones:
        st.caption(f"Región de Control: {', '.join(r.title() for r in sorted(regiones))}")
    return zona


def vista_pnd(panel):
    """v0.7.0 · Precio de zona de carga (PND) histórico de una zona. Carril separado: no usa ningún dato PML."""
    limites, fechas_zona, version = PND["limites"], PND["zonas"], PND["version"]
    zonas = list(fechas_zona)
    with panel:
        zona = selector_zona(zonas)
        inicio, fin, resolucion = controles_rango(limites)
        primera, ultima = fechas_zona.get(zona, (None, None))
        if primera:
            st.caption(f"{zona.title()} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state.get("vista", VISTAS_URL["historico"]))
    solista_pnd(zona)

    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    if resolucion == "horaria" and (fin - inicio).days + 1 > PND_HORARIA_MAX_DIAS:
        st.warning(f"La resolución horaria admite hasta {PND_HORARIA_MAX_DIAS} días. "
                   "Acorta el rango o elige diaria o mensual.")
        st.stop()

    try:
        e = consultar_estadisticas_pnd(zona, inicio, fin, str(pnd_zonas.PND_DIR), version).iloc[0]
        df = consultar_serie_pnd(zona, inicio, fin, resolucion, str(pnd_zonas.PND_DIR), version)
    except (duckdb.Error, OSError):
        st.error("No se puede consultar el rango con el paquete público de PND. Es necesario revisar sus archivos.")
        st.stop()

    sin_dato = [d for d in limites["dias_sin_dato"] if inicio <= d <= fin]
    if e["horas_con_dato"] == 0:
        st.warning(f"Sin datos de PND para {zona.title()} entre {inicio} y {fin}. No se muestra ninguna "
                   "cifra: la ausencia de datos no equivale a precio cero."
                   + (" Ese periodo no tiene dato disponible en la consulta verificada al servicio de CENACE; "
                      "se reintenta en cada actualización." if sin_dato else ""))
        st.stop()

    st.subheader(f"{zona.title()}: precio de zona de carga (PND), {inicio} a {fin}")
    con_dato, del_rango = int(e["horas_con_dato"]), int(e["horas_del_rango"])
    desde_obs, hasta_obs = e["primera_fecha"].date(), e["ultima_fecha"].date()

    def pnd_del_dia(d):
        x = consultar_estadisticas_pnd(zona, d, d, str(pnd_zonas.PND_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["promedio"]
    cabecera(pnd_del_dia, hasta_obs, limites, "PND promedio")
    st.markdown(f"Zona de carga · MDA · SIN · CENACE | **Cobertura:** {e['cobertura_pct']}% ({con_dato:,} de "
                f"{del_rango:,} horas con dato) | **Rango con observaciones:** {desde_obs} a {hasta_obs}")
    if sin_dato:
        evidencia = limites["evidencia_sin_dato"]
        detalle = "; ".join(f"{d} (consulta verificada {evidencia[d]['consultado_utc']})" for d in sin_dato)
        st.warning(f"Sin dato disponible en la consulta verificada al servicio de CENACE: {detalle}. Ese día no "
                   "tiene precio en el paquete (no es cero ni se rellena) y la cobertura lo cuenta como faltante; "
                   "se vuelve a consultar en cada actualización.")
    if e["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura escasa: los indicadores describen solo {con_dato:,} horas, entre {desde_obs} y "
                   f"{hasta_obs}. Las horas sin dato no se tratan como cero.")
    corregidos = [d for d in limites["dias_corregidos"] if inicio <= d <= fin]
    if corregidos:
        st.caption(f"Días corregidos por CENACE después de su primera publicación: {', '.join(map(str, corregidos))}.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    titulo = {"horaria": "PND horario", "diaria": "PND promedio diario", "mensual": "PND promedio mensual"}[resolucion]
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown(f"**{titulo} (MXN/MWh)**")
            grafica(df, "pnd_promedio", "PND (MXN/MWh)", resolucion, nodo=zona.title(), titulo_serie="Zona")
        with der, st.container(key="ficha"):
            st.markdown(barra_rango("Rango horario del periodo", e["minimo"], e["maximo"], e["promedio"]),
                        unsafe_allow_html=True)
            st.metric("Promedio horario", mxn(e["promedio"]), help="Promedio simple de las horas con dato.")
            st.metric("Mediana horaria", mxn(e["mediana"]))
            st.metric("Mínimo horario", mxn(e["minimo"]), help="Menor PND de una hora en el rango.")
            st.metric("Máximo horario", mxn(e["maximo"]), help="Mayor PND de una hora en el rango.")
            st.metric("Horas con PND < 0", f"{int(e['horas_negativas']):,}")
            st.markdown(fila("Energía", mxn(e["energia"])) + fila("Pérdidas", mxn(e["perdidas"]))
                        + fila("Congestión", mxn(e["congestion"])) + fila("Desv. estándar", mxn(e["desv_std"]))
                        + fila("Percentil 10", mxn(e["p10"])) + fila("Percentil 90", mxn(e["p90"]))
                        + fila("Cobertura", f"{e['cobertura_pct']}%"), unsafe_allow_html=True)
    descarga_csv("pnd", exportar.tabla_pnd(df, zona, resolucion), [zona], inicio, fin, resolucion,
                 ayuda="Los datos de esta gráfica: fecha, hora (si es horaria), zona de carga, PND y sus componentes "
                       "en MXN/MWh.")
    st.caption(f"Indicadores calculados sobre las {con_dato:,} horas con dato, en MXN/MWh"
               + ("." if resolucion == "horaria" else f", aunque la gráfica sea {resolucion}.")
               + " Energía, pérdidas y congestión: promedios sobre las mismas horas.")
    avisos_parciales(df, resolucion)

    with st.expander("Tabla del PND y sus componentes"):
        tabla = df[["etiqueta", "pnd_promedio", "energia", "perdidas", "congestion", "horas", "horas_posibles"]].rename(
            columns={"etiqueta": "Periodo", "pnd_promedio": "PND", "energia": "Energía", "perdidas": "Pérdidas",
                     "congestion": "Congestión", "horas": "Horas con dato", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.2f")
                                    for c in ("PND", "Energía", "Pérdidas", "Congestión")})

# ---------------------------------------------------------------------------------------------------------------
# v0.8.0 · Graphite Trading | Ensemble & Solo. ENSEMBLE es el tablero compacto del mercado; SOLO son las vistas de
# v0.7.0 con el nodo o la zona como protagonista. Cambiar de escena es un callback: un solo rerun, sin animaciones,
# y las consultas ya hechas se reutilizan de la caché. Ver escena.py (URL) y ensemble.py (consultas).
# ---------------------------------------------------------------------------------------------------------------

def entrar_solo(modalidad, elemento):
    """Callback: pasa a SOLO con `elemento` (nodo PML o zona PND) como protagonista. Fechas y resolución se conservan.

    PML abre en la vista 1 y deja el nodo también como nodo A de «Comparar» (decisión D3); PND abre su histórico.
    """
    estado = st.session_state
    if PND:
        estado["modalidad"] = modalidad
        ajustar_fechas_modalidad()
    if modalidad == "pnd":
        estado["zona"] = elemento
    else:
        estado["nodo"] = estado["nodo_a"] = elemento
        estado["vista"] = VISTAS_URL["historico"]
    estado["escena"] = SOLO
    descartar_avisos()


def entrar_solo_seleccion():
    """Callback del panel derecho: el nodo o la zona que está elegido en su selector."""
    if PND and st.session_state.get("modalidad") == "pnd":
        entrar_solo("pnd", st.session_state["zona"])
    else:
        entrar_solo("pml", st.session_state["nodo"])


def volver_al_mercado():
    """Callback de «Volver al mercado»: ENSEMBLE con las mismas fechas, resolución, modalidad y última selección."""
    st.session_state["escena"] = ENSEMBLE
    descartar_avisos()


def solista_pml(nodo, nodo_b=None):
    """Encabezado de SOLO PML: el nodo protagonista (o A − B en «Comparar») con su nombre oficial y ubicación."""
    nombres = UBICACION.get("nombres", {}) if UBICACION else {}
    if nodo_b:
        titulo, detalle = f"{nodo} <span class='vs'>vs</span> {nodo_b}", (
            f"{nombres.get(nodo) or nodo} · {nombres.get(nodo_b) or nodo_b}" if nombres else "")
    else:
        titulo = nodo
        detalle = (f"{nombres.get(nodo) or ''} · {ubicacion_de(nodo)}".lstrip(" ·") if UBICACION else "")
    st.markdown(f'<div class="solista pml"><span class="et">SOLO · PML · NodoP</span><span class="nombre">{titulo}'
                f'</span><span class="detalle">{detalle}</span></div>', unsafe_allow_html=True)


def solista_pnd(zona):
    """Encabezado de SOLO PND: la zona de carga protagonista y su Región de Control."""
    regiones = sorted(r.title() for r, zs in PND.get("regiones", {}).items() if zona in zs)
    detalle = f"Región de Control: {', '.join(regiones)}" if regiones else "Zona de carga del SIN"
    st.markdown(f'<div class="solista pnd"><span class="et">SOLO · PND · Zona de carga</span><span class="nombre">'
                f'{zona.title()}</span><span class="detalle">{detalle}</span></div>', unsafe_allow_html=True)


def actualizar_url_ensemble():
    """URL de ENSEMBLE: solo fechas y resolución. Un enlace con fechas inválidas avisa igual que en SOLO."""
    estado = st.session_state
    enlace = enlace_ensemble({clave: estado.get(clave) for clave in ("desde", "hasta", "resolucion")})
    problemas, _ = estado.get("enlace_avisos", ([], []))
    if problemas and enlace != estado.setdefault("enlace_inicial", enlace):
        problemas = []
        descartar_avisos()
    if problemas:
        st.error("Este enlace no se puede abrir tal cual:\n\n" + "\n".join(f"- {p}" for p in problemas)
                 + "\n\nNo se muestra ninguna cifra para no presentar un análisis distinto del compartido. "
                 "Corrige las fechas en el panel o continúa con la configuración que se ve ahí.")
        st.button("Continuar con la configuración mostrada", on_click=descartar_avisos)
        st.stop()
    actual = st.query_params.to_dict()
    nuevo = {k: v for k, v in actual.items() if k not in PARAMETROS} | enlace  # conserva parámetros ajenos
    if nuevo != actual:
        st.query_params.from_dict(nuevo)


def panel_ensemble(nodos, limites_activos):
    """Panel derecho de ENSEMBLE: elegir el solista (nodo PML o zona PND) y los filtros que se conservan."""
    with st.container(key="atril"):
        st.markdown("**Elige el solista**")
        st.caption("Al elegir un nodo o una zona se abre su vista SOLO. «Volver al mercado» regresa aquí.")
        if PND:
            st.radio("Precio", list(MODALIDADES), key="modalidad", horizontal=True, format_func=MODALIDADES.get,
                     on_change=ajustar_fechas_modalidad,
                     help="PML: precio de un nodo (NodoP). PND: precio de una zona de carga. No se mezclan.")
        if PND and st.session_state.get("modalidad") == "pnd":
            selector_zona(list(PND["zonas"]), al_cambiar=entrar_solo_seleccion)
        else:
            selector_nodo(nodos, "Nodo · clave o nombre", "nodo", "01AAN-85", en_columnas=False,
                          al_cambiar=entrar_solo_seleccion)
        st.button("Abrir en SOLO", key="abrir_solo", type="primary", icon=":material/open_in_full:",
                  on_click=entrar_solo_seleccion, width="stretch")
        controles_rango(limites_activos, en_columnas=False)
        st.caption("ENSEMBLE usa «Hasta» como día de referencia. «Desde» y la resolución se aplican al abrir SOLO.")


def kpis(celdas):
    """Indicadores compactos en rejilla (4 → 2 → 1 columnas según el ancho). `celdas`: [(etiqueta, valor, nota)]."""
    html = "".join(f'<div class="kpi"><div class="et">{e}</div><div class="v">{v}</div><div class="nota">{n}</div></div>'
                   for e, v, n in celdas)
    st.markdown(f'<div class="kpis">{html}</div>', unsafe_allow_html=True)


def distribucion(ranking, color, unidad):
    """Gráfica compacta de distribución: cuántos elementos tienen su promedio del día en cada intervalo.

    Solo agrupa los promedios del ranking para dibujarlos; no calcula ningún indicador nuevo.
    """
    df = ranking[["elemento", "promedio"]]
    intervalos = alt.Bin(maxbins=30)
    grafica_ = alt.Chart(df).mark_bar(color=color, opacity=.9, cornerRadiusTopLeft=1, cornerRadiusTopRight=1).encode(
        x=alt.X("promedio:Q", bin=intervalos, title=None,
                axis=alt.Axis(grid=False, domain=False, tickColor=EJE, format=",.0f", labelOverlap=True)),
        y=alt.Y("count():Q", title=None,
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=3)),
        tooltip=[alt.Tooltip("promedio:Q", bin=intervalos, title="Promedio del día (MXN/MWh)", format=",.2f"),
                 alt.Tooltip("count():Q", title=unidad)])
    st.altair_chart(grafica_.properties(height=ALTO_DISTRIBUCION, background="transparent")
                    .configure_view(stroke=None).configure(locale=LOCALE_ES), width="stretch")


def lista_ranking(titulo, filas, modalidad, clave, etiqueta):
    """Filas del ranking como botones: tocar una abre SOLO de ese nodo o zona."""
    with st.container(key=clave):
        st.markdown(f'<div class="lista-et">{titulo}</div>', unsafe_allow_html=True)
        for i, fila_ in enumerate(filas.itertuples()):
            parcial = f" · {fila_.horas} h" if fila_.horas < 24 else ""
            st.button(f"{etiqueta(fila_.elemento)} · {mxn(fila_.promedio)}{parcial}", key=f"{clave}_{i}",
                      on_click=entrar_solo, args=(modalidad, fila_.elemento), width="stretch",
                      help=f"Abrir SOLO de {fila_.elemento}. Promedio de {fila_.horas} horas con dato, MXN/MWh.")


def seccion_pml(dia, total, version):
    with st.container(key="seccion_pml"):
        st.markdown(f'<div class="seccion-et"><span class="marca pml"></span><b>PML · NodoP</b>'
                    f'<span>Precio Marginal Local por nodo · día {dia} · CENACE SW-PML, MDA, SIN</span></div>',
                    unsafe_allow_html=True)
        try:
            ranking = consultar_ranking_pml(dia, str(DATA_DIR), version)
        except (DatosNoDisponibles, duckdb.Error):
            st.error("No se puede consultar el día con el paquete público PML. Es necesario revisar sus particiones.")
            return
        if ranking.empty:
            st.warning(f"Ningún nodo tiene PML el {dia}. No se muestra ninguna cifra: sin dato no es precio cero.")
            return
        r = ens.resumen(ranking, total)
        kpis([("Nodos con dato", f"{r['con_dato']:,}", f"de {total:,} en el paquete · {r['sin_dato']:,} sin dato"),
              ("Más caro", mxn(r["caro"]["promedio"]), r["caro"]["elemento"]),
              ("Más barato", mxn(r["barato"]["promedio"]), r["barato"]["elemento"]),
              ("Nodos con alguna hora < 0", f"{r['con_negativos']:,}", "PML horario negativo ese día")])
        st.markdown('<div class="mini-et">Distribución del PML promedio del día entre nodos (MXN/MWh)</div>',
                    unsafe_allow_html=True)
        distribucion(ranking, NARANJA, "Nodos")
        caros, baratos = st.columns(2, gap="medium")
        with caros:
            lista_ranking("Más caros", ranking.head(RANKING_N), "pml", "rk_pml_caros", str)
        with baratos:
            lista_ranking("Más baratos", ranking.tail(RANKING_N).iloc[::-1], "pml", "rk_pml_baratos", str)
        st.caption("Promedio simple de las horas con dato de cada nodo ese día, el mismo valor que su vista SOLO. "
                   + (f"{r['incompletos']:,} nodos tienen menos de 24 horas con dato. " if r["incompletos"] else "")
                   + "Un nodo sin horas con dato no entra al ranking ni se trata como cero.")


def seccion_pnd(hasta):
    lim = PND["limites"]
    carpeta = str(pnd_zonas.PND_DIR)
    dia = ens.dia_pnd(hasta, lim, carpeta)
    with st.container(key="seccion_pnd"):
        st.markdown(f'<div class="seccion-et"><span class="marca pnd"></span><b>PND · Zona de carga</b>'
                    f'<span>Precio de zona de carga · día {dia or "—"} · CENACE SW-PEND, MDA, SIN</span></div>',
                    unsafe_allow_html=True)
        if dia is None:
            st.warning(f"El paquete PND no tiene datos hasta el {hasta}. No se muestra ninguna cifra.")
            return
        if dia < min(hasta, lim["hasta"]):
            st.caption(f"El {min(hasta, lim['hasta'])} no tiene PND en el paquete (sin dato, no cero); "
                       f"se muestra el último día con dato, {dia}.")
        try:
            ranking = consultar_ranking_pnd(dia, carpeta, PND["version"])
        except (duckdb.Error, OSError):
            st.error("No se puede consultar el día con el paquete público de PND. Es necesario revisar sus archivos.")
            return
        total = len(PND["zonas"])
        r = ens.resumen(ranking, total)
        kpis([("Zonas con dato", f"{r['con_dato']:,}", f"de {total:,} zonas de carga · {r['sin_dato']:,} sin dato"),
              ("Más cara", mxn(r["caro"]["promedio"]), r["caro"]["elemento"].title()),
              ("Más barata", mxn(r["barato"]["promedio"]), r["barato"]["elemento"].title()),
              ("Zonas con alguna hora < 0", f"{r['con_negativos']:,}", "PND horario negativo ese día")])
        st.markdown('<div class="mini-et">Distribución del PND promedio del día entre zonas de carga (MXN/MWh)</div>',
                    unsafe_allow_html=True)
        distribucion(ranking, AZUL, "Zonas")
        caras, baratas = st.columns(2, gap="medium")
        with caras:
            lista_ranking("Más caras", ranking.head(RANKING_N), "pnd", "rk_pnd_caras", str.title)
        with baratas:
            lista_ranking("Más baratas", ranking.tail(RANKING_N).iloc[::-1], "pnd", "rk_pnd_baratas", str.title)
        st.caption("PND publicado por CENACE para cada zona; promedio simple de sus horas con dato ese día, el mismo "
                   "valor que su vista SOLO. No se compara con el PML de ningún nodo.")


def vista_ensemble(limites, nodos, version, limites_activos):
    """v0.8.0 · ENSEMBLE: el mercado del día de referencia, PML y PND en secciones separadas, y el panel derecho."""
    with st.container(key="ensemble"):
        principal, derecho = st.columns([2.7, 1], gap="large")
        with derecho:
            panel_ensemble(nodos, limites_activos)
        with principal:
            actualizar_url_ensemble()
            hasta = st.session_state["hasta"]
            seccion_pml(ens.dia_pml(hasta, limites), len(nodos), version)
            if PND:
                seccion_pnd(hasta)
            else:
                st.caption("PND por zona de carga no está en esta publicación; el tablero muestra solo PML.")


def metodologia_ensemble():
    with st.expander("Metodología · Ensemble"):
        st.markdown("""
- **Qué muestra:** el día de referencia («Hasta», acotado a cada paquete) de **todos** los nodos PML y, por separado, de **todas** las zonas de carga PND. PML y PND tienen su propio paquete y su propio día; nunca se combinan ni se comparan entre sí.
- **Promedio del día:** el mismo valor que la vista SOLO de ese nodo o zona para ese día: promedio simple de sus horas con dato (fuera de la ventana horaria PML, suma ÷ horas válidas del diario). El tablero solo **ordena** esos valores y **cuenta** elementos; no hay índices, promedios entre nodos ni ponderaciones nuevas.
- **Distribución:** cuántos nodos (o zonas) tienen su promedio del día en cada intervalo de precio. Agrupa los mismos promedios para dibujarlos; no es un indicador nuevo.
- **Faltantes:** un nodo o una zona sin horas con dato ese día no entra al ranking ni se trata como cero; se cuenta como «sin dato». Si un día PND no tiene dato, se usa el último día anterior con dato y se dice.
- **Solo:** tocar un nodo o una zona abre su vista SOLO con las fechas y la resolución del panel. «Volver al mercado» regresa con los mismos filtros.
""")


def conservar_widgets():
    """v0.7.0 · Streamlit borra el estado de un widget que no se dibuja en una corrida. Al pasar a PND (o volver a
    PML) se ocultan pestañas y selectores de la otra modalidad; reescribir su valor lo conserva para el regreso."""
    claves = ["vista", "zona", "zona_region"] + [f"{n}{s}" for n in ("nodo", "nodo_a", "nodo_b")
                                                for s in ("", "_region", "_estado", "_zona")]
    for clave in claves:
        if clave in st.session_state:
            st.session_state[clave] = st.session_state[clave]


st.set_page_config(page_title="PML Explorer", page_icon=str(ASSETS / "logo.svg"), layout="wide",
                   initial_sidebar_state="collapsed")
st.html(ESTILOS)
# H01: regreso explícito al sitio editorial, fuera de cualquier panel para que se vea en las tres vistas.
st.markdown(f"[← Mercados · edarji.net]({SITIO_MERCADOS})")
# v0.6.4: logo y título en un contenedor horizontal, para que en móvil queden en la misma fila.
with st.container(key="marca", horizontal=True, vertical_alignment="center", gap="medium"):
    logo()
    with st.container():
        st.title("PML Explorer")
        # v0.7.0 · El subtítulo depende de la modalidad (se conoce más abajo, tras leer el enlace): hueco reservado.
        subtitulo = st.empty()
        subtitulo.caption("Precio Marginal Local · Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · "
                          "datos diarios publicados, no en tiempo real")

if not (DATA_DIR / "metadata.json").is_file():
    st.info("Los derivados públicos de CENACE todavía no están disponibles en esta publicación.")
    st.stop()

try:
    # La versión de la app entra en la llave de la caché: al publicar una versión nueva, ningún resultado
    # guardado por el código anterior se reutiliza (v0.6.2: KeyError pml_a tras el despliegue).
    version = huella_paquete() + VERSION_APP
    limites, nodos, fechas_nodo = cargar_paquete(str(DATA_DIR), version)
except (DatosNoDisponibles, duckdb.Error):
    st.error("El paquete público está incompleto o su esquema no es compatible. La integración debe validarse antes de publicar cifras.")
    st.stop()

if not nodos:
    st.warning("El paquete público no contiene nodos con datos.")
    st.stop()
UBICACION.update(cargar_ubicacion(tuple(nodos), firma_catalogo()))
# v0.7.0 · PND: solo si la carpeta pública pnd/ existe y cumple su contrato. Si falla, PML sigue igual.
if (pnd_zonas.PND_DIR / "metadata.json").is_file():
    try:
        version_pnd = pnd_zonas.huella_pnd() + VERSION_APP
        limites_pnd, fechas_zona = cargar_pnd(str(pnd_zonas.PND_DIR), version_pnd)
        regiones_pnd = pnd_zonas.regiones_de_zonas(UBICACION["union"]) if UBICACION else {}
        PND.update(limites=limites_pnd, zonas=fechas_zona, version=version_pnd, limites_pml=limites,
                   regiones={r: [z for z in zs if z in fechas_zona] for r, zs in regiones_pnd.items()})
    except Exception:  # noqa: BLE001 — cualquier falla del paquete PND solo deshabilita PND; PML sigue igual
        PND.clear()


VISTAS = {VISTAS_URL["historico"]: vista_1, VISTAS_URL["comparacion"]: vista_2, VISTAS_URL["componentes"]: vista_3}
# v0.5.1: un enlace compartido elige vista y filtros antes de que se dibujen (ver enlaces.py).
leer_url(nodos, limites)
# H07: vista y filtros en un panel con texto visible dentro del contenido, cerrado al iniciar, en vez de la
# barra lateral (en móvil quedaba sobre los resultados o como un icono sin texto). Cerrarlo no borra la selección.
# v0.5: las vistas son una barra de pestañas visible arriba; nodo, fechas y resolución siguen en el panel.
conservar_widgets()
# v0.8.0 · Graphite Trading: ENSEMBLE (tablero del mercado) o SOLO (un nodo o una zona). Ver escena.py.
en_solo = st.session_state["escena"] == SOLO
if en_solo:
    st.button("Volver al mercado", key="volver", icon=":material/arrow_back:", on_click=volver_al_mercado,
              help="Regresa al tablero ENSEMBLE con las mismas fechas, resolución y selección.")
if PND and en_solo:
    # v0.7.0 · Modalidad: PML por nodo (como siempre) o PND por zona de carga. Sin PND publicado no se dibuja.
    # v0.8.0: en ENSEMBLE el mismo selector va en el panel derecho.
    st.radio("Precio", list(MODALIDADES), key="modalidad", horizontal=True, format_func=MODALIDADES.get,
             on_change=ajustar_fechas_modalidad,
             help="PML: precio de un nodo (NodoP). PND: precio de una zona de carga, con el que se liquida la demanda.")
modo_pnd = bool(PND) and st.session_state.get("modalidad") == "pnd"
if en_solo:
    subtitulo.caption(("Precio de zona de carga (PND) · " if modo_pnd else "Precio Marginal Local · ")
                      + "Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · datos diarios publicados, no en tiempo real")
else:
    subtitulo.caption("Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · PML por nodo y PND por zona de carga, "
                      "por separado · datos diarios publicados, no en tiempo real")
limites_activos = PND["limites"] if modo_pnd else limites
col_pestanas, col_rangos = st.columns([3, 1], vertical_alignment="bottom")
with col_pestanas, st.container(key="pestanas"):
    if not en_solo:
        st.markdown("**Mercado · ENSEMBLE** · el día de referencia de todos los nodos y zonas de carga")
    elif modo_pnd:
        st.markdown("**Precio de zona de carga (PND)** · histórico por zona")
    else:
        vista = st.radio("Vista", list(VISTAS), key="vista", horizontal=True, label_visibility="collapsed",
                         format_func=lambda v: v.split(". ", 1)[1])
with col_rangos:
    botones_rango(limites_activos)
# Si el enlace trae problemas, el panel abre solo para corregirlos. v0.8.0: en ENSEMBLE el panel es la columna derecha.
panel = st.expander("Vista y filtros", expanded=st.session_state["panel_abierto"]) if en_solo else None
# El contenido va en un contenedor creado antes que el pie: si una vista se detiene con st.stop()
# (sin datos, fechas invertidas), metodología y fechas disponibles siguen visibles debajo.
contenido = st.container()
if not en_solo:
    metodologia_ensemble()
if not en_solo and PND:
    metodologia()
    metodologia_pnd()
    lp = PND["limites"]
    st.caption(f"PML Explorer {VERSION_APP} · PML: esquema v{metadata()['version_esquema']}, {limites['desde']} a "
               f"{limites['hasta']}, actualización {actualizado_cdmx(limites['generado_utc'])} · PND: contrato v1, "
               f"{lp['desde']} a {lp['hasta']} ({lp['zonas']} zonas), actualización "
               f"{actualizado_cdmx(lp['generado_utc'])} · Ciudad de México.")
elif modo_pnd:
    metodologia_pnd()
    lp = PND["limites"]
    st.caption(f"PML Explorer {VERSION_APP} · PND: contrato v1 · Fechas de operación disponibles: {lp['desde']} a "
               f"{lp['hasta']} ({lp['zonas']} zonas de carga) · Actualización del paquete PND: "
               f"{actualizado_cdmx(lp['generado_utc'])}, Ciudad de México · Fuente: CENACE SW-PEND, MDA, SIN.")
else:
    metodologia()
    st.caption(f"PML Explorer {VERSION_APP} · Datos: esquema v{metadata()['version_esquema']} · "
               f"Fechas de operación disponibles: {limites['desde']} a {limites['hasta']} (diario); "
               f"{limites['horario_desde']} a {limites['horario_hasta']} (horario). "
               f"Actualización del paquete: {actualizado_cdmx(limites['generado_utc'])}, Ciudad de México."
               + (f" · Nombres y ubicación: Catálogo de NodosP de CENACE, versión "
                  f"{UBICACION['manifiesto']['version_catalogo']}." if UBICACION else ""))
with contenido:
    if not en_solo:
        vista_ensemble(limites, nodos, version, limites_activos)
    elif modo_pnd:
        vista_pnd(panel)
    else:
        VISTAS[vista](limites, nodos, fechas_nodo, version, panel)

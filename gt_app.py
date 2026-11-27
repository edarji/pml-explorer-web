"""Guatemala Price Explorer v0.1 · POE del Mercado Mayorista de Guatemala (AMM).

App separada de PML Explorer (entrypoint propio, segunda app de Streamlit Community Cloud). Reutiliza sin modificarlos
el tema Graphite (.streamlit/config.toml), los estilos de la barra y del ticker (constantes ESTILOS de app.py, leídas
sin ejecutar app.py), los rangos y granularidades de `rangos.py` y la protección de fórmulas de `exportar.py`.
No lee `data/` ni `pnd/`: México queda intacto.

    .venv/bin/python -m streamlit run gt_app.py --server.address 127.0.0.1
"""
import ast
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import gt_datos as gd
import gt_ticker as gtk
import rangos

VERSION_APP = "v0.1 beta"
RAIZ = Path(__file__).resolve().parent
SITIO_MERCADOS = "https://edarji.net/mercados/"
AMBAR, EJE, REJILLA = "#FFB000", "#C9CBD0", "#E3E5E9"
ETIQUETAS_RANGO = {"Último día": "1D", "Últimos 7 días": "7D", "Mes en curso": "Mes", "Año en curso": "YTD"}
ETIQUETAS_RES = {"horaria": "Horaria", "diaria": "Diaria", "mensual": "Mensual"}


def constante_de_app(nombre):
    """Una constante de texto de app.py (estilos compartidos) sin importar ni ejecutar la app de México."""
    arbol = ast.parse((RAIZ / "app.py").read_text(encoding="utf-8"))
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], "id", None) == nombre:
            return ast.literal_eval(nodo.value)
    return ""


@st.cache_data(max_entries=2, show_spinner=False)
def cargar(clave):
    """Paquete validado. `clave` = huella de metadata.json + versión de app: una corrección invalida la caché."""
    return gd.leer(gd.GT_DIR)


def tramos(periodos, resolucion):
    """(tramo, aislado): misma regla que app.py v0.8.8 · la línea no cruza periodos sin dato."""
    f = pd.to_datetime(pd.Series(periodos)).reset_index(drop=True)
    if f.empty:
        return pd.Series(dtype=int), pd.Series(dtype=bool)
    if resolucion == "mensual":
        i = f.dt.year * 12 + f.dt.month
    elif resolucion == "diaria":
        i = (f - pd.Timestamp("2000-01-01")).dt.days
    else:
        i = (f - pd.Timestamp("2000-01-01")) // pd.Timedelta(hours=1)
    tramo = (i.diff().fillna(1) != 1).cumsum().astype(int)
    return tramo, tramo.map(tramo.value_counts()) == 1


def grafica(s, resolucion):
    tramo, aislado = tramos(s["periodo"], resolucion)
    d = s.assign(tramo=tramo.values, aislado=aislado.values)
    fmt = {"horaria": "%d %b %H:%M", "diaria": "%d %b %Y", "mensual": "%b %Y"}[resolucion]
    x = alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE))
    y = alt.Y("poe:Q", title="USD/MWh", axis=alt.Axis(orient="right", gridColor=REJILLA, domain=False))
    tip = [alt.Tooltip("periodo:T", title="Periodo", format=fmt), alt.Tooltip("poe:Q", title="POE USD/MWh", format=",.2f")]
    if resolucion != "horaria":
        tip.append(alt.Tooltip("horas:Q", title="Horas con dato"))
    linea = alt.Chart(d).mark_line(color=AMBAR, strokeWidth=2).encode(x=x, y=y, detail="tramo:N", tooltip=tip)
    puntos = alt.Chart(d[d["aislado"]]).mark_point(color=AMBAR, filled=True, size=40).encode(x=x, y=y, tooltip=tip)
    return (linea + puntos).properties(height=300).configure_view(stroke=None)


def aplicar_rango(opcion):
    st.session_state.inicio, st.session_state.fin = rangos.rango_rapido(opcion, LIM)
    st.session_state.resolucion = rangos.resoluciones_permitidas(st.session_state.inicio, st.session_state.fin, LIM)[0]


def ver_dia(dia):
    st.session_state.inicio = st.session_state.fin = dia
    st.session_state.resolucion = "horaria"


# ------------------------------------------------------------------ página
st.set_page_config(page_title="Guatemala Price Explorer", page_icon=str(RAIZ / "assets" / "logo.svg"), layout="wide",
                   initial_sidebar_state="collapsed")
st.html(constante_de_app("ESTILOS"))
st.markdown(f"[← Mercados · edarji.net]({SITIO_MERCADOS})")

barra = st.container(key="barra", horizontal=True, vertical_alignment="center", gap="medium")
with barra, st.container(key="marca_texto"):
    st.title("Guatemala Price Explorer")
    st.caption("Precio de Oportunidad de la Energía (POE) · Mercado Mayorista de Guatemala (AMM) · posdespacho · "
               "USD/MWh · datos diarios publicados, no en tiempo real")

if not (gd.GT_DIR / "metadata.json").is_file():
    st.info("Los datos públicos de Guatemala todavía no están disponibles en esta publicación.")
    st.stop()
try:
    P = cargar(gd.huella(gd.GT_DIR) + VERSION_APP)
except gd.PaqueteInvalido as e:
    st.error(f"El paquete de datos de Guatemala no pasó la validación ({e}). No se muestran cifras.")
    st.stop()
META, H = P["metadata"], P["poe_horario"]
LIM = gd.limites(META)

# Estado inicial: enlace (?desde&hasta&resolucion) o, sin él, los últimos 7 días en horaria.
if "inicio" not in st.session_state:
    u_ini, u_fin, u_res = gd.leer_url(dict(st.query_params), LIM)
    st.session_state.inicio, st.session_state.fin = (u_ini, u_fin) if u_ini and u_fin else \
        rangos.rango_rapido("Últimos 7 días", LIM)
    permitidas = rangos.resoluciones_permitidas(st.session_state.inicio, st.session_state.fin, LIM)
    st.session_state.resolucion = u_res if u_res in permitidas else permitidas[0]

# Ticker: siempre el último día del paquete, independiente del rango elegido.
f = gtk.ficha(P["poe_diario"])
if f:
    with barra, st.container(key="ticker", horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f'<div class="tk-et"><b>{gtk.ROTULO}</b><span>Día de operación {f["dia"]} vs {f["dia_previo"]}'
                    f'</span></div>', unsafe_allow_html=True)
        with st.container(key="cinta", horizontal=True, gap="small"):
            clase = f["direccion"] or "neutro"
            st.button(f"*POE* **{f['precio']:,.2f}** `{gtk.cambio(f)}`", key=f"tka_{clase}_poe", on_click=ver_dia,
                      args=(f["dia"],), help=gtk.descripcion(f) + f" Botón: abrir {f['dia']} en horaria.")
            st.button(f"*Mín. horario* **{f['minimo']:,.2f}**", key="tka_neutro_min", on_click=ver_dia, args=(f["dia"],),
                      help=f"Mínimo horario del {f['dia']}, USD/MWh. Botón: abrir ese día en horaria.")
            st.button(f"*Máx. horario* **{f['maximo']:,.2f}**", key="tka_neutro_max", on_click=ver_dia, args=(f["dia"],),
                      help=f"Máximo horario del {f['dia']}, USD/MWh. Botón: abrir ese día en horaria.")

estado, esperado = gd.frescura(META, datetime.now(gd.ZONA_GT))
with barra, st.container(key="controles", horizontal=True, vertical_alignment="center", gap="small"):
    for opcion, corto in ETIQUETAS_RANGO.items():
        st.button(corto, key=f"rango_{corto}", on_click=aplicar_rango, args=(opcion,), help=opcion)
    st.date_input("Desde", key="inicio", min_value=LIM["desde"], max_value=LIM["hasta"], label_visibility="collapsed")
    st.date_input("Hasta", key="fin", min_value=LIM["desde"], max_value=LIM["hasta"], label_visibility="collapsed")
    aviso = "" if estado == "al_dia" else f' · <b>atrasado</b>: se esperaba {esperado}'
    st.markdown(f'<div class="estado-barra"><span class="activo">Datos {LIM["desde"]} a {LIM["hasta"]}</span>'
                f'<span>Paquete actualizado {gd.actualizado_gt(META)} (hora de Guatemala){aviso}</span></div>',
                unsafe_allow_html=True)

inicio, fin = st.session_state.inicio, st.session_state.fin
if inicio > fin:
    st.error("La fecha «Desde» debe ser anterior a «Hasta».")
    st.stop()
permitidas = rangos.resoluciones_permitidas(inicio, fin, LIM)
if st.session_state.resolucion not in permitidas:
    st.session_state.resolucion = permitidas[0]
resolucion = st.pills("Resolución", permitidas, key="resolucion", format_func=ETIQUETAS_RES.get,
                      selection_mode="single") or permitidas[0]
st.query_params.update(gd.escribir_url(inicio, fin, resolucion))

e = gd.estadisticas(H, inicio, fin)
st.subheader(f"POE · {inicio} a {fin}")
if e["horas"] == 0:
    st.warning("No hay datos publicados en el rango elegido.")
    st.stop()
st.write(f"**Cobertura:** {e['cobertura_pct']}% ({e['horas']:,} de {e['horas_rango']:,} horas con dato). "
         "Los días sin dato no se rellenan.")
c = st.columns(5)
for col, (et, v) in zip(c, [("Promedio", e["promedio"]), ("Mediana", e["mediana"]), ("Mínimo", e["minimo"]),
                             ("Máximo", e["maximo"]), ("Desv. estándar", e["desviacion"])]):
    col.metric(f"{et} (USD/MWh)", "—" if pd.isna(v) else f"{v:,.2f}")
if e["horas_cero_o_negativas"]:
    st.caption(f"{e['horas_cero_o_negativas']} horas con POE ≤ 0 en el rango (se muestran tal cual).")

s = gd.serie(H, inicio, fin, resolucion)
st.altair_chart(grafica(s, resolucion), width="stretch")
st.caption("Hora = inicio del intervalo (00:00–01:00 … 23:00–24:00, America/Guatemala, UTC−6). "
           "Promedios diarios y mensuales: simples sobre las horas con dato, sin ponderar por demanda.")

faltan = gd.dias_sin_dato(META, inicio, fin)
if faltan:
    st.info(f"{len(faltan)} días sin dato publicado en el rango: {', '.join(faltan[:10])}{' …' if len(faltan) > 10 else ''}")

datos, nombre = gd.csv(H, inicio, fin, resolucion)
c1, c2 = st.columns([1, 2])
c1.download_button(f"Descargar CSV ({ETIQUETAS_RES[resolucion].lower()})", datos, file_name=nombre, mime="text/csv")
c2.code("?" + "&".join(f"{k}={v}" for k, v in gd.escribir_url(inicio, fin, resolucion).items()), language=None)

with st.expander("Generador marginal: participación en las horas del rango"):
    st.caption("Proporción de horas en que cada central fijó el POE. No es participación en la energía generada.")
    st.dataframe(gd.marginales(H, inicio, fin), hide_index=True)
with st.expander("Tabla"):
    st.dataframe(s.drop(columns=["generador_marginal"], errors="ignore"), hide_index=True)

fuente = META["fuente"]
st.markdown(f"**Fuente:** [{fuente['nombre']}]({fuente['url']}). {fuente['nota']}")
st.caption(f"Guatemala Price Explorer {VERSION_APP} · esquema {META['version_esquema']} · "
           f"datos {LIM['desde']} a {LIM['hasta']} · actualizado {gd.actualizado_gt(META)} (hora de Guatemala)")

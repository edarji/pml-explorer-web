"""Entrada pública de la vista 1 de PML Explorer."""
import duckdb
import streamlit as st

from vista1 import (DATA_DIR, RESOLUCIONES, DatosNoDisponibles, catalogo,
                    cobertura_horaria, estadisticas, huella_paquete,
                    inspeccionar_paquete, serie)


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_paquete(data_dir, version):
    return inspeccionar_paquete(data_dir), catalogo(data_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas(nodo, inicio, fin, data_dir, version):
    return estadisticas(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie(nodo, inicio, fin, resolucion, data_dir, version):
    return serie(nodo, inicio, fin, resolucion, data_dir)


st.set_page_config(page_title="PML Explorer", layout="wide")
st.title("PML Explorer v0.1")
st.caption("Precio Marginal Local, MDA del SIN (CENACE). Unidades: MXN/MWh.")

if not (DATA_DIR / "metadata.json").is_file():
    st.info("Los derivados públicos de CENACE todavía no están disponibles en esta publicación.")
    st.stop()

try:
    version = huella_paquete()
    limites, nodos = cargar_paquete(str(DATA_DIR), version)
except (DatosNoDisponibles, duckdb.Error):
    st.error("El paquete público está incompleto o su esquema no es compatible. La integración debe validarse antes de publicar cifras.")
    st.stop()

if not nodos:
    st.warning("El paquete público no contiene nodos con datos.")
    st.stop()

st.caption(f"Datos diarios: {limites['desde']} a {limites['hasta']}. "
           f"Histórico horario disponible: {limites['horario_desde']} a {limites['horario_hasta']}.")

with st.sidebar:
    nodo = st.selectbox("Nodo", nodos, index=nodos.index("01AAN-85") if "01AAN-85" in nodos else 0)
    inicio = st.date_input("Desde", limites["desde"], min_value=limites["desde"], max_value=limites["hasta"])
    fin = st.date_input("Hasta", limites["hasta"], min_value=limites["desde"], max_value=limites["hasta"])
    resolucion = st.radio("Resolución", list(RESOLUCIONES), index=1)

if inicio > fin:
    st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
    st.stop()

horario_completo = cobertura_horaria(inicio, fin)
if not horario_completo and resolucion == "horaria":
    st.warning("La resolución horaria requiere que todo el rango esté dentro del histórico horario disponible. Ajusta las fechas o elige diaria o mensual.")
    st.stop()

try:
    e = consultar_estadisticas(nodo, inicio, fin, str(DATA_DIR), version).iloc[0]
    df = consultar_serie(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
except (DatosNoDisponibles, duckdb.Error):
    st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
    st.stop()

if e["horas_con_dato"] == 0:
    st.warning("Este nodo no tiene datos en el rango elegido.")
    st.stop()

st.subheader(f"{nodo}: {inicio} a {fin}")
st.write(f"**Cobertura:** {e['cobertura_pct']}% "
         f"({int(e['horas_con_dato']):,} de {int(e['horas_del_rango']):,} horas con dato)")
st.caption("La cobertura usa las horas de todo el rango calendario; puede incluir fechas anteriores al alta del nodo.")
if not horario_completo:
    st.info("Mediana, P10 y P90 no disponibles: el rango excede el histórico horario. Los demás indicadores se reconstruyen de los acumuladores diarios, sin imputar precios.")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Promedio", f"{e['promedio']:,.0f}")
c2.metric("Mediana", f"{e['mediana']:,.2f}" if horario_completo else "No disponible")
c3.metric("Mínimo", f"{e['minimo']:,.2f}")
c4.metric("Máximo", f"{e['maximo']:,.2f}")
c5.metric("Horas negativas", f"{int(e['horas_negativas']):,}")

st.line_chart(df, x="periodo", y="pml_promedio", y_label="MXN/MWh", x_label="")

with st.expander("Todas las estadísticas"):
    tabla = e.to_frame("valor").astype(object)
    for nombre in ("mediana", "p10", "p90"):
        if not horario_completo:
            tabla.loc[nombre, "valor"] = "No disponible: requiere histórico horario completo"
    st.dataframe(tabla)

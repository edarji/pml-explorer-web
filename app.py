from datetime import date, timedelta

import streamlit as st

from vista1 import DATA_DIR, RESOLUCIONES, catalogo, estadisticas, serie

serie = st.cache_data(serie)
estadisticas = st.cache_data(estadisticas)

st.set_page_config(page_title="PML Explorer", layout="wide")
st.title("PML Explorer v0.1")
st.caption("Precio Marginal Local, MDA del SIN (CENACE). Unidades: MXN/MWh.")

# Solo se consultan derivados públicos incluidos en este repositorio.
if not any(DATA_DIR.glob("*.parquet")):
    st.info("Los derivados públicos de CENACE todavía no están disponibles en esta publicación.")
    st.stop()

# Controles en la barra lateral
nodos = catalogo()
if not nodos:
    st.warning("El paquete público no contiene nodos con datos.")
    st.stop()
with st.sidebar:
    nodo = st.selectbox("Nodo", nodos, index=nodos.index("01AAN-85") if "01AAN-85" in nodos else 0)
    inicio = st.date_input("Desde", date(2023, 1, 1), min_value=date(2023, 1, 1))
    fin = st.date_input("Hasta", date.today(), max_value=date.today() + timedelta(days=1))
    resolucion = st.radio("Resolución", list(RESOLUCIONES), index=1)

if inicio > fin:
    st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
    st.stop()

# Estadísticas y cobertura
e = estadisticas(nodo, inicio, fin).iloc[0]
if e["horas_con_dato"] == 0:
    st.warning("Este nodo no tiene datos en el rango elegido.")
    st.stop()

st.subheader(f"{nodo}: {inicio} a {fin}")
st.write(f"**Cobertura:** {e['cobertura_pct']}% "
         f"({int(e['horas_con_dato']):,} de {int(e['horas_del_rango']):,} horas con dato)")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Promedio", f"{e['promedio']:,.0f}")
c2.metric("Mediana", f"{e['mediana']:,.2f}")
c3.metric("Mínimo", f"{e['minimo']:,.2f}")
c4.metric("Máximo", f"{e['maximo']:,.2f}")
c5.metric("Horas negativas", f"{int(e['horas_negativas']):,}")

# Gráfica
df = serie(nodo, inicio, fin, resolucion)
st.line_chart(df, x="periodo", y="pml_promedio", y_label="MXN/MWh", x_label="")

with st.expander("Todas las estadísticas"):
    st.dataframe(e.to_frame("valor"))

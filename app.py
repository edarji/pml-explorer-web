"""Entrada pública de PML Explorer."""
import altair as alt
import duckdb
import pandas as pd
import streamlit as st

from vista1 import (DATA_DIR, RESOLUCIONES, DatosNoDisponibles, actualizado_cdmx, catalogo,
                    cobertura_horaria, estadisticas, huella_paquete,
                    inspeccionar_paquete, marcar_periodos, observado, serie)

REPO = "https://github.com/edarji/pml-explorer-web/blob/main"
COBERTURA_ESCASA = 80  # % de horas con dato bajo el cual se advierte explícitamente


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_paquete(data_dir, version):
    return inspeccionar_paquete(data_dir), catalogo(data_dir), observado(data_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas(nodo, inicio, fin, data_dir, version):
    return estadisticas(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie(nodo, inicio, fin, resolucion, data_dir, version):
    return serie(nodo, inicio, fin, resolucion, data_dir)


def mxn(valor):
    """Precio con la misma precisión en indicadores y tablas: dos decimales."""
    return "—" if pd.isna(valor) else f"{valor:,.2f}"


def grafica(df, y, titulo_y, resolucion, color=None):
    """Línea con puntos; los periodos parciales se marcan con ▼ y se explican en el tooltip."""
    base = alt.Chart(df).encode(
        x=alt.X("periodo:T", title=None),
        y=alt.Y(f"{y}:Q", title=titulo_y),
        tooltip=[alt.Tooltip("etiqueta:N", title="Periodo"),
                 alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.2f"),
                 alt.Tooltip("horas:Q", title="Horas con dato", format=",")],
    )
    linea = base.mark_line(color=color) if color else base.mark_line()
    capas = [linea]
    # Con muchos periodos solo se dibujan los puntos parciales, para no saturar la gráfica.
    puntos = base if len(df) <= 400 else base.transform_filter("datum.parcial")
    if resolucion != "horaria":
        capas.append(puntos.mark_point(size=60, filled=True).encode(
            shape=alt.Shape("parcial:N", title="Periodo",
                            scale=alt.Scale(domain=[False, True], range=["circle", "triangle-down"]),
                            legend=alt.Legend(labelExpr="datum.value ? 'parcial' : 'completo'")),
        ))
    st.altair_chart(alt.layer(*capas), width="stretch")


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
- **Histórico horario y diario:** mediana y percentiles requieren que todo el rango esté dentro de la ventana horaria (último año). Fuera de ella se usan acumuladores diarios exactos para promedio, extremos, desviación y horas negativas.
- **Fechas:** “Desde/Hasta” son **fechas de operación** del mercado. “Actualización” es cuándo se generó el paquete público, no cuándo CENACE publicó cada día.
- **Precisión:** precios con dos decimales; la desviación estándar es muestral.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def vista_1(limites, nodos, fechas_nodo, version):
    """Vista 1: PML histórico de un nodo."""
    with st.sidebar:
        nodo = st.selectbox("Nodo", nodos, index=nodos.index("01AAN-85") if "01AAN-85" in nodos else 0,
                            help="Busca por clave NodoP (por ejemplo 01AAN-85). El paquete público "
                                 "aún no incluye nombres de localidad ni regiones.")
        inicio = st.date_input("Desde", limites["desde"], min_value=limites["desde"], max_value=limites["hasta"])
        fin = st.date_input("Hasta", limites["hasta"], min_value=limites["desde"], max_value=limites["hasta"])
        resolucion = st.radio("Resolución de la gráfica", list(RESOLUCIONES), index=1,
                              help="Solo cambia la gráfica. Los indicadores siempre son horarios.")
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
    st.write(f"**Cobertura:** {e['cobertura_pct']}% ({con_dato:,} de {del_rango:,} horas con dato). "
             f"**Rango con observaciones:** {desde_obs} a {hasta_obs}.")
    if e["cobertura_pct"] < COBERTURA_ESCASA:
        motivo = (f" El nodo tiene datos desde {primera}." if primera and primera > inicio else "")
        st.warning(f"Cobertura escasa: los indicadores describen solo {con_dato:,} horas, entre {desde_obs} y "
                   f"{hasta_obs}, no todo el rango elegido.{motivo} Las horas sin dato no se tratan como cero.")
    elif e["cobertura_pct"] < 100:
        st.caption("Hay horas sin dato en el rango; los indicadores usan solo las horas con dato.")

    st.caption(f"Indicadores calculados sobre las {con_dato:,} horas con dato, en MXN/MWh"
               + ("." if resolucion == "horaria" else f", aunque la gráfica sea {resolucion}."))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Promedio horario", mxn(e["promedio"]), help="Promedio simple de las horas con dato.")
    c2.metric("Mediana horaria", mxn(e["mediana"]) if horario_completo else "—",
              help=None if horario_completo else
              f"Requiere datos horarios: disponible solo si todo el rango está entre "
              f"{limites['horario_desde']} y {limites['horario_hasta']}.")
    c3.metric("Mínimo horario", mxn(e["minimo"]), help="Menor PML de una hora en el rango.")
    c4.metric("Máximo horario", mxn(e["maximo"]), help="Mayor PML de una hora en el rango.")
    c5.metric("Horas con PML < 0", f"{int(e['horas_negativas']):,}")
    if not horario_completo:
        st.caption("— Mediana, P10 y P90 requieren datos horarios: el rango excede la ventana horaria "
                   f"({limites['horario_desde']} a {limites['horario_hasta']}). No se estiman.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    titulo = {"horaria": "PML horario", "diaria": "PML promedio diario",
              "mensual": "PML promedio mensual"}[resolucion]
    st.markdown(f"**{titulo} (MXN/MWh)**")
    grafica(df, "pml_promedio", "MXN/MWh", resolucion)
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


st.set_page_config(page_title="PML Explorer", layout="wide")
st.title("PML Explorer v0.1")
st.caption("Precio Marginal Local, MDA del SIN (CENACE). Unidades: MXN/MWh.")

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

st.caption(f"Fechas de operación disponibles: {limites['desde']} a {limites['hasta']} (diario); "
           f"{limites['horario_desde']} a {limites['horario_hasta']} (horario). "
           f"Actualización del paquete: {actualizado_cdmx(limites['generado_utc'])}, Ciudad de México.")
metodologia()

vista_1(limites, nodos, fechas_nodo, version)

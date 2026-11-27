"""v0.9.0 · Chaly's Bebop 🎷 (Issue #42): vista estacional del PML de un NodoP.

Funciones puras (sin Streamlit ni DuckDB), como `yoy.py` y `rangos.py`. Reciben los acumuladores diarios publicados
(`fecha`, `suma_pml`, `horas_validas`) y arman una tabla por fecha de calendario (mes-día):

- **Y**: el año elegido; **Y−1** y **Y−2**: los dos anteriores. Precio = promedio diario `suma_pml / horas_validas`
  (horas_validas > 0), redondeado a 2 decimales como en el resto de la aplicación. Un día sin dato queda vacío.
- **Banda Mín–Máx 5Y**: por mes-día, el mínimo y el máximo de los promedios diarios de **Y−5 a Y−1** (nunca Y).
  Es una envolvente descriptiva, no un intervalo de confianza. Solo cuentan los años con dato en esa fecha (`n`).
  Con n < 2 no hay banda (una sola observación no es un rango); con n = 0 hay hueco.
- **29 de febrero** queda fuera de esta vista: no tiene par en los años no bisiestos. El calendario tiene 365 fechas
  y las fechas posteriores de un año bisiesto no se desplazan. Las demás vistas y sus CSV lo conservan.
- **Fuera de banda**: Y por encima del máximo o por debajo del mínimo, solo donde la banda existe (n ≥ 2).
- Nada se interpola ni se extrapola: Y termina en el último día publicado.
"""
from datetime import date, timedelta

import pandas as pd

VENTANA = 5          # años de la banda: Y−5 … Y−1
MIN_ANIOS_BANDA = 2  # con menos años por fecha no se dibuja banda
EJE = 2001           # año no bisiesto que sostiene el eje de calendario (solo mes y día; el año no se muestra)


def calendario():
    """Las 365 fechas de calendario (sin 29 de febrero) sobre el año del eje."""
    inicio = date(EJE, 1, 1)
    return [inicio + timedelta(days=i) for i in range(365)]


def rango_consulta(anio, limites):
    """(inicio, fin) de la única lectura que necesita la vista: Y−5 a Y, recortado al paquete."""
    inicio = max(date(anio - VENTANA, 1, 1), limites["desde"])
    fin = min(date(anio, 12, 31), limites["hasta"])
    return inicio, fin


def anios_disponibles(primera, ultima):
    """Años elegibles como Y: los que tienen al menos un día con dato del nodo (del más reciente al más antiguo)."""
    if primera is None or ultima is None:
        return []
    return list(range(ultima.year, primera.year - 1, -1))


def promedios_diarios(acumulados):
    """DataFrame (fecha, anio, mes_dia, pml, horas) desde los acumuladores diarios; sin 29 de febrero."""
    df = acumulados[acumulados["horas_validas"] > 0].copy()
    fechas = pd.to_datetime(df["fecha"])
    df = df[~((fechas.dt.month == 2) & (fechas.dt.day == 29))]
    fechas = pd.to_datetime(df["fecha"])
    return pd.DataFrame({"fecha": fechas.dt.date, "anio": fechas.dt.year.astype(int),
                         "mes_dia": fechas.dt.strftime("%m-%d"),
                         "pml": (df["suma_pml"] / df["horas_validas"]).round(2).to_numpy(),
                         "horas": df["horas_validas"].astype(int).to_numpy()}).reset_index(drop=True)


def tabla(acumulados, anio):
    """Una fila por fecha de calendario (365) con Y, Y−1, Y−2, la banda y su n real.

    Columnas: eje (fecha en el año del eje), mes_dia, y, y_1, y_2, horas_y, banda_min, banda_max, n,
    anios_banda (texto, p. ej. «2023, 2024, 2025»), fuera ("arriba", "abajo" o None).
    """
    diarios = promedios_diarios(acumulados)
    ancho = diarios.pivot_table(index="mes_dia", columns="anio", values="pml", aggfunc="first")
    horas = diarios[diarios["anio"] == anio].set_index("mes_dia")["horas"]
    dias = calendario()
    t = pd.DataFrame({"eje": pd.to_datetime(dias), "mes_dia": [d.strftime("%m-%d") for d in dias]})
    serie = lambda a: t["mes_dia"].map(ancho[a]) if a in ancho.columns else pd.Series(float("nan"), index=t.index)
    t["y"], t["y_1"], t["y_2"] = serie(anio), serie(anio - 1), serie(anio - 2)
    t["horas_y"] = t["mes_dia"].map(horas)
    referencia = [a for a in range(anio - VENTANA, anio) if a in ancho.columns]
    if referencia:
        ref = ancho[referencia].reindex(t["mes_dia"])
        t["n"] = ref.notna().sum(axis=1).to_numpy()
        t["anios_banda"] = [", ".join(str(a) for a in referencia if pd.notna(fila[a])) for _, fila in ref.iterrows()]
        con_banda = t["n"] >= MIN_ANIOS_BANDA
        t["banda_min"] = ref.min(axis=1).to_numpy()
        t["banda_max"] = ref.max(axis=1).to_numpy()
        t.loc[~con_banda, ["banda_min", "banda_max"]] = float("nan")
    else:
        t["n"], t["anios_banda"] = 0, ""
        t["banda_min"] = t["banda_max"] = float("nan")
    t["fuera"] = None
    t.loc[t["y"] > t["banda_max"], "fuera"] = "arriba"
    t.loc[t["y"] < t["banda_min"], "fuera"] = "abajo"
    return t


def resumen(t, acumulados, anio):
    """Indicadores del encabezado. El promedio de Y frente a Y−1 se pondera por horas (acumuladores), sobre las
    fechas de calendario con dato en los dos años; nunca promedia promedios."""
    con_banda = t["banda_min"].notna()
    diarios = acumulados[acumulados["horas_validas"] > 0].copy()
    fechas = pd.to_datetime(diarios["fecha"])
    diarios = diarios[~((fechas.dt.month == 2) & (fechas.dt.day == 29))]
    fechas = pd.to_datetime(diarios["fecha"])
    diarios = diarios.assign(anio=fechas.dt.year, mes_dia=fechas.dt.strftime("%m-%d"))
    actual = diarios[diarios["anio"] == anio].set_index("mes_dia")
    previo = diarios[diarios["anio"] == anio - 1].set_index("mes_dia")
    comunes = actual.index.intersection(previo.index)
    def promedio(d):
        horas = d.loc[comunes, "horas_validas"].sum()
        return round(float(d.loc[comunes, "suma_pml"].sum() / horas), 2) if horas else None
    referencia = sorted({int(a) for texto in t["anios_banda"] if texto for a in texto.split(", ")})
    return {
        "dias_y": int(t["y"].notna().sum()),
        "ultimo_dia": max((d for d in pd.to_datetime(acumulados.loc[acumulados["horas_validas"] > 0, "fecha"]).dt.date
                           if d.year == anio), default=None),
        "dias_con_banda": int((t["y"].notna() & con_banda).sum()),
        "arriba": int((t["fuera"] == "arriba").sum()),
        "abajo": int((t["fuera"] == "abajo").sum()),
        "anios_referencia": referencia,
        "n_max": int(t["n"].max()) if len(t) else 0,
        "dias_comunes": len(comunes),
        "promedio_y": promedio(actual) if len(comunes) else None,
        "promedio_y_1": promedio(previo) if len(comunes) else None,
    }


def tramos(t, columna):
    """Número de tramo por fila para `columna`: un hueco (valor vacío) empieza un tramo nuevo (líneas sin unir)."""
    hay = t[columna].notna()
    return (hay != hay.shift(fill_value=False)).cumsum().where(hay)


def tabla_csv(t, anio):
    """CSV propio de la vista: fecha de calendario, Y, Y−1, Y−2 con sus años reales, banda, n y años de la banda."""
    return pd.DataFrame({
        "fecha_calendario": t["mes_dia"],
        f"pml_{anio}": t["y"], f"horas_{anio}": t["horas_y"].astype("Int64"),
        f"pml_{anio - 1}": t["y_1"], f"pml_{anio - 2}": t["y_2"],
        "banda_min": t["banda_min"], "banda_max": t["banda_max"],
        "banda_n_anios": t["n"].astype(int), "banda_anios": t["anios_banda"],
        "fuera_de_banda": t["fuera"].fillna(""),
    })

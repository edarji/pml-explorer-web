"""v0.8.0 · Consultas del tablero ENSEMBLE: el día de referencia de todos los nodos (PML) o zonas (PND).

No hay indicadores nuevos: el promedio del día de cada elemento usa exactamente la fórmula que la vista SOLO
de ese elemento usa para un día, sobre la misma fuente:
- PML dentro de la ventana horaria: ROUND(AVG(pml), 2) de las horas con dato (= `vista1.estadisticas`).
- PML fuera de la ventana horaria: ROUND(suma_pml / horas_validas, 2) del diario (= `vista1.estadisticas_diarias`).
- PND: ROUND(AVG(pnd), 2) de las horas con dato de la zona (= `pnd.estadisticas_pnd`).
El tablero solo ordena esos valores y cuenta elementos. PML y PND se consultan por separado, con su paquete y
su propio día de referencia; nunca se combinan.
Un elemento sin horas con dato ese día no entra al ranking (sin dato no es precio cero): se cuenta aparte.
"""
from datetime import timedelta
from pathlib import Path

import duckdb

from vista1 import DATA_DIR, MAX_DIARIO, MIN_DIARIO, _archivos, cobertura_horaria

COLUMNAS = ["elemento", "horas", "promedio", "minimo", "maximo", "horas_negativas"]


def _consulta(sql, parametros):
    with duckdb.connect(":memory:") as con:
        return con.execute(sql, parametros).df()


def dia_pml(hasta, limites):
    """Día de referencia PML: «Hasta» acotado al paquete. Los días del paquete PML son continuos."""
    return min(max(hasta, limites["desde"]), limites["hasta"])


def ranking_pml(dia, data_dir=DATA_DIR):
    """Promedio del día y horas con dato de cada nodo con al menos una hora, del más caro al más barato."""
    if cobertura_horaria(dia, dia, data_dir):
        sql = """
            SELECT nodo AS elemento, COUNT(*) AS horas, ROUND(AVG(pml), 2) AS promedio,
                   MIN(pml) AS minimo, MAX(pml) AS maximo, COUNT(*) FILTER (WHERE pml < 0) AS horas_negativas
            FROM read_parquet(?) WHERE fecha = ? GROUP BY nodo
            ORDER BY promedio DESC, elemento"""
        return _consulta(sql, [_archivos("hourly", dia, dia, data_dir), dia])
    sql = f"""
        SELECT nodo AS elemento, horas_validas::BIGINT AS horas, ROUND(suma_pml / horas_validas, 2) AS promedio,
               {MIN_DIARIO} AS minimo, {MAX_DIARIO} AS maximo, horas_negativas::BIGINT AS horas_negativas
        FROM read_parquet(?) WHERE fecha = ? AND horas_validas > 0
        ORDER BY promedio DESC, elemento"""
    return _consulta(sql, [_archivos("daily", dia, dia, data_dir), dia])


def dia_pnd(hasta, limites, carpeta):
    """Último día ≤ «Hasta» con archivo PND (un día sin dato no tiene archivo), o None si no hay ninguno."""
    dia = min(hasta, limites["hasta"])
    while dia >= limites["desde"]:
        if (Path(carpeta) / "hourly" / f"{dia}.parquet").is_file():
            return dia
        dia -= timedelta(days=1)
    return None


def ranking_pnd(dia, carpeta):
    """Promedio del día y horas con dato de cada zona de carga, de la más cara a la más barata."""
    ruta = Path(carpeta) / "hourly" / f"{dia}.parquet"
    sql = """
        SELECT zona_carga AS elemento, COUNT(*) AS horas, ROUND(AVG(pnd), 2) AS promedio,
               MIN(pnd) AS minimo, MAX(pnd) AS maximo, COUNT(*) FILTER (WHERE pnd < 0) AS horas_negativas
        FROM read_parquet(?) WHERE fecha = ? GROUP BY zona_carga
        ORDER BY promedio DESC, elemento"""
    return _consulta(sql, [str(ruta), dia])


def resumen(ranking, total):
    """Conteos del día. `total`: elementos del paquete; los que no tienen horas ese día se cuentan aparte."""
    con_dato = len(ranking)
    return {"con_dato": con_dato, "sin_dato": max(total - con_dato, 0),
            "incompletos": int((ranking["horas"] < 24).sum()),
            "con_negativos": int((ranking["horas_negativas"] > 0).sum()),
            "caro": ranking.iloc[0] if con_dato else None,
            "barato": ranking.iloc[-1] if con_dato else None}


# v0.8.7 · Intervalos de la distribución (Issue #36). Réplica exacta del `bin` de Vega (vega-statistics, el que usa
# `alt.Bin(maxbins=30)`), para que la gráfica y la lista de zonas de una barra salgan de los MISMOS intervalos: la
# gráfica dibuja estas barras ya agrupadas, así que el conteo de cada barra es, por construcción, el de su lista.
# Regla de Vega: cada intervalo es [inicio, fin) salvo el último, que incluye su límite superior.
EPSILON_BIN = 1e-14  # el mismo margen que usa Vega al asignar un valor a su intervalo


def pasos_bin(minimo, maximo, maxbins=30, base=10, divide=(5, 2)):
    """(inicio, fin, paso) como `bin()` de vega-statistics con nice=True (el valor por omisión de Vega-Lite)."""
    import math
    logb = math.log(base)
    span = (maximo - minimo) or abs(minimo) or 1
    nivel = math.ceil(math.log(maxbins) / logb)
    paso = max(0, base ** (round(math.log(span) / logb) - nivel))
    while math.ceil(span / paso) > maxbins:
        paso *= base
    for d in divide:
        v = paso / d
        if v >= 0 and span / v <= maxbins:
            paso = v
    v = math.log(paso)
    precision = 0 if v >= 0 else int(-v / logb) + 1
    eps = base ** (-precision - 1)
    v = math.floor(minimo / paso + eps) * paso
    inicio = v - paso if minimo < v else v
    fin = math.ceil(maximo / paso) * paso
    return inicio, (inicio + paso if fin == inicio else fin), paso


def intervalos(ranking, maxbins=30):
    """Agrega a cada fila del ranking su intervalo (`bin_ini`, `bin_fin`) con las reglas de Vega.

    No cambia ningún promedio: solo dice en qué barra cae cada uno. Filas sin promedio no se agrupan (sin dato).
    """
    import math
    df = ranking.dropna(subset=["promedio"]).copy()
    if df.empty:
        df["bin_ini"], df["bin_fin"] = [], []
        return df
    inicio, fin, paso = pasos_bin(float(df["promedio"].min()), float(df["promedio"].max()), maxbins)

    def asignar(x):
        x = max(inicio, min(float(x), fin - paso))
        return inicio + paso * math.floor(EPSILON_BIN + (x - inicio) / paso)
    df["bin_ini"] = df["promedio"].map(asignar).astype(float)
    df["bin_fin"] = (df["bin_ini"] + paso).astype(float)
    return df


def barras(con_intervalos):
    """Una fila por barra: inicio, fin y número de elementos (los mismos que lista `miembros`)."""
    return (con_intervalos.groupby(["bin_ini", "bin_fin"], as_index=False).size().rename(columns={"size": "n"})
            .sort_values("bin_ini", ignore_index=True))


def miembros(con_intervalos, bin_ini):
    """Elementos de la barra que empieza en `bin_ini`, del promedio más alto al más bajo."""
    return (con_intervalos[con_intervalos["bin_ini"] == bin_ini]
            .sort_values(["promedio", "elemento"], ascending=[False, True], ignore_index=True))

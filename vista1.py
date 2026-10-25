from pathlib import Path
import duckdb

DATA_DIR = Path(__file__).resolve().parent / "data" / "public"
DATA_GLOB = str(DATA_DIR / "*.parquet")

RESOLUCIONES = {"horaria": "hour", "diaria": "day", "mensual": "month"}


def serie(nodo, inicio, fin, resolucion):
    """PML promedio de un nodo por periodo, y cuántas horas tiene cada periodo."""
    unidad = RESOLUCIONES[resolucion]
    consulta = f"""
    SELECT date_trunc('{unidad}', fecha + to_hours(hora - 1)) AS periodo,
           ROUND(AVG(pml), 2) AS pml_promedio,
           COUNT(*) AS horas
    FROM read_parquet(?)
    WHERE nodo = ? AND fecha BETWEEN ? AND ?
    GROUP BY periodo
    ORDER BY periodo
    """
    return duckdb.execute(consulta, [DATA_GLOB, nodo, inicio, fin]).df()

def estadisticas(nodo, inicio, fin):
    """Estadísticas descriptivas del PML horario de un nodo y cobertura del rango."""
    consulta = """
    SELECT COUNT(*) AS horas_con_dato,
           (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
           ROUND(AVG(pml), 2) AS promedio,
           ROUND(MEDIAN(pml), 2) AS mediana,
           ROUND(STDDEV(pml), 2) AS desv_std,
           MIN(pml) AS minimo,
           MAX(pml) AS maximo,
           ROUND(QUANTILE_CONT(pml, 0.10), 2) AS p10,
           ROUND(QUANTILE_CONT(pml, 0.90), 2) AS p90,
           COUNT(*) FILTER (WHERE pml < 0) AS horas_negativas
    FROM read_parquet(?)
    WHERE nodo = ? AND fecha BETWEEN ? AND ?
    """
    df = duckdb.execute(consulta, [fin, inicio, DATA_GLOB, nodo, inicio, fin]).df()
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / df["horas_del_rango"], 1)
    return df

def catalogo():
    """Nodos realmente presentes en el paquete público, sin catálogo local privado."""
    return [r[0] for r in duckdb.execute(
        "SELECT DISTINCT nodo FROM read_parquet(?) WHERE nodo IS NOT NULL ORDER BY nodo",
        [DATA_GLOB],
    ).fetchall()]

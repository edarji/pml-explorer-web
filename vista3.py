"""Vista 3: PML = energía + pérdidas + congestión (contrato v2).

Dentro de la ventana horaria se usa la consulta validada en power-market-lab (scripts/vista3.py).
Fuera de ella se usan los acumuladores diarios: cada componente promedia sobre las mismas horas
que el PML (horas_validas), así que la base de observaciones es la misma. Se conservan los signos.
"""
from vista1 import (DATA_DIR, RESOLUCIONES, UMBRAL_DESCUADRE, DatosNoDisponibles, _archivos,
                    _consulta, _rango, cobertura_horaria)


def componentes(nodo, inicio, fin, resolucion, data_dir=DATA_DIR):
    """PML y sus componentes promedio por periodo, más el descuadre promedio."""
    inicio, fin = _rango(inicio, fin)
    unidad = RESOLUCIONES[resolucion]
    if not cobertura_horaria(inicio, fin, data_dir):
        if resolucion == "horaria":
            raise DatosNoDisponibles("La resolución horaria requiere todo el rango dentro de la ventana horaria.")
        return _consulta(f"""
            SELECT date_trunc('{unidad}', fecha) AS periodo,
                   ROUND(SUM(suma_pml) / SUM(horas_validas), 2) AS pml,
                   ROUND(SUM(suma_energia) / SUM(horas_validas), 2) AS energia,
                   ROUND(SUM(suma_perdidas) / SUM(horas_validas), 2) AS perdidas,
                   ROUND(SUM(suma_congestion) / SUM(horas_validas), 2) AS congestion,
                   ROUND(SUM(suma_pml - (suma_energia + suma_perdidas + suma_congestion)) / SUM(horas_validas), 4) AS descuadre,
                   SUM(horas_validas)::BIGINT AS horas
            FROM read_parquet(?)
            WHERE nodo = ? AND fecha BETWEEN ? AND ? AND horas_validas > 0
            GROUP BY periodo ORDER BY periodo
        """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin])
    consulta = f"""
    SELECT date_trunc('{unidad}', fecha + to_hours(hora - 1)) AS periodo,
           ROUND(AVG(pml), 2) AS pml,
           ROUND(AVG(energia), 2) AS energia,
           ROUND(AVG(perdidas), 2) AS perdidas,
           ROUND(AVG(congestion), 2) AS congestion,
           ROUND(AVG(pml - (energia + perdidas + congestion)), 4) AS descuadre,
           COUNT(*) AS horas
    FROM read_parquet(?)
    WHERE nodo = ? AND fecha BETWEEN ? AND ?
    GROUP BY periodo
    ORDER BY periodo
    """
    return _consulta(consulta, [_archivos("hourly", inicio, fin, data_dir), nodo, inicio, fin])


def resumen_componentes(nodo, inicio, fin, data_dir=DATA_DIR):
    """Promedio de cada componente, horas con congestión de cada signo y descuadre."""
    inicio, fin = _rango(inicio, fin)
    if not cobertura_horaria(inicio, fin, data_dir):
        df = _consulta(f"""
            WITH acumulado AS (
                SELECT COALESCE(SUM(horas_validas), 0)::BIGINT AS n,
                       SUM(suma_pml) AS sp, SUM(suma_energia) AS se, SUM(suma_perdidas) AS sl,
                       SUM(suma_congestion) AS sc,
                       COALESCE(SUM(horas_congestion_positiva), 0)::BIGINT AS cpos,
                       COALESCE(SUM(horas_congestion_negativa), 0)::BIGINT AS cneg,
                       MAX(descuadre_max) AS dmax,
                       COALESCE(SUM(horas_descuadre), 0)::BIGINT AS dh,
                       MIN(fecha) AS primera_fecha, MAX(fecha) AS ultima_fecha
                FROM read_parquet(?) WHERE nodo = ? AND fecha BETWEEN ? AND ? AND horas_validas > 0
            )
            SELECT n AS horas_con_dato,
                   (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
                   ROUND(sp / NULLIF(n, 0), 2) AS pml, ROUND(se / NULLIF(n, 0), 2) AS energia,
                   ROUND(sl / NULLIF(n, 0), 2) AS perdidas, ROUND(sc / NULLIF(n, 0), 2) AS congestion,
                   cpos AS horas_congestion_positiva, cneg AS horas_congestion_negativa,
                   ROUND(dmax, 4) AS descuadre_max, dh AS horas_descuadre,
                   primera_fecha, ultima_fecha
            FROM acumulado
        """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin, fin, inicio])
    else:
        consulta = f"""
        SELECT COUNT(*) AS horas_con_dato,
               (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
               ROUND(AVG(pml), 2) AS pml,
               ROUND(AVG(energia), 2) AS energia,
               ROUND(AVG(perdidas), 2) AS perdidas,
               ROUND(AVG(congestion), 2) AS congestion,
               COUNT(*) FILTER (WHERE congestion > 0) AS horas_congestion_positiva,
               COUNT(*) FILTER (WHERE congestion < 0) AS horas_congestion_negativa,
               ROUND(MAX(ABS(pml - (energia + perdidas + congestion))), 4) AS descuadre_max,
               COUNT(*) FILTER (WHERE ROUND(ABS(pml - (energia + perdidas + congestion)), 6) > {UMBRAL_DESCUADRE}) AS horas_descuadre,
               MIN(fecha) AS primera_fecha,
               MAX(fecha) AS ultima_fecha
        FROM read_parquet(?)
        WHERE nodo = ? AND fecha BETWEEN ? AND ?
        """
        df = _consulta(consulta, [fin, inicio, _archivos("hourly", inicio, fin, data_dir), nodo, inicio, fin])
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / df["horas_del_rango"], 1)
    return df

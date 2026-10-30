"""Vista 2: spread entre dos nodos, PML_A − PML_B, solo en las horas en que ambos tienen dato.

Dentro de la ventana horaria se usa la consulta validada en power-market-lab (scripts/vista2.py):
JOIN por fecha y hora, y después se agrega. Fuera de ella se usan los acumuladores diarios, pero
solo en los días en que los dos nodos tienen las 24 horas: ahí las horas coincidentes son todas y
(suma_A − suma_B) / 24 es exactamente el promedio horario del spread. Un día en que algún nodo tiene
entre 1 y 23 horas no permite saber qué horas coinciden; se excluye y se cuenta, sin imputar.
"""
from vista1 import RESOLUCIONES, _archivos, _consulta, _rango, cobertura_horaria, DatosNoDisponibles, DATA_DIR


def diferencial(nodo_a, nodo_b, inicio, fin, resolucion, data_dir=DATA_DIR):
    """Spread A − B promedio por periodo y horas coincidentes de cada periodo."""
    inicio, fin = _rango(inicio, fin)
    unidad = RESOLUCIONES[resolucion]
    if not cobertura_horaria(inicio, fin, data_dir):
        if resolucion == "horaria":
            raise DatosNoDisponibles("La resolución horaria requiere todo el rango dentro de la ventana horaria.")
        return _consulta(f"""
            WITH d AS (SELECT * FROM read_parquet(?) WHERE fecha BETWEEN ? AND ?)
            SELECT date_trunc('{unidad}', a.fecha) AS periodo,
                   ROUND(SUM(a.suma_pml - b.suma_pml) / SUM(a.horas_validas), 2) AS dif_promedio,
                   SUM(a.horas_validas)::BIGINT AS horas
            FROM d a JOIN d b ON a.fecha = b.fecha
            WHERE a.nodo = ? AND b.nodo = ? AND a.horas_validas = 24 AND b.horas_validas = 24
            GROUP BY periodo ORDER BY periodo
        """, [_archivos("daily", inicio, fin, data_dir), inicio, fin, nodo_a, nodo_b])
    consulta = f"""
    SELECT date_trunc('{unidad}', a.fecha + to_hours(a.hora - 1)) AS periodo,
           ROUND(AVG(a.pml - b.pml), 2) AS dif_promedio,
           COUNT(*) AS horas
    FROM read_parquet(?) a
    JOIN read_parquet(?) b
      ON a.fecha = b.fecha AND a.hora = b.hora
    WHERE a.nodo = ? AND b.nodo = ?
      AND a.fecha BETWEEN ? AND ?
      AND b.fecha BETWEEN ? AND ?
    GROUP BY periodo
    ORDER BY periodo
    """
    archivos = _archivos("hourly", inicio, fin, data_dir)
    return _consulta(consulta, [archivos, archivos, nodo_a, nodo_b, inicio, fin, inicio, fin])


def resumen(nodo_a, nodo_b, inicio, fin, data_dir=DATA_DIR):
    """Estadísticas del spread horario A − B y cobertura común (horas coincidentes / horas del rango)."""
    inicio, fin = _rango(inicio, fin)
    if not cobertura_horaria(inicio, fin, data_dir):
        df = _consulta("""
            WITH d AS (SELECT * FROM read_parquet(?) WHERE fecha BETWEEN ? AND ?),
            par AS (SELECT a.fecha, a.horas_validas AS ha, b.horas_validas AS hb,
                           a.suma_pml - b.suma_pml AS dif
                    FROM d a JOIN d b ON a.fecha = b.fecha
                    WHERE a.nodo = ? AND b.nodo = ? AND a.horas_validas > 0 AND b.horas_validas > 0)
            SELECT COALESCE(SUM(ha) FILTER (WHERE ha = 24 AND hb = 24), 0)::BIGINT AS horas_coincidentes,
                   (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
                   ROUND(SUM(dif) FILTER (WHERE ha = 24 AND hb = 24)
                         / NULLIF(SUM(ha) FILTER (WHERE ha = 24 AND hb = 24), 0), 2) AS promedio,
                   NULL::DOUBLE AS mediana, NULL::DOUBLE AS minimo, NULL::DOUBLE AS maximo,
                   NULL::BIGINT AS horas_a_mas_caro,
                   COUNT(*) FILTER (WHERE NOT (ha = 24 AND hb = 24))::BIGINT AS dias_no_comparables,
                   MIN(fecha) FILTER (WHERE ha = 24 AND hb = 24) AS primera_fecha,
                   MAX(fecha) FILTER (WHERE ha = 24 AND hb = 24) AS ultima_fecha
            FROM par
        """, [_archivos("daily", inicio, fin, data_dir), inicio, fin, nodo_a, nodo_b, fin, inicio])
    else:
        consulta = """
        SELECT COUNT(*) AS horas_coincidentes,
               (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
               ROUND(AVG(a.pml - b.pml), 2) AS promedio,
               ROUND(MEDIAN(a.pml - b.pml), 2) AS mediana,
               ROUND(MIN(a.pml - b.pml), 2) AS minimo,
               ROUND(MAX(a.pml - b.pml), 2) AS maximo,
               COUNT(*) FILTER (WHERE a.pml > b.pml) AS horas_a_mas_caro,
               0::BIGINT AS dias_no_comparables,
               MIN(a.fecha) AS primera_fecha,
               MAX(a.fecha) AS ultima_fecha
        FROM read_parquet(?) a
        JOIN read_parquet(?) b
          ON a.fecha = b.fecha AND a.hora = b.hora
        WHERE a.nodo = ? AND b.nodo = ?
          AND a.fecha BETWEEN ? AND ?
          AND b.fecha BETWEEN ? AND ?
        """
        archivos = _archivos("hourly", inicio, fin, data_dir)
        df = _consulta(consulta, [fin, inicio, archivos, archivos, nodo_a, nodo_b, inicio, fin, inicio, fin])
    df["cobertura_pct"] = round(100 * df["horas_coincidentes"] / df["horas_del_rango"], 1)
    n = df["horas_coincidentes"].where(df["horas_coincidentes"] > 0)
    df["pct_a_mas_caro"] = round(100 * df["horas_a_mas_caro"] / n, 1)
    return df

"""Vista 1 validada y adaptación de lectura a los derivados públicos.

Las consultas horarias conservan las estadísticas originales. El resumen diario
usa los acumuladores acordados; ver docs/data-contract.md antes de integrar.
"""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

DATA_DIR = Path(__file__).resolve().parent / "data"
RESOLUCIONES = {"horaria": "hour", "diaria": "day", "mensual": "month"}
# Únicos nombres inferidos: cotejar con el esquema final de Claude.
MIN_DIARIO = "min_pml"
MAX_DIARIO = "max_pml"


class DatosNoDisponibles(ValueError):
    """El paquete está ausente, incompleto o no satisface la interfaz del lector."""


def _fecha(valor):
    return date.fromisoformat(str(valor)[:10])


def _rango(inicio, fin):
    inicio, fin = _fecha(inicio), _fecha(fin)
    if inicio > fin:
        raise ValueError("La fecha 'Desde' debe ser anterior a 'Hasta'.")
    return inicio, fin


def huella_paquete(data_dir=DATA_DIR):
    """Clave de caché: cambia con metadata y con archivos añadidos/reemplazados."""
    root = Path(data_dir)
    archivos = [root / "metadata.json", root / "nodes.parquet"]
    archivos += sorted(root.glob("hourly/*.parquet"))
    archivos += sorted(root.glob("daily/*.parquet"))
    h = hashlib.sha256()
    for p in archivos:
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            s = p.stat()
            h.update(f"{s.st_size}:{s.st_mtime_ns}".encode())
            if p.suffix == ".json":
                h.update(p.read_bytes())
    return h.hexdigest()


def metadata(data_dir=DATA_DIR):
    try:
        m = json.loads((Path(data_dir) / "metadata.json").read_text())
        if not isinstance(m, dict):
            raise ValueError("metadata debe ser un objeto")
        for clave in ("horario_desde", "horario_hasta"):
            date.fromisoformat(m[clave])
        desde, hasta = _rango(m["horario_desde"], m["horario_hasta"])
        if (hasta - desde).days >= 365:
            raise ValueError("la ventana horaria excede 365 días")
        return m
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DatosNoDisponibles(
            "Falta metadata.json válido con horario_desde y horario_hasta."
        ) from exc


def cobertura_horaria(inicio, fin, data_dir=DATA_DIR):
    inicio, fin = _rango(inicio, fin)
    m = metadata(data_dir)
    return _fecha(m["horario_desde"]) <= inicio <= fin <= _fecha(m["horario_hasta"])


def _archivos(tipo, inicio, fin, data_dir=DATA_DIR):
    inicio, fin = _rango(inicio, fin)
    if tipo == "hourly":
        esperados = [(inicio + timedelta(days=i)).isoformat()
                     for i in range((fin - inicio).days + 1)]
    elif tipo == "daily":
        actual = inicio.replace(day=1)
        esperados = []
        while actual <= fin:
            esperados.append(actual.strftime("%Y-%m"))
            actual = (actual.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        raise ValueError("Partición desconocida")
    paths = [Path(data_dir) / tipo / f"{nombre}.parquet" for nombre in esperados]
    if any(not p.is_file() for p in paths):
        raise DatosNoDisponibles("El paquete no contiene todas las particiones del rango.")
    return [str(p) for p in paths]


def _consulta(sql, parametros):
    # Conexión aislada por consulta, sin base operativa ni escritura persistente.
    with duckdb.connect(":memory:") as con:
        return con.execute(sql, parametros).df()


def inspeccionar_paquete(data_dir=DATA_DIR):
    """Comprueba estructura y esquema; la validación de filas está en scripts/."""
    root = Path(data_dir)
    m = metadata(root)
    _archivos("hourly", m["horario_desde"], m["horario_hasta"], root)
    requeridas = {
        "hourly": {"nodo": "texto", "fecha": "fecha", "hora": "entero", "pml": "numero"},
        "daily": {"nodo": "texto", "fecha": "fecha", "horas_validas": "entero",
                  "suma_pml": "numero", "suma_pml_cuadrado": "numero",
                  "horas_negativas": "entero", MIN_DIARIO: "numero", MAX_DIARIO: "numero"},
        "nodes": {"nodo": "texto"},
    }
    tipos = {
        "texto": lambda t: pa.types.is_string(t) or pa.types.is_large_string(t),
        "fecha": lambda t: pa.types.is_date(t) or (pa.types.is_timestamp(t) and t.tz is None),
        "entero": pa.types.is_integer,
        "numero": lambda t: pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_decimal(t),
    }
    for grupo in requeridas:
        paths = [root / "nodes.parquet"] if grupo == "nodes" else sorted(root.glob(f"{grupo}/*.parquet"))
        if not paths:
            raise DatosNoDisponibles(f"Falta el paquete {grupo}.")
        for path in paths:
            patron = r"\d{4}-\d{2}-\d{2}" if grupo == "hourly" else r"\d{4}-\d{2}"
            if grupo != "nodes" and not re.fullmatch(patron, path.stem):
                raise DatosNoDisponibles(f"Nombre de partición incompatible en {grupo}.")
            try:
                esquema = pq.read_schema(path)
                for nombre, tipo in requeridas[grupo].items():
                    if nombre not in esquema.names or not tipos[tipo](esquema.field(nombre).type):
                        raise DatosNoDisponibles(f"Esquema incompatible: {grupo}.{nombre}. Ver docs/data-contract.md.")
            except (OSError, pa.ArrowException) as exc:
                raise DatosNoDisponibles(f"No se puede leer un Parquet de {grupo}.") from exc
    limites = _consulta("SELECT MIN(fecha)::DATE AS desde, MAX(fecha)::DATE AS hasta FROM read_parquet(?)",
                        [[str(p) for p in sorted(root.glob("daily/*.parquet"))]]).iloc[0]
    if limites.isna().any():
        raise DatosNoDisponibles("El resumen diario está vacío.")
    desde, hasta = _rango(limites["desde"], limites["hasta"])
    if not desde <= _fecha(m["horario_desde"]) <= _fecha(m["horario_hasta"]) <= hasta:
        raise DatosNoDisponibles("La ventana horaria queda fuera del histórico diario.")
    _archivos("daily", desde, hasta, root)
    return {"desde": desde, "hasta": hasta, "horario_desde": _fecha(m["horario_desde"]),
            "horario_hasta": _fecha(m["horario_hasta"])}


def serie(nodo, inicio, fin, resolucion, data_dir=DATA_DIR):
    """PML promedio de un nodo por periodo, y cuántas horas tiene cada periodo."""
    inicio, fin = _rango(inicio, fin)
    unidad = RESOLUCIONES[resolucion]
    if not cobertura_horaria(inicio, fin, data_dir):
        if resolucion == "horaria":
            raise DatosNoDisponibles("La resolución horaria requiere todo el rango dentro de la ventana horaria.")
        return serie_diaria(nodo, inicio, fin, resolucion, data_dir)
    consulta = f"""
    SELECT date_trunc('{unidad}', fecha + to_hours(hora - 1)) AS periodo,
           ROUND(AVG(pml), 2) AS pml_promedio,
           COUNT(*) AS horas
    FROM read_parquet(?)
    WHERE nodo = ? AND fecha BETWEEN ? AND ?
    GROUP BY periodo
    ORDER BY periodo
    """
    return _consulta(consulta, [_archivos("hourly", inicio, fin, data_dir), nodo, inicio, fin])


def estadisticas(nodo, inicio, fin, data_dir=DATA_DIR):
    """Estadísticas descriptivas del PML horario de un nodo y cobertura del rango."""
    inicio, fin = _rango(inicio, fin)
    if not cobertura_horaria(inicio, fin, data_dir):
        return estadisticas_diarias(nodo, inicio, fin, data_dir)
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
    df = _consulta(consulta, [fin, inicio, _archivos("hourly", inicio, fin, data_dir), nodo, inicio, fin])
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / df["horas_del_rango"], 1)
    return df


def serie_diaria(nodo, inicio, fin, resolucion, data_dir=DATA_DIR):
    """Agrupa acumuladores diarios; nunca promedia promedios de días."""
    if resolucion not in ("diaria", "mensual"):
        raise ValueError("El resumen diario no permite resolución horaria.")
    unidad = RESOLUCIONES[resolucion]
    return _consulta(f"""
        SELECT date_trunc('{unidad}', fecha) AS periodo,
               ROUND(SUM(suma_pml) / NULLIF(SUM(horas_validas), 0), 2) AS pml_promedio,
               SUM(horas_validas)::BIGINT AS horas
        FROM read_parquet(?)
        WHERE nodo = ? AND fecha BETWEEN ? AND ?
        GROUP BY periodo ORDER BY periodo
    """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin])


def estadisticas_diarias(nodo, inicio, fin, data_dir=DATA_DIR):
    """Mismos estadísticos reconstruibles; cuantiles horarios no disponibles."""
    df = _consulta(f"""
        WITH acumulado AS (
            SELECT COALESCE(SUM(horas_validas), 0)::BIGINT AS n,
                   SUM(suma_pml) AS s, SUM(suma_pml_cuadrado) AS q,
                   MIN({MIN_DIARIO}) AS minimo, MAX({MAX_DIARIO}) AS maximo,
                   COALESCE(SUM(horas_negativas), 0)::BIGINT AS negativas
            FROM read_parquet(?) WHERE nodo = ? AND fecha BETWEEN ? AND ?
        )
        SELECT n AS horas_con_dato,
               (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
               ROUND(s / NULLIF(n, 0), 2) AS promedio,
               NULL::DOUBLE AS mediana,
               CASE WHEN n > 1 THEN ROUND(SQRT(GREATEST(0, (q - s*s/n) / (n-1))), 2) END AS desv_std,
               minimo, maximo, NULL::DOUBLE AS p10, NULL::DOUBLE AS p90,
               negativas AS horas_negativas
        FROM acumulado
    """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin, fin, inicio])
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / df["horas_del_rango"], 1)
    return df


def catalogo(data_dir=DATA_DIR):
    """Catálogo público entregado por el pipeline, sin configuración privada."""
    return _consulta("SELECT DISTINCT nodo FROM read_parquet(?) WHERE nodo IS NOT NULL ORDER BY nodo",
                     [str(Path(data_dir) / "nodes.parquet")])["nodo"].tolist()

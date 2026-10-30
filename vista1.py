"""Vista 1 validada y adaptación de lectura a los derivados públicos.

Las consultas horarias conservan las estadísticas originales. El resumen diario
usa los acumuladores acordados; ver docs/data-contract.md antes de integrar.
"""
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

DATA_DIR = Path(__file__).resolve().parent / "data"
RESOLUCIONES = {"horaria": "hour", "diaria": "day", "mensual": "month"}
# Contrato público v1.
MIN_DIARIO = "pml_min"
MAX_DIARIO = "pml_max"


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


def validar_metadata(m):
    """Valida el contrato v1 sin escribir archivos ni inferir fechas."""
    if not isinstance(m, dict) or m.get("version_esquema") != "1":
        raise DatosNoDisponibles("Se requiere metadata del esquema 1.")
    try:
        for campo, esperado in (("fuente", "CENACE SW-PML, MDA, SIN"),
                                ("unidades", "MXN/MWh"),
                                ("convencion_hora", "1-24 hora final")):
            if m[campo] != esperado:
                raise ValueError(f"{campo} incompatible")
        fechas = {k: date.fromisoformat(m[k]) for k in
                  ("diario_desde", "diario_hasta", "horario_desde", "horario_hasta")}
        if not (fechas["diario_desde"] <= fechas["horario_desde"] <=
                fechas["horario_hasta"] <= fechas["diario_hasta"]):
            raise ValueError("rangos inconsistentes")
        if (fechas["horario_hasta"] - fechas["horario_desde"]).days >= 365:
            raise ValueError("ventana horaria mayor que 365 días")
        generado = datetime.fromisoformat(m["generado_utc"].replace("Z", "+00:00"))
        if generado.utcoffset() != timedelta(0):
            raise ValueError("generado_utc debe incluir zona UTC")
        if type(m["nodos"]) is not int or m["nodos"] < 1:
            raise ValueError("conteo de nodos inválido")
        archivos = m["archivos"]
        if not isinstance(archivos, dict) or not archivos:
            raise ValueError("manifiesto vacío")
        for nombre, info in archivos.items():
            if not re.fullmatch(r"(?:hourly/\d{4}-\d{2}-\d{2}\.parquet|daily/\d{4}-\d{2}\.parquet|nodes\.parquet)", nombre):
                raise ValueError("ruta fuera del contrato")
            if not isinstance(info, dict) or type(info.get("filas")) is not int or info["filas"] < 0:
                raise ValueError("conteo de filas inválido")
            if not isinstance(info.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", info["sha256"]):
                raise ValueError("sha256 inválido")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise DatosNoDisponibles("metadata.json no cumple el contrato v1.") from exc
    return m


def metadata(data_dir=DATA_DIR):
    try:
        return validar_metadata(json.loads((Path(data_dir) / "metadata.json").read_text()))
    except (OSError, ValueError) as exc:
        raise DatosNoDisponibles("Falta metadata.json válido del esquema 1.") from exc


def actualizado_cdmx(generado_utc):
    instante = datetime.fromisoformat(generado_utc.replace("Z", "+00:00"))
    if instante.utcoffset() != timedelta(0):
        raise DatosNoDisponibles("La fecha de generación debe incluir zona UTC.")
    return instante.astimezone(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S %Z")


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
    """Verifica manifiesto, SHA-256, filas y esquema; las filas se auditan en scripts/."""
    root = Path(data_dir)
    m = metadata(root)
    esperados = {"nodes.parquet"}
    for tipo, prefijo in (("hourly", "horario"), ("daily", "diario")):
        esperados.update(str(Path(p).relative_to(root)) for p in
                         _archivos(tipo, m[f"{prefijo}_desde"], m[f"{prefijo}_hasta"], root))
    presentes = {str(p.relative_to(root)) for p in root.rglob("*.parquet")}
    if set(m["archivos"]) != esperados or presentes != esperados:
        raise DatosNoDisponibles("Las particiones no coinciden con el manifiesto y sus rangos.")
    requeridas = {
        "hourly": {"nodo": pa.string(), "fecha": pa.date32(), "hora": pa.int32(), "pml": pa.float64()},
        "daily": {"nodo": pa.string(), "fecha": pa.date32(), "horas_validas": pa.int32(),
                  "suma_pml": pa.float64(), "suma_pml_cuadrado": pa.float64(),
                  "horas_negativas": pa.int32(), MIN_DIARIO: pa.float64(), MAX_DIARIO: pa.float64()},
        "nodes": {"nodo": pa.string(), "primera_fecha": pa.date32(), "ultima_fecha": pa.date32()},
    }
    for nombre in sorted(esperados):
        path = root / nombre
        grupo = "nodes" if nombre == "nodes.parquet" else path.parent.name
        try:
            with path.open("rb") as archivo:
                digest = hashlib.file_digest(archivo, "sha256").hexdigest()
            if digest != m["archivos"][nombre]["sha256"].lower():
                raise DatosNoDisponibles(f"SHA-256 no coincide: {nombre}.")
            parquet = pq.ParquetFile(path)
            if parquet.metadata.num_rows != m["archivos"][nombre]["filas"]:
                raise DatosNoDisponibles(f"Conteo de filas no coincide: {nombre}.")
            esquema = parquet.schema_arrow
            if set(esquema.names) != set(requeridas[grupo]):
                raise DatosNoDisponibles(f"Columnas incompatibles en {nombre}.")
            for columna, tipo in requeridas[grupo].items():
                if esquema.field(columna).type != tipo:
                    raise DatosNoDisponibles(f"Tipo incompatible: {grupo}.{columna}.")
            if grupo == "nodes" and parquet.metadata.num_rows != m["nodos"]:
                raise DatosNoDisponibles("Conteo de nodos incompatible con metadata.")
            for i in range(parquet.metadata.num_row_groups):
                row_group = parquet.metadata.row_group(i)
                if any(row_group.column(j).compression != "ZSTD" for j in range(row_group.num_columns)):
                    raise DatosNoDisponibles(f"Compresión distinta de zstd en {nombre}.")
        except (OSError, pa.ArrowException) as exc:
            raise DatosNoDisponibles(f"No se puede leer {nombre}.") from exc
    # La fuente de fechas de la interfaz es siempre metadata.json.
    return {"desde": _fecha(m["diario_desde"]), "hasta": _fecha(m["diario_hasta"]),
            "horario_desde": _fecha(m["horario_desde"]), "horario_hasta": _fecha(m["horario_hasta"]),
            "generado_utc": m["generado_utc"]}


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
           COUNT(*) FILTER (WHERE pml < 0) AS horas_negativas,
           MIN(fecha) AS primera_fecha,
           MAX(fecha) AS ultima_fecha
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
        WHERE nodo = ? AND fecha BETWEEN ? AND ? AND horas_validas > 0
        GROUP BY periodo ORDER BY periodo
    """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin])


def estadisticas_diarias(nodo, inicio, fin, data_dir=DATA_DIR):
    """Mismos estadísticos reconstruibles; cuantiles horarios no disponibles."""
    df = _consulta(f"""
        WITH acumulado AS (
            SELECT COALESCE(SUM(horas_validas), 0)::BIGINT AS n,
                   SUM(suma_pml) AS s, SUM(suma_pml_cuadrado) AS q,
                   MIN({MIN_DIARIO}) AS minimo, MAX({MAX_DIARIO}) AS maximo,
                   COALESCE(SUM(horas_negativas), 0)::BIGINT AS negativas,
                   MIN(fecha) AS primera_fecha, MAX(fecha) AS ultima_fecha
            FROM read_parquet(?) WHERE nodo = ? AND fecha BETWEEN ? AND ? AND horas_validas > 0
        )
        SELECT n AS horas_con_dato,
               (CAST(? AS DATE) - CAST(? AS DATE) + 1) * 24 AS horas_del_rango,
               ROUND(s / NULLIF(n, 0), 2) AS promedio,
               NULL::DOUBLE AS mediana,
               CASE WHEN n > 1 THEN ROUND(SQRT(GREATEST(0, (q - s*s/n) / (n-1))), 2) END AS desv_std,
               minimo, maximo, NULL::DOUBLE AS p10, NULL::DOUBLE AS p90,
               negativas AS horas_negativas, primera_fecha, ultima_fecha
        FROM acumulado
    """, [_archivos("daily", inicio, fin, data_dir), nodo, inicio, fin, fin, inicio])
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / df["horas_del_rango"], 1)
    return df


def catalogo(data_dir=DATA_DIR):
    """Catálogo público entregado por el pipeline, sin configuración privada."""
    return _consulta("SELECT DISTINCT nodo FROM read_parquet(?) WHERE nodo IS NOT NULL ORDER BY nodo",
                     [str(Path(data_dir) / "nodes.parquet")])["nodo"].tolist()


def observado(data_dir=DATA_DIR):
    """Primer y último día con dato de cada nodo, según nodes.parquet (no son altas/bajas oficiales)."""
    df = _consulta("SELECT nodo, primera_fecha, ultima_fecha FROM read_parquet(?)",
                   [str(Path(data_dir) / "nodes.parquet")])
    return {n: (_fecha(a), _fecha(b)) for n, a, b in df.itertuples(index=False)}


_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def marcar_periodos(df, inicio, fin, resolucion):
    """Añade a una serie las horas posibles de cada periodo dentro del rango y si es parcial.

    Un periodo es parcial si el rango elegido no cubre el día o mes completo, o si tiene
    menos horas con dato que horas posibles. No cambia los promedios.
    """
    inicio, fin = _rango(inicio, fin)
    df = df.copy()
    if df.empty:
        for c in ("desde", "hasta", "horas_posibles", "parcial", "etiqueta"):
            df[c] = []
        return df
    desde, hasta, posibles, parcial, etiqueta = [], [], [], [], []
    for periodo, horas in zip(df["periodo"], df["horas"]):
        dia = _fecha(periodo)
        if resolucion == "mensual":
            fin_mes = (dia.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            a, b = max(dia, inicio), min(fin_mes, fin)
            dias_mes = fin_mes.day
            n = (b - a).days + 1
            texto = f"{_MESES[dia.month - 1]} {dia.year}"
            if n < dias_mes:
                texto += f" ({a.day}–{b.day} {_MESES[dia.month - 1]}: {n} de {dias_mes} días)"
            posible = n * 24
        elif resolucion == "diaria":
            a = b = dia
            texto, posible = dia.isoformat(), 24
        else:
            a = b = dia
            texto, posible = str(periodo)[:16], 1
        desde.append(a)
        hasta.append(b)
        posibles.append(posible)
        es_parcial = int(horas) < posible or (resolucion == "mensual" and texto.endswith("días)"))
        parcial.append(bool(es_parcial))
        etiqueta.append(texto + (f" · {int(horas)} de {posible} h con dato" if int(horas) < posible else ""))
    df["desde"], df["hasta"], df["horas_posibles"] = desde, hasta, posibles
    df["parcial"], df["etiqueta"] = parcial, etiqueta
    return df

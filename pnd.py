"""Precio de zona de carga (PND) de PML Explorer (v0.7.0).

Carril separado del PML: lee solo la carpeta pública `pnd/` (contrato PND v1, generado por
power-market-lab/scripts/exportar_pnd.py y revisado por validar_pnd.py) y nunca `data/`.
Funciones puras sin Streamlit, para probarlas sin levantar la app.

Contrato PND v1 (pnd/):
    hourly/AAAA-MM-DD.parquet   sistema, mercado, zona_carga, fecha DATE, hora INTEGER (1-24, hora final),
                                pnd, energia, perdidas, congestion (DOUBLE, MXN/MWh), zstd
    zonas.parquet               zona_carga, primera_fecha, ultima_fecha
    metadata.json               version_esquema "1", generado_utc, desde, hasta, zonas, archivos{filas, sha256},
                                dias_corregidos (opcional), dias_sin_dato (opcional, ver abajo)

Un día sin dato no es precio cero: no tiene archivo, se lista en `dias_sin_dato` y no se rellena.
`dias_sin_dato` (decisión de producto 2026-11-20) es una lista de objetos con la evidencia de la consulta real
al servicio: {"fecha", "consultado_utc", "status" y/o "http", "resumen", "url"}. No es una ausencia permanente:
es «sin dato disponible en la consulta verificada» y el pipeline lo reintenta. Un hueco sin esa evidencia, o un
día declarado que sí tiene archivo, invalida el paquete.
Los promedios son simples sobre las horas con dato, igual que en el PML.
"""
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

PND_DIR = Path(os.environ.get("PML_PND_DIR") or Path(__file__).resolve().parent / "pnd")
UNIDADES = {"horaria": "hour", "diaria": "day", "mensual": "month"}
ESQUEMA_HORARIO = {"sistema": pa.string(), "mercado": pa.string(), "zona_carga": pa.string(),
                   "fecha": pa.date32(), "hora": pa.int32(), "pnd": pa.float64(), "energia": pa.float64(),
                   "perdidas": pa.float64(), "congestion": pa.float64()}
ESQUEMA_ZONAS = {"zona_carga": pa.string(), "primera_fecha": pa.date32(), "ultima_fecha": pa.date32()}
CAMPOS = ("version_esquema", "generado_utc", "desde", "hasta", "zonas", "archivos")


class PndNoDisponible(Exception):
    """El paquete PND falta o no cumple el contrato: la modalidad PND no se ofrece."""


def _fecha(valor):
    return date.fromisoformat(str(valor)[:10])


def _dias(inicio, fin):
    return [inicio + timedelta(days=i) for i in range((fin - inicio).days + 1)]


def metadata_pnd(carpeta=PND_DIR):
    ruta = Path(carpeta) / "metadata.json"
    try:
        m = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PndNoDisponible("No hay metadata.json de PND legible.") from exc
    if not isinstance(m, dict) or any(c not in m for c in CAMPOS) or m["version_esquema"] != "1":
        raise PndNoDisponible("metadata.json de PND no cumple el contrato v1.")
    return m


def huella_pnd(carpeta=PND_DIR):
    """Clave de caché: cambia con metadata.json y con cualquier archivo añadido o reemplazado."""
    raiz = Path(carpeta)
    h = hashlib.sha256()
    for p in [raiz / "metadata.json", raiz / "zonas.parquet"] + sorted(raiz.glob("hourly/*.parquet")):
        h.update(str(p.relative_to(raiz)).encode())
        if p.is_file():
            s = p.stat()
            h.update(f"{s.st_size}:{s.st_mtime_ns}".encode())
            if p.suffix == ".json":
                h.update(p.read_bytes())
    return h.hexdigest()


def _revisar_parquet(ruta, nombre, info, esquema):
    with ruta.open("rb") as archivo:
        if hashlib.file_digest(archivo, "sha256").hexdigest() != str(info["sha256"]).lower():
            raise PndNoDisponible(f"SHA-256 no coincide: {nombre}.")
    parquet = pq.ParquetFile(ruta)
    if parquet.metadata.num_rows != info["filas"]:
        raise PndNoDisponible(f"Conteo de filas no coincide: {nombre}.")
    if parquet.schema_arrow.names != list(esquema) or any(
            parquet.schema_arrow.field(c).type != t for c, t in esquema.items()):
        raise PndNoDisponible(f"Esquema incompatible en {nombre}.")
    for i in range(parquet.metadata.num_row_groups):
        grupo = parquet.metadata.row_group(i)
        if any(grupo.column(j).compression != "ZSTD" for j in range(grupo.num_columns)):
            raise PndNoDisponible(f"Compresión distinta de zstd en {nombre}.")


def inspeccionar_pnd(carpeta=PND_DIR):
    """Verifica manifiesto, archivos esperados, SHA-256, filas, esquema y zstd. Devuelve los límites del paquete.

    Las reglas de filas (24 horas, zonas exactas, finitos, descuadre) las revisa validar_pnd.py antes de publicar.
    """
    raiz = Path(carpeta)
    m = metadata_pnd(raiz)
    try:
        desde, hasta = _fecha(m["desde"]), _fecha(m["hasta"])
        evidencia = {}
        for e in m.get("dias_sin_dato", []):
            if not (isinstance(e, dict) and e.get("consultado_utc") and (e.get("status") or e.get("http"))):
                raise PndNoDisponible("Un día sin dato no trae la evidencia de su consulta.")
            evidencia[_fecha(e["fecha"])] = e
        sin_dato = sorted(evidencia)
        if len(sin_dato) != len(m.get("dias_sin_dato", [])):
            raise PndNoDisponible("Días sin dato repetidos en metadata.")
        corregidos = sorted({_fecha(d) for d in m.get("dias_corregidos", [])})
    except (TypeError, ValueError) as exc:
        raise PndNoDisponible("Fechas inválidas en metadata.json de PND.") from exc
    if desde > hasta or any(not desde < d < hasta for d in sin_dato):
        raise PndNoDisponible("Rango de PND inválido o días sin dato fuera del rango.")
    esperados = {f"hourly/{d}.parquet" for d in _dias(desde, hasta) if d not in sin_dato} | {"zonas.parquet"}
    presentes = {p.relative_to(raiz).as_posix() for p in raiz.rglob("*.parquet")}
    if set(m["archivos"]) != esperados or presentes != esperados:
        raise PndNoDisponible("Los archivos de PND no coinciden con el manifiesto y su rango.")
    try:
        for nombre in sorted(esperados):
            _revisar_parquet(raiz / nombre, nombre, m["archivos"][nombre],
                             ESQUEMA_ZONAS if nombre == "zonas.parquet" else ESQUEMA_HORARIO)
        if pq.ParquetFile(raiz / "zonas.parquet").metadata.num_rows != m["zonas"]:
            raise PndNoDisponible("Conteo de zonas incompatible con metadata.")
    except (OSError, KeyError, pa.ArrowException) as exc:
        raise PndNoDisponible("No se pueden leer los archivos de PND.") from exc
    return {"desde": desde, "hasta": hasta, "generado_utc": m["generado_utc"], "zonas": m["zonas"],
            "dias_sin_dato": sin_dato, "evidencia_sin_dato": evidencia, "dias_corregidos": corregidos}


def zonas(carpeta=PND_DIR):
    """{zona_carga: (primera_fecha, ultima_fecha)} en orden alfabético."""
    with duckdb.connect(":memory:") as con:
        filas = con.execute(f"SELECT * FROM read_parquet('{Path(carpeta) / 'zonas.parquet'}') ORDER BY 1").fetchall()
    return {z: (a, b) for z, a, b in filas}


def regiones_de_zonas(catalogo):
    """{Región de Control: [zonas]} a partir del catálogo de NodosP (una zona puede estar en dos regiones)."""
    pares = catalogo[["region_control", "zona_carga"]].dropna().drop_duplicates()
    return {r: sorted(g["zona_carga"]) for r, g in pares.groupby("region_control")}


def _archivos(inicio, fin, carpeta):
    """Archivos de los días del rango que existen (un día sin dato no tiene archivo)."""
    rutas = [Path(carpeta) / "hourly" / f"{d}.parquet" for d in _dias(inicio, fin)]
    return [str(p) for p in rutas if p.is_file()]


def _rango(inicio, fin):
    inicio, fin = _fecha(inicio), _fecha(fin)
    if inicio > fin:
        raise ValueError("La fecha 'Desde' debe ser anterior a 'Hasta'.")
    return inicio, fin


def _consulta(sql, parametros):
    with duckdb.connect(":memory:") as con:
        return con.execute(sql, parametros).df()


def serie_pnd(zona, inicio, fin, resolucion, carpeta=PND_DIR):
    """PND y componentes promedio por periodo (promedio simple de las horas con dato) y horas de cada periodo."""
    inicio, fin = _rango(inicio, fin)
    archivos = _archivos(inicio, fin, carpeta)
    if not archivos:
        return _consulta("SELECT NULL::TIMESTAMP periodo, NULL::DOUBLE pnd_promedio, NULL::DOUBLE energia, "
                         "NULL::DOUBLE perdidas, NULL::DOUBLE congestion, 0::BIGINT horas WHERE FALSE", [])
    return _consulta(f"""
        SELECT date_trunc('{UNIDADES[resolucion]}', fecha + to_hours(hora - 1)) AS periodo,
               ROUND(AVG(pnd), 2) AS pnd_promedio, ROUND(AVG(energia), 2) AS energia,
               ROUND(AVG(perdidas), 2) AS perdidas, ROUND(AVG(congestion), 2) AS congestion,
               COUNT(*) AS horas
        FROM read_parquet(?)
        WHERE zona_carga = ? AND fecha BETWEEN ? AND ?
        GROUP BY periodo ORDER BY periodo
    """, [archivos, zona, inicio, fin])


def estadisticas_pnd(zona, inicio, fin, carpeta=PND_DIR):
    """Indicadores sobre las horas con dato del rango; la cobertura es horas con dato ÷ (24 × días)."""
    inicio, fin = _rango(inicio, fin)
    archivos = _archivos(inicio, fin, carpeta)
    horas_rango = len(_dias(inicio, fin)) * 24
    if not archivos:
        archivos, filtro = [], "FALSE"
    else:
        filtro = "zona_carga = ? AND fecha BETWEEN ? AND ?"
    fuente = "read_parquet(?)" if archivos else "(SELECT NULL::DOUBLE pnd, NULL::DOUBLE energia, " \
        "NULL::DOUBLE perdidas, NULL::DOUBLE congestion, NULL::DATE fecha)"
    df = _consulta(f"""
        SELECT COUNT(*) AS horas_con_dato,
               ROUND(AVG(pnd), 2) AS promedio, ROUND(MEDIAN(pnd), 2) AS mediana,
               ROUND(STDDEV_SAMP(pnd), 2) AS desv_std, MIN(pnd) AS minimo, MAX(pnd) AS maximo,
               ROUND(QUANTILE_CONT(pnd, 0.10), 2) AS p10, ROUND(QUANTILE_CONT(pnd, 0.90), 2) AS p90,
               COUNT(*) FILTER (WHERE pnd < 0) AS horas_negativas,
               ROUND(AVG(energia), 2) AS energia, ROUND(AVG(perdidas), 2) AS perdidas,
               ROUND(AVG(congestion), 2) AS congestion,
               MIN(fecha) AS primera_fecha, MAX(fecha) AS ultima_fecha
        FROM {fuente} WHERE {filtro}
    """, ([archivos, zona, inicio, fin] if archivos else []))
    df["horas_del_rango"] = horas_rango
    df["cobertura_pct"] = round(100 * df["horas_con_dato"] / horas_rango, 1)
    return df

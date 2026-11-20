"""Precio de zona de carga (PND) de PML Explorer (v0.7.0).

Carril separado del PML: lee solo la carpeta pública `pnd/` (contrato PND v1, generado por
power-market-lab/scripts/exportar_pnd.py y revisado por validar_pnd.py) y nunca `data/`.
Funciones puras sin Streamlit, para probarlas sin levantar la app.

Contrato PND v1 (pnd/):
    hourly/AAAA-MM-DD.parquet   sistema, mercado, zona_carga, fecha DATE, hora INTEGER (1-24, hora final),
                                pnd, energia, perdidas, congestion (DOUBLE, MXN/MWh), zstd
    zonas.parquet               zona_carga, primera_fecha, ultima_fecha
    metadata.json               version_esquema "1", generado_utc, desde, hasta, zonas, archivos{filas, sha256},
                                dias_corregidos, dias_sin_dato (obligatorio, ver abajo)

Un día sin dato no es precio cero: no tiene archivo, se lista en `dias_sin_dato` y no se rellena.
`dias_sin_dato` (obligatorio; decisión de producto 2026-11-20) es la copia exacta de las entradas de
power-market-lab config/pnd_dias_sin_dato.json: {"fecha", "estado", "decision", "consultas": [{"consultado_utc",
"url", "http", "status", "respuesta", "sha256_respuesta"}], "notas"}. Cada consulta debe ser HTTP 200 + ZERO_RESULTS. No es una ausencia permanente:
es «sin dato disponible en la consulta verificada» y el pipeline lo reintenta. Un hueco sin esa evidencia, o un
día declarado que sí tiene archivo, invalida el paquete.
Los promedios son simples sobre las horas con dato, igual que en el PML.
"""
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

PND_DIR = Path(os.environ.get("PML_PND_DIR") or Path(__file__).resolve().parent / "pnd")
URL_SERVICIO = "https://ws01.cenace.gob.mx:8082/SWPEND/SIM/SIN/MDA/"
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


def es_utc(texto):
    """True si es fecha y hora ISO en UTC terminada en Z, p. ej. 2026-11-20T12:18:26Z (igual que validar_pnd.py)."""
    try:
        return isinstance(texto, str) and texto.endswith("Z") and bool(datetime.fromisoformat(texto[:-1] + "+00:00"))
    except ValueError:
        return False


def evidencia_valida(consulta, dia):
    """Una consulta real al servicio que respondió «sin resultados» para ese día: HTTP 200 + ZERO_RESULTS, hora UTC,
    URL de SW-PEND con la fecha del día y respuesta resumida. Un 500, un ERROR o un timeout no son un faltante válido."""
    return (isinstance(consulta, dict) and consulta.get("http") == 200 and consulta.get("status") == "ZERO_RESULTS"
            and es_utc(consulta.get("consultado_utc")) and isinstance(consulta.get("url"), str)
            and consulta["url"].startswith(URL_SERVICIO) and f"/{dia:%Y/%m/%d}/" in consulta["url"]
            and isinstance(consulta.get("respuesta"), str) and consulta["respuesta"].strip() != "")


def ultima_consulta(entrada):
    """Consulta más reciente que respalda un día sin dato, o None si la entrada no tiene evidencia aceptable.

    Forma única (power-market-lab config/pnd_dias_sin_dato.json, copiada tal cual a metadata.dias_sin_dato):
    {"fecha", "estado", "decision", "consultas": [{consultado_utc, url, http, status, respuesta, sha256_respuesta}],
    "notas"}. Todas las consultas listadas deben ser evidencia válida (mismo criterio que validar_pnd.py).
    """
    if not isinstance(entrada, dict) or not isinstance(entrada.get("fecha"), str):
        return None
    try:
        dia = _fecha_iso(entrada["fecha"])
    except ValueError:
        return None
    consultas = entrada.get("consultas")
    if not isinstance(consultas, list) or not consultas or not all(evidencia_valida(c, dia) for c in consultas):
        return None
    return max(consultas, key=lambda c: c["consultado_utc"])


def _fecha_iso(texto):
    """Fecha AAAA-MM-DD exacta (sin aceptar 20261105 ni otros formatos que fromisoformat admite)."""
    if not (isinstance(texto, str) and len(texto) == 10 and texto[4] == texto[7] == "-"):
        raise ValueError(f"fecha inválida: {texto!r}")
    return date.fromisoformat(texto)


def _es_hash(texto):
    return isinstance(texto, str) and len(texto) == 64 and all(c in "0123456789abcdefABCDEF" for c in texto)


def inspeccionar_pnd(carpeta=PND_DIR):
    """Verifica manifiesto, archivos esperados, SHA-256, filas, esquema y zstd. Devuelve los límites del paquete.

    Cualquier metadata malformada (tipos, campos faltantes, evidencia) termina en PndNoDisponible: así solo se
    deshabilita la modalidad PND y PML sigue igual. Las reglas de filas (24 horas, zonas exactas, finitos,
    descuadre) las revisa validar_pnd.py antes de publicar.
    """
    try:
        return _inspeccionar(Path(carpeta))
    except PndNoDisponible:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OSError, pa.ArrowException, duckdb.Error) as exc:
        raise PndNoDisponible(f"Paquete PND ilegible o malformado ({type(exc).__name__}).") from exc


def _inspeccionar(raiz):
    m = metadata_pnd(raiz)
    desde, hasta = _fecha_iso(m["desde"]), _fecha_iso(m["hasta"])
    if desde > hasta or not es_utc(m["generado_utc"]):
        raise PndNoDisponible("Rango o fecha de generación inválidos en metadata.json de PND.")
    if not isinstance(m["zonas"], int) or isinstance(m["zonas"], bool) or m["zonas"] < 1:
        raise PndNoDisponible("metadata.zonas inválido.")
    lista = m.get("dias_sin_dato")
    if not isinstance(lista, list):
        raise PndNoDisponible("metadata.dias_sin_dato falta o no es una lista.")
    evidencia = {}
    for e in lista:
        consulta = ultima_consulta(e)
        if consulta is None:
            raise PndNoDisponible("Un día sin dato no trae evidencia válida de su consulta.")
        dia = _fecha_iso(e["fecha"])
        if dia in evidencia or not desde < dia < hasta:
            raise PndNoDisponible("Día sin dato repetido o fuera del rango del paquete.")
        evidencia[dia] = consulta
    sin_dato = sorted(evidencia)
    corregidos = m.get("dias_corregidos", [])
    if not isinstance(corregidos, list) or not all(isinstance(d, str) for d in corregidos):
        raise PndNoDisponible("metadata.dias_corregidos no es una lista de fechas.")
    corregidos = sorted({_fecha_iso(d) for d in corregidos})
    archivos = m["archivos"]
    if not isinstance(archivos, dict) or not all(
            isinstance(info, dict) and isinstance(info.get("filas"), int) and not isinstance(info["filas"], bool)
            and info["filas"] >= 0 and _es_hash(info.get("sha256")) for info in archivos.values()):
        raise PndNoDisponible("metadata.archivos no tiene filas enteras y sha256 por archivo.")
    esperados = {f"hourly/{d}.parquet" for d in _dias(desde, hasta) if d not in sin_dato} | {"zonas.parquet"}
    presentes = {p.relative_to(raiz).as_posix() for p in raiz.rglob("*.parquet")}
    if set(archivos) != esperados or presentes != esperados:
        raise PndNoDisponible("Los archivos de PND no coinciden con el manifiesto y su rango.")
    for nombre in sorted(esperados):
        _revisar_parquet(raiz / nombre, nombre, archivos[nombre],
                         ESQUEMA_ZONAS if nombre == "zonas.parquet" else ESQUEMA_HORARIO)
    if pq.ParquetFile(raiz / "zonas.parquet").metadata.num_rows != m["zonas"]:
        raise PndNoDisponible("Conteo de zonas incompatible con metadata.")
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

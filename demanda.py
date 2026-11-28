"""v0.10.0 · Demanda del día por región (Issue #32): lector del contrato «demanda v1».

El Mac mini lee cada hora la Gráfica de Demanda pública del CENACE y publica un CSV por día en la rama
`datos-demanda` de este repo (power-market-lab/docs/demanda-contrato.md). La app NUNCA consulta al CENACE: solo lee
esos archivos, con caché, y valida su forma antes de mostrar una cifra.

Reglas (las mismas del contrato):
- MW por hora CENACE (1–24, hora final: la 1 es 00:00–01:00), día de operación de Ciudad de México.
- Una celda vacía es «sin dato», nunca 0. `estado_demanda`: ok · pendiente (la hora aún no termina) · sin_dato.
- SIN no incluye BCA ni BCS. SEN = SIN + BCA + BCS, solo en las horas en que las tres tienen el valor.
- Información indicativa de la operación, no para liquidación. La demanda real se revisa durante el día.
"""
import io
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

import pandas as pd

URL_BASE = os.environ.get(
    "DEMANDA_URL", "https://raw.githubusercontent.com/edarji/pml-explorer-web/datos-demanda/demanda")
FUENTE = "https://www.cenace.gob.mx/graficademanda.aspx"
CONTRATO = "demanda v1"
TIMEOUT_S = 8
COLUMNAS = ["fecha", "gerencia", "hora", "demanda_mw", "pronostico_mw", "generacion_mw", "enlace_mw",
            "estado_demanda", "consultado_utc"]
ESTADOS = {"ok", "pendiente", "sin_dato"}
GERENCIAS = ["SIN", "BCA", "BCS", "CENTRAL", "NORESTE", "NOROESTE", "NORTE", "OCCIDENTAL", "ORIENTAL", "PENINSULAR"]
SEN = "SEN"
NOMBRES = {"SEN": "SEN (SIN + BCA + BCS)", "SIN": "SIN",
           "BCA": "Baja California", "BCS": "Baja California Sur", "CENTRAL": "Central", "NORESTE": "Noreste",
           "NOROESTE": "Noroeste", "NORTE": "Norte", "OCCIDENTAL": "Occidental", "ORIENTAL": "Oriental",
           "PENINSULAR": "Peninsular"}
OPCIONES = [SEN, "SIN", "BCA", "BCS", "CENTRAL", "NORESTE", "NOROESTE", "NORTE", "OCCIDENTAL", "ORIENTAL",
            "PENINSULAR"]
MEXICO = timezone(timedelta(hours=-6))  # Ciudad de México, sin horario de verano desde 2022 (igual que el colector)
AL_DIA_MIN = 90  # el Mac mini lee a los :10 de cada hora; con la caché, una lectura de más de 90 min está atrasada


class DemandaInvalida(Exception):
    """Los archivos publicados no cumplen el contrato: no se muestra ninguna cifra."""


def _texto(url, timeout=TIMEOUT_S):
    with urlopen(Request(url, headers={"User-Agent": "pml-explorer"}), timeout=timeout) as r:
        return r.read().decode("utf-8")


def descargar(url_base=URL_BASE, timeout=TIMEOUT_S):
    """(metadata.json, CSV del último día publicado) como texto. Dos lecturas; errores de red tal cual."""
    metadata = _texto(f"{url_base}/metadata.json", timeout)
    dias = json.loads(metadata).get("dias") or []
    if not dias:
        raise DemandaInvalida("metadata.json no tiene días publicados")
    return metadata, _texto(f"{url_base}/{dias[-1]}.csv", timeout)


def leer(metadata_texto, csv_texto):
    """Valida y lee lo publicado -> (metadata, tabla del día con las columnas del contrato)."""
    try:
        m = json.loads(metadata_texto)
    except ValueError as error:
        raise DemandaInvalida(f"metadata.json no es JSON: {error}") from error
    if m.get("contrato") != CONTRATO:
        raise DemandaInvalida(f"contrato inesperado: {m.get('contrato')!r}")
    try:
        df = pd.read_csv(io.StringIO(csv_texto), dtype={"gerencia": str, "estado_demanda": str})
    except (ValueError, pd.errors.ParserError) as error:
        raise DemandaInvalida(f"el CSV no se puede leer: {error}") from error
    if list(df.columns) != COLUMNAS:
        raise DemandaInvalida(f"columnas inesperadas: {list(df.columns)}")
    if df.empty or df["fecha"].nunique() != 1:
        raise DemandaInvalida("el CSV debe traer un solo día")
    if not set(df["gerencia"]) <= set(GERENCIAS) or not set(df["estado_demanda"]) <= ESTADOS:
        raise DemandaInvalida("gerencias o estados fuera del contrato")
    if df.duplicated(["gerencia", "hora"]).any() or not df["hora"].between(1, 24).all():
        raise DemandaInvalida("horas repetidas o fuera de 1–24")
    for c in ("demanda_mw", "pronostico_mw", "generacion_mw", "enlace_mw"):
        df[c] = pd.to_numeric(df[c], errors="raise").astype("float64")
    if (df["demanda_mw"] <= 0).any() or (df["demanda_mw"].notna() != (df["estado_demanda"] == "ok")).any():
        raise DemandaInvalida("la demanda y su estado no coinciden (un 0 nunca es demanda)")
    df["hora"] = df["hora"].astype("int64")
    df["consultado_utc"] = pd.to_datetime(df["consultado_utc"], utc=True)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    return m, df.sort_values(["gerencia", "hora"]).reset_index(drop=True)


def con_sen(df):
    """Agrega las filas SEN = SIN + BCA + BCS. Una hora sin alguna de las tres queda sin valor (no se suma media)."""
    tres = df[df["gerencia"].isin(["SIN", "BCA", "BCS"])]
    filas = []
    for hora, g in tres.groupby("hora"):
        completa = len(g) == 3
        demanda = g["demanda_mw"].sum() if completa and g["demanda_mw"].notna().all() else None
        pronostico = g["pronostico_mw"].sum() if completa and g["pronostico_mw"].notna().all() else None
        if demanda is not None:
            estado = "ok"
        elif completa and (g["estado_demanda"] == "pendiente").any():
            estado = "pendiente"
        else:
            estado = "sin_dato"
        filas.append({"fecha": g["fecha"].iloc[0], "gerencia": SEN, "hora": hora, "demanda_mw": demanda,
                      "pronostico_mw": pronostico, "generacion_mw": None, "enlace_mw": None,
                      "estado_demanda": estado, "consultado_utc": g["consultado_utc"].min()})
    if not filas:
        return df
    sen = pd.DataFrame(filas, columns=COLUMNAS).astype({"demanda_mw": "float64", "pronostico_mw": "float64",
                                                       "generacion_mw": "float64", "enlace_mw": "float64"})
    return pd.concat([df, sen], ignore_index=True)


def tramo(hora):
    """Hora CENACE -> texto del intervalo: 16 -> '15:00–16:00'."""
    return f"{hora - 1:02d}:00–{hora:02d}:00"


def resumen(df, gerencia):
    """Cifras del panel para una gerencia (o SEN). Ninguna se inventa: si falta, queda en None."""
    g = df[df["gerencia"] == gerencia].sort_values("hora")
    if g.empty:
        return None
    ok = g[g["estado_demanda"] == "ok"]
    r = {"gerencia": gerencia, "fecha": g["fecha"].iloc[0], "horas_ok": len(ok),
         "horas_pendientes": int((g["estado_demanda"] == "pendiente").sum()),
         "horas_sin_dato": int((g["estado_demanda"] == "sin_dato").sum()),
         "consultado_utc": g["consultado_utc"].max(), "hora": None, "demanda": None, "pronostico": None,
         "desvio_mw": None, "desvio_pct": None, "max_real": None, "hora_max_real": None, "max_pronostico": None,
         "hora_max_pronostico": None}
    if not ok.empty:
        ultima = ok.iloc[-1]
        r.update(hora=int(ultima["hora"]), demanda=float(ultima["demanda_mw"]))
        if pd.notna(ultima["pronostico_mw"]):
            r["pronostico"] = float(ultima["pronostico_mw"])
            r["desvio_mw"] = r["demanda"] - r["pronostico"]
            r["desvio_pct"] = 100 * r["desvio_mw"] / r["pronostico"] if r["pronostico"] else None
        pico = ok.loc[ok["demanda_mw"].idxmax()]
        r.update(max_real=float(pico["demanda_mw"]), hora_max_real=int(pico["hora"]))
    pron = g[g["pronostico_mw"].notna()]
    if not pron.empty:
        pico = pron.loc[pron["pronostico_mw"].idxmax()]
        r.update(max_pronostico=float(pico["pronostico_mw"]), hora_max_pronostico=int(pico["hora"]))
    return r


def frescura(ultima_lectura, fecha, ahora=None):
    """Estado de la publicación: «al_dia», «atrasada» o «otro_dia» (el último día publicado no es hoy en CDMX)."""
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lectura = pd.Timestamp(ultima_lectura).to_pydatetime().astimezone(timezone.utc)
    minutos = max(0, int((ahora - lectura).total_seconds() // 60))
    if str(fecha) != str(ahora.astimezone(MEXICO).date()):
        estado = "otro_dia"
    elif minutos > AL_DIA_MIN:
        estado = "atrasada"
    else:
        estado = "al_dia"
    return {"estado": estado, "minutos": minutos, "lectura_cdmx": lectura.astimezone(MEXICO)}


def hace(minutos):
    if minutos < 60:
        return f"hace {minutos} min"
    horas, resto = divmod(minutos, 60)
    if horas < 48:
        return f"hace {horas} h {resto:02d} min" if resto else f"hace {horas} h"
    return f"hace {horas // 24} días"


def serie(df, gerencia):
    """Tabla larga para la gráfica: hora, serie (Real / Pronóstico), MW. Solo horas con valor; nada se interpola."""
    g = df[df["gerencia"] == gerencia][["hora", "demanda_mw", "pronostico_mw"]]
    largo = g.melt("hora", var_name="serie", value_name="mw").dropna()
    largo["serie"] = largo["serie"].map({"demanda_mw": "Real", "pronostico_mw": "Pronóstico"})
    return largo.sort_values(["serie", "hora"]).reset_index(drop=True)

"""Guatemala Price Explorer · datos: lectura validada del paquete gt-1 y cálculos de la vista.

Funciones puras (sin Streamlit). El paquete lo escribe solo el pipeline de power-market-lab (scripts/gt_publico.py)
en `gt/`. No hay ningún cálculo del AMM aquí: los precios son los del posdespacho; los agregados son promedios simples
de las horas con dato, iguales a los del paquete (`poe_diario`, `poe_mensual`), y no se rellena ningún faltante.

Hora: 0-23 = inicio del intervalo ("De" del AMM) en hora de Guatemala (UTC-6, sin horario de verano).
Separado de México: no lee ni escribe `data/` ni `pnd/`.
"""
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from exportar import INICIO_FORMULA

GT_DIR = Path(__file__).resolve().parent / "gt"
VERSION_ESQUEMA = "gt-1"
ARCHIVOS = ("poe_horario", "poe_diario", "poe_mensual")
ZONA_GT = ZoneInfo("America/Guatemala")
HORA_PUBLICACION = 14       # el posdespacho de D sale en D+1 hacia las 12:00 (pauta, no garantía): margen hasta 14:00
RESOLUCIONES = ("horaria", "diaria", "mensual")
FRECUENCIA = {"horaria": "h", "diaria": "D", "mensual": "MS"}


class PaqueteInvalido(Exception):
    """El paquete no se puede leer con confianza: no se muestra ninguna cifra."""


# ------------------------------------------------------------------ paquete

def huella(carpeta=GT_DIR):
    """sha256 de metadata.json: cambia con cualquier archivo nuevo o corregido, aunque la fecha final sea la misma."""
    return hashlib.sha256((Path(carpeta) / "metadata.json").read_bytes()).hexdigest()


def leer(carpeta=GT_DIR):
    """{"poe_horario", "poe_diario", "poe_mensual", "metadata"} verificando esquema, sha256 y filas."""
    carpeta = Path(carpeta)
    try:
        meta = json.loads((carpeta / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PaqueteInvalido(f"metadata.json ilegible ({e})") from e
    if meta.get("version_esquema") != VERSION_ESQUEMA:
        raise PaqueteInvalido(f"esquema {meta.get('version_esquema')!r}, se esperaba {VERSION_ESQUEMA!r}")
    salida = {"metadata": meta}
    for nombre in ARCHIVOS:
        ruta = carpeta / f"{nombre}.parquet"
        declarado = meta.get("archivos", {}).get(ruta.name, {})
        if not ruta.is_file():
            raise PaqueteInvalido(f"falta {ruta.name}")
        if hashlib.sha256(ruta.read_bytes()).hexdigest() != declarado.get("sha256"):
            raise PaqueteInvalido(f"{ruta.name} no coincide con su sha256")
        df = pd.read_parquet(ruta)
        if len(df) != declarado.get("filas"):
            raise PaqueteInvalido(f"{ruta.name}: {len(df)} filas, metadata declara {declarado.get('filas')}")
        salida[nombre] = df
    h = salida["poe_horario"]
    h["fecha"] = pd.to_datetime(h["fecha"]).dt.date
    h["periodo"] = pd.to_datetime(h["fecha"]) + pd.to_timedelta(h["hora"], unit="h")
    salida["poe_diario"]["fecha"] = pd.to_datetime(salida["poe_diario"]["fecha"]).dt.date
    return salida


def limites(meta):
    return {"desde": date.fromisoformat(meta["desde"]), "hasta": date.fromisoformat(meta["hasta"])}


def actualizado_gt(meta):
    """Hora de generación del paquete en hora de Guatemala ("AAAA-MM-DD HH:MM")."""
    utc = datetime.fromisoformat(meta["generado_utc"].replace("Z", "+00:00"))
    return utc.astimezone(ZONA_GT).strftime("%Y-%m-%d %H:%M")


def frescura(meta, ahora):
    """("al_dia" | "atrasado", último día de operación esperado). `ahora` con zona horaria.

    Se espera el posdespacho de D en D+1 desde las HORA_PUBLICACION h (hora GT). Antes de esa hora no se marca atraso.
    """
    ahora = ahora.astimezone(ZONA_GT)
    esperado = ahora.date() - timedelta(days=1 if ahora.hour >= HORA_PUBLICACION else 2)
    return ("al_dia" if limites(meta)["hasta"] >= esperado else "atrasado"), esperado


# ------------------------------------------------------------------ consultas

def seleccion(horario, inicio, fin):
    return horario[(horario["fecha"] >= inicio) & (horario["fecha"] <= fin)]


def serie(horario, inicio, fin, resolucion):
    """periodo, poe (USD/MWh), horas, minimo, maximo. Diaria y mensual: promedio simple de las horas con dato.

    Un periodo sin dato no tiene fila: la gráfica lo muestra como hueco (no se une ni se rellena).
    """
    sel = seleccion(horario, inicio, fin)
    if resolucion == "horaria":
        return (sel[["periodo", "poe_usd_mwh", "generador_marginal"]].rename(columns={"poe_usd_mwh": "poe"})
                .assign(horas=1, minimo=lambda d: d["poe"], maximo=lambda d: d["poe"]).reset_index(drop=True))
    clave = pd.to_datetime(sel["fecha"]).dt.to_period("M" if resolucion == "mensual" else "D").dt.to_timestamp()
    g = sel.groupby(clave)["poe_usd_mwh"]
    return (pd.DataFrame({"poe": g.mean(), "horas": g.count(), "minimo": g.min(), "maximo": g.max()})
            .rename_axis("periodo").reset_index())


def estadisticas(horario, inicio, fin):
    sel = seleccion(horario, inicio, fin)["poe_usd_mwh"]
    horas_rango = ((fin - inicio).days + 1) * 24
    return {"horas": int(sel.count()), "horas_rango": horas_rango,
            "cobertura_pct": round(100 * sel.count() / horas_rango, 1) if horas_rango else 0.0,
            "promedio": sel.mean(), "mediana": sel.median(), "minimo": sel.min(), "maximo": sel.max(),
            "desviacion": sel.std(), "horas_cero_o_negativas": int((sel <= 0).sum())}


def marginales(horario, inicio, fin):
    """Participación de cada generador marginal en las horas del rango (%). No es participación en energía."""
    sel = seleccion(horario, inicio, fin)["generador_marginal"].fillna("(sin dato)")
    if sel.empty:
        return pd.DataFrame(columns=["generador_marginal", "horas", "pct_horas"])
    c = sel.value_counts()
    return pd.DataFrame({"generador_marginal": c.index, "horas": c.values,
                         "pct_horas": (100 * c.values / c.values.sum()).round(1)})


def dias_sin_dato(meta, inicio, fin):
    return [d for d in meta.get("dias_sin_dato", []) if str(inicio) <= d <= str(fin)]


# ------------------------------------------------------------------ CSV y enlaces

def _texto_seguro(valor):
    """Un texto que empieza como fórmula se escribe con apóstrofo para que Excel no lo ejecute."""
    if isinstance(valor, str) and valor.startswith(INICIO_FORMULA):
        return "'" + valor
    return valor


def csv(horario, inicio, fin, resolucion):
    """(bytes, nombre): CSV de la resolución pedida, con los mismos valores de la gráfica y la tabla.

    UTF-8 con BOM, coma, punto decimal. Sin filas para periodos sin dato. El nombre declara mercado, fuente,
    variable, unidad, resolución y rango; la hora horaria es la de inicio en hora de Guatemala.
    """
    s = serie(horario, inicio, fin, resolucion)
    if s.empty:
        raise ValueError("sin datos en el rango")
    if resolucion == "horaria":
        out = pd.DataFrame({"fecha": s["periodo"].dt.date.astype(str), "hora_inicio_gt": s["periodo"].dt.hour,
                            "poe_usd_mwh": s["poe"].round(2),
                            "generador_marginal": s["generador_marginal"].map(_texto_seguro)})
    else:
        tiempo = s["periodo"].dt.strftime("%Y-%m" if resolucion == "mensual" else "%Y-%m-%d")
        out = pd.DataFrame({("mes" if resolucion == "mensual" else "fecha"): tiempo,
                            "poe_promedio_usd_mwh": s["poe"].round(2), "horas_validas": s["horas"],
                            "poe_minimo_usd_mwh": s["minimo"].round(2), "poe_maximo_usd_mwh": s["maximo"].round(2)})
    nombre = f"gt_amm_poe_posdespacho_usd_mwh_{resolucion}_{inicio}_{fin}.csv"
    return out.to_csv(index=False).encode("utf-8-sig"), nombre


def leer_url(params, lim):
    """(inicio, fin, resolucion) válidos desde ?desde=&hasta=&resolucion=, o None en lo que falte o no sirva."""
    def fecha(clave):
        try:
            d = date.fromisoformat(params.get(clave, ""))
        except ValueError:
            return None
        return d if lim["desde"] <= d <= lim["hasta"] else None
    inicio, fin = fecha("desde"), fecha("hasta")
    if inicio and fin and inicio > fin:
        inicio = fin = None
    res = params.get("resolucion")
    return inicio, fin, (res if res in RESOLUCIONES else None)


def escribir_url(inicio, fin, resolucion):
    return {"desde": str(inicio), "hasta": str(fin), "resolucion": resolucion}

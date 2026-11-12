"""Catálogo geográfico de NodosP (v0.6.0): datos de referencia, separados de los precios.

El catálogo dice CÓMO SE LLAMA y DÓNDE ESTÁ cada NodoP según una versión del Catálogo de NodosP de
CENACE. Nunca participa en un cálculo: las vistas reciben solo la clave elegida y calculan igual que
antes. Este módulo no importa Streamlit ni las vistas, y las vistas no lo importan a él.

Archivos (generados por scripts/preparar_catalogo.py, publicados por PR):
    referencia/nodos_catalogo.parquet   una fila por NodoP del SIN
    referencia/nodos_catalogo.json      procedencia: fuente, versión, SHA-256 del Excel, conteos

Si faltan o no pasan la validación, la app sigue funcionando como en v0.5.1: solo claves.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

REFERENCIA_DIR = Path(__file__).with_name("referencia")
ARCHIVO = "nodos_catalogo.parquet"
MANIFIESTO = "nodos_catalogo.json"
COLUMNAS = ("nodo", "nombre", "region_control", "zona_carga", "tension_kv", "estado_inegi", "estado")
SIN_CLASIFICACION = "Sin clasificación verificada"
SEPARADOR = " · "


class CatalogoInvalido(Exception):
    """El catálogo de referencia no cumple su contrato; la app debe ignorarlo, no adivinar."""


def validar(df, manifiesto):
    """Comprueba el contrato del catálogo ya leído. Lanza CatalogoInvalido con el motivo."""
    if list(df.columns) != list(COLUMNAS):
        raise CatalogoInvalido(f"Columnas inesperadas: {list(df.columns)}")
    if df["nodo"].isna().any() or (df["nodo"].str.strip() != df["nodo"]).any() or (df["nodo"] == "").any():
        raise CatalogoInvalido("Hay claves vacías o con espacios.")
    if df["nodo"].duplicated().any():
        repetidas = sorted(df.loc[df["nodo"].duplicated(), "nodo"].unique())[:5]
        raise CatalogoInvalido(f"Claves duplicadas, por ejemplo {repetidas}.")
    if df["nombre"].isna().any():
        raise CatalogoInvalido("Hay nodos sin nombre oficial.")
    # Región y zona van juntas: un nodo o tiene las dos o no tiene ninguna.
    if (df["region_control"].isna() != df["zona_carga"].isna()).any():
        raise CatalogoInvalido("Hay nodos con región sin zona o zona sin región.")
    if manifiesto.get("filas") != len(df):
        raise CatalogoInvalido("El número de filas no coincide con el manifiesto.")
    for campo in ("fuente", "version_catalogo", "sha256_origen"):
        if not manifiesto.get(campo):
            raise CatalogoInvalido(f"Falta «{campo}» en el manifiesto.")


def cargar(directorio=None):
    """Lee y valida el catálogo. Devuelve (DataFrame, manifiesto) o lanza CatalogoInvalido."""
    directorio = Path(REFERENCIA_DIR if directorio is None else directorio)
    ruta, ruta_m = directorio / ARCHIVO, directorio / MANIFIESTO
    if not ruta.is_file() or not ruta_m.is_file():
        raise CatalogoInvalido("No hay catálogo de referencia publicado.")
    manifiesto = json.loads(ruta_m.read_text(encoding="utf-8"))
    digest = hashlib.sha256(ruta.read_bytes()).hexdigest()
    if digest != manifiesto.get("sha256_parquet"):
        raise CatalogoInvalido("El SHA-256 del catálogo no coincide con su manifiesto.")
    df = pd.read_parquet(ruta)
    validar(df, manifiesto)
    return df, manifiesto


def unir(nodos, catalogo):
    """Left join: TODOS los nodos con precios, con su clasificación si existe.

    `nodos` es la lista de claves del paquete de precios. Ningún nodo se pierde ni se duplica
    (el catálogo ya se validó sin claves repetidas). Un nodo sin fila en el catálogo, o con región
    «No Aplica» en CENACE, queda con región y zona vacías: «sin clasificación verificada».
    """
    base = pd.DataFrame({"nodo": list(nodos)})
    union = base.merge(catalogo, on="nodo", how="left", validate="one_to_one")
    union["clasificado"] = union["region_control"].notna()
    return union


def etiqueta(nodo, nombres):
    """Texto de una opción del selector: «Clave · Nombre», o solo la clave si no hay nombre."""
    nombre = nombres.get(nodo)
    return f"{nodo}{SEPARADOR}{nombre}" if nombre else nodo


def regiones(union):
    """Regiones de control disponibles, en orden alfabético."""
    return sorted(union["region_control"].dropna().unique())


def _acotar(union, region=None, estado=None):
    filas = union
    if region is not None:
        filas = filas[filas["region_control"] == region]
    if estado is not None:
        filas = filas[filas["estado"] == estado]
    return filas


def estados(union, region=None):
    """Estados (INEGI, según CENACE) con nodos en la región elegida (o en todas).

    El estado es un dato por nodo: una región o una zona de carga puede abarcar varios estados.
    """
    return sorted(_acotar(union, region)["estado"].dropna().unique())


def zonas(union, region=None, estado=None):
    """Zonas de carga de los nodos que cumplen región y estado (None = «Todas»).

    Se calcula desde los nodos y no con una tabla zona -> región: en CENACE una misma zona puede
    tener nodos en dos regiones (CENTRO ORIENTE, v2026-10-23) y en varios estados.
    """
    return sorted(_acotar(union, region, estado)["zona_carga"].dropna().unique())


def filtrar(union, region=None, zona=None, estado=None):
    """Claves que cumplen los filtros; None en un filtro significa «Todas»."""
    filas = _acotar(union, region, estado)
    if zona is not None:
        filas = filas[filas["zona_carga"] == zona]
    return filas["nodo"].tolist()

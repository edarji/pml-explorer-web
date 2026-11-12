"""Comparación entre dos versiones del catálogo de NodosP y reglas para aceptarla (v0.6.1).

Funciones puras, sin red ni archivos: reciben DataFrames con las columnas de catalogo.COLUMNAS
y devuelven datos. Las usa scripts/revisar_catalogo.py, la revisión semanal en el Mac mini.

Principio: se automatiza la detección y la validación, NO la aprobación. Un bloqueo impide
preparar una propuesta; una advertencia la deja lista pero señalada para que Lalo la revise.
"""
import hashlib
import re

import pandas as pd

import catalogo as cat

CAMPOS = ("nombre", "region_control", "zona_carga", "estado", "tension_kv")
CLASIFICACION = ("region_control", "zona_carga", "estado")
UMBRAL_RECLASIFICADOS = 0.02  # más de 2 % de nodos con región, zona o estado distinto: bloqueo
# Clave de NodoP: dos dígitos de región, letras/dígitos y, casi siempre, «-tensión» (01PMX1115 no lo trae).
PATRON_CLAVE = re.compile(r"\b\d{2}[A-Z][A-Z0-9]{2,}(?:-\d+(?:\.\d+)?)?\b")


def huella_contenido(df):
    """SHA-256 del catálogo ya limpio, ordenado por clave y escrito como texto.

    Dos Excel distintos (otro nombre, guardado de nuevo) con los mismos datos dan la misma huella.
    """
    ordenado = df[list(cat.COLUMNAS)].sort_values("nodo").reset_index(drop=True)
    texto = ordenado.to_csv(index=False, na_rep="", float_format="%.3f", lineterminator="\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _distinto(a, b):
    if pd.isna(a) and pd.isna(b):
        return False
    if pd.isna(a) or pd.isna(b):
        return True
    return a != b


def comparar(anterior, nuevo):
    """Altas, bajas y cambios por campo entre el catálogo aprobado y el nuevo.

    Devuelve {"altas": [...], "bajas": [...], "cambios": DataFrame(nodo, campo, antes, despues)}.
    """
    viejo, nue = anterior.set_index("nodo"), nuevo.set_index("nodo")
    altas = sorted(set(nue.index) - set(viejo.index))
    bajas = sorted(set(viejo.index) - set(nue.index))
    filas = []
    for nodo in sorted(set(nue.index) & set(viejo.index)):
        for campo in CAMPOS:
            antes, despues = viejo.at[nodo, campo], nue.at[nodo, campo]
            if _distinto(antes, despues):
                filas.append({"nodo": nodo, "campo": campo,
                              "antes": None if pd.isna(antes) else antes,
                              "despues": None if pd.isna(despues) else despues})
    cambios = pd.DataFrame(filas, columns=["nodo", "campo", "antes", "despues"])
    return {"altas": altas, "bajas": bajas, "cambios": cambios}


def claves_mencionadas(textos):
    """Claves de NodoP que aparecen en textos libres de «Control de Cambios»."""
    claves = set()
    for t in textos:
        claves.update(PATRON_CLAVE.findall(str(t)))
    return claves


def evaluar(anterior, nuevo, dif, nodos_con_precio, explicadas=frozenset()):
    """Aplica la tabla de bloqueos, advertencias e información del diagnóstico v0.6.1.

    nodos_con_precio: claves del paquete público (data/nodes.parquet).
    explicadas: claves que menciona «Control de Cambios» en las versiones nuevas.
    Devuelve {"bloqueos": [...], "advertencias": [...], "informacion": [...]} con textos legibles.
    """
    bloqueos, advertencias, informacion = [], [], []
    con_precio = set(nodos_con_precio)
    nuevas_claves = set(nuevo["nodo"])
    cambios = dif["cambios"]

    perdidos = sorted(con_precio - nuevas_claves)
    if perdidos:
        bloqueos.append(f"{len(perdidos)} nodo(s) con precios publicados ya no están en el catálogo: "
                        f"{perdidos[:10]}")

    sin_region_antes = set(anterior.loc[anterior["region_control"].isna(), "nodo"])
    clasif = cambios[cambios["campo"].isin(CLASIFICACION)]
    desclasificados = sorted(set(clasif.loc[clasif["despues"].isna() & clasif["antes"].notna()
                                            & (clasif["campo"] == "region_control"), "nodo"]))
    if desclasificados:
        bloqueos.append(f"{len(desclasificados)} nodo(s) clasificados pasan a «No Aplica»: "
                        f"{desclasificados[:10]}")
    internacionales = sorted(set(clasif.loc[clasif["nodo"].isin(sin_region_antes)
                                            & clasif["despues"].notna(), "nodo"]))
    if internacionales:
        bloqueos.append(f"{len(internacionales)} nodo(s) sin región (internacionales) reciben región, "
                        f"zona o estado: {internacionales}")

    reclasificados = sorted(set(clasif["nodo"]))
    limite = UMBRAL_RECLASIFICADOS * len(anterior)
    if len(reclasificados) > limite:
        bloqueos.append(f"{len(reclasificados)} nodos cambian de región, zona o estado "
                        f"(más del {UMBRAL_RECLASIFICADOS:.0%}, límite {limite:.0f}): "
                        "probable reorganización o error masivo")

    sin_explicar = sorted((set(dif["altas"]) | set(dif["bajas"]) | set(reclasificados)) - set(explicadas))
    if sin_explicar:
        advertencias.append(f"{len(sin_explicar)} alta(s), baja(s) o reclasificación(es) que «Control de "
                            f"Cambios» no menciona: {sin_explicar[:10]}")
    explicados = sorted((set(dif["altas"]) | set(dif["bajas"]) | set(reclasificados)) & set(explicadas))
    if explicados:
        informacion.append(f"{len(explicados)} cambio(s) explicados por «Control de Cambios»: {explicados[:10]}")
    for campo, texto in (("nombre", "nombre"), ("tension_kv", "tensión")):
        n = sorted(set(cambios.loc[cambios["campo"] == campo, "nodo"]))
        if n:
            advertencias.append(f"{len(n)} cambio(s) de {texto} (pueden ser correcciones): {n[:10]}")

    solo_catalogo = sorted(nuevas_claves - con_precio)
    if solo_catalogo:
        informacion.append(f"{len(solo_catalogo)} nodo(s) del catálogo aún sin precios en el paquete "
                           f"(normal en altas recientes): {solo_catalogo[:10]}")
    if len(nuevo) != len(anterior):
        informacion.append(f"Total de nodos SIN: {len(anterior):,} → {len(nuevo):,} "
                           f"({len(dif['altas'])} altas, {len(dif['bajas'])} bajas)")
    return {"bloqueos": bloqueos, "advertencias": advertencias, "informacion": informacion}


def informe(datos, dif, evaluacion):
    """Texto Markdown del informe que lee Lalo. `datos` trae la procedencia (versión, URL, huellas)."""
    estado = "BLOQUEADO" if evaluacion["bloqueos"] else "APROBABLE (requiere revisión de Lalo)"
    lineas = [
        f"# Catálogo de NodosP · revisión {datos.get('revision', '')}",
        "",
        f"- Resultado: **{datos.get('resultado', '')}** · {estado}",
        f"- Versión nueva: {datos.get('version_nueva', '')} · aprobada: {datos.get('version_aprobada', '')}",
        f"- Archivo: {datos.get('archivo', '')}",
        f"- URL: {datos.get('url', '')}",
        f"- SHA-256 del Excel: {datos.get('sha256_excel', '')}",
        f"- Huella del contenido: {datos.get('huella_contenido', '')}",
        f"- Nodos SIN: {datos.get('filas', '')}",
        "",
    ]
    for titulo, clave in (("Bloqueos", "bloqueos"), ("Advertencias", "advertencias"),
                          ("Información", "informacion")):
        lineas.append(f"## {titulo}")
        lineas += [f"- {t}" for t in evaluacion[clave]] or ["- Nada"]
        lineas.append("")
    lineas += ["## Altas", ", ".join(dif["altas"]) or "Ninguna", "",
               "## Bajas", ", ".join(dif["bajas"]) or "Ninguna", "",
               "## Cambios por campo"]
    if dif["cambios"].empty:
        lineas.append("Ninguno")
    else:
        lineas += ["| Nodo | Campo | Antes | Después |", "|---|---|---|---|"]
        for f in dif["cambios"].itertuples():
            lineas.append(f"| {f.nodo} | {f.campo} | {f.antes} | {f.despues} |")
    lineas += ["", "La versión del catálogo no es la vigencia de cada NodoP. Nada se publica sin la "
               "aprobación de Lalo: este informe solo propone."]
    return "\n".join(lineas) + "\n"

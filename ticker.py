"""v0.8.5 · Ticker PND de la barra superior: promedio del día de unas zonas de carga y su cambio contra ayer.

No hay cálculo nuevo de PND: cada precio es el promedio del día de `ensemble.ranking_pnd` (promedio simple de las
horas con dato, ROUND(AVG(pnd), 2)), el mismo que ENSEMBLE y la vista SOLO PND muestran para esa zona y ese día.

- D = último día publicado del paquete PND con archivo (`ensemble.dia_pnd`), no el reloj ni el rango del usuario.
- D−1 = el día calendario inmediatamente anterior. Si no tiene archivo, no se busca otro más antiguo: «s/c vs ayer».
- Se compara solo si la zona tiene precio en D y en D−1. La diferencia es D − D−1 en MXN/MWh, con dos decimales.
- Si alguno de los dos días tiene menos de 24 horas con dato, la diferencia se muestra sin color ni flecha
  («parcial»): no se afirma que los dos días sean plenamente comparables.
- Una zona sin precio en D se muestra «sin dato». Nada se imputa ni se rellena con cero.
"""
from datetime import timedelta
from pathlib import Path

import ensemble as ens

# Selección editorial inicial (Issue #34). Una zona por cada Gerencia de Control Regional del SIN, la de su ciudad
# principal, más Querétaro porque Occidental es la región con más zonas (26 de 101) y Guadalajara sola no cubre el
# Bajío. Nombres exactos de `pnd/zonas.parquet`; la región sale del Catálogo de NodosP de CENACE (región de control
# de los nodos de cada zona). El paquete PND es solo del SIN: no hay zonas de Baja California ni Baja California Sur.
# Para cambiar la selección basta con editar esta tupla (el orden es el de la cinta).
ZONAS_TICKER = (
    ("VDM CENTRO", "Central"),
    ("MONTERREY", "Noreste"),
    ("GUADALAJARA", "Occidental"),
    ("QUERETARO", "Occidental"),
    ("PUEBLA", "Oriental"),
    ("MERIDA", "Peninsular"),
    ("CHIHUAHUA", "Norte"),
    ("HERMOSILLO", "Noroeste"),
)
HORAS_DIA = 24


def _ranking(dia, carpeta):
    """{zona: (promedio, horas)} del día, o None si el día no tiene archivo en el paquete (sin dato publicado)."""
    if dia is None or not (Path(carpeta) / "hourly" / f"{dia}.parquet").is_file():
        return None
    r = ens.ranking_pnd(dia, carpeta)
    return {fila.elemento: (float(fila.promedio), int(fila.horas)) for fila in r.itertuples()}


def fichas(limites, carpeta, zonas_paquete, seleccion=ZONAS_TICKER):
    """Datos de la cinta. `limites`: {"desde", "hasta"} del paquete PND; `zonas_paquete`: zonas que existen en él.

    Devuelve {"dia", "dia_previo", "previo_publicado", "fichas": [...]} o None si el paquete no tiene ningún día.
    Las zonas de la selección que no existen en el paquete se omiten (no se inventa ninguna).
    """
    dia = ens.dia_pnd(limites["hasta"], limites, carpeta)
    if dia is None:
        return None
    previo = dia - timedelta(days=1)
    hoy = _ranking(dia, carpeta) or {}
    ayer = _ranking(previo, carpeta) if previo >= limites["desde"] else None
    salida = []
    for zona, region in seleccion:
        if zona not in zonas_paquete:
            continue
        ficha = {"zona": zona, "region": region, "precio": None, "horas": 0, "previo": None, "horas_previo": 0,
                 "delta": None, "direccion": None, "estado": "sin_dato"}
        if zona in hoy:
            ficha["precio"], ficha["horas"] = hoy[zona]
            ficha["estado"] = "sin_comparacion"
            if ayer and zona in ayer:
                ficha["previo"], ficha["horas_previo"] = ayer[zona]
                ficha["delta"] = round(ficha["precio"] - ficha["previo"], 2)
                completo = ficha["horas"] >= HORAS_DIA and ficha["horas_previo"] >= HORAS_DIA
                ficha["estado"] = "comparable" if completo else "parcial"
                if completo:
                    ficha["direccion"] = "sube" if ficha["delta"] > 0 else "baja" if ficha["delta"] < 0 else "igual"
        salida.append(ficha)
    return {"dia": dia, "dia_previo": previo, "previo_publicado": ayer is not None, "fichas": salida}


def cambio(ficha):
    """Cambio contra ayer como texto («▲ +12.30», «s/c vs ayer», «… · parcial 22/24 h»); vacío si no hay precio."""
    if ficha["estado"] == "sin_dato":
        return ""
    if ficha["estado"] == "sin_comparacion":
        return "s/c vs ayer" + (f" · {ficha['horas']} h" if ficha["horas"] < HORAS_DIA else "")
    flecha = {"sube": "▲ ", "baja": "▼ ", "igual": "= "}.get(ficha["direccion"], "")
    texto = f"{flecha}{ficha['delta']:+,.2f}"
    if ficha["estado"] == "parcial":
        texto += f" · parcial {ficha['horas']}/{ficha['horas_previo']} h"
    return texto


def texto_ficha(ficha):
    """Rótulo de la ficha: zona, precio del día y cambio contra ayer (sin color: el color lo pone la clase)."""
    if ficha["estado"] == "sin_dato":
        return f"{ficha['zona']} · sin dato"
    return f"{ficha['zona']} {ficha['precio']:,.2f} {cambio(ficha)}"


def descripcion(ficha, dia, previo):
    """Texto completo para la ayuda y lectores de pantalla (lo que la ficha abrevia)."""
    base = f"PND {ficha['zona']} (región {ficha['region']}), {dia}"
    if ficha["estado"] == "sin_dato":
        return f"{base}: sin dato publicado para esta zona."
    texto = f"{base}: {ficha['precio']:,.2f} MXN/MWh ({ficha['horas']} de 24 horas con dato)."
    if ficha["estado"] == "sin_comparacion":
        return texto + f" Sin comparación: {previo} no tiene dato publicado para esta zona."
    texto += f" {previo}: {ficha['previo']:,.2f} MXN/MWh. Cambio: {ficha['delta']:+,.2f} MXN/MWh."
    if ficha["estado"] == "parcial":
        texto += (f" Comparación parcial: {ficha['horas']} y {ficha['horas_previo']} horas con dato; "
                  "sin color porque los días no están completos.")
    return texto + " Toca para abrir el detalle de la zona."

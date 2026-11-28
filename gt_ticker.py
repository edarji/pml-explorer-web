"""Guatemala Price Explorer · ticker POE: promedio diario del último día publicado frente al día calendario anterior.

Mismas reglas que el ticker PND (ticker.py), con una sola serie nacional:
- D = último día de operación del paquete validado (no el reloj ni el rango elegido).
- D−1 = el día calendario anterior. Si no tiene dato, «sin comparación»; nunca se busca un día más antiguo.
- Δ = promedio(D) − promedio(D−1) en USD/MWh, redondeado a 2 decimales, sin porcentaje (la base puede ser 0 o < 0).
- Si alguno de los dos días tiene menos de 24 horas, la diferencia va sin color ni flecha («parcial»).
- Mínimo y máximo horario de D: extremos intradía del mismo precio nacional, no otros mercados.
"""
from datetime import timedelta

HORAS_DIA = 24
ROTULO = "GUATEMALA · AMM · POE posdespacho · promedio diario simple · USD/MWh · preliminar · no tiempo real"


def ficha(diario):
    """Datos de la cinta a partir de `poe_diario` del paquete. None si el paquete no tiene días."""
    if diario.empty:
        return None
    por_dia = diario.set_index("fecha")
    dia = max(por_dia.index)
    previo = dia - timedelta(days=1)
    d = por_dia.loc[dia]
    f = {"dia": dia, "dia_previo": previo, "precio": round(float(d["promedio"]), 2), "horas": int(d["horas_validas"]),
         "minimo": round(float(d["minimo"]), 2), "maximo": round(float(d["maximo"]), 2),
         "previo": None, "horas_previo": 0, "delta": None, "direccion": None, "estado": "sin_comparacion"}
    if previo in por_dia.index:
        p = por_dia.loc[previo]
        f["previo"], f["horas_previo"] = round(float(p["promedio"]), 2), int(p["horas_validas"])
        f["delta"] = round(f["precio"] - f["previo"], 2)
        completo = f["horas"] >= HORAS_DIA and f["horas_previo"] >= HORAS_DIA
        f["estado"] = "comparable" if completo else "parcial"
        if completo:
            f["direccion"] = "sube" if f["delta"] > 0 else "baja" if f["delta"] < 0 else "igual"
    return f


def cambio(f):
    if f["estado"] == "sin_comparacion":
        return "sin comparación"
    flecha = {"sube": "▲ ", "baja": "▼ ", "igual": "= "}.get(f["direccion"], "")
    texto = f"{flecha}{f['delta']:+,.2f}"
    if f["estado"] == "parcial":
        texto += f" · parcial {f['horas']}/{f['horas_previo']} h"
    return texto


def descripcion(f):
    """Texto completo para la ayuda y lectores de pantalla."""
    t = (f"POE Guatemala (AMM, posdespacho preliminar), día de operación {f['dia']}: promedio simple "
         f"{f['precio']:,.2f} USD/MWh ({f['horas']} de 24 horas). Mínimo horario {f['minimo']:,.2f}, "
         f"máximo horario {f['maximo']:,.2f} USD/MWh.")
    if f["estado"] == "sin_comparacion":
        return t + f" Sin comparación: {f['dia_previo']} no tiene dato publicado."
    t += f" {f['dia_previo']}: {f['previo']:,.2f} USD/MWh. Cambio: {f['delta']:+,.2f} USD/MWh."
    if f["estado"] == "parcial":
        t += " Comparación parcial: uno de los días no tiene las 24 horas; sin color."
    return t + " El color indica la dirección del precio, no una recomendación."

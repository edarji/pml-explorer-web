"""Rangos rápidos de fechas para PML Explorer (v0.4.1).

Solo aritmética de fechas: no consulta datos ni toca fórmulas. El ancla es la última fecha de operación
del paquete público (`limites["hasta"]`, que viene de `diario_hasta` en metadata.json), nunca el reloj.
"""
from datetime import timedelta

RANGOS_RAPIDOS = ("Último día", "Últimos 7 días", "Mes en curso", "Año en curso")


def rango_rapido(opcion, limites):
    """Devuelve (inicio, fin) de un rango rápido, recortado a las fechas del paquete.

    - «Último día»: el último día del paquete.
    - «Últimos 7 días»: los 7 días que terminan en el último día (inclusivo).
    - «Mes en curso»: del día 1 del mes del último día hasta ese último día (mes parcial).
    - «Año en curso» (v0.8.2, YTD): del 1 de enero del año del último día hasta ese último día.
    """
    fin = limites["hasta"]
    if opcion == "Último día":
        inicio = fin
    elif opcion == "Últimos 7 días":
        inicio = fin - timedelta(days=6)
    elif opcion == "Mes en curso":
        inicio = fin.replace(day=1)
    elif opcion == "Año en curso":
        inicio = fin.replace(month=1, day=1)
    else:
        raise ValueError(f"Rango rápido desconocido: {opcion!r}")
    # Si el paquete empieza después del inicio calculado, no se inventan días anteriores.
    return max(inicio, limites["desde"]), fin


# v0.9.1 · Granularidad según el rango (pedido de Eduardo, 2026-11-27). Lógica pura, sin Streamlit ni datos.
#
# - 1 día: solo horaria (una gráfica diaria o mensual de un día sería un solo punto).
# - 2 a 7 días: horaria o diaria.
# - Más de 7 días (Mes, YTD o fechas a mano): horaria, diaria o mensual.
# La horaria además debe caber en la horaria publicada (PML: ventana `horario_desde` a `horario_hasta`; PND: hasta
# `max_dias` días). Si no cabe, se ofrece lo demás y, si no queda nada (1 día fuera de la ventana horaria), diaria.
# Al pulsar 1D, 7D, Mes o YTD la gráfica vuelve a la primera permitida: horaria siempre que se pueda.
# Reemplaza la restauración de v0.8.10 (#40): ya no hay cambio automático a diaria que recordar.

GRANULARIDADES = ("horaria", "diaria", "mensual")


def admite_horaria(inicio, fin, limites, max_dias=None):
    """¿El rango cabe en la resolución horaria del paquete activo?

    PML: todo el rango dentro de la ventana horaria publicada (`horario_desde` a `horario_hasta`).
    PND: como mucho `max_dias` días (la serie horaria de PND cubre todo el paquete).
    """
    if "horario_desde" in limites and not (limites["horario_desde"] <= inicio <= fin <= limites["horario_hasta"]):
        return False
    return max_dias is None or (fin - inicio).days + 1 <= max_dias


def resoluciones_permitidas(inicio, fin, limites, max_dias=None):
    """Resoluciones que admite el rango, en orden (la primera es la predeterminada)."""
    dias = (fin - inicio).days + 1
    if dias < 1:  # fechas invertidas: la vista ya muestra su aviso; no se restringe nada
        return GRANULARIDADES
    por_rango = ("horaria",) if dias == 1 else ("horaria", "diaria") if dias <= 7 else GRANULARIDADES
    if not admite_horaria(inicio, fin, limites, max_dias):
        por_rango = tuple(r for r in por_rango if r != "horaria") or ("diaria",)
    return por_rango


def motivo_no_permitida(resolucion, inicio, fin, limites, max_dias=None):
    """Frase corta de por qué `resolucion` no está disponible para el rango (o None si lo está)."""
    if resolucion in resoluciones_permitidas(inicio, fin, limites, max_dias):
        return None
    dias = (fin - inicio).days + 1
    if resolucion == "horaria":
        if "horario_desde" in limites:
            return (f"La horaria cubre del {limites['horario_desde']} al {limites['horario_hasta']}; "
                    "este rango no cabe completo.")
        return f"La horaria admite hasta {max_dias} días."
    if dias == 1:
        return ("Con un día solo hay resolución horaria." if admite_horaria(inicio, fin, limites, max_dias)
                else "Un día fuera de la ventana horaria solo tiene resolución diaria.")
    return "Con 7 días o menos: horaria o diaria."

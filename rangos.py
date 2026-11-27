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


# v0.8.10 · Resolución tras un rango rápido (Issue #40). Sigue siendo lógica pura, sin Streamlit ni datos.
#
# YTD en horaria serían miles de puntos: la gráfica pasa sola a diaria (v0.8.2). Ese cambio automático queda
# anotado como «pendiente» para que 1D, 7D o Mes devuelvan la horaria, siempre que el nuevo rango la admita.
# Una diaria o mensual elegida por el usuario (antes de YTD o en «Fechas» después) no se toca: elegir la
# resolución a mano borra lo pendiente (eso lo hace la app en el on_change del selector).

def admite_horaria(inicio, fin, limites, max_dias=None):
    """¿El rango cabe en la resolución horaria del paquete activo?

    PML: todo el rango dentro de la ventana horaria publicada (`horario_desde` a `horario_hasta`).
    PND: como mucho `max_dias` días (la serie horaria de PND cubre todo el paquete).
    """
    if "horario_desde" in limites and not (limites["horario_desde"] <= inicio <= fin <= limites["horario_hasta"]):
        return False
    return max_dias is None or (fin - inicio).days + 1 <= max_dias


def resolucion_tras_rango(opcion, inicio, fin, resolucion, pendiente, limites, max_dias=None):
    """Devuelve (resolución, pendiente, aviso) después de pulsar un rango rápido ya aplicado a (inicio, fin).

    - YTD en horaria: pasa a diaria y deja «horaria» pendiente; aviso "auto".
    - 1D, 7D o Mes con «horaria» pendiente: la recupera si el rango la admite; si no, sigue en la resolución
      actual, conserva lo pendiente y avisa "sin_horaria" (nunca se dibuja una horaria sin datos).
    - Cualquier otro caso: no cambia la resolución.
    """
    if opcion == "Año en curso":
        if resolucion == "horaria":
            return "diaria", "horaria", "auto"
        return resolucion, pendiente, "auto" if pendiente else None
    if pendiente == "horaria":
        if admite_horaria(inicio, fin, limites, max_dias):
            return "horaria", None, None
        return resolucion, pendiente, "sin_horaria"
    return resolucion, None, None

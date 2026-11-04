"""Rangos rápidos de fechas para PML Explorer (v0.4.1).

Solo aritmética de fechas: no consulta datos ni toca fórmulas. El ancla es la última fecha de operación
del paquete público (`limites["hasta"]`, que viene de `diario_hasta` en metadata.json), nunca el reloj.
"""
from datetime import timedelta

RANGOS_RAPIDOS = ("Último día", "Últimos 7 días", "Mes en curso")


def rango_rapido(opcion, limites):
    """Devuelve (inicio, fin) de un rango rápido, recortado a las fechas del paquete.

    - «Último día»: el último día del paquete.
    - «Últimos 7 días»: los 7 días que terminan en el último día (inclusivo).
    - «Mes en curso»: del día 1 del mes del último día hasta ese último día (mes parcial).
    """
    fin = limites["hasta"]
    if opcion == "Último día":
        inicio = fin
    elif opcion == "Últimos 7 días":
        inicio = fin - timedelta(days=6)
    elif opcion == "Mes en curso":
        inicio = fin.replace(day=1)
    else:
        raise ValueError(f"Rango rápido desconocido: {opcion!r}")
    # Si el paquete empieza después del inicio calculado, no se inventan días anteriores.
    return max(inicio, limites["desde"]), fin

"""v0.8.0 · Graphite Trading | Ensemble & Solo: escena inicial y URL de cada escena.

Funciones puras, sin Streamlit ni datos, como `enlaces.py`.

- ENSEMBLE: tablero compacto del mercado (PML por nodo y PND por zona de carga, en secciones separadas).
- SOLO: el análisis de un nodo o de una zona; son las vistas de v0.7.0 sin cambios de cálculo.

Regla de entrada (plan aprobado en la Issue #19, decisión D2): si un enlace trae algún parámetro de análisis
(`vista`, `nodo`, `nodo_a`, `nodo_b`, `modalidad` o `zona`), abre SOLO con exactamente el resultado de v0.7.0.
Sin ellos (URL vacía, o solo fechas y resolución) abre ENSEMBLE. Todos los enlaces que la app genera desde
v0.5.1 traen nodo o zona, así que ningún enlace compartido cambia de análisis.
"""

ENSEMBLE = "ensemble"
SOLO = "solo"
PARAMETROS_SOLO = ("vista", "nodo", "nodo_a", "nodo_b", "modalidad", "zona")
PARAMETROS_ENSEMBLE = ("desde", "hasta", "resolucion")


def escena_de_enlace(parametros):
    """Escena con la que abre la sesión. `parametros`: {nombre: [valores]} tal como llegan en la URL."""
    return SOLO if any(p in parametros for p in PARAMETROS_SOLO) else ENSEMBLE


def enlace_ensemble(estado):
    """Parámetros de la URL en ENSEMBLE: solo fechas absolutas y resolución, sin vista, nodo ni zona.

    Así un enlace del tablero vuelve a abrir el tablero (no tiene parámetros de análisis) y conserva los filtros.
    """
    enlace = {}
    for clave in ("desde", "hasta"):
        if estado.get(clave) is not None:
            enlace[clave] = estado[clave].isoformat()
    if estado.get("resolucion"):
        enlace["resolucion"] = estado["resolucion"]
    return enlace

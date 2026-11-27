"""Enlaces compartibles de PML Explorer (v0.5.1).

Traduce entre los parámetros de la URL y los filtros de la aplicación. Son funciones puras: no usan
Streamlit ni consultan datos, por eso se prueban sin levantar la app. La URL guarda la configuración
del análisis (vista, nodos, fechas absolutas y resolución), nunca una copia de los datos.

Ejemplo:
    ?vista=comparacion&nodo_a=01AAN-85&nodo_b=01AGU-230&desde=2026-10-01&hasta=2026-11-04&resolucion=diaria

v0.7.0 · Precio de zona de carga (decisión F, 2026-11-13): ?modalidad=pnd&zona=MONTERREY&desde=...&hasta=...
&resolucion=... Un enlace sin `modalidad` es PML, exactamente como antes; los enlaces PML no cambian.
"""
from datetime import date

# Nombre en la URL -> etiqueta de la pestaña. La URL usa nombres cortos y estables: renombrar una
# pestaña no rompe los enlaces ya compartidos.
VISTAS_URL = {"historico": "1. PML histórico",
              "comparacion": "2. Comparar nodos (spread)",
              "componentes": "3. Componentes del PML",
              "estacional": "4. Chaly's Bebop"}  # v0.9.0 · vista estacional (Issue #42)
NODOS_DE_VISTA = {"historico": ("nodo",), "comparacion": ("nodo_a", "nodo_b"), "componentes": ("nodo",),
                  "estacional": ("nodo",)}
RESOLUCIONES_URL = ("horaria", "diaria", "mensual")
PARAMETROS = ("vista", "nodo", "nodo_a", "nodo_b", "desde", "hasta", "resolucion", "modalidad", "zona")
MODALIDADES_URL = ("pnd",)  # sin el parámetro: PML
# v0.8.9 · Parámetros opcionales: solo van en la URL cuando están activos, y si faltan no se avisa (el valor
# predeterminado es «apagado»). `yoy=1`: comparar con el mismo periodo del año anterior (PML histórico y PND).
OPCIONALES = ("yoy", "anio")
VISTAS_CON_YOY = ("historico",)
# v0.9.0 · `anio=AAAA`: año Y de la vista estacional (Chaly's Bebop). Sin él, el año más reciente con dato.


def leer_enlace(parametros, nodos, limites, zonas=None, limites_pnd=None):
    """Valida los parámetros de un enlace y devuelve (estado, problemas, faltantes).

    - `parametros`: {nombre: [valores]} tal como llegan en la URL (una lista por si vienen repetidos).
    - `estado`: solo los valores válidos, con las claves de los widgets (`vista`, `nodo`, `desde`...),
      listos para copiarse a st.session_state.
    - `problemas`: frases para el usuario; un valor inválido nunca se sustituye por otro en silencio.
    - `faltantes`: parámetros que el enlace no trae; la app usa sus valores predeterminados y lo dice.
    Sin ningún parámetro conocido no hay enlace que leer: devuelve todo vacío.
    v0.7.0: con `modalidad=pnd` se validan `zona` contra `zonas` y las fechas contra `limites_pnd`; si la
    publicación no trae PND (`zonas` None) el enlace se avisa como problema, nunca se abre como PML.
    """
    if not any(p in parametros for p in PARAMETROS):
        return {}, [], []
    estado, problemas, faltantes = {}, [], []

    def valor(nombre):
        """El valor único del parámetro, o None si falta o viene repetido (y anota el motivo)."""
        valores = parametros.get(nombre, [])
        if len(valores) > 1:
            problemas.append(f"El parámetro «{nombre}» aparece {len(valores)} veces; debe aparecer una sola.")
            return None
        if not valores:
            faltantes.append(nombre)
            return None
        return valores[0]

    if "modalidad" in parametros:
        modalidad = valor("modalidad")
        if modalidad not in MODALIDADES_URL:
            problemas.append(f"La modalidad «{modalidad}» no existe. Opción: pnd (sin el parámetro, PML).")
            return estado, problemas, faltantes
        if zonas is None or limites_pnd is None:
            problemas.append("Este enlace es de precios de zona de carga (PND), que no están en esta publicación.")
            return estado, problemas, faltantes
        estado["modalidad"] = modalidad
        zona = valor("zona")
        if zona is not None:
            if zona in zonas:
                estado["zona"] = zona
            else:
                problemas.append(f"La zona de carga «{zona}» no está en el paquete público de PND.")
        limites = limites_pnd
    else:
        vista = valor("vista")
        if vista is not None:
            if vista in VISTAS_URL:
                estado["vista"] = VISTAS_URL[vista]
            else:
                problemas.append(f"La vista «{vista}» no existe. Opciones: {', '.join(VISTAS_URL)}.")
        # Si la vista falta o es inválida, se revisan los nodos de la vista que mostrará la app (la primera).
        for clave in NODOS_DE_VISTA.get(vista, NODOS_DE_VISTA["historico"]):
            nodo = valor(clave)
            if nodo is None:
                continue
            if nodo in nodos:
                estado[clave] = nodo
            else:
                problemas.append(f"El nodo «{nodo}» ({clave}) no está en el paquete público. "
                                 "Búscalo por su clave NodoP en «Vista y filtros».")

    fechas = {}
    for clave in ("desde", "hasta"):
        texto = valor(clave)
        if texto is None:
            continue
        try:
            fechas[clave] = date.fromisoformat(texto)
        except ValueError:
            problemas.append(f"La fecha «{texto}» ({clave}) no es válida; el formato es AAAA-MM-DD.")
    fuera = [f"{clave} = {f}" for clave, f in fechas.items() if not limites["desde"] <= f <= limites["hasta"]]
    if fuera:
        # No se recorta el periodo: el análisis compartido sería otro sin que el usuario lo note.
        problemas.append(f"El periodo del enlace ({'; '.join(fuera)}) no está en el paquete público, que cubre "
                         f"del {limites['desde']} al {limites['hasta']}.")
    else:
        estado.update(fechas)  # Unas fechas invertidas pasan: la vista ya muestra su propio aviso.

    resolucion = valor("resolucion")
    if resolucion is not None:
        if resolucion in RESOLUCIONES_URL:
            estado["resolucion"] = resolucion
        else:
            problemas.append(f"La resolución «{resolucion}» no existe. Opciones: {', '.join(RESOLUCIONES_URL)}.")
    if "yoy" in parametros:  # opcional: si falta no se anota como faltante
        yoy = parametros["yoy"]
        if yoy == ["1"]:
            estado["yoy"] = True
        else:
            problemas.append("El parámetro «yoy» solo admite el valor 1 (comparar con el mismo periodo del año "
                             "anterior), una sola vez.")
    if estado.get("vista") == VISTAS_URL["estacional"]:  # usa el año calendario: fechas y resolución no le faltan
        faltantes = [f for f in faltantes if f not in ("desde", "hasta", "resolucion")]
    if "anio" in parametros:  # opcional, solo lo escribe la vista estacional
        anio = parametros["anio"]
        if (len(anio) == 1 and anio[0].isdigit() and len(anio[0]) == 4
                and limites["desde"].year <= int(anio[0]) <= limites["hasta"].year):
            estado["anio"] = int(anio[0])
        else:
            problemas.append(f"El año «{', '.join(anio)}» no es válido: debe ser un año entre "
                             f"{limites['desde'].year} y {limites['hasta'].year}, una sola vez.")
    return estado, problemas, faltantes


def construir_enlace(estado):
    """Parámetros de la URL para el estado actual: solo los de la vista activa, con fechas absolutas.

    `estado` usa las claves de los widgets; `vista` es la etiqueta de la pestaña. Devuelve {nombre: texto}.
    """
    if estado.get("modalidad") == "pnd":  # v0.7.0: zona de carga; la vista PML no va en el enlace
        enlace = {"modalidad": "pnd", "zona": estado["zona"]}
    else:
        vista = next(nombre for nombre, etiqueta in VISTAS_URL.items() if etiqueta == estado["vista"])
        enlace = {"vista": vista}
        for clave in NODOS_DE_VISTA[vista]:
            enlace[clave] = estado[clave]
    enlace["desde"] = estado["desde"].isoformat()
    enlace["hasta"] = estado["hasta"].isoformat()
    enlace["resolucion"] = estado["resolucion"]
    if estado.get("yoy") and (estado.get("modalidad") == "pnd" or enlace.get("vista") in VISTAS_CON_YOY):
        enlace["yoy"] = "1"
    if enlace.get("vista") == "estacional" and estado.get("anio"):
        enlace["anio"] = str(estado["anio"])
    return enlace

"""Exportación CSV de PML Explorer (v0.6.2).

Funciones puras: reciben los DataFrames que la vista ya calculó (y marcó con `marcar_periodos`), solo
eligen, renombran y ordenan columnas, y escriben el CSV. No consultan datos ni calculan precios: los
valores del archivo son exactamente los de la gráfica y la tabla de la aplicación.

Formato (aprobado 2026-11-13): coma como separador, punto decimal, UTF-8 con BOM (Excel reconoce los
acentos), una fila de encabezados en snake_case ASCII y ninguna fila decorativa. Un periodo sin dato no
tiene fila (no se inventan registros); una celda vacía significa «sin valor», nunca cero.
"""
import re

import pandas as pd

UNIDAD = "MXN/MWh"
# Prefijo del archivo según la vista (nombre de la vista en la URL -> prefijo).
PREFIJOS = {"historico": "pml_historico", "comparacion": "pml_spread", "componentes": "pml_componentes"}
# Un texto que empieza así puede ejecutarse como fórmula al abrir el CSV en Excel u hojas de cálculo.
INICIO_FORMULA = ("=", "+", "-", "@", "\t", "\r")


class SinDatosExportables(ValueError):
    """La consulta no tiene filas: no se genera un archivo que parezca válido."""


def _fecha(valor):
    return pd.Timestamp(valor).date().isoformat()


def columnas_tiempo(df, resolucion, horas="horas_con_dato"):
    """Columnas de tiempo y de horas según la resolución, a partir de `periodo` y de `marcar_periodos`.

    - horaria: fecha de operación y hora CENACE 1–24 (hora final: el periodo 00:00 es la hora 1).
    - diaria: fecha de operación, horas con dato, horas posibles y si el día es parcial.
    - mensual: mes, parte del mes dentro de la consulta (desde/hasta), horas y si es parcial.
    """
    periodo = pd.to_datetime(df["periodo"])
    if resolucion == "horaria":
        return pd.DataFrame({"fecha_operacion": periodo.dt.strftime("%Y-%m-%d"),
                             "hora_cenace": (periodo.dt.hour + 1).astype("int64")})
    if resolucion == "diaria":
        t = pd.DataFrame({"fecha_operacion": periodo.dt.strftime("%Y-%m-%d")})
    elif resolucion == "mensual":
        t = pd.DataFrame({"mes": periodo.dt.strftime("%Y-%m"),
                          "fecha_desde": [_fecha(x) for x in df["desde"]],
                          "fecha_hasta": [_fecha(x) for x in df["hasta"]]})
    else:
        raise ValueError(f"Resolución desconocida: {resolucion}")
    t[horas] = df["horas"].astype("int64").to_numpy()
    t["horas_posibles"] = df["horas_posibles"].astype("int64").to_numpy()
    t["periodo_parcial"] = ["true" if p else "false" for p in df["parcial"]]
    return t


# Columnas de tiempo que identifican el periodo; las de la vista van justo después y las horas al final.
CLAVES_TIEMPO = {"horaria": 2, "diaria": 1, "mensual": 3}


def _insertar(t, resolucion, columnas):
    for desplazamiento, (columna, valores) in enumerate(columnas):
        t.insert(CLAVES_TIEMPO[resolucion] + desplazamiento, columna, valores)
    return t


def tabla_historico(df, nodo, resolucion):
    """Vista 1: PML de un nodo. En horaria, `pml` es el PML de esa hora; si no, el promedio del periodo."""
    return _insertar(columnas_tiempo(df, resolucion), resolucion,
                     [("nodo", nodo), ("pml", df["pml_promedio"].to_numpy())])


def tabla_spread(d, nodo_a, nodo_b, resolucion):
    """Vista 2: spread A − B en las horas en que los dos nodos tienen dato (`horas_comunes`).

    `pml_a` y `pml_b` se promedian sobre esas mismas horas comunes (ver vista2.diferencial). El spread es
    el de la aplicación, calculado hora por hora y redondeado al final; puede diferir de pml_a − pml_b en ±0.01.
    """
    return _insertar(columnas_tiempo(d, resolucion, horas="horas_comunes"), resolucion, [
        ("nodo_a", nodo_a), ("nodo_b", nodo_b), ("pml_a", d["pml_a"].to_numpy()),
        ("pml_b", d["pml_b"].to_numpy()), ("spread_a_menos_b", d["dif_promedio"].to_numpy())])


def tabla_componentes(df, nodo, resolucion):
    """Vista 3: PML y componentes con su signo; descuadre promedio con signo (4 decimales)."""
    return _insertar(columnas_tiempo(df, resolucion), resolucion, [("nodo", nodo)] + [
        (columna, df[origen].to_numpy()) for columna, origen in (
            ("pml", "pml"), ("energia", "energia"), ("perdidas", "perdidas"),
            ("congestion", "congestion"), ("descuadre_promedio", "descuadre"))])


def metadatos(vista, resolucion, desde, hasta, observado_desde, observado_hasta, cobertura_pct,
              paquete, version_app):
    """Columnas constantes de contexto y procedencia, en orden.

    `paquete` es metadata.json ya validado por el lector. `paquete_generado_utc` es cuándo se generó el
    paquete público, no una fecha de operación. Sin rutas, equipos ni datos personales.
    """
    fuente, mercado, sistema = (p.strip() for p in paquete["fuente"].split(","))
    return {"vista": vista, "resolucion": resolucion,
            "consulta_desde": _fecha(desde), "consulta_hasta": _fecha(hasta),
            "observado_desde": _fecha(observado_desde), "observado_hasta": _fecha(observado_hasta),
            "cobertura_consulta_pct": float(cobertura_pct), "unidad": paquete["unidades"],
            "fuente": fuente, "mercado": mercado, "sistema": sistema,
            "paquete_generado_utc": paquete["generado_utc"], "esquema_datos": str(paquete["version_esquema"]),
            "version_app": version_app}


def nombre_archivo(vista, nodos, desde, hasta, resolucion):
    """Nombre descriptivo y seguro: pml_<vista>_<nodos>_<desde>[_<hasta>]_<resolucion>.csv."""
    seguro = [re.sub(r"[^A-Za-z0-9.-]", "_", n) for n in nodos]
    fechas = [_fecha(desde)] if _fecha(desde) == _fecha(hasta) else [_fecha(desde), _fecha(hasta)]
    return "_".join([PREFIJOS[vista], *seguro, *fechas, resolucion]) + ".csv"


def proteger_texto(valor):
    """Antepone ' a un texto que Excel leería como fórmula. Solo se aplica a columnas de texto."""
    return "'" + valor if isinstance(valor, str) and valor.startswith(INICIO_FORMULA) else valor


def a_csv(tabla, meta):
    """Bytes del CSV: tabla + columnas de metadatos, UTF-8 con BOM. Sin filas lanza SinDatosExportables."""
    if tabla is None or tabla.empty:
        raise SinDatosExportables("La consulta no tiene resultados para exportar.")
    salida = tabla.assign(**meta)
    for columna in salida.columns:
        if not pd.api.types.is_numeric_dtype(salida[columna]) and not pd.api.types.is_bool_dtype(salida[columna]):
            salida[columna] = salida[columna].map(proteger_texto)
    return salida.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")

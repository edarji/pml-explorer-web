"""v0.8.9 · Comparar YoY (Issue #27, fase 2): el mismo periodo del año anterior, alineado por calendario.

Funciones puras (sin Streamlit), como `enlaces.py` y `escena.py`. No hay cálculo de precios nuevo: los dos periodos
usan las mismas consultas de la vista (promedio simple de las horas con dato) y aquí solo se alinean y se restan.

- Periodo anterior: las mismas fechas un año antes (2026-10-25 → 2025-10-25). Un 29 de febrero pasa al 28.
- Se compara solo si los dos periodos tienen horas con dato. Si alguno no tiene todas sus horas (cobertura < 100 %),
  la diferencia se muestra sin color ni flecha («parcial»): no se afirma que sean plenamente comparables.
- Sin porcentajes: el precio base puede ser cero o negativo (misma regla que el ticker PND).
- Curva del año anterior: la serie diaria o mensual de ese periodo con sus fechas movidas un año, para dibujarla
  sobre la actual. Un 29 de febrero no tiene par en un año sin él y no se dibuja; nada se interpola.
"""
import pandas as pd


def un_anio_antes(dia):
    """La misma fecha un año antes; el 29 de febrero pasa al 28."""
    try:
        return dia.replace(year=dia.year - 1)
    except ValueError:
        return dia.replace(year=dia.year - 1, day=28)


def periodo_anterior(inicio, fin):
    return un_anio_antes(inicio), un_anio_antes(fin)


def comparacion(actual, anterior):
    """Compara dos filas de estadísticas (`horas_con_dato`, `horas_del_rango`, `promedio`, `cobertura_pct`).

    Devuelve {"estado", "actual", "anterior", "delta", "direccion", "cobertura", "cobertura_anterior"}.
    estado: "comparable" (las dos con 100 % de cobertura), "parcial" o "sin_anterior" (sin horas un año antes).
    """
    salida = {"actual": float(actual["promedio"]), "anterior": None, "delta": None, "direccion": None,
              "cobertura": float(actual["cobertura_pct"]), "cobertura_anterior": float(anterior["cobertura_pct"])
              if anterior is not None and pd.notna(anterior["cobertura_pct"]) else 0.0}
    if anterior is None or int(anterior["horas_con_dato"]) == 0 or pd.isna(anterior["promedio"]):
        return salida | {"estado": "sin_anterior"}
    salida["anterior"] = float(anterior["promedio"])
    salida["delta"] = round(salida["actual"] - salida["anterior"], 2)
    completo = salida["cobertura"] >= 100 and salida["cobertura_anterior"] >= 100
    if completo:
        salida["direccion"] = "sube" if salida["delta"] > 0 else "baja" if salida["delta"] < 0 else "igual"
    return salida | {"estado": "comparable" if completo else "parcial"}


def curva_anterior(df, columna, resolucion):
    """Serie del año anterior con `periodo` movido un año, lista para dibujarse sobre la actual.

    Solo diaria y mensual. Columnas: periodo (movido), periodo_original, `columna`, horas.
    """
    if resolucion not in ("diaria", "mensual"):
        raise ValueError("La curva del año anterior se dibuja en resolución diaria o mensual.")
    if df is None or df.empty:
        return pd.DataFrame(columns=["periodo", "periodo_original", columna, "horas"])
    salida = df[["periodo", columna, "horas"]].dropna(subset=[columna]).copy()
    original = pd.to_datetime(salida["periodo"])
    salida = salida[~((original.dt.month == 2) & (original.dt.day == 29))]  # sin par en un año no bisiesto
    original = pd.to_datetime(salida["periodo"])
    salida["periodo_original"] = original
    salida["periodo"] = original + pd.DateOffset(years=1)
    return salida.reset_index(drop=True)

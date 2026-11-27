"""v0.9.0 · Chaly's Bebop 🎷 (Issue #42): vista estacional del PML de un NodoP.

- Lógica pura (`estacional.py`) con valores sintéticos: mínimo y máximo exactos por mes-día con negativos, Y fuera
  de su propia banda, n real por fecha, sin banda con menos de 2 años, 29 de febrero fuera, huecos sin unir,
  promedio Y vs Y−1 ponderado por horas sobre las mismas fechas.
- Enlace `vista=estacional&nodo=…&anio=…`.
- En la app (AppTest con el paquete público): 01LCP-400 Y=2026 usa solo 2023–2025, Y termina en el último día
  publicado, nodos con poca historia, cambio de año y CSV propio.
"""
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import estacional as es
import vista1 as v
from enlaces import VISTAS_URL, construir_enlace, leer_enlace

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()


def acumulados(valores):
    """{fecha ISO: (promedio, horas)} -> DataFrame de acumuladores diarios como los publica el paquete."""
    filas = [(date.fromisoformat(f), p * h, h) for f, (p, h) in valores.items()]
    return pd.DataFrame(filas, columns=["fecha", "suma_pml", "horas_validas"])


def fila(t, mes_dia):
    return t[t["mes_dia"] == mes_dia].iloc[0]


class Banda(unittest.TestCase):
    def setUp(self):
        valores = {}
        # 1 de enero y 31 de diciembre de 2021 a 2026, con negativos y extremos; 2026 (Y) fuera de rango a propósito.
        for anio, enero, diciembre in ((2021, -50.0, 900.0), (2022, 10.0, 1200.0), (2023, 30.0, -5.0),
                                       (2024, 20.0, 400.0), (2025, -12.5, 7000.0), (2026, 9999.0, None)):
            valores[f"{anio}-01-01"] = (enero, 24)
            if diciembre is not None:
                valores[f"{anio}-12-31"] = (diciembre, 24)
        valores["2024-02-29"] = (123.0, 24)  # bisiesto: no entra
        valores["2024-03-01"] = (50.0, 24)
        valores["2025-03-01"] = (60.0, 24)
        valores["2026-03-01"] = (55.0, 20)   # día parcial de Y
        self.a = acumulados(valores)
        self.t = es.tabla(self.a, 2026)

    def test_minimo_y_maximo_exactos_con_negativos(self):
        enero = fila(self.t, "01-01")
        self.assertEqual((enero["banda_min"], enero["banda_max"], enero["n"]), (-50.0, 30.0, 5))
        self.assertEqual(enero["anios_banda"], "2021, 2022, 2023, 2024, 2025")
        diciembre = fila(self.t, "12-31")
        self.assertEqual((diciembre["banda_min"], diciembre["banda_max"]), (-5.0, 7000.0))

    def test_y_no_entra_en_su_banda(self):
        enero = fila(self.t, "01-01")
        self.assertEqual(enero["y"], 9999.0)
        self.assertLess(enero["banda_max"], 9999.0)
        self.assertEqual(enero["fuera"], "arriba")
        self.assertTrue(pd.isna(fila(self.t, "12-31")["y"]))  # Y sin dato en diciembre: no se inventa

    def test_y1_y2_son_los_anios_anteriores(self):
        enero = fila(self.t, "01-01")
        self.assertEqual((enero["y_1"], enero["y_2"]), (-12.5, 20.0))

    def test_sin_29_de_febrero_y_365_fechas(self):
        self.assertEqual(len(self.t), 365)
        self.assertNotIn("02-29", set(self.t["mes_dia"]))
        self.assertEqual(fila(self.t, "03-01")["y_2"], 50.0)  # el 1 de marzo bisiesto no se desplaza

    def test_menos_de_dos_anios_no_hay_banda(self):
        marzo = fila(self.t, "03-01")
        self.assertEqual((marzo["n"], marzo["banda_min"], marzo["banda_max"]), (2, 50.0, 60.0))
        un_anio = es.tabla(acumulados({"2025-05-05": (80.0, 24), "2026-05-05": (90.0, 24)}), 2026)
        mayo = fila(un_anio, "05-05")
        self.assertEqual(mayo["n"], 1)
        self.assertTrue(pd.isna(mayo["banda_min"]) and pd.isna(mayo["banda_max"]))
        self.assertIsNone(mayo["fuera"])  # sin banda no hay «fuera de banda»
        self.assertEqual(fila(un_anio, "05-06")["n"], 0)

    def test_dia_parcial_y_horas(self):
        self.assertEqual(fila(self.t, "03-01")["horas_y"], 20)

    def test_resumen_pondera_por_horas_sobre_fechas_comunes(self):
        a = acumulados({"2025-01-01": (100.0, 24), "2025-01-02": (200.0, 12), "2025-01-03": (999.0, 24),
                        "2026-01-01": (110.0, 24), "2026-01-02": (220.0, 24)})
        r = es.resumen(es.tabla(a, 2026), a, 2026)
        self.assertEqual(r["dias_comunes"], 2)  # el 3 de enero de 2025 no tiene par en 2026
        self.assertEqual(r["promedio_y_1"], round((100 * 24 + 200 * 12) / 36, 2))
        self.assertEqual(r["promedio_y"], round((110 * 24 + 220 * 24) / 48, 2))
        self.assertEqual(r["dias_y"], 2)

    def test_tramos_no_unen_huecos(self):
        a = acumulados({"2026-01-01": (1.0, 24), "2026-01-02": (2.0, 24), "2026-01-04": (3.0, 24)})
        t = es.tabla(a, 2026)
        tramo = es.tramos(t, "y")
        self.assertEqual(tramo.iloc[0], tramo.iloc[1])
        self.assertTrue(pd.isna(tramo.iloc[2]))
        self.assertNotEqual(tramo.iloc[1], tramo.iloc[3])

    def test_rango_y_anios(self):
        L = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 27)}
        self.assertEqual(es.rango_consulta(2026, L), (date(2023, 1, 1), date(2026, 11, 27)))
        self.assertEqual(es.rango_consulta(2024, L), (date(2023, 1, 1), date(2024, 12, 31)))
        self.assertEqual(es.anios_disponibles(date(2025, 1, 11), date(2026, 11, 27)), [2026, 2025])
        self.assertEqual(es.anios_disponibles(None, None), [])

    def test_csv_con_anios_reales(self):
        c = es.tabla_csv(self.t, 2026)
        self.assertEqual(list(c.columns), ["fecha_calendario", "pml_2026", "horas_2026", "pml_2025", "pml_2024",
                                           "banda_min", "banda_max", "banda_n_anios", "banda_anios",
                                           "fuera_de_banda"])
        self.assertEqual(len(c), 365)
        self.assertEqual(c.iloc[0]["fuera_de_banda"], "arriba")


class Enlace(unittest.TestCase):
    L = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 27)}

    def test_ida_y_vuelta_con_anio(self):
        estado = {"vista": VISTAS_URL["estacional"], "nodo": "01LCP-400", "desde": date(2026, 11, 27),
                  "hasta": date(2026, 11, 27), "resolucion": "horaria", "anio": 2025}
        enlace = construir_enlace(estado)
        self.assertEqual(enlace["anio"], "2025")
        leido, problemas, faltantes = leer_enlace({k: [v] for k, v in enlace.items()}, ["01LCP-400"], self.L)
        self.assertEqual((leido, problemas, faltantes), (estado, [], []))

    def test_sin_anio_ni_fechas_no_falta_nada(self):
        _, problemas, faltantes = leer_enlace({"vista": ["estacional"], "nodo": ["01LCP-400"]}, ["01LCP-400"], self.L)
        self.assertEqual((problemas, faltantes), ([], []))

    def test_anio_invalido(self):
        for valor in (["2019"], ["abc"], ["2025", "2026"]):
            _, problemas, _ = leer_enlace({"vista": ["estacional"], "nodo": ["X"], "anio": valor}, ["X"], self.L)
            self.assertTrue(any("año" in p for p in problemas), valor)

    def test_otras_vistas_no_llevan_anio(self):
        estado = {"vista": VISTAS_URL["historico"], "nodo": "X", "desde": date(2026, 1, 1), "hasta": date(2026, 1, 2),
                  "resolucion": "diaria", "anio": 2025}
        self.assertNotIn("anio", construir_enlace(estado))


def abrir(**parametros):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    return app


def datos_grafica(app):
    import pyarrow as pa
    grafica = app.get("vega_lite_chart")[0]
    spec = json.loads(grafica.proto.spec)
    datos = {d.name: pa.ipc.open_stream(io.BytesIO(d.data.data)).read_pandas() for d in grafica.proto.datasets}
    return spec, datos


@unittest.skipUnless(HAY_PML, "Sin paquete público en data/")
class EnLaApp(unittest.TestCase):
    def test_lcp_2026_banda_solo_con_anios_publicados(self):
        app = abrir(vista="estacional", nodo="01LCP-400", anio="2026")
        metricas = {m.label: m.value for m in app.metric}
        self.assertEqual(metricas["Años en la banda"], "3 de 5")
        leyenda = next(m.value for m in app.markdown if "bebop-leyenda" in m.value)
        self.assertIn("3 de 5 años con dato (2023, 2024, 2025)", leyenda)
        self.assertNotIn("2022", leyenda.split("Banda")[1].split(":")[1])  # la ventana se nombra, no se inventa
        self.assertTrue(any("hasta 3 de 5 años disponibles" in c.value for c in app.caption))
        # Y termina en el último día publicado: ni una fila de Y después.
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        spec, datos = datos_grafica(app)
        lineas = [c for c in spec["layer"] if isinstance(c.get("mark"), dict) and c["mark"].get("type") == "line"]
        y = next(c for c in lineas if c["encoding"]["y"]["field"] == "y")
        df_y = datos[y["data"]["name"]]
        self.assertEqual(pd.to_datetime(df_y["eje"]).max().strftime("%m-%d"), hasta.strftime("%m-%d"))
        # Mismo promedio diario que la vista 1 (serie diaria) en una fecha
        dia = hasta - timedelta(days=3)
        esperado = v.serie_diaria("01LCP-400", dia, dia, "diaria").iloc[0]["pml_promedio"]
        fila_dia = df_y[pd.to_datetime(df_y["eje"]).dt.strftime("%m-%d") == dia.strftime("%m-%d")]
        self.assertAlmostEqual(float(fila_dia["y"].iloc[0]), float(esperado), places=2)
        self.assertEqual(app.query_params["anio"], "2026")
        self.assertTrue(any("pml_bebop_01LCP-400_2026.csv" in c.value for c in app.caption))

    def test_cambiar_anio(self):
        app = abrir(vista="estacional", nodo="01LCP-400", anio="2026")
        app.radio(key="anio").set_value(2024).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.query_params["anio"], "2024")
        self.assertEqual({m.label: m.value for m in app.metric}["Años en la banda"], "1 de 5")
        leyenda = next(m.value for m in app.markdown if "bebop-leyenda" in m.value)
        self.assertIn("Sin banda", leyenda)
        self.assertIn("2022 sin dato", leyenda)

    def test_nodo_con_un_anio_de_historia(self):
        app = abrir(vista="estacional", nodo="01PEM-230")
        self.assertEqual(list(app.radio(key="anio").options), ["2026", "2025"])
        self.assertEqual({m.label: m.value for m in app.metric}["Años en la banda"], "1 de 5")

    def test_anio_que_el_nodo_no_tiene_pasa_al_mas_reciente(self):
        app = abrir(vista="estacional", nodo="01PEM-230", anio="2023")
        self.assertEqual(app.radio(key="anio").value, 2026)

    def test_las_otras_vistas_siguen_igual(self):
        app = abrir(vista="historico", nodo="01LCP-400")
        self.assertEqual(app.radio(key="vista").options[-1], "Chaly's Bebop")
        self.assertNotIn("anio", app.query_params)
        self.assertFalse(any("bebop-leyenda" in m.value for m in app.markdown))


if __name__ == "__main__":
    unittest.main()

"""v0.8.9 · Comparar YoY (Issue #27, fase 2): mismo periodo un año antes, alineado por calendario."""
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pnd
import vista1 as v
import yoy
from enlaces import construir_enlace, leer_enlace

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()


def fila(promedio, horas, del_rango):
    return pd.Series({"promedio": promedio, "horas_con_dato": horas, "horas_del_rango": del_rango,
                      "cobertura_pct": round(100 * horas / del_rango, 1) if del_rango else 0.0})


class Calendario(unittest.TestCase):
    def test_un_anio_antes(self):
        self.assertEqual(yoy.un_anio_antes(date(2026, 11, 24)), date(2025, 11, 24))
        self.assertEqual(yoy.un_anio_antes(date(2028, 2, 29)), date(2027, 2, 28))
        self.assertEqual(yoy.periodo_anterior(date(2026, 1, 1), date(2026, 3, 31)), (date(2025, 1, 1), date(2025, 3, 31)))

    def test_curva_anterior_mueve_un_anio_sin_29_de_febrero(self):
        df = pd.DataFrame({"periodo": pd.to_datetime(["2024-02-28", "2024-02-29", "2024-03-01"]),
                           "pml_promedio": [10.0, 11.0, 12.0], "horas": [24, 24, 24]})
        c = yoy.curva_anterior(df, "pml_promedio", "diaria")
        self.assertEqual(c["periodo"].dt.strftime("%Y-%m-%d").tolist(), ["2025-02-28", "2025-03-01"])
        self.assertEqual(c["pml_promedio"].tolist(), [10.0, 12.0])  # sin interpolar ni inventar el 29
        mensual = yoy.curva_anterior(pd.DataFrame({"periodo": pd.to_datetime(["2025-01-01"]), "pnd_promedio": [5.0],
                                                   "horas": [744]}), "pnd_promedio", "mensual")
        self.assertEqual(mensual["periodo"].iloc[0], pd.Timestamp("2026-01-01"))

    def test_curva_solo_diaria_o_mensual(self):
        with self.assertRaises(ValueError):
            yoy.curva_anterior(pd.DataFrame(), "pml_promedio", "horaria")


class Comparacion(unittest.TestCase):
    def test_comparable_con_direccion(self):
        c = yoy.comparacion(fila(110.0, 48, 48), fila(100.0, 48, 48))
        self.assertEqual((c["estado"], c["delta"], c["direccion"]), ("comparable", 10.0, "sube"))
        self.assertEqual(yoy.comparacion(fila(90.0, 48, 48), fila(100.0, 48, 48))["direccion"], "baja")
        self.assertEqual(yoy.comparacion(fila(100.0, 48, 48), fila(100.0, 48, 48))["direccion"], "igual")

    def test_parcial_sin_direccion(self):
        c = yoy.comparacion(fila(110.0, 47, 48), fila(100.0, 48, 48))
        self.assertEqual((c["estado"], c["delta"], c["direccion"]), ("parcial", 10.0, None))

    def test_sin_dato_un_anio_antes(self):
        for anterior in (None, fila(float("nan"), 0, 48)):
            c = yoy.comparacion(fila(110.0, 48, 48), anterior)
            self.assertEqual((c["estado"], c["delta"], c["anterior"]), ("sin_anterior", None, None))

    def test_negativos_sin_porcentaje(self):
        c = yoy.comparacion(fila(-5.0, 24, 24), fila(-12.5, 24, 24))
        self.assertEqual(c["delta"], 7.5)
        self.assertNotIn("pct", " ".join(c))


class Enlace(unittest.TestCase):
    limites = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 24)}

    def test_lee_yoy_opcional(self):
        estado, problemas, faltantes = leer_enlace({"vista": ["historico"], "nodo": ["01AAN-85"], "yoy": ["1"]},
                                                   ["01AAN-85"], self.limites)
        self.assertTrue(estado["yoy"])
        self.assertNotIn("yoy", faltantes)
        _, _, faltantes = leer_enlace({"vista": ["historico"], "nodo": ["01AAN-85"]}, ["01AAN-85"], self.limites)
        self.assertNotIn("yoy", faltantes)
        _, problemas, _ = leer_enlace({"nodo": ["01AAN-85"], "yoy": ["si"]}, ["01AAN-85"], self.limites)
        self.assertTrue(any("yoy" in p for p in problemas))

    def test_construye_solo_en_historico_y_pnd(self):
        base = {"desde": date(2026, 11, 1), "hasta": date(2026, 11, 2), "resolucion": "diaria", "yoy": True}
        self.assertEqual(construir_enlace(base | {"vista": "1. PML histórico", "nodo": "X"})["yoy"], "1")
        self.assertEqual(construir_enlace(base | {"modalidad": "pnd", "zona": "MONTERREY"})["yoy"], "1")
        self.assertNotIn("yoy", construir_enlace(base | {"vista": "2. Comparar nodos (spread)", "nodo_a": "X",
                                                          "nodo_b": "Y"}))
        self.assertNotIn("yoy", construir_enlace(base | {"yoy": False, "vista": "1. PML histórico", "nodo": "X"}))


def abrir(**parametros):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    return app


def bloque(app):
    return [m.value for m in app.markdown if 'class="yoy"' in m.value]


def lineas_punteadas(app):
    spec = json.loads(app.get("vega_lite_chart")[0].proto.spec)
    return [c for c in spec["layer"] if isinstance(c.get("mark"), dict) and c["mark"].get("type") == "line"
            and c["mark"].get("strokeDash")]


@unittest.skipUnless(HAY_PML and HAY_PND, "Sin paquete público en data/ o pnd/")
class EnLaApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        cls.desde = cls.hasta - timedelta(days=30)

    def test_pml_diaria_mismos_promedios_que_las_estadisticas(self):
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(self.desde), hasta=str(self.hasta),
                    resolucion="diaria", yoy="1")
        (html,) = bloque(app)
        actual = v.estadisticas("01AAN-85", self.desde, self.hasta).iloc[0]["promedio"]
        ini_a, fin_a = yoy.periodo_anterior(self.desde, self.hasta)
        anterior = v.estadisticas("01AAN-85", ini_a, fin_a).iloc[0]["promedio"]
        self.assertIn(f"<b>{actual:,.2f}</b>", html)
        self.assertIn(f"<b>{anterior:,.2f}</b>", html)
        self.assertIn(f"{round(actual - anterior, 2):+,.2f} MXN/MWh", html)
        self.assertEqual(len(lineas_punteadas(app)), 1)
        self.assertEqual(app.query_params["yoy"], "1")
        self.assertTrue(app.toggle(key="yoy").value)

    def test_horaria_solo_promedio(self):
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(self.hasta), hasta=str(self.hasta),
                    resolucion="horaria", yoy="1")
        self.assertEqual(len(bloque(app)), 1)
        self.assertEqual(lineas_punteadas(app), [])

    def test_pnd_sin_dato_un_anio_antes(self):
        inicio = date.fromisoformat(pnd.metadata_pnd()["desde"])
        app = abrir(modalidad="pnd", zona="MONTERREY", desde=str(inicio), hasta=str(inicio + timedelta(days=30)),
                    resolucion="diaria", yoy="1")
        (html,) = bloque(app)
        self.assertIn("Sin dato publicado", html)
        self.assertEqual(lineas_punteadas(app), [])

    def test_apagado_no_cambia_nada(self):
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(self.desde), hasta=str(self.hasta),
                    resolucion="diaria")
        self.assertEqual(bloque(app), [])
        self.assertEqual(lineas_punteadas(app), [])
        self.assertNotIn("yoy", app.query_params)

    def test_sin_interruptor_en_spread_ni_ensemble(self):
        app = abrir(vista="comparacion", nodo_a="01AAN-85", nodo_b="01AGU-230", desde=str(self.desde),
                    hasta=str(self.hasta), resolucion="diaria", yoy="1")
        self.assertEqual([t for t in app.toggle if t.key == "yoy"], [])
        self.assertNotIn("yoy", app.query_params)
        app = abrir(desde=str(self.desde), hasta=str(self.hasta), resolucion="diaria")
        self.assertEqual([t for t in app.toggle if t.key == "yoy"], [])


if __name__ == "__main__":
    unittest.main()

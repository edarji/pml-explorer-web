"""Validación del spread A − B con el paquete público real versionado en data/.

Comprueba las propiedades acordadas: A=A → cero, intercambiar A/B invierte el signo,
solo horas coincidentes (sin imputación) y equivalencia exacta entre el cálculo horario
y el diario dentro de la ventana. Se omite si no hay paquete.
"""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vista1 as v
import vista2 as v2

APP = str(Path(v.__file__).with_name("app.py"))
A, B = "01AAN-85", "03TLJ-230"  # B nace dentro de la ventana horaria


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class Spread(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = v.metadata()
        cls.hasta = date.fromisoformat(m["horario_hasta"])
        cls.desde = cls.hasta - timedelta(days=89)  # 90 días dentro de la ventana
        cls.primera_b = v.observado()[B][0]

    def test_mismo_nodo_es_cero(self):
        for horario in (True, False):
            with self.subTest(horario=horario), patch.object(v2, "cobertura_horaria", return_value=horario):
                r = v2.resumen(A, A, self.desde, self.hasta).iloc[0]
                self.assertEqual(r["promedio"], 0)
                self.assertEqual(r["horas_coincidentes"], r["horas_del_rango"])
                d = v2.diferencial(A, A, self.desde, self.hasta, "diaria")
                self.assertTrue((d["dif_promedio"] == 0).all())
        r = v2.resumen(A, A, self.desde, self.hasta).iloc[0]
        self.assertEqual((r["minimo"], r["maximo"], r["horas_a_mas_caro"]), (0, 0, 0))

    def test_intercambiar_invierte_signo(self):
        for horario in (True, False):
            for res in (("horaria", "diaria", "mensual") if horario else ("diaria", "mensual")):
                with self.subTest(horario=horario, res=res), patch.object(v2, "cobertura_horaria", return_value=horario):
                    ab = v2.diferencial(A, B, self.desde, self.hasta, res)
                    ba = v2.diferencial(B, A, self.desde, self.hasta, res)
                    pd.testing.assert_series_equal(ab["dif_promedio"], -ba["dif_promedio"], check_names=False)
                    pd.testing.assert_series_equal(ab["horas"], ba["horas"])
        ab = v2.resumen(A, B, self.desde, self.hasta).iloc[0]
        ba = v2.resumen(B, A, self.desde, self.hasta).iloc[0]
        self.assertEqual(ab["promedio"], -ba["promedio"])
        self.assertEqual((ab["minimo"], ab["maximo"]), (-ba["maximo"], -ba["minimo"]))

    def test_solo_horas_coincidentes_sin_imputacion(self):
        r = v2.resumen(A, B, self.desde, self.hasta).iloc[0]
        horas_b = v.estadisticas(B, self.desde, self.hasta).iloc[0]["horas_con_dato"]
        self.assertEqual(r["horas_coincidentes"], horas_b)  # A completo: coinciden todas las horas de B
        self.assertEqual(r["primera_fecha"].date(), max(self.primera_b, self.desde))
        d = v2.diferencial(A, B, self.desde, self.hasta, "diaria")
        self.assertGreaterEqual(d["periodo"].min().date(), self.primera_b)
        self.assertEqual(d["horas"].sum(), r["horas_coincidentes"])

    def test_diario_equivale_a_horario_en_la_ventana(self):
        for res in ("diaria", "mensual"):
            with self.subTest(res=res):
                horario = v2.diferencial(A, B, self.desde, self.hasta, res)
                with patch.object(v2, "cobertura_horaria", return_value=False):
                    diario = v2.diferencial(A, B, self.desde, self.hasta, res)
                # Mismo valor sin redondear; tras ROUND(…, 2) puede diferir un centavo en una frontera .xx5
                pd.testing.assert_frame_equal(horario, diario, check_dtype=False, atol=0.0100001, rtol=0)
        h = v2.resumen(A, B, self.desde, self.hasta).iloc[0]
        with patch.object(v2, "cobertura_horaria", return_value=False):
            dd = v2.resumen(A, B, self.desde, self.hasta).iloc[0]
        self.assertAlmostEqual(h["promedio"], dd["promedio"], delta=0.005)
        self.assertEqual(h["horas_coincidentes"], dd["horas_coincidentes"])
        self.assertTrue(pd.isna(dd["mediana"]))

    def test_sin_horas_comunes(self):
        antes = self.primera_b - timedelta(days=1)
        r = v2.resumen(A, B, antes - timedelta(days=5), antes).iloc[0]
        self.assertEqual(r["horas_coincidentes"], 0)
        self.assertTrue(pd.isna(r["promedio"]))

    def test_interfaz(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        app.radio(key="vista").set_value("2. Comparar nodos (spread)").run()
        app.selectbox(key="nodo_a").set_value(A)
        app.selectbox(key="nodo_b").set_value(B)
        app.date_input(key="desde").set_value(date(2023, 1, 1))
        app.radio(key="resolucion").set_value("mensual")
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].label, "Spread promedio")
        self.assertIn("Cobertura común escasa", " ".join(w.value for w in app.warning))
        self.assertEqual(app.metric[1].value, "—")
        # Nodo igual: se bloquea
        app.selectbox(key="nodo_b").set_value(A).run()
        self.assertIn("dos nodos distintos", app.error[0].value)
        # Horaria fuera de ventana: bloqueada
        app.selectbox(key="nodo_b").set_value(B)
        app.radio(key="resolucion").set_value("horaria").run()
        self.assertIn("resolución horaria requiere", app.warning[0].value)
        # Sin horas comunes
        app.radio(key="resolucion").set_value("diaria")
        app.date_input(key="hasta").set_value(date(2023, 1, 31)).run()
        self.assertEqual(len(app.metric), 0)
        self.assertIn("no tienen horas con dato en común", app.warning[0].value)


if __name__ == "__main__":
    unittest.main()

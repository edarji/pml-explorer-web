"""Validación de componentes (vista 3) con el paquete público real versionado en data/.

Requiere el contrato v2 (componentes). Con un paquete v1 se omite y la vista muestra
«pendiente». Comprueba identidad horaria = diaria, signos, base común de horas, umbral
de descuadre y estados sin datos.
"""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vista1 as v
import vista3 as v3

APP = str(Path(v.__file__).with_name("app.py"))


def es_v2():
    try:
        return v.metadata()["version_esquema"] == "2"
    except v.DatosNoDisponibles:
        return False


class Contrato(unittest.TestCase):
    def test_vista3_pendiente_con_paquete_v1(self):
        if es_v2() or not (v.DATA_DIR / "metadata.json").is_file():
            self.skipTest("El paquete ya es v2 o no existe")
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        app.radio(key="vista").set_value("3. Componentes del PML").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertIn("todavía no están en el paquete público", app.info[0].value)


@unittest.skipUnless(es_v2(), "El paquete público todavía es v1 (sin componentes)")
class Componentes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = v.metadata()
        cls.hasta = date.fromisoformat(m["horario_hasta"])
        cls.desde = max(date.fromisoformat(m["horario_desde"]), cls.hasta - timedelta(days=89))
        cls.nodos = ["01AAN-85", "03TLJ-230"]

    def test_diario_equivale_a_horario(self):
        for nodo in self.nodos:
            with self.subTest(nodo=nodo):
                h = v3.resumen_componentes(nodo, self.desde, self.hasta)
                with patch.object(v3, "cobertura_horaria", return_value=False):
                    d = v3.resumen_componentes(nodo, self.desde, self.hasta)
                    for res in ("diaria", "mensual"):
                        pd.testing.assert_frame_equal(v3.componentes(nodo, self.desde, self.hasta, res),
                                                      _horaria(nodo, self.desde, self.hasta, res),
                                                      check_dtype=False, atol=0.0100001, rtol=0)
                for c in ("horas_con_dato", "horas_congestion_positiva", "horas_congestion_negativa",
                          "horas_descuadre", "descuadre_max"):
                    self.assertEqual(h[c][0], d[c][0], c)
                for c in ("pml", "energia", "perdidas", "congestion"):
                    self.assertAlmostEqual(h[c][0], d[c][0], delta=0.0100001)

    def test_base_comun_y_signos(self):
        for nodo in self.nodos:
            r = v3.resumen_componentes(nodo, self.desde, self.hasta).iloc[0]
            e = v.estadisticas(nodo, self.desde, self.hasta).iloc[0]
            self.assertEqual(r["horas_con_dato"], e["horas_con_dato"])
            self.assertAlmostEqual(r["pml"], e["promedio"], delta=0.005)
            self.assertLessEqual(r["horas_congestion_positiva"] + r["horas_congestion_negativa"], r["horas_con_dato"])
            # La suma de promedios cuadra con el PML salvo redondeo y descuadre de CENACE
            self.assertLess(abs(r["pml"] - (r["energia"] + r["perdidas"] + r["congestion"])), 0.03 + r["descuadre_max"])

    def test_sin_datos(self):
        primera = v.observado()["03TLJ-230"][0]
        antes = primera - timedelta(days=1)
        r = v3.resumen_componentes("03TLJ-230", antes - timedelta(days=3), antes).iloc[0]
        self.assertEqual(r["horas_con_dato"], 0)
        self.assertTrue(pd.isna(r["pml"]))


def _horaria(nodo, inicio, fin, res):
    with patch.object(v3, "cobertura_horaria", return_value=True):
        return v3.componentes(nodo, inicio, fin, res)


if __name__ == "__main__":
    unittest.main()

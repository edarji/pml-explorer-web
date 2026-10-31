"""Recorridos de la interfaz con el paquete público versionado en data/.

Usan solo los derivados reales publicados por pml-bot; se omiten si el paquete no está.
Casos tomados de la auditoría del 2026-10-30.
"""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vista1 as v

APP = str(Path(v.__file__).with_name("app.py"))


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class InterfazPublica(unittest.TestCase):
    def correr(self, nodo, desde, hasta, resolucion):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        app.sidebar.selectbox[0].set_value(nodo)
        app.sidebar.date_input[0].set_value(desde)
        app.sidebar.date_input[1].set_value(hasta)
        app.sidebar.radio[0].set_value(resolucion)
        app.run()
        self.assertFalse(app.exception)
        return app

    def textos(self, app):
        return " ".join([c.value for c in app.caption] + [m.value for m in app.markdown]
                        + [w.value for w in app.warning])

    def test_cobertura_escasa_muestra_rango_efectivo(self):
        primera = v.observado()["03TLJ-230"][0]
        app = self.correr("03TLJ-230", date(2023, 1, 1), date(2026, 10, 29), "mensual")
        aviso = " ".join(w.value for w in app.warning)
        self.assertIn("Cobertura escasa", aviso)
        self.assertIn(str(primera), aviso)
        self.assertIn(f"Rango con observaciones:** {primera}", self.textos(app))

    def test_mes_parcial_se_marca(self):
        app = self.correr("01AAN-85", date(2026, 10, 29), date(2026, 10, 30), "mensual")
        self.assertIn("oct 2026 (29–30 oct: 2 de 31 días)", self.textos(app))

    def test_kpi_explicitan_base_horaria_y_dos_decimales(self):
        app = self.correr("01AAN-85", date(2023, 1, 1), v.metadata()["diario_hasta"], "diaria")
        etiquetas = [m.label for m in app.metric]
        self.assertEqual(etiquetas, ["Promedio horario", "Mediana horaria", "Mínimo horario",
                                     "Máximo horario", "Horas con PML < 0"])
        self.assertRegex(app.metric[0].value, r"^-?[\d,]+\.\d\d$")
        self.assertEqual(app.metric[1].value, "—")
        tabla = app.dataframe[0].value
        self.assertNotIn("desv_std", " ".join(map(str, tabla["Indicador"])))
        self.assertIn(app.metric[0].value, list(tabla["Valor"]))

    def test_sin_datos_no_muestra_cifras(self):
        app = self.correr("03TLJ-230", date(2023, 1, 1), date(2023, 1, 2), "diaria")
        self.assertEqual(len(app.metric), 0)
        self.assertIn("no equivale a precio cero", app.warning[0].value)

    def test_horaria_fuera_de_ventana_se_bloquea(self):
        app = self.correr("01AAN-85", date(2023, 1, 1), date(2023, 1, 5), "horaria")
        self.assertEqual(len(app.metric), 0)
        self.assertIn("resolución horaria requiere", app.warning[0].value)


class Periodos(unittest.TestCase):
    def test_marcar_periodos(self):
        import pandas as pd
        df = pd.DataFrame({"periodo": pd.to_datetime(["2026-09-01", "2026-10-01"]), "horas": [480, 48]})
        m = v.marcar_periodos(df, date(2026, 9, 1), date(2026, 10, 2), "mensual")
        self.assertEqual(list(m["horas_posibles"]), [720, 48])
        self.assertEqual(list(m["parcial"]), [True, True])
        self.assertIn("480 de 720 h", m["etiqueta"][0])
        self.assertIn("1–2 oct: 2 de 31 días", m["etiqueta"][1])
        completo = v.marcar_periodos(df.iloc[:1].assign(horas=720), date(2026, 9, 1), date(2026, 9, 30), "mensual")
        self.assertFalse(completo["parcial"][0])


if __name__ == "__main__":
    unittest.main()

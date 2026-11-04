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
        app.selectbox(key="nodo").set_value(nodo)
        app.date_input(key="desde").set_value(desde)
        app.date_input(key="hasta").set_value(hasta)
        app.radio(key="resolucion").set_value(resolucion)
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


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class AuditoriaUxV03(unittest.TestCase):
    """Correcciones P1 de la auditoría UX v0.3: H01, H05, H07 y fechas por defecto."""

    def abrir(self, vista=None):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        if vista:
            app.radio(key="vista").set_value(vista).run()
        self.assertFalse(app.exception)
        return app

    def test_enlace_a_mercados_en_las_tres_vistas(self):
        for vista in ("1. PML histórico", "2. Comparar nodos (spread)", "3. Componentes del PML"):
            with self.subTest(vista=vista):
                app = self.abrir(vista)
                self.assertIn("[← Mercados · edarji.net](https://edarji.net/mercados/)", app.markdown[0].value)

    def test_filtros_en_panel_cerrado_sin_barra_lateral(self):
        app = self.abrir()
        self.assertEqual(len(app.sidebar.children), 0)
        panel = app.expander[0]
        self.assertEqual(panel.label, "Vista y filtros")
        self.assertFalse(panel.proto.expanded)
        # v0.5: la vista se elige en la barra de pestañas; el panel conserva nodo, fechas y resolución.
        self.assertEqual(app.radio(key="vista").value, "1. PML histórico")
        self.assertEqual(panel.selectbox(key="nodo").label, "Buscar por clave de nodo")

    def test_busqueda_por_clave_con_ayuda(self):
        app = self.abrir()
        self.assertEqual(app.selectbox(key="nodo").label, "Buscar por clave de nodo")
        self.assertIn("no incluye nombres", app.selectbox(key="nodo").help)
        self.assertIn("Busca por clave, no por nombre", " ".join(c.value for c in app.caption))
        app2 = self.abrir("2. Comparar nodos (spread)")
        self.assertTrue(app2.selectbox(key="nodo_a").label.startswith("Nodo A · buscar por clave"))

    def test_fechas_por_defecto_en_el_dia_de_la_consulta(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        m = v.metadata()
        hoy = datetime.now(ZoneInfo("America/Mexico_City")).date()
        esperado = min(max(hoy, date.fromisoformat(m["diario_desde"])), date.fromisoformat(m["diario_hasta"]))
        app = self.abrir()
        self.assertEqual(app.date_input(key="desde").value, esperado)
        self.assertEqual(app.date_input(key="hasta").value, esperado)
        self.assertEqual(app.radio(key="resolucion").value, "horaria")


    def test_fechas_invertidas_avisan_sin_cifras(self):
        app = self.abrir()
        app.date_input(key="desde").set_value(date(2026, 10, 30))
        app.date_input(key="hasta").set_value(date(2026, 10, 1))
        app.run()
        self.assertEqual(len(app.metric), 0)
        self.assertIn("'Desde' debe ser anterior", app.error[0].value)


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class RangosRapidosApp(unittest.TestCase):
    """v0.4.1: los botones solo cambian Desde/Hasta, en las tres vistas, con el último día del paquete."""
    VISTAS = (("1. PML histórico", "nodo"), ("2. Comparar nodos (spread)", "nodo_a"), ("3. Componentes del PML", "nodo"))

    def setUp(self):
        from rangos import rango_rapido
        m = v.metadata()
        self.lim = {"desde": date.fromisoformat(m["diario_desde"]), "hasta": date.fromisoformat(m["diario_hasta"])}
        self.esperado = {o: rango_rapido(o, self.lim) for o in ("Último día", "Últimos 7 días", "Mes en curso")}

    def pulsar(self, vista, clave_nodo, opcion, resolucion):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        app.radio(key="vista").set_value(vista).run()
        app.selectbox(key=clave_nodo).set_value("01AGU-230" if clave_nodo == "nodo" else "01AAN-85")
        app.radio(key="resolucion").set_value(resolucion).run()
        app.button(key=f"rango_{opcion}").click().run()
        self.assertFalse(app.exception)
        return app

    def test_tres_rangos_en_tres_vistas_conservan_filtros(self):
        for vista, clave in self.VISTAS:
            for opcion, (inicio, fin) in self.esperado.items():
                with self.subTest(vista=vista, opcion=opcion):
                    app = self.pulsar(vista, clave, opcion, "diaria")
                    self.assertEqual(app.date_input(key="desde").value, inicio)
                    self.assertEqual(app.date_input(key="hasta").value, fin)
                    self.assertEqual(app.radio(key="vista").value, vista)
                    self.assertEqual(app.radio(key="resolucion").value, "diaria")
                    nodo = "01AGU-230" if clave == "nodo" else "01AAN-85"
                    self.assertEqual(app.selectbox(key=clave).value, nodo)
                    self.assertEqual(len(app.error), 0)
                    self.assertGreater(len(app.metric), 0)
                    self.assertIn(f"{inicio} a {fin}", app.subheader[0].value)

    def test_rangos_caben_en_la_ventana_horaria(self):
        for opcion, (inicio, fin) in self.esperado.items():
            with self.subTest(opcion=opcion):
                self.assertTrue(v.cobertura_horaria(inicio, fin))
                app = self.pulsar("1. PML histórico", "nodo", opcion, "horaria")
                self.assertNotIn("resolución horaria requiere", " ".join(w.value for w in app.warning))
                self.assertNotEqual(app.metric[1].value, "—")  # la mediana horaria sí se calcula

    def test_mes_en_curso_se_marca_parcial(self):
        inicio, fin = self.esperado["Mes en curso"]
        app = self.pulsar("1. PML histórico", "nodo", "Mes en curso", "mensual")
        textos = " ".join(c.value for c in app.caption)
        if fin.day < 28 or inicio.day > 1:
            self.assertIn("▼ Periodos parciales", textos)

    def test_mismas_cifras_que_con_fechas_manuales(self):
        inicio, fin = self.esperado["Últimos 7 días"]
        rapido = self.pulsar("1. PML histórico", "nodo", "Últimos 7 días", "diaria")
        from streamlit.testing.v1 import AppTest
        manual = AppTest.from_file(APP, default_timeout=120).run()
        manual.selectbox(key="nodo").set_value("01AGU-230")
        manual.date_input(key="desde").set_value(inicio)
        manual.date_input(key="hasta").set_value(fin)
        manual.radio(key="resolucion").set_value("diaria").run()
        self.assertEqual([m.value for m in rapido.metric], [m.value for m in manual.metric])


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

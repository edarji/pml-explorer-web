"""Recorridos de la interfaz con el paquete público versionado en data/.

Usan solo los derivados reales publicados por pml-bot; se omiten si el paquete no está.
Casos tomados de la auditoría del 2026-10-30.
"""
from datetime import date, timedelta
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
        self.assertEqual(panel.selectbox(key="nodo").label, "Nodo · clave o nombre")

    def test_busqueda_por_clave_con_ayuda(self):
        app = self.abrir()
        # v0.6.0: la búsqueda directa acepta clave o nombre oficial; el valor sigue siendo la clave.
        self.assertEqual(app.selectbox(key="nodo").label, "Nodo · clave o nombre")
        self.assertIn("La clave identifica el nodo", app.selectbox(key="nodo").help)
        self.assertIn("Prueba con la clave", " ".join(c.value for c in app.caption))
        app2 = self.abrir("2. Comparar nodos (spread)")
        self.assertTrue(app2.selectbox(key="nodo_a").label.startswith("Nodo A · clave o nombre"))

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


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class EnlacesCompartibles(unittest.TestCase):
    """v0.5.1: un enlace abre vista y filtros en una sesión nueva; los filtros se reflejan en la URL."""

    def setUp(self):
        m = v.metadata()
        self.hasta = date.fromisoformat(m["diario_hasta"])
        self.desde = self.hasta - timedelta(days=6)
        self.esquema = m["version_esquema"]

    def abrir(self, **parametros):
        """Cada AppTest es una sesión nueva, sin session_state previo (AC-08)."""
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120)
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        app.run()
        self.assertFalse(app.exception)
        return app

    def fechas(self):
        return {"desde": str(self.desde), "hasta": str(self.hasta)}

    def test_historico_restaura_todo(self):  # AC-01, AC-04
        enlace = {"vista": "historico", "nodo": "01AGU-230", **self.fechas(), "resolucion": "diaria"}
        app = self.abrir(**enlace)
        self.assertEqual(app.radio(key="vista").value, "1. PML histórico")
        self.assertEqual(app.selectbox(key="nodo").value, "01AGU-230")
        self.assertEqual((app.date_input(key="desde").value, app.date_input(key="hasta").value), (self.desde, self.hasta))
        self.assertEqual(app.radio(key="resolucion").value, "diaria")
        self.assertEqual(app.subheader[0].value, f"01AGU-230: {self.desde} a {self.hasta}")
        self.assertEqual(dict(app.query_params), enlace)

    def test_comparacion_conserva_a_menos_b(self):  # AC-02
        enlace = {"vista": "comparacion", "nodo_a": "01AGU-230", "nodo_b": "01AAN-85", **self.fechas(),
                  "resolucion": "horaria"}
        app = self.abrir(**enlace)
        self.assertEqual(app.radio(key="vista").value, "2. Comparar nodos (spread)")
        self.assertEqual(app.subheader[0].value, f"01AGU-230 − 01AAN-85: {self.desde} a {self.hasta}")
        self.assertEqual(dict(app.query_params), enlace)

    def test_componentes_restaura_todo(self):  # AC-03
        enlace = {"vista": "componentes", "nodo": "01AGU-230", **self.fechas(), "resolucion": "mensual"}
        app = self.abrir(**enlace)
        self.assertEqual(app.radio(key="vista").value, "3. Componentes del PML")
        self.assertIn(f"01AGU-230: componentes del PML, {self.desde} a {self.hasta}", app.subheader[0].value)
        self.assertEqual(app.radio(key="resolucion").value, "mensual")

    def test_cambiar_filtros_actualiza_la_url(self):  # AC-05
        app = self.abrir()
        app.selectbox(key="nodo").set_value("01AGU-230").run()
        self.assertEqual(app.query_params["nodo"], "01AGU-230")
        app.radio(key="vista").set_value("2. Comparar nodos (spread)").run()
        self.assertEqual(app.query_params["vista"], "comparacion")
        self.assertNotIn("nodo", app.query_params)  # solo los parámetros de la vista activa
        self.assertIn("nodo_b", app.query_params)

    def test_rango_rapido_deja_fechas_absolutas(self):  # AC-06
        app = self.abrir()
        app.button(key="rango_Últimos 7 días").click().run()
        self.assertEqual((app.query_params["desde"], app.query_params["hasta"]), (str(self.desde), str(self.hasta)))

    def test_mismas_cifras_que_con_filtros_manuales(self):  # AC-13
        enlazado = self.abrir(vista="historico", nodo="01AGU-230", **self.fechas(), resolucion="diaria")
        manual = self.abrir()
        manual.selectbox(key="nodo").set_value("01AGU-230")
        manual.date_input(key="desde").set_value(self.desde)
        manual.date_input(key="hasta").set_value(self.hasta)
        manual.radio(key="resolucion").set_value("diaria").run()
        self.assertEqual([m.value for m in enlazado.metric], [m.value for m in manual.metric])

    def test_nodo_inexistente_avisa_y_no_muestra_cifras(self):  # AC-07
        app = self.abrir(vista="historico", nodo="99XXX-999", **self.fechas(), resolucion="diaria")
        self.assertEqual(len(app.metric), 0)
        self.assertIn("«99XXX-999»", app.error[0].value)
        self.assertEqual(app.query_params["nodo"], "99XXX-999")  # la URL recibida no se reescribe
        next(b for b in app.button if b.label.startswith("Continuar")).click().run()
        self.assertEqual(len(app.error), 0)
        self.assertGreater(len(app.metric), 0)
        self.assertEqual(app.query_params["nodo"], app.selectbox(key="nodo").value)

    def test_periodo_fuera_de_cobertura_y_vista_desconocida(self):  # AC-07
        app = self.abrir(vista="mapa", nodo="01AGU-230", desde="2020-01-01", hasta="2020-01-31", resolucion="diaria")
        self.assertEqual(len(app.metric), 0)
        errores = app.error[0].value
        self.assertIn("«mapa» no existe", errores)
        self.assertIn("no está en el paquete público", errores)

    def test_enlace_incompleto_lo_dice(self):  # AC-07
        app = self.abrir(vista="comparacion", nodo_a="01AGU-230")
        self.assertIn("nodo_b", app.info[0].value)
        self.assertEqual(app.selectbox(key="nodo_a").value, "01AGU-230")

    def test_version_esquema_y_fecha_separados(self):  # AC-12
        app = self.abrir()
        pie = " ".join(c.value for c in app.caption)
        self.assertIn(f"PML Explorer v0.6.2 beta · Datos: esquema v{self.esquema}", pie)
        self.assertIn("Actualización del paquete:", pie)


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class RecuadroGrafica(unittest.TestCase):
    """v0.5.1: al pasar el mouse, la gráfica muestra nodo, fecha, hora (CENACE, hora final) y valor."""

    def specs(self, **parametros):
        import json
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120)
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        app.run()
        self.assertFalse(app.exception)
        return [e.proto for e in app.get("vega_lite_chart")], app

    def campos(self, proto):
        """Títulos del recuadro (capa del punto más cercano) y los datos que recibe la gráfica."""
        import json
        import pyarrow as pa
        spec = json.loads(proto.spec)
        capa = next(c for c in spec["layer"] if "tooltip" in c.get("encoding", {}))
        datos = pa.ipc.open_stream(proto.datasets[0].data.data).read_all().to_pandas()
        return [t["title"] for t in capa["encoding"]["tooltip"]], datos

    def test_horaria_muestra_nodo_fecha_hora_y_pml(self):
        hasta = v.metadata()["diario_hasta"]
        specs, _ = self.specs(vista="historico", nodo="01AGU-230", desde=hasta, hasta=hasta, resolucion="horaria")
        titulos, datos = self.campos(specs[0])
        self.assertEqual(titulos, ["Nodo", "Fecha", "Hora", "PML (MXN/MWh)"])
        self.assertEqual(datos["hora_txt"].iloc[0], "1 (00:00–01:00)")  # el punto de las 00:00 es la hora 1
        self.assertEqual(datos["nodo_txt"].iloc[0], "01AGU-230")

    def test_spread_nombra_a_menos_b(self):
        hasta = v.metadata()["diario_hasta"]
        specs, _ = self.specs(vista="comparacion", nodo_a="01AGU-230", nodo_b="01AAN-85", desde=hasta, hasta=hasta,
                              resolucion="diaria")
        titulos, datos = self.campos(specs[0])
        self.assertEqual(titulos, ["Nodos", "Fecha", "Spread A − B (MXN/MWh)", "Horas con dato"])
        self.assertEqual(datos["nodo_txt"].iloc[0], "01AGU-230 − 01AAN-85")


class PestanasMovil(unittest.TestCase):
    """v0.5.1: en pantallas angostas la barra de pestañas se parte en filas; ninguna vista queda fuera de la pantalla.

    AppTest no dibuja CSS: esta prueba fija la regla. La comprobación visual (320 y 390 px) se hace en navegador.
    """
    def test_regla_de_pestanas_en_varias_filas(self):
        import re
        css = Path(APP).read_text(encoding="utf-8")
        bloque = re.search(r"@media \(max-width:(\d+)px\)\{(.*?)\n\}", css, re.S)
        self.assertIsNotNone(bloque, "Falta la regla móvil de las pestañas")
        self.assertGreaterEqual(int(bloque.group(1)), 560)  # la barra mide ≈526 px en una fila
        self.assertIn(".st-key-pestanas div[role=radiogroup]{flex-wrap:wrap", bloque.group(2))


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

"""v0.8.10 · Issue #40: YTD pasa a diaria y 1D, 7D o Mes devuelven la horaria (si el usuario no eligió otra).

- Lógica pura (`rangos.resolucion_tras_rango`, `rangos.admite_horaria`): transiciones, preferencia explícita,
  ventana horaria de PML y tope de días de PND.
- En la app (AppTest con el paquete público): la gráfica vuelve a tener un punto por hora, no solo la radio.
"""
from datetime import date, timedelta
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pnd
import vista1 as v
from rangos import admite_horaria, rango_rapido, resolucion_tras_rango

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()
YTD, D1, D7, MES = "Año en curso", "Último día", "Últimos 7 días", "Mes en curso"

PML = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 27),
       "horario_desde": date(2025, 11, 28), "horario_hasta": date(2026, 11, 27)}


def pulsar(opcion, resolucion, pendiente, limites=PML, max_dias=None):
    inicio, fin = rango_rapido(opcion, limites)
    return resolucion_tras_rango(opcion, inicio, fin, resolucion, pendiente, limites, max_dias)


class Transiciones(unittest.TestCase):
    def test_horaria_ytd_vuelve_con_1d_mes_y_7d(self):
        res, pend, aviso = pulsar(YTD, "horaria", None)
        self.assertEqual((res, pend, aviso), ("diaria", "horaria", "auto"))
        for opcion in (D1, MES, D7):
            with self.subTest(opcion=opcion):
                self.assertEqual(pulsar(opcion, res, pend), ("horaria", None, None))

    def test_ytd_dos_veces_conserva_lo_pendiente(self):
        self.assertEqual(pulsar(YTD, "diaria", "horaria"), ("diaria", "horaria", "auto"))

    def test_preferencia_explicita_no_se_toca(self):
        for res in ("diaria", "mensual"):
            with self.subTest(res=res):
                self.assertEqual(pulsar(YTD, res, None), (res, None, None))
                for opcion in (D1, D7, MES):
                    self.assertEqual(pulsar(opcion, res, None), (res, None, None))

    def test_fuera_de_la_ventana_horaria_sigue_en_diaria(self):
        """Paquete con la ventana horaria terminada antes del último día diario: 1D no cabe."""
        viejo = PML | {"horario_desde": date(2025, 1, 1), "horario_hasta": date(2025, 12, 31)}
        self.assertEqual(pulsar(D1, "diaria", "horaria", viejo), ("diaria", "horaria", "sin_horaria"))
        self.assertFalse(admite_horaria(date(2026, 11, 27), date(2026, 11, 27), viejo))
        self.assertTrue(admite_horaria(date(2025, 12, 1), date(2025, 12, 31), viejo))

    def test_pnd_tope_de_dias(self):
        L = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 19)}  # PND: sin ventana horaria, solo tope
        self.assertEqual(pulsar(D7, "diaria", "horaria", L, max_dias=366), ("horaria", None, None))
        self.assertEqual(pulsar(D7, "diaria", "horaria", L, max_dias=5), ("diaria", "horaria", "sin_horaria"))
        self.assertTrue(admite_horaria(date(2025, 11, 19), date(2026, 11, 19), L, 366))
        self.assertFalse(admite_horaria(date(2025, 1, 1), date(2026, 11, 19), L, 366))


def abrir(**parametros):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    return app


def pulsar_app(app, opcion):
    app.button(key=f"rango_{opcion}").click().run()
    assert not app.exception, app.exception
    return app


def puntos(app):
    """Filas de datos de la primera gráfica (la serie que se dibuja)."""
    import pyarrow as pa
    grafica = app.get("vega_lite_chart")[0]
    tamanos = [len(pa.ipc.open_stream(io.BytesIO(d.data.data)).read_pandas()) for d in grafica.proto.datasets]
    return max(tamanos)


@unittest.skipUnless(HAY_PML and HAY_PND, "Sin paquete público en data/ o pnd/")
class EnLaApp(unittest.TestCase):
    def estado(self, app):
        return app.session_state["resolucion"], app.query_params["resolucion"]

    def test_pml_horaria_ytd_1d_mes_7d(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        self.assertEqual(puntos(app), 24)
        pulsar_app(app, YTD)
        self.assertEqual(self.estado(app), ("diaria", "diaria"))
        self.assertIn("automática (YTD)", app.markdown[[i for i, m in enumerate(app.markdown)
                                                         if "estado-barra" in m.value][0]].value)
        self.assertTrue(any("1D, 7D o Mes vuelven a horaria" in c.value for c in app.caption))
        pulsar_app(app, D1)
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertEqual(puntos(app), 24)  # vuelve el precio por hora, no solo la radio
        self.assertTrue(any("resolución horaria, 24 filas" in c.value for c in app.caption))  # CSV horario
        self.assertFalse(any("res-auto" in m.value for m in app.markdown))
        pulsar_app(app, YTD)
        pulsar_app(app, MES)
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertEqual(puntos(app), 24 * hasta.day)
        pulsar_app(app, YTD)
        pulsar_app(app, D7)
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertEqual(puntos(app), 24 * 7)

    def test_mensual_elegida_durante_ytd_se_respeta(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        pulsar_app(app, YTD)
        app.radio(key="resolucion").set_value("mensual").run()
        pulsar_app(app, D1)
        self.assertEqual(self.estado(app), ("mensual", "mensual"))

    def test_diaria_y_mensual_explicitas(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        for res, regreso in (("diaria", D1), ("mensual", MES)):
            with self.subTest(res=res):
                app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion=res)
                pulsar_app(app, YTD)
                pulsar_app(app, regreso)
                self.assertEqual(self.estado(app), (res, res))

    def test_spread_y_componentes(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        for vista, series in (("comparacion", 1), ("componentes", 3)):  # componentes: energía, pérdidas, congestión
            with self.subTest(vista=vista):
                app = abrir(vista=vista, nodo="01AAN-85", nodo_a="01AAN-85", nodo_b="01AGU-230", desde=str(hasta),
                            hasta=str(hasta), resolucion="horaria")
                pulsar_app(app, YTD)
                self.assertEqual(self.estado(app), ("diaria", "diaria"))
                pulsar_app(app, D7)
                self.assertEqual(self.estado(app), ("horaria", "horaria"))
                self.assertEqual(puntos(app), 24 * 7 * series)

    def test_pnd(self):
        hasta = date.fromisoformat(pnd.metadata_pnd()["hasta"])
        app = abrir(modalidad="pnd", zona="MONTERREY", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        pulsar_app(app, YTD)
        self.assertEqual(self.estado(app), ("diaria", "diaria"))
        pulsar_app(app, D1)
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertEqual(puntos(app), 24)

    def test_enlace_nuevo_no_arrastra_pendiente(self):
        """Un enlace con resolucion=diaria abre una sesión nueva: 1D no la cambia a horaria."""
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta - timedelta(days=30)), hasta=str(hasta),
                    resolucion="diaria")
        pulsar_app(app, D1)
        self.assertEqual(self.estado(app), ("diaria", "diaria"))


if __name__ == "__main__":
    unittest.main()

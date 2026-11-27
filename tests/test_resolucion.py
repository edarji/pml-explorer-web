"""v0.9.1 · Selector de granularidad (Horaria · Diaria · Mensual) sobre los rangos 1D · 7D · Mes · YTD.

Reglas (Lalo, 2026-11-27), por la longitud del rango:
- 1 día: solo horaria (diaria y mensual desactivadas).
- 2 a 7 días: horaria o diaria (mensual desactivada).
- 8 días o más (Mes, YTD, fechas a mano): horaria, diaria o mensual.
- Cada botón de rango abre en horaria. Si la horaria no cabe (fuera de la ventana horaria de PML o más días que el
  tope de PND), la primera permitida.

Corrige el bug de #40: YTD o YoY y regreso a 1D ya no deja un solo punto diario; 1D siempre dibuja 24 horas.
"""
from datetime import date, timedelta
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pnd
import vista1 as v
from rangos import admite_horaria, motivo_no_permitida, rango_rapido, resoluciones_permitidas

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()
YTD, D1, D7, MES = "Año en curso", "Último día", "Últimos 7 días", "Mes en curso"
TODAS = ("horaria", "diaria", "mensual")

PML = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 27),
       "horario_desde": date(2025, 11, 28), "horario_hasta": date(2026, 11, 27)}
PND = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 19)}  # sin ventana horaria, solo tope de días


def permitidas(opcion, limites=PML, max_dias=None):
    return resoluciones_permitidas(*rango_rapido(opcion, limites), limites, max_dias)


class Reglas(unittest.TestCase):
    def test_por_boton_de_rango(self):
        self.assertEqual(permitidas(D1), ("horaria",))
        self.assertEqual(permitidas(D7), ("horaria", "diaria"))
        self.assertEqual(permitidas(MES), TODAS)  # 27 días (anclado al 27 de noviembre)
        self.assertEqual(permitidas(YTD), TODAS)

    def test_horaria_siempre_es_la_primera(self):
        """La primera permitida es la que abre cada botón de rango."""
        for opcion in (D1, D7, MES, YTD):
            with self.subTest(opcion=opcion):
                self.assertEqual(permitidas(opcion)[0], "horaria")

    def test_por_longitud_con_fechas_a_mano(self):
        fin = date(2026, 11, 27)
        for dias, esperado in ((1, ("horaria",)), (2, ("horaria", "diaria")), (7, ("horaria", "diaria")),
                               (8, TODAS), (365, TODAS)):
            with self.subTest(dias=dias):
                self.assertEqual(resoluciones_permitidas(fin - timedelta(days=dias - 1), fin, PML), esperado)

    def test_fuera_de_la_ventana_horaria(self):
        fin = date(2025, 6, 30)
        self.assertEqual(resoluciones_permitidas(fin, fin, PML), ("diaria",))  # un día sin horaria: su promedio
        self.assertEqual(resoluciones_permitidas(fin - timedelta(days=6), fin, PML), ("diaria",))
        self.assertEqual(resoluciones_permitidas(date(2025, 1, 1), fin, PML), ("diaria", "mensual"))
        self.assertEqual(resoluciones_permitidas(date(2025, 1, 1), date(2026, 11, 27), PML), ("diaria", "mensual"))
        self.assertFalse(admite_horaria(fin, fin, PML))
        self.assertTrue(admite_horaria(date(2025, 12, 1), date(2025, 12, 31), PML))

    def test_pnd_tope_de_dias(self):
        self.assertEqual(permitidas(YTD, PND, 366), TODAS)
        self.assertEqual(resoluciones_permitidas(date(2025, 1, 1), date(2026, 11, 19), PND, 366), ("diaria", "mensual"))
        self.assertTrue(admite_horaria(date(2025, 11, 19), date(2026, 11, 19), PND, 366))
        self.assertFalse(admite_horaria(date(2025, 1, 1), date(2026, 11, 19), PND, 366))

    def test_motivos(self):
        dia = date(2026, 11, 27)
        self.assertIsNone(motivo_no_permitida("horaria", dia, dia, PML))
        self.assertEqual(motivo_no_permitida("diaria", dia, dia, PML), "Con un día solo hay resolución horaria.")
        self.assertEqual(motivo_no_permitida("mensual", dia - timedelta(days=6), dia, PML),
                         "Con 7 días o menos: horaria o diaria.")
        self.assertIn("2025-11-28", motivo_no_permitida("horaria", date(2025, 1, 1), dia, PML))
        self.assertEqual(motivo_no_permitida("horaria", date(2025, 1, 1), date(2026, 11, 19), PND, 366),
                         "La horaria admite hasta 366 días.")


def abrir(**parametros):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    return app


def pulsar(app, clave):
    app.button(key=clave).click().run()
    assert not app.exception, app.exception
    return app


def puntos(app):
    """Filas de datos de la primera gráfica (la serie que se dibuja)."""
    import pyarrow as pa
    grafica = app.get("vega_lite_chart")[0]
    tamanos = [len(pa.ipc.open_stream(io.BytesIO(d.data.data)).read_pandas()) for d in grafica.proto.datasets]
    return max(tamanos)


def activos(app):
    """Botones de granularidad: {resolución: (activo, seleccionado)}."""
    return {r: (not app.button(key=f"gran_{r}").disabled, app.button(key=f"gran_{r}").proto.type == "primary")
            for r in TODAS}


@unittest.skipUnless(HAY_PML and HAY_PND, "Sin paquete público en data/ o pnd/")
class EnLaApp(unittest.TestCase):
    def estado(self, app):
        return app.session_state["resolucion"], app.query_params["resolucion"]

    def test_botones_por_rango(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        self.assertEqual(activos(app), {"horaria": (True, True), "diaria": (False, False), "mensual": (False, False)})
        pulsar(app, f"rango_{D7}")
        self.assertEqual(activos(app), {"horaria": (True, True), "diaria": (True, False), "mensual": (False, False)})
        for opcion in (MES, YTD):
            with self.subTest(opcion=opcion):
                pulsar(app, f"rango_{opcion}")
                self.assertEqual({r: a for r, (a, _) in activos(app).items()},
                                 {"horaria": True, "diaria": True, "mensual": hasta.day >= 8 or opcion == YTD})
                self.assertEqual(self.estado(app), ("horaria", "horaria"))

    def test_ytd_diaria_y_regreso_a_1d_es_horaria(self):
        """El bug de Lalo: YTD (o YoY) en diaria o mensual y regreso a 1D dejaba un solo punto."""
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        for res in ("diaria", "mensual"):
            with self.subTest(res=res):
                app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta),
                            resolucion="horaria")
                pulsar(app, f"rango_{YTD}")
                self.assertEqual(self.estado(app), ("horaria", "horaria"))
                pulsar(app, f"gran_{res}")
                self.assertEqual(self.estado(app), (res, res))
                pulsar(app, f"rango_{D1}")
                self.assertEqual(self.estado(app), ("horaria", "horaria"))
                self.assertEqual(puntos(app), 24)
                self.assertTrue(any("resolución horaria, 24 filas" in c.value for c in app.caption))  # CSV horario

    def test_ytd_yoy_y_regreso(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="horaria",
                    yoy="1")
        pulsar(app, f"rango_{YTD}")
        pulsar(app, "gran_diaria")
        pulsar(app, f"rango_{D1}")
        self.assertEqual(self.estado(app), ("horaria", "horaria"))

    def test_7d_diaria_y_mensual_desactivada(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        pulsar(app, f"rango_{D7}")
        self.assertEqual(puntos(app), 24 * 7)
        pulsar(app, "gran_diaria")
        self.assertEqual(self.estado(app), ("diaria", "diaria"))
        self.assertEqual(puntos(app), 7)

    def test_enlace_de_un_dia_en_mensual_abre_en_horaria(self):
        """Enlaces viejos: 1 día con diaria o mensual se dibuja en horaria (la única que admite) y se avisa."""
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta), hasta=str(hasta), resolucion="mensual")
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertTrue(any("Con un día solo hay resolución horaria" in t.proto.body for t in app.toast))

    def test_enlace_valido_se_respeta(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = abrir(vista="historico", nodo="01AAN-85", desde=str(hasta - timedelta(days=30)), hasta=str(hasta),
                    resolucion="diaria")
        self.assertEqual(self.estado(app), ("diaria", "diaria"))
        self.assertEqual(len(app.toast), 0)

    def test_spread_y_componentes(self):
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        for vista, series in (("comparacion", 1), ("componentes", 3)):  # componentes: energía, pérdidas, congestión
            with self.subTest(vista=vista):
                app = abrir(vista=vista, nodo="01AAN-85", nodo_a="01AAN-85", nodo_b="01AGU-230", desde=str(hasta),
                            hasta=str(hasta), resolucion="horaria")
                pulsar(app, f"rango_{YTD}")
                pulsar(app, "gran_mensual")
                pulsar(app, f"rango_{D7}")
                self.assertEqual(self.estado(app), ("horaria", "horaria"))
                self.assertEqual(puntos(app), 24 * 7 * series)

    def test_pnd(self):
        hasta = date.fromisoformat(pnd.metadata_pnd()["hasta"])
        app = abrir(modalidad="pnd", zona="MONTERREY", desde=str(hasta), hasta=str(hasta), resolucion="horaria")
        self.assertEqual(activos(app)["diaria"], (False, False))
        pulsar(app, f"rango_{YTD}")
        pulsar(app, "gran_diaria")
        pulsar(app, f"rango_{D1}")
        self.assertEqual(self.estado(app), ("horaria", "horaria"))
        self.assertEqual(puntos(app), 24)


if __name__ == "__main__":
    unittest.main()

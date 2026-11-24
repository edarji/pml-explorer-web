"""v0.8.4 · Eje de tiempo por resolución (regresión de escalas).

Con 7 días de serie diaria el eje rotulaba «12 PM» entre fechas porque la escala temporal elegía marcas cada
12 horas. Se comprueba en el spec real de las gráficas (AppTest con el paquete público) que las marcas van en días
o meses enteros según la resolución, que línea y barras de congestión comparten el mismo eje, y que los rangos
largos y la serie horaria siguen con las marcas automáticas de Vega.
"""
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pnd
import vista1 as v

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()


def ejes_x(**parametros):
    """Ejes X (temporales) de las gráficas de la escena abierta con esos parámetros de URL."""
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    assert not app.error, [e.value for e in app.error]
    ejes = []
    for grafica in app.get("vega_lite_chart"):
        spec = json.loads(grafica.proto.spec)
        for capa in spec.get("layer", [spec]):
            x = capa.get("encoding", {}).get("x", {})
            if x.get("type") == "temporal":
                ejes.append(x.get("axis", {}))
                break
    return ejes


@unittest.skipUnless(HAY_PML and HAY_PND, "Sin paquete público en data/ o pnd/")
class EjeDeTiempo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pml_hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        cls.pnd_hasta = date.fromisoformat(pnd.metadata_pnd()["hasta"])

    def marcas_diarias(self, ejes, paso=1):
        self.assertGreaterEqual(len(ejes), 2, "línea + barras de congestión")
        for eje in ejes:
            self.assertEqual(eje.get("tickCount"), {"interval": "day", "step": paso})
            self.assertEqual(eje.get("format"), "%d %b")

    def test_pnd_7d_diaria_sin_marcas_de_12_pm(self):
        """El caso reportado: PND diaria de 7 días, una marca por día y rotulada con la fecha."""
        ejes = ejes_x(modalidad="pnd", zona="MONTERREY", resolucion="diaria",
                      desde=str(self.pnd_hasta - timedelta(days=6)), hasta=str(self.pnd_hasta))
        self.marcas_diarias(ejes)

    def test_pml_7d_diaria_y_spread(self):
        filtros = dict(resolucion="diaria", desde=str(self.pml_hasta - timedelta(days=6)), hasta=str(self.pml_hasta))
        self.marcas_diarias(ejes_x(vista="historico", nodo="01AAN-85", **filtros))
        for eje in ejes_x(vista="comparacion", nodo_a="01AAN-85", nodo_b="01AGU-230", **filtros):
            self.assertEqual(eje.get("tickCount"), {"interval": "day", "step": 1})

    def test_mes_diaria_cada_2_dias(self):
        desde = self.pml_hasta - timedelta(days=17)
        self.marcas_diarias(ejes_x(vista="historico", nodo="01AAN-85", resolucion="diaria",
                                   desde=str(desde), hasta=str(self.pml_hasta)), paso=2)

    def test_mensual_marca_meses(self):
        desde = (self.pml_hasta.replace(day=1) - timedelta(days=62)).replace(day=1)
        ejes = ejes_x(vista="historico", nodo="01AAN-85", resolucion="mensual",
                      desde=str(desde), hasta=str(self.pml_hasta))
        self.assertTrue(ejes)
        for eje in ejes:
            self.assertEqual(eje.get("tickCount"), {"interval": "month", "step": 1})
            self.assertEqual(eje.get("format"), "%b %Y")

    def test_horaria_y_rangos_largos_sin_cambio(self):
        for ejes in (ejes_x(vista="historico", nodo="01AAN-85", resolucion="horaria",
                            desde=str(self.pml_hasta), hasta=str(self.pml_hasta)),
                     ejes_x(vista="historico", nodo="01AAN-85", resolucion="diaria",
                            desde=str(self.pml_hasta.replace(month=1, day=1)), hasta=str(self.pml_hasta))):
            self.assertTrue(ejes)
            for eje in ejes:
                self.assertNotIn("tickCount", eje)
                self.assertNotIn("format", eje)


if __name__ == "__main__":
    unittest.main()

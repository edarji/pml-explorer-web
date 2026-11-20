"""v0.8.0 · Escena inicial (ENSEMBLE o SOLO) y URL del tablero: funciones puras, sin Streamlit ni datos."""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enlaces import PARAMETROS
from escena import ENSEMBLE, PARAMETROS_ENSEMBLE, PARAMETROS_SOLO, SOLO, enlace_ensemble, escena_de_enlace


def url(**parametros):
    return {k: [v] for k, v in parametros.items()}


class EscenaDeEnlace(unittest.TestCase):
    def test_sin_parametros_abre_ensemble(self):  # AC-G01
        self.assertEqual(escena_de_enlace({}), ENSEMBLE)

    def test_solo_fechas_y_resolucion_abre_ensemble(self):  # AC-G01
        self.assertEqual(escena_de_enlace(url(desde="2026-11-01", hasta="2026-11-05", resolucion="diaria")), ENSEMBLE)

    def test_parametros_ajenos_no_cuentan(self):
        self.assertEqual(escena_de_enlace(url(utm_source="x", embed="true")), ENSEMBLE)

    def test_enlaces_existentes_abren_solo(self):  # AC-G02, D2
        casos = [url(vista="historico", nodo="01AAN-85", desde="2026-11-01", hasta="2026-11-05", resolucion="diaria"),
                 url(vista="comparacion", nodo_a="01AAN-85", nodo_b="01AGU-230"),
                 url(vista="componentes", nodo="06ESC-115"),
                 url(modalidad="pnd", zona="MONTERREY"),
                 url(vista="comparacion"),          # D2: sin nodos abre SOLO con valores predeterminados
                 url(modalidad="pnd"),
                 url(nodo="01AAN-85"),
                 url(vista="mapa", nodo="01AGU-230")]  # inválido: SOLO muestra el mismo aviso que v0.7.0
        for parametros in casos:
            with self.subTest(parametros=parametros):
                self.assertEqual(escena_de_enlace(parametros), SOLO)

    def test_parametros_cubren_los_de_enlaces(self):
        self.assertEqual(set(PARAMETROS_SOLO) | set(PARAMETROS_ENSEMBLE), set(PARAMETROS))
        self.assertFalse(set(PARAMETROS_SOLO) & set(PARAMETROS_ENSEMBLE))


class EnlaceEnsemble(unittest.TestCase):
    def test_solo_fechas_y_resolucion(self):  # AC-G05
        estado = {"vista": "1. PML histórico", "nodo": "01AAN-85", "zona": "MONTERREY", "modalidad": "pnd",
                  "desde": date(2026, 11, 1), "hasta": date(2026, 11, 5), "resolucion": "mensual"}
        self.assertEqual(enlace_ensemble(estado), {"desde": "2026-11-01", "hasta": "2026-11-05", "resolucion": "mensual"})

    def test_ida_y_vuelta_abre_ensemble(self):
        enlace = enlace_ensemble({"desde": date(2026, 11, 1), "hasta": date(2026, 11, 5), "resolucion": "diaria"})
        self.assertEqual(escena_de_enlace({k: [v] for k, v in enlace.items()}), ENSEMBLE)

    def test_sin_valores_no_inventa(self):
        self.assertEqual(enlace_ensemble({}), {})


if __name__ == "__main__":
    unittest.main()

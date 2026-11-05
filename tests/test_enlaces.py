"""Enlaces compartibles (v0.5.1): lectura y construcción de la URL, puras, sin Streamlit ni datos."""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enlaces import VISTAS_URL, construir_enlace, leer_enlace
from vista1 import RESOLUCIONES

NODOS = ["01AAN-85", "01AGU-230", "06ESC-115"]
LIMITES = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 4)}


def url(**parametros):
    """Simula lo que llega de la URL: cada parámetro es una lista de valores."""
    return {k: v if isinstance(v, list) else [v] for k, v in parametros.items()}


class LeerEnlace(unittest.TestCase):
    def leer(self, **parametros):
        return leer_enlace(url(**parametros), NODOS, LIMITES)

    def test_sin_parametros_no_hay_enlace(self):
        self.assertEqual(leer_enlace({}, NODOS, LIMITES), ({}, [], []))

    def test_parametros_ajenos_se_ignoran(self):
        self.assertEqual(leer_enlace(url(embed="true", utm_source="x"), NODOS, LIMITES), ({}, [], []))

    def test_historico_completo(self):
        estado, problemas, faltantes = self.leer(vista="historico", nodo="06ESC-115", desde="2026-10-29",
                                                 hasta="2026-11-04", resolucion="horaria", embed="true")
        self.assertEqual(estado, {"vista": VISTAS_URL["historico"], "nodo": "06ESC-115",
                                  "desde": date(2026, 10, 29), "hasta": date(2026, 11, 4), "resolucion": "horaria"})
        self.assertEqual((problemas, faltantes), ([], []))

    def test_comparacion_conserva_a_y_b(self):
        estado, problemas, _ = self.leer(vista="comparacion", nodo_a="01AGU-230", nodo_b="01AAN-85",
                                         desde="2026-10-01", hasta="2026-11-04", resolucion="diaria")
        self.assertEqual((estado["nodo_a"], estado["nodo_b"]), ("01AGU-230", "01AAN-85"))
        self.assertEqual(problemas, [])

    def test_vista_desconocida(self):
        estado, problemas, _ = self.leer(vista="mapa", nodo="01AAN-85")
        self.assertNotIn("vista", estado)
        self.assertIn("«mapa» no existe", problemas[0])

    def test_nodo_inexistente_no_se_sustituye(self):
        estado, problemas, _ = self.leer(vista="historico", nodo="99XXX-999")
        self.assertNotIn("nodo", estado)
        self.assertIn("«99XXX-999»", problemas[0])

    def test_resolucion_no_permitida(self):
        estado, problemas, _ = self.leer(vista="historico", resolucion="semanal")
        self.assertNotIn("resolucion", estado)
        self.assertIn("«semanal» no existe", problemas[0])

    def test_fecha_mal_escrita(self):
        estado, problemas, _ = self.leer(vista="historico", desde="04/11/2026", hasta="2026-11-04")
        self.assertNotIn("desde", estado)
        self.assertIn("AAAA-MM-DD", problemas[0])

    def test_periodo_fuera_de_cobertura_no_se_recorta(self):
        estado, problemas, _ = self.leer(vista="historico", desde="2022-12-01", hasta="2023-01-31")
        self.assertNotIn("desde", estado)
        self.assertNotIn("hasta", estado)  # tampoco la fecha válida: el periodo es uno solo
        self.assertIn("del 2023-01-01 al 2026-11-04", problemas[0])

    def test_fechas_invertidas_pasan_para_el_aviso_de_la_vista(self):
        estado, problemas, _ = self.leer(vista="historico", desde="2026-11-04", hasta="2026-11-01")
        self.assertEqual((estado["desde"], estado["hasta"]), (date(2026, 11, 4), date(2026, 11, 1)))
        self.assertEqual(problemas, [])

    def test_parametro_duplicado(self):
        estado, problemas, _ = self.leer(vista="historico", nodo=["01AAN-85", "01AGU-230"])
        self.assertNotIn("nodo", estado)
        self.assertIn("«nodo» aparece 2 veces", problemas[0])

    def test_incompleto_informa_faltantes(self):
        estado, problemas, faltantes = self.leer(vista="comparacion", nodo_a="01AAN-85")
        self.assertEqual(problemas, [])
        self.assertEqual(faltantes, ["nodo_b", "desde", "hasta", "resolucion"])
        self.assertEqual(estado["nodo_a"], "01AAN-85")


class ConstruirEnlace(unittest.TestCase):
    def test_ida_y_vuelta_en_las_tres_vistas(self):
        for vista, nodos in (("historico", {"nodo": "06ESC-115"}), ("componentes", {"nodo": "01AGU-230"}),
                             ("comparacion", {"nodo_a": "01AGU-230", "nodo_b": "01AAN-85"})):
            with self.subTest(vista=vista):
                estado = {"vista": VISTAS_URL[vista], **nodos, "desde": date(2026, 10, 1),
                          "hasta": date(2026, 11, 4), "resolucion": "mensual"}
                enlace = construir_enlace(estado)
                self.assertEqual(leer_enlace(url(**enlace), NODOS, LIMITES), (estado, [], []))

    def test_solo_parametros_de_la_vista_activa(self):
        estado = {"vista": VISTAS_URL["historico"], "nodo": "01AAN-85", "nodo_a": "01AGU-230",
                  "nodo_b": "06ESC-115", "desde": date(2026, 11, 4), "hasta": date(2026, 11, 4),
                  "resolucion": "horaria"}
        self.assertEqual(construir_enlace(estado), {"vista": "historico", "nodo": "01AAN-85", "desde": "2026-11-04",
                                                    "hasta": "2026-11-04", "resolucion": "horaria"})

    def test_resoluciones_coinciden_con_las_de_la_app(self):
        from enlaces import RESOLUCIONES_URL
        self.assertEqual(set(RESOLUCIONES_URL), set(RESOLUCIONES))


if __name__ == "__main__":
    unittest.main()

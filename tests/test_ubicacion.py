"""v0.6.0 · Selector guiado Región de Control -> Zona de carga -> NodoP en las tres vistas.

Recorre la app real con el paquete público y el catálogo de referencia. Comprueba que los filtros
solo acotan la lista, que la clave sigue siendo el valor (URL y cálculos), que el nodo elegido no
se pierde al filtrar y que la app vuelve a «solo claves» si el catálogo falta.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalogo as cat
import vista1 as v

APP = str(Path(v.__file__).with_name("app.py"))
HAY_DATOS = (v.DATA_DIR / "metadata.json").is_file() and (cat.REFERENCIA_DIR / cat.ARCHIVO).is_file()


@unittest.skipUnless(HAY_DATOS, "Sin paquete público o sin catálogo de referencia")
class Ubicacion(unittest.TestCase):
    def abrir(self, vista=None):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120).run()
        if vista:
            app.radio(key="vista").set_value(vista).run()
        self.assertFalse(app.exception)
        return app

    def textos(self, app):
        return " ".join(c.value for c in app.caption)

    def test_por_defecto_todas_y_clave_con_nombre(self):
        app = self.abrir()
        self.assertEqual(app.selectbox(key="nodo_region").value, "Todas")
        self.assertEqual(app.selectbox(key="nodo_zona").value, "Todas")
        nodo = app.selectbox(key="nodo")
        self.assertEqual(nodo.value, "01AAN-85")  # el valor es la clave
        self.assertEqual(len(nodo.options), len(v.catalogo()))
        self.assertIn("01AAN-85 · Actopan", nodo.options)
        self.assertIn("Región Central · Zona de carga Centro Oriente", self.textos(app))
        self.assertIn("Catálogo de NodosP de CENACE, versión 2026-10-23", self.textos(app))

    def test_region_y_zona_acotan_y_conservan_el_nodo(self):
        app = self.abrir()
        app.selectbox(key="nodo_region").set_value("NORESTE").run()
        zonas = app.selectbox(key="nodo_zona").options
        self.assertIn("MONTERREY", zonas)
        self.assertNotIn("CENTRO ORIENTE", zonas)
        app.selectbox(key="nodo_zona").set_value("MONTERREY").run()
        opciones = app.selectbox(key="nodo").options
        # 130 nodos de Monterrey + el nodo elegido, que queda fuera del filtro pero no se pierde.
        self.assertEqual(len(opciones), 131)
        self.assertEqual(app.selectbox(key="nodo").value, "01AAN-85")
        self.assertIn("fuera de este filtro", self.textos(app))
        self.assertFalse(app.exception)

    def test_cambiar_region_reinicia_zona_y_limpiar(self):
        app = self.abrir()
        app.selectbox(key="nodo_region").set_value("NORESTE").run()
        app.selectbox(key="nodo_zona").set_value("MONTERREY").run()
        app.selectbox(key="nodo_region").set_value("OCCIDENTAL").run()
        self.assertEqual(app.selectbox(key="nodo_zona").value, "Todas")
        app.button(key="nodo_limpiar").click().run()
        self.assertEqual(app.selectbox(key="nodo_region").value, "Todas")
        self.assertEqual(app.selectbox(key="nodo").value, "01AAN-85")

    def test_nodo_internacional_sin_clasificacion(self):
        app = self.abrir()
        app.selectbox(key="nodo").set_value("09LBR-230").run()
        self.assertIn("sin clasificación verificada", self.textos(app))
        self.assertFalse(app.exception)

    def test_url_sigue_con_claves(self):
        """AC-09: región y zona no van a la URL; el enlace guarda la clave."""
        app = self.abrir()
        app.selectbox(key="nodo_region").set_value("NORESTE").run()
        self.assertEqual(app.query_params["nodo"], "01AAN-85")
        self.assertFalse(any("region" in k or "zona" in k for k in app.query_params))

    def test_comparar_regiones_distintas(self):
        """AC-08: Nodo A y Nodo B tienen filtros independientes."""
        app = self.abrir("2. Comparar nodos (spread)")
        app.selectbox(key="nodo_a_region").set_value("NORESTE").run()
        app.selectbox(key="nodo_b_region").set_value("PENINSULAR").run()
        self.assertEqual(app.selectbox(key="nodo_a_region").value, "NORESTE")
        self.assertEqual(app.selectbox(key="nodo_b_region").value, "PENINSULAR")
        a = next(o for o in app.selectbox(key="nodo_a").options if o.startswith("06"))
        b = next(o for o in app.selectbox(key="nodo_b").options if o.startswith("08"))
        app.selectbox(key="nodo_a").set_value(a.split(" · ")[0])
        app.selectbox(key="nodo_b").set_value(b.split(" · ")[0]).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.query_params["nodo_a"], a.split(" · ")[0])

    def test_componentes_usa_el_mismo_selector(self):
        app = self.abrir("3. Componentes del PML")
        self.assertEqual(app.selectbox(key="nodo").label, "Nodo · clave o nombre")
        self.assertEqual(app.selectbox(key="nodo_region").value, "Todas")

    def test_sin_catalogo_vuelve_a_solo_claves(self):
        """Si el catálogo falta, la app no se detiene: funciona como v0.5.1."""
        with tempfile.TemporaryDirectory() as vacio, patch.object(cat, "REFERENCIA_DIR", Path(vacio)):
            app = self.abrir()
            self.assertEqual(len(app.selectbox(key="nodo").options), len(v.catalogo()))
            self.assertIn("01AAN-85", app.selectbox(key="nodo").options)
            self.assertEqual([s for s in app.selectbox if s.key == "nodo_region"], [])
            self.assertNotIn("Catálogo de NodosP", self.textos(app))


if __name__ == "__main__":
    unittest.main()

"""v0.8.7 · Drill-down de la distribución PND (Issue #36).

Los intervalos de las barras son los del `bin` de Vega (maxbins=30): se comparan con barras que dibujó Vega-Lite 5
(vl-convert) para casos de borde, y con el paquete real se verifica que cada barra cuenta exactamente las zonas de su
lista. La app se recorre con AppTest usando la lista «Ver zonas de un rango» (la misma acción que tocar la barra).
"""
from datetime import date
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ensemble as ens
import pnd
import vista1 as v
from test_pnd import armar_paquete

APP = str(Path(v.__file__).with_name("app.py"))

# Valores → barras [inicio, fin, n] dibujadas por Vega-Lite 5 con bin maxbins=30 (vl-convert 1.9, 2026-11-25).
VEGA = {
    "borde_interior": ([100.0, 150.0, 200.0, 250.0, 300.0], [[100.0, 110.0, 1], [150.0, 160.0, 1], [200.0, 210.0, 1], [250.0, 260.0, 1], [290.0, 300.0, 1]]),
    "maximo_en_borde": ([0.0, 10.0, 20.0, 30.0, 40.0, 50.0], [[0.0, 2.0, 1], [10.0, 12.0, 1], [20.0, 22.0, 1], [30.0, 32.0, 1], [40.0, 42.0, 1], [48.0, 50.0, 1]]),
    "negativos": ([-37.5, -12.25, 0.0, 5.5, 18.75, 61.0], [[-40.0, -35.0, 1], [-15.0, -10.0, 1], [0.0, 5.0, 1], [5.0, 10.0, 1], [15.0, 20.0, 1], [60.0, 65.0, 1]]),
    "un_valor": ([512.3], [[500.0, 520.0, 1]]),
    "iguales": ([700.0, 700.0, 700.0], [[700.0, 750.0, 3]]),
    "decimales": ([1.01, 1.02, 1.07, 1.11, 1.2], [[1.01, 1.02, 1], [1.02, 1.03, 1], [1.07, 1.08, 1], [1.11, 1.12, 1], [1.19, 1.2, 1]]),
    "redondeo": ([799.99, 800.0, 800.01, 899.99, 900.0, 1250.5, 405.3], [[400.0, 450.0, 1], [750.0, 800.0, 1], [800.0, 850.0, 2], [850.0, 900.0, 1], [900.0, 950.0, 1], [1250.0, 1300.0, 1]]),
}


def barras_de(valores):
    r = pd.DataFrame({"elemento": [f"z{i}" for i in range(len(valores))], "promedio": valores})
    b = ens.barras(ens.intervalos(r))
    return [[round(a, 6), round(c, 6), int(n)] for a, c, n in zip(b["bin_ini"], b["bin_fin"], b["n"])]


class Intervalos(unittest.TestCase):
    def test_mismas_barras_que_vega(self):
        for caso, (valores, esperado) in VEGA.items():
            with self.subTest(caso):
                self.assertEqual(barras_de(valores), esperado)

    def test_bordes(self):
        # Un valor en el borde interior va a la barra de arriba ([inicio, fin)); el máximo, a la última (cerrada).
        r = ens.intervalos(pd.DataFrame({"elemento": list("abcd"), "promedio": [799.99, 800.0, 800.01, 900.0]}))
        self.assertEqual(dict(zip(r["elemento"], r["bin_ini"])), {"a": 795.0, "b": 800.0, "c": 800.0, "d": 895.0})
        self.assertEqual(float(r.loc[r["elemento"] == "d", "bin_fin"].iloc[0]), 900.0)  # [895, 900] cerrado

    def test_sin_dato_no_entra(self):
        r = pd.DataFrame({"elemento": ["a", "b", "c"], "promedio": [100.0, None, 300.0]})
        con = ens.intervalos(r)
        self.assertEqual(list(con["elemento"]), ["a", "c"])
        self.assertEqual(int(ens.barras(con)["n"].sum()), 2)

    def test_miembros_en_orden(self):
        r = pd.DataFrame({"elemento": ["a", "b", "c", "d"], "promedio": [811.0, 812.0, 811.0, 900.0]})
        con = ens.intervalos(r)  # paso 5: a, b y c en [810, 815)
        self.assertEqual(list(ens.miembros(con, 810.0)["elemento"]), ["b", "a", "c"])


@unittest.skipUnless((pnd.PND_DIR / "metadata.json").is_file(), "Sin paquete público en pnd/")
class PaquetePublico(unittest.TestCase):
    def test_conteo_de_cada_barra_es_su_lista(self):
        dias = sorted((pnd.PND_DIR / "hourly").glob("*.parquet"))[-45:]
        for ruta in dias:
            dia = date.fromisoformat(ruta.stem)
            ranking = ens.ranking_pnd(dia, pnd.PND_DIR)
            con = ens.intervalos(ranking)
            tabla = ens.barras(con)
            self.assertEqual(int(tabla["n"].sum()), len(ranking.dropna(subset=["promedio"])))
            for fila in tabla.itertuples():
                lista = ens.miembros(con, fila.bin_ini)
                self.assertEqual(len(lista), fila.n, (dia, fila.bin_ini))
                self.assertTrue(((lista["promedio"] >= fila.bin_ini) & (lista["promedio"] <= fila.bin_fin)).all())


class App(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")  # 2026-11-01..05 sin el 03; CENTRO ORIENTE 112.5, MONTERREY 212.5, VDM 312.5

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def abrir(self, carpeta, **parametros):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=180)
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        self.carpeta = carpeta
        self.correr(app)
        return app

    def correr(self, app):
        with mock.patch.object(pnd, "PND_DIR", self.carpeta):
            app.run()
        self.assertFalse(app.exception, app.exception)

    @staticmethod
    def rango(app):
        return next(s for s in app.selectbox if s.key.startswith("rango_pnd_"))

    @staticmethod
    def zonas(app):
        return [b for b in app.button if b.key.startswith("dz_pnd_")]

    def test_elegir_rango_lista_zonas_y_abre_solista(self):
        app = self.abrir(self.dir)
        rango = self.rango(app)
        self.assertEqual(rango.key, "rango_pnd_2026-11-05")
        self.assertIsNone(rango.value)
        self.assertEqual(self.zonas(app), [])
        opciones = rango.options  # «Toca una barra…» + una por barra
        self.assertEqual(len(opciones), 4)
        self.assertIn("210–220 MXN/MWh · 1 zona", opciones[2])
        self.rango(app).select_index(2)
        self.correr(app)
        etiqueta = next(m.value for m in app.markdown if "drill-et" in m.value)
        self.assertIn("210–220 MXN/MWh · 1 zona de carga", etiqueta)
        self.assertIn("zonas, no NodosP", etiqueta)
        self.assertEqual([b.label for b in self.zonas(app)], ["Monterrey · 212.50"])
        self.zonas(app)[0].click()
        self.correr(app)
        self.assertEqual((app.session_state["modalidad"], app.session_state["zona"]), ("pnd", "MONTERREY"))
        self.assertTrue(any(b.key == "volver" for b in app.button))  # detalle abierto
        self.assertEqual(len(self.zonas(app)), 1)  # ENSEMBLE y el panel siguen debajo
        next(b for b in app.button if b.key == "quitar_barra_pnd").click()
        self.correr(app)
        self.assertEqual(self.zonas(app), [])
        self.assertIsNone(self.rango(app).value)

    def test_cambiar_de_dia_descarta_la_seleccion(self):
        app = self.abrir(self.dir)
        self.rango(app).select_index(1)
        self.correr(app)
        self.assertEqual(len(self.zonas(app)), 1)
        app.session_state["pnd_barra"] = (date(2026, 11, 4), app.session_state["pnd_barra"][1])  # de otro día
        self.correr(app)
        self.assertEqual(self.zonas(app), [])
        self.assertIsNone(app.session_state["pnd_barra"])

    def test_horas_parciales(self):
        """Una zona con 18 horas entra con su promedio de esas horas, marcada; el ranking es el de ENSEMBLE."""
        import streamlit as st
        ranking = pd.DataFrame({"elemento": ["PUEBLA", "MONTERREY", "MERIDA"], "horas": [24, 18, 24],
                                "promedio": [505.0, 500.0, 900.0], "minimo": [505.0, 500.0, 900.0],
                                "maximo": [505.0, 500.0, 900.0], "horas_negativas": [0, 0, 0]})
        st.cache_data.clear()
        try:
            with mock.patch.object(ens, "ranking_pnd", return_value=ranking):
                app = self.abrir(self.dir)
                rango = self.rango(app)
                rango.select_index(next(i for i, o in enumerate(rango.options) if o.startswith("500–")))
                self.correr(app)
        finally:
            st.cache_data.clear()
        self.assertEqual([b.label for b in self.zonas(app)], ["Puebla · 505.00", "Monterrey · 500.00 · 18 h"])
        self.assertTrue(any("menos de 24 horas" in c.value for c in app.caption))

    def test_sin_pnd_sin_controles(self):
        app = self.abrir(self.tmp / "no-existe")
        self.assertFalse([s for s in app.selectbox if s.key.startswith("rango_pnd_")])


if __name__ == "__main__":
    unittest.main()

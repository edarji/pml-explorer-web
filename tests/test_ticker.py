"""v0.8.5 · Ticker PND de la barra superior (Issue #34).

Cifras con paquetes PND ficticios (precio, D−1 calendario, faltantes, horas parciales, igualdad) y con el paquete
público real (mismo promedio que ENSEMBLE y que SOLO PND); recorridos de la app con AppTest.
"""
from datetime import date, timedelta
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ensemble as ens
import pnd
import ticker
import vista1 as v
from test_pnd import armar_paquete, escribir_metadata

APP = str(Path(v.__file__).with_name("app.py"))
D = date(2026, 11, 10)
SEL = (("MONTERREY", "Noreste"), ("PUEBLA", "Oriental"), ("MERIDA", "Peninsular"), ("CHIHUAHUA", "Norte"),
       ("HERMOSILLO", "Noroeste"), ("INVENTADA", "Ninguna"))


def paquete(carpeta, dias):
    """`dias`: {fecha: {zona: [precios por hora]}}; un día ausente no tiene archivo (sin dato publicado)."""
    carpeta = Path(carpeta)
    (carpeta / "hourly").mkdir(parents=True)
    filas = [("SIN", "MDA", z, d, h, float(p), float(p), 0.0, 0.0)
             for d, zonas in dias.items() for z, precios in zonas.items() for h, p in enumerate(precios, start=1)]
    df = pd.DataFrame(filas, columns=["sistema", "mercado", "zona_carga", "fecha", "hora", "pnd", "energia",
                                      "perdidas", "congestion"])
    con = duckdb.connect()
    con.register("df", df)
    for d in dias:
        con.execute(f"""COPY (SELECT sistema, mercado, zona_carga, fecha::DATE fecha, hora::INTEGER hora, pnd, energia,
                                     perdidas, congestion FROM df WHERE fecha = DATE '{d}')
                        TO '{carpeta}/hourly/{d}.parquet' (FORMAT parquet)""")
    zonas = sorted({z for zs in dias.values() for z in zs})
    escribir_metadata(carpeta, min(dias), max(dias), [], len(zonas))
    return carpeta, {"desde": min(dias), "hasta": max(dias)}, set(zonas)


class Cifras(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def fichas(self, dias, sel=SEL):
        carpeta, lim, zonas = paquete(self.tmp / "pnd", dias)
        return ticker.fichas(lim, carpeta, zonas, sel)

    def test_sube_baja_igual_parcial_y_faltantes(self):
        previo = D - timedelta(days=1)
        datos = self.fichas({
            previo: {"MONTERREY": [500] * 24, "PUEBLA": [700] * 24, "MERIDA": [800] * 24, "CHIHUAHUA": [400] * 22},
            D: {"MONTERREY": [512.3] * 24, "PUEBLA": [690] * 24, "MERIDA": [800] * 24, "CHIHUAHUA": [430] * 24},
        })
        self.assertEqual((datos["dia"], datos["dia_previo"], datos["previo_publicado"]), (D, previo, True))
        f = {x["zona"]: x for x in datos["fichas"]}
        # Zonas que no existen en el paquete no aparecen (HERMOSILLO no tiene datos; INVENTADA no existe).
        self.assertEqual(list(f), ["MONTERREY", "PUEBLA", "MERIDA", "CHIHUAHUA"])
        self.assertEqual((f["MONTERREY"]["precio"], f["MONTERREY"]["delta"], f["MONTERREY"]["direccion"]),
                         (512.3, 12.3, "sube"))  # el promedio redondeado de ENSEMBLE, y la resta de esos valores
        self.assertEqual((f["PUEBLA"]["delta"], f["PUEBLA"]["direccion"]), (-10.0, "baja"))
        self.assertEqual((f["MERIDA"]["delta"], f["MERIDA"]["direccion"]), (0.0, "igual"))
        # Ayer con 22 horas: se muestra la diferencia pero sin color ni flecha.
        self.assertEqual((f["CHIHUAHUA"]["estado"], f["CHIHUAHUA"]["direccion"], f["CHIHUAHUA"]["delta"]),
                         ("parcial", None, 30.0))
        self.assertEqual(ticker.cambio(f["MONTERREY"]), "▲ +12.30")
        self.assertEqual(ticker.cambio(f["PUEBLA"]), "▼ -10.00")
        self.assertEqual(ticker.cambio(f["MERIDA"]), "= +0.00")
        self.assertEqual(ticker.cambio(f["CHIHUAHUA"]), "+30.00 · parcial 24/22 h")
        self.assertIn("Comparación parcial", ticker.descripcion(f["CHIHUAHUA"], D, previo))

    def test_sin_dia_anterior_no_busca_uno_mas_antiguo(self):
        """D−1 sin archivo: «s/c vs ayer», aunque D−2 sí tenga dato."""
        datos = self.fichas({D - timedelta(days=2): {"MONTERREY": [100] * 24}, D: {"MONTERREY": [200] * 24}})
        self.assertFalse(datos["previo_publicado"])
        ficha = datos["fichas"][0]
        self.assertEqual((ficha["estado"], ficha["previo"], ficha["delta"], ficha["direccion"]),
                         ("sin_comparacion", None, None, None))
        self.assertEqual(ticker.cambio(ficha), "s/c vs ayer")

    def test_zona_sin_precio_hoy_o_ayer(self):
        previo = D - timedelta(days=1)
        datos = self.fichas({previo: {"MONTERREY": [100] * 24, "PUEBLA": [100] * 24},
                             D: {"PUEBLA": [100] * 23, "MERIDA": [50] * 24}})
        f = {x["zona"]: x for x in datos["fichas"]}
        self.assertEqual((f["MONTERREY"]["estado"], f["MONTERREY"]["precio"]), ("sin_dato", None))  # nada de ceros
        self.assertEqual(ticker.texto_ficha(f["MONTERREY"]), "MONTERREY · sin dato")
        self.assertEqual(ticker.cambio(f["MONTERREY"]), "")
        self.assertEqual(f["MERIDA"]["estado"], "sin_comparacion")  # sin precio ayer
        self.assertEqual(f["PUEBLA"]["estado"], "parcial")  # 23 horas hoy
        self.assertEqual(ticker.cambio(f["PUEBLA"]), "+0.00 · parcial 23/24 h")

    def test_negativos_sin_porcentaje(self):
        previo = D - timedelta(days=1)
        datos = self.fichas({previo: {"MONTERREY": [-20] * 24}, D: {"MONTERREY": [10] * 24}})
        ficha = datos["fichas"][0]
        self.assertEqual((ficha["delta"], ficha["direccion"]), (30.0, "sube"))
        self.assertNotIn("%", ticker.texto_ficha(ficha))

    def test_paquete_sin_dias(self):
        carpeta = self.tmp / "vacio"
        (carpeta / "hourly").mkdir(parents=True)
        self.assertIsNone(ticker.fichas({"desde": D, "hasta": D}, carpeta, set(), SEL))

    def test_seleccion_editorial_existe_en_el_paquete_publico(self):
        if not (pnd.PND_DIR / "zonas.parquet").is_file():
            self.skipTest("Sin paquete público en pnd/")
        zonas = set(pnd.zonas(pnd.PND_DIR))
        self.assertTrue(6 <= len(ticker.ZONAS_TICKER) <= 10)
        self.assertEqual([z for z, _ in ticker.ZONAS_TICKER if z not in zonas], [])


@unittest.skipUnless((pnd.PND_DIR / "metadata.json").is_file(), "Sin paquete público en pnd/")
class PaquetePublico(unittest.TestCase):
    def test_mismo_promedio_que_ensemble_y_solo(self):
        m = pnd.metadata_pnd()
        lim = {"desde": date.fromisoformat(m["desde"]), "hasta": date.fromisoformat(m["hasta"])}
        datos = ticker.fichas(lim, pnd.PND_DIR, set(pnd.zonas(pnd.PND_DIR)))
        dia = ens.dia_pnd(lim["hasta"], lim, pnd.PND_DIR)
        self.assertEqual(datos["dia"], dia)
        ranking = ens.ranking_pnd(dia, pnd.PND_DIR).set_index("elemento")
        for ficha in datos["fichas"]:
            if ficha["precio"] is None:
                continue
            self.assertEqual(ficha["precio"], ranking.loc[ficha["zona"], "promedio"])
            solo = pnd.estadisticas_pnd(ficha["zona"], dia, dia, pnd.PND_DIR).iloc[0]
            self.assertAlmostEqual(ficha["precio"], round(float(solo["promedio"]), 2), places=2)


class App(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")  # 2026-11-01..05, sin el 03; mismos precios cada día

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def abrir(self, carpeta, **parametros):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=180)
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        with mock.patch.object(pnd, "PND_DIR", carpeta):
            app.run()
        self.assertFalse(app.exception, app.exception)
        return app, carpeta

    def correr(self, app, carpeta):
        with mock.patch.object(pnd, "PND_DIR", carpeta):
            app.run()
        self.assertFalse(app.exception, app.exception)

    @staticmethod
    def fichas(app, copia="a"):
        return [b for b in app.button if b.key.startswith(f"tk{copia}_")]

    def test_cinta_en_ensemble_con_fechas_del_paquete(self):
        app, _ = self.abrir(self.dir)
        botones = self.fichas(app)
        # Del paquete ficticio solo existen MONTERREY y VDM CENTRO de la selección; mismos precios ayer y hoy.
        self.assertEqual([b.key for b in botones], ["tka_igual_vdm-centro", "tka_igual_monterrey"])
        self.assertEqual(botones[1].label, "*MONTERREY* **212.50** `= +0.00`")
        self.assertEqual(len(self.fichas(app, "b")), 2)  # copia visual para el bucle
        rotulo = next(m.value for m in app.markdown if "tk-et" in m.value)
        self.assertIn("PND · Zonas de carga · promedio diario (MXN/MWh)", rotulo)
        self.assertIn("2026-11-05 vs 2026-11-04", rotulo)
        self.assertIn("Datos publicados por CENACE · MDA · no tiempo real", rotulo)

    def test_dia_anterior_sin_dato(self):
        carpeta = armar_paquete(self.tmp / "pnd-hueco", hasta=date(2026, 11, 4))  # D = 04, D−1 = 03 sin archivo
        app, _ = self.abrir(carpeta)
        self.assertTrue(all("s/c vs ayer" in b.label for b in self.fichas(app)))
        rotulo = next(m.value for m in app.markdown if "tk-et" in m.value)
        self.assertIn("2026-11-04 2026-11-03 sin dato publicado", rotulo)

    def test_tocar_zona_abre_solista_pnd_con_ensemble(self):
        app, carpeta = self.abrir(self.dir)
        desde, hasta, resolucion = (app.session_state[k] for k in ("desde", "hasta", "resolucion"))
        next(b for b in self.fichas(app) if b.key.endswith("monterrey")).click()
        self.correr(app, carpeta)
        self.assertEqual((app.session_state["modalidad"], app.session_state["zona"]), ("pnd", "MONTERREY"))
        self.assertTrue(any(b.key == "volver" for b in app.button))  # detalle abierto («Cerrar detalle»)
        self.assertTrue(any("seccion-et" in m.value for m in app.markdown))  # ENSEMBLE sigue debajo
        # La cinta sigue igual en SOLO y no movió fechas ni resolución dentro del paquete PND.
        self.assertEqual(len(self.fichas(app)), 2)
        self.assertEqual(app.session_state["resolucion"], resolucion)
        self.assertLessEqual(app.session_state["hasta"], date(2026, 11, 5))
        del desde, hasta

    def test_cinta_no_cambia_fechas_de_un_enlace(self):
        app, _ = self.abrir(self.dir, modalidad="pnd", zona="MONTERREY", desde="2026-11-01", hasta="2026-11-02",
                            resolucion="diaria")
        self.assertEqual((str(app.session_state["desde"]), str(app.session_state["hasta"])), ("2026-11-01", "2026-11-02"))
        self.assertEqual(dict(app.query_params)["hasta"], "2026-11-02")
        self.assertEqual(len(self.fichas(app)), 2)

    def test_sin_pnd_no_hay_cinta(self):
        app, _ = self.abrir(self.tmp / "no-existe")
        self.assertEqual(self.fichas(app), [])
        self.assertFalse(any("tk-et" in m.value for m in app.markdown))


if __name__ == "__main__":
    unittest.main()

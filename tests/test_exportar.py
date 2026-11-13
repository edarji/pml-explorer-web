"""Exportación CSV (v0.6.2): funciones puras, valores contra los cálculos de la app y botón en la interfaz."""
from datetime import date
import io
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import exportar as x
import vista1 as v
import vista2 as v2
import vista3 as v3

PAQUETE = {"fuente": "CENACE SW-PML, MDA, SIN", "unidades": "MXN/MWh", "generado_utc": "2026-11-13T05:00:04Z",
           "version_esquema": "2"}
META = x.metadatos("historico", "diaria", date(2026, 11, 1), date(2026, 11, 3), date(2026, 11, 1),
                   date(2026, 11, 2), 66.7, PAQUETE, "v0.6.2 beta")
HAY_DATOS = (v.DATA_DIR / "metadata.json").is_file()


def leer(contenido):
    return pd.read_csv(io.BytesIO(contenido), keep_default_na=True)


def serie_falsa(resolucion, inicio, fin, filas):
    """DataFrame con la forma de vista1.serie: periodo, pml_promedio, horas."""
    df = pd.DataFrame(filas, columns=["periodo", "pml_promedio", "horas"])
    df["periodo"] = pd.to_datetime(df["periodo"])
    return v.marcar_periodos(df, inicio, fin, resolucion)


class FuncionesPuras(unittest.TestCase):
    def test_columnas_por_resolucion(self):
        horaria = serie_falsa("horaria", date(2026, 11, 1), date(2026, 11, 1),
                              [("2026-11-01 00:00", 500.0, 1), ("2026-11-01 23:00", 450.5, 1)])
        diaria = serie_falsa("diaria", date(2026, 11, 1), date(2026, 11, 2),
                             [("2026-11-01", 500.0, 24), ("2026-11-02", 480.0, 20)])
        mensual = serie_falsa("mensual", date(2026, 10, 15), date(2026, 11, 2),
                              [("2026-10-01", 500.0, 408), ("2026-11-01", 480.0, 48)])
        self.assertEqual(list(x.tabla_historico(horaria, "06ESC-115", "horaria").columns),
                         ["fecha_operacion", "hora_cenace", "nodo", "pml"])
        self.assertEqual(list(x.tabla_historico(diaria, "06ESC-115", "diaria").columns),
                         ["fecha_operacion", "nodo", "pml", "horas_con_dato", "horas_posibles", "periodo_parcial"])
        t = x.tabla_historico(mensual, "06ESC-115", "mensual")
        self.assertEqual(list(t.columns), ["mes", "fecha_desde", "fecha_hasta", "nodo", "pml", "horas_con_dato",
                                           "horas_posibles", "periodo_parcial"])
        self.assertEqual(t.iloc[0][["mes", "fecha_desde", "fecha_hasta", "periodo_parcial"]].tolist(),
                         ["2026-10", "2026-10-15", "2026-10-31", "true"])

    def test_hora_cenace_es_hora_final(self):
        df = serie_falsa("horaria", date(2026, 11, 1), date(2026, 11, 1),
                         [("2026-11-01 00:00", 1.0, 1), ("2026-11-01 23:00", 2.0, 1)])
        self.assertEqual(x.tabla_historico(df, "N", "horaria")["hora_cenace"].tolist(), [1, 24])

    def test_parcial_por_horas_faltantes(self):
        df = serie_falsa("diaria", date(2026, 11, 1), date(2026, 11, 2),
                         [("2026-11-01", 500.0, 24), ("2026-11-02", 480.0, 20)])
        t = leer(x.a_csv(x.tabla_historico(df, "N", "diaria"), META))
        self.assertEqual(t["horas_con_dato"].tolist(), [24, 20])
        self.assertEqual(t["periodo_parcial"].tolist(), [False, True])

    def test_vacio_no_es_cero(self):
        tabla = pd.DataFrame({"fecha_operacion": ["2026-11-01", "2026-11-02"], "pml": [0.0, float("nan")]})
        texto = x.a_csv(tabla, META).decode("utf-8-sig").splitlines()
        self.assertTrue(texto[1].startswith("2026-11-01,0.0,"))
        self.assertTrue(texto[2].startswith("2026-11-02,,"))
        leido = leer(x.a_csv(tabla, META))
        self.assertEqual(leido["pml"].iloc[0], 0.0)
        self.assertTrue(pd.isna(leido["pml"].iloc[1]))

    def test_negativos_siguen_siendo_numeros(self):
        tabla = pd.DataFrame({"nodo": ["06ESC-115"], "congestion": [-105.88], "descuadre_promedio": [-0.0006]})
        leido = leer(x.a_csv(tabla, META))
        self.assertEqual(leido["congestion"].iloc[0], -105.88)
        self.assertEqual(leido["descuadre_promedio"].iloc[0], -0.0006)

    def test_texto_con_formula_se_neutraliza(self):
        tabla = pd.DataFrame({"nodo": ["=HYPERLINK(1)", "-1+2", "@SUM", "08CHB-34.5"], "pml": [1.0, -2.0, 3.0, 4.0]})
        leido = leer(x.a_csv(tabla, META))
        self.assertEqual(leido["nodo"].tolist(), ["'=HYPERLINK(1)", "'-1+2", "'@SUM", "08CHB-34.5"])
        self.assertEqual(leido["pml"].tolist(), [1.0, -2.0, 3.0, 4.0])

    def test_bom_y_viaje_redondo_exacto(self):
        tabla = pd.DataFrame({"fecha_operacion": ["2026-11-01"] * 3, "pml": [691.86, 1234.5, -0.01]})
        contenido = x.a_csv(tabla, META)
        self.assertTrue(contenido.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", contenido)
        leido = leer(contenido)
        self.assertEqual(leido.columns[0], "fecha_operacion")
        self.assertEqual(leido["pml"].tolist(), [691.86, 1234.5, -0.01])

    def test_metadatos_y_procedencia(self):
        leido = leer(x.a_csv(pd.DataFrame({"pml": [1.0]}), META))
        self.assertEqual(list(leido.columns)[1:], list(META))
        fila = leido.iloc[0]
        self.assertEqual((fila["fuente"], fila["mercado"], fila["sistema"], fila["unidad"]),
                         ("CENACE SW-PML", "MDA", "SIN", "MXN/MWh"))
        self.assertEqual(fila["paquete_generado_utc"], "2026-11-13T05:00:04Z")
        self.assertEqual((fila["consulta_desde"], fila["observado_hasta"]), ("2026-11-01", "2026-11-02"))
        texto = x.a_csv(pd.DataFrame({"pml": [1.0]}), META).decode("utf-8-sig")
        for privado in ("/Users", "/home", "edarji@", "macmini"):
            self.assertNotIn(privado, texto)

    def test_sin_filas_no_genera_archivo(self):
        with self.assertRaises(x.SinDatosExportables):
            x.a_csv(pd.DataFrame({"pml": []}), META)

    def test_nombre_de_archivo(self):
        self.assertEqual(x.nombre_archivo("historico", ["06ESC-115"], date(2026, 11, 1), date(2026, 11, 13), "diaria"),
                         "pml_historico_06ESC-115_2026-11-01_2026-11-13_diaria.csv")
        self.assertEqual(x.nombre_archivo("comparacion", ["01AAN-85", "08CHB-34.5"], date(2026, 11, 13),
                                          date(2026, 11, 13), "horaria"),
                         "pml_spread_01AAN-85_08CHB-34.5_2026-11-13_horaria.csv")
        self.assertEqual(x.nombre_archivo("componentes", ["a/b c"], date(2026, 1, 1), date(2026, 1, 2), "mensual"),
                         "pml_componentes_a_b_c_2026-01-01_2026-01-02_mensual.csv")


# Consultas del spread tal como estaban antes de v0.6.2: el spread exportado debe salir idéntico.
SPREAD_HORARIO_ORIGINAL = """
    SELECT date_trunc('{u}', a.fecha + to_hours(a.hora - 1)) AS periodo, ROUND(AVG(a.pml - b.pml), 2) AS dif_promedio,
           COUNT(*) AS horas
    FROM read_parquet(?) a JOIN read_parquet(?) b ON a.fecha = b.fecha AND a.hora = b.hora
    WHERE a.nodo = ? AND b.nodo = ? AND a.fecha BETWEEN ? AND ? AND b.fecha BETWEEN ? AND ?
    GROUP BY periodo ORDER BY periodo"""
SPREAD_DIARIO_ORIGINAL = """
    WITH d AS (SELECT * FROM read_parquet(?) WHERE fecha BETWEEN ? AND ?)
    SELECT date_trunc('{u}', a.fecha) AS periodo,
           ROUND(SUM(a.suma_pml - b.suma_pml) / SUM(a.horas_validas), 2) AS dif_promedio,
           SUM(a.horas_validas)::BIGINT AS horas
    FROM d a JOIN d b ON a.fecha = b.fecha
    WHERE a.nodo = ? AND b.nodo = ? AND a.horas_validas = 24 AND b.horas_validas = 24
    GROUP BY periodo ORDER BY periodo"""


@unittest.skipUnless(HAY_DATOS, "Sin paquete público en data/")
class ContraLosCalculos(unittest.TestCase):
    """Con el paquete real: el CSV trae exactamente los valores que la app calcula."""
    A, B = "01AAN-85", "08BNV-115"  # 08BNV-115 tiene horas faltantes en la ventana horaria

    @classmethod
    def setUpClass(cls):
        m = v.metadata()
        cls.paquete = m
        cls.hd, cls.hh = date.fromisoformat(m["horario_desde"]), date.fromisoformat(m["horario_hasta"])

    def csv(self, tabla):
        meta = x.metadatos("historico", "diaria", self.hd, self.hh, self.hd, self.hh, 100, self.paquete, "v")
        return leer(x.a_csv(tabla, meta))

    def test_historico_coincide_con_la_serie(self):
        for res in ("horaria", "diaria", "mensual"):
            df = v.marcar_periodos(v.serie(self.B, self.hd, self.hh, res), self.hd, self.hh, res)
            leido = self.csv(x.tabla_historico(df, self.B, res))
            self.assertEqual(len(leido), len(df), res)
            self.assertEqual(leido["pml"].tolist(), df["pml_promedio"].tolist(), res)
        # Horas sin dato: no hay fila inventada.
        horaria = v.serie(self.B, self.hd, self.hh, "horaria")
        self.assertLess(len(horaria), ((self.hh - self.hd).days + 1) * 24)

    def test_spread_identico_al_de_antes(self):
        archivos_h = v._archivos("hourly", self.hd, self.hh)
        for res in ("horaria", "diaria", "mensual"):
            antes = v._consulta(SPREAD_HORARIO_ORIGINAL.format(u=v.RESOLUCIONES[res]),
                                [archivos_h, archivos_h, self.A, self.B, self.hd, self.hh, self.hd, self.hh])
            ahora = v2.diferencial(self.A, self.B, self.hd, self.hh, res)
            pd.testing.assert_frame_equal(ahora[["periodo", "dif_promedio", "horas"]], antes, check_dtype=False)
        inicio = date(2023, 1, 1)
        for res in ("diaria", "mensual"):
            antes = v._consulta(SPREAD_DIARIO_ORIGINAL.format(u=v.RESOLUCIONES[res]),
                                [v._archivos("daily", inicio, self.hh), inicio, self.hh, self.A, self.B])
            ahora = v2.diferencial(self.A, self.B, inicio, self.hh, res)
            pd.testing.assert_frame_equal(ahora[["periodo", "dif_promedio", "horas"]], antes, check_dtype=False)

    def test_spread_se_reconstruye_con_a_y_b(self):
        for res, tolerancia in (("horaria", 0.0051), ("diaria", 0.0101), ("mensual", 0.0101)):
            d = v.marcar_periodos(v2.diferencial(self.A, self.B, self.hd, self.hh, res), self.hd, self.hh, res)
            leido = self.csv(x.tabla_spread(d, self.A, self.B, res))
            self.assertEqual(leido["spread_a_menos_b"].tolist(), d["dif_promedio"].tolist())
            self.assertEqual((leido["nodo_a"].iloc[0], leido["nodo_b"].iloc[0]), (self.A, self.B))
            error = (leido["pml_a"] - leido["pml_b"] - leido["spread_a_menos_b"]).abs().max()
            self.assertLessEqual(error, tolerancia, res)

    def test_componentes_conservan_signos(self):
        for res in ("horaria", "diaria", "mensual"):
            df = v.marcar_periodos(v3.componentes(self.A, self.hd, self.hh, res), self.hd, self.hh, res)
            leido = self.csv(x.tabla_componentes(df, self.A, res))
            for origen, columna in (("pml", "pml"), ("energia", "energia"), ("perdidas", "perdidas"),
                                    ("congestion", "congestion"), ("descuadre", "descuadre_promedio")):
                self.assertEqual(leido[columna].tolist(), df[origen].tolist(), f"{res} {columna}")
        horaria = self.csv(x.tabla_componentes(
            v.marcar_periodos(v3.componentes(self.A, self.hd, self.hh, "horaria"), self.hd, self.hh, "horaria"),
            self.A, "horaria"))
        self.assertTrue((horaria["congestion"] < 0).any())


@unittest.skipUnless(HAY_DATOS, "Sin paquete público en data/")
class BotonEnLaInterfaz(unittest.TestCase):
    APP = str(Path(v.__file__).with_name("app.py"))

    def abrir(self, vista, nodo=None, desde=None, hasta=None, resolucion=None):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(self.APP, default_timeout=120).run()
        app.radio(key="vista").set_value(vista).run()
        if nodo:
            app.selectbox(key="nodo").set_value(nodo)
            app.date_input(key="desde").set_value(desde)
            app.date_input(key="hasta").set_value(hasta)
            app.radio(key="resolucion").set_value(resolucion)
            app.run()
        self.assertFalse(app.exception)
        return app

    def test_un_boton_por_vista_con_su_enlace(self):
        for vista, nombre in (("1. PML histórico", "vista=historico"), ("2. Comparar nodos (spread)", "vista=comparacion"),
                              ("3. Componentes del PML", "vista=componentes")):
            app = self.abrir(vista)
            self.assertEqual(len(app.get("download_button")), 1, vista)
            self.assertIn(nombre, app.code[0].value)
            self.assertEqual(app.query_params["vista"], nombre.split("=")[1])
            self.assertTrue(any(".csv · resolución" in c.value for c in app.caption))

    def test_sin_datos_no_hay_boton(self):
        app = self.abrir("1. PML histórico", "03TLJ-230", date(2023, 1, 1), date(2023, 1, 2), "diaria")
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertIn("no equivale a precio cero", app.warning[0].value)

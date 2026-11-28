"""v0.10.0 · Operación · Demanda (Issue #32): lector del contrato «demanda v1» y panel derecho. Sin red.

Los archivos de tests/fixtures/demanda son la publicación real de la rama datos-demanda del 2026-11-28 06:10 CDMX
(10 gerencias; el 27 completo y el 28 hasta la hora 6).
    python -m pytest tests/test_demanda.py -q
"""
from datetime import date, datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demanda as dem  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "demanda"
APP = str(Path(__file__).resolve().parents[1] / "app.py")
A_LAS_0630 = datetime(2026, 11, 28, 12, 30, tzinfo=timezone.utc)


def publicado(dia="2026-11-28"):
    return (FIX / "metadata.json").read_text(encoding="utf-8"), (FIX / f"{dia}.csv").read_text(encoding="utf-8")


class Lector(unittest.TestCase):
    def test_descarga_y_lectura_de_lo_publicado(self):
        m, df = dem.leer(*dem.descargar(FIX.as_uri()))
        self.assertEqual(m["dias"][-1], "2026-11-28")
        self.assertEqual(len(df), 240)
        self.assertEqual(list(df.columns), dem.COLUMNAS)
        self.assertEqual(set(df["fecha"]), {date(2026, 11, 28)})
        self.assertTrue(df.loc[df["estado_demanda"] != "ok", "demanda_mw"].isna().all())

    def test_contrato_roto_no_muestra_cifras(self):
        m, csv = publicado()
        casos = {
            "contrato": (m.replace("demanda v1", "demanda v2"), csv),
            "columnas": (m, csv.replace("demanda_mw", "demanda")),
            "un 0 como demanda": (m, csv.replace("2026-11-28,SIN,1,34475,", "2026-11-28,SIN,1,0,")),
            "estado sin demanda": (m, csv.replace(",ok,", ",pendiente,", 1)),
            "gerencia desconocida": (m, csv.replace(",BCA,", ",MULEGE,")),
            "hora repetida": (m, csv + csv.splitlines()[1] + "\n"),
            "no es JSON": ("{", csv),
        }
        for nombre, (mt, ct) in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(dem.DemandaInvalida):
                    dem.leer(mt, ct)

    def test_sin_dias_publicados(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "metadata.json").write_text('{"contrato": "demanda v1", "dias": []}', encoding="utf-8")
        with self.assertRaises(dem.DemandaInvalida):
            dem.descargar(tmp.as_uri())


class Cifras(unittest.TestCase):
    def setUp(self):
        _, self.df = dem.leer(*publicado())
        self.t = dem.con_sen(self.df)

    def test_sen_es_la_suma_solo_con_las_tres(self):
        sen = self.t[self.t["gerencia"] == "SEN"].set_index("hora")
        tres = self.df[self.df["gerencia"].isin(["SIN", "BCA", "BCS"])].groupby("hora")
        self.assertEqual(sen.loc[1, "demanda_mw"], tres["demanda_mw"].sum()[1])
        self.assertEqual(sen.loc[24, "pronostico_mw"], tres["pronostico_mw"].sum()[24])
        self.assertTrue(sen.loc[7:, "demanda_mw"].isna().all())
        self.assertEqual(set(sen.loc[7:, "estado_demanda"]), {"pendiente"})

    def test_sen_no_suma_si_falta_una(self):
        sin_bcs = self.df.copy()
        sin_bcs.loc[(sin_bcs["gerencia"] == "BCS") & (sin_bcs["hora"] == 3), ["demanda_mw", "estado_demanda"]] = \
            [None, "sin_dato"]
        sen = dem.con_sen(sin_bcs).query("gerencia == 'SEN'").set_index("hora")
        self.assertTrue(pd.isna(sen.loc[3, "demanda_mw"]))
        self.assertEqual(sen.loc[3, "estado_demanda"], "sin_dato")
        self.assertFalse(pd.isna(sen.loc[2, "demanda_mw"]))

    def test_resumen_del_sin(self):
        r = dem.resumen(self.t, "SIN")
        sin = self.df[self.df["gerencia"] == "SIN"].set_index("hora")
        self.assertEqual((r["hora"], r["demanda"], r["pronostico"]),
                         (6, sin.loc[6, "demanda_mw"], sin.loc[6, "pronostico_mw"]))
        self.assertAlmostEqual(r["desvio_mw"], sin.loc[6, "demanda_mw"] - sin.loc[6, "pronostico_mw"])
        self.assertEqual((r["max_real"], r["hora_max_real"]), (sin["demanda_mw"].max(), int(sin["demanda_mw"].idxmax())))
        self.assertEqual((r["max_pronostico"], r["hora_max_pronostico"]),
                         (sin["pronostico_mw"].max(), int(sin["pronostico_mw"].idxmax())))
        self.assertEqual((r["horas_ok"], r["horas_pendientes"], r["horas_sin_dato"]), (6, 18, 0))

    def test_una_region_atrasada_usa_su_propia_ultima_hora(self):
        self.assertEqual(dem.resumen(self.t, "NORTE")["hora"], 5)  # NORTE y PENINSULAR llevaban una hora menos

    def test_sin_horas_con_dato_no_inventa(self):
        vacio = self.df.copy()
        vacio["demanda_mw"], vacio["estado_demanda"] = None, "pendiente"
        r = dem.resumen(dem.con_sen(vacio), "SEN")
        self.assertIsNone(r["hora"])
        self.assertIsNone(r["demanda"])
        self.assertIsNone(r["max_real"])
        self.assertIsNotNone(r["max_pronostico"])

    def test_serie_sin_horas_futuras_de_demanda(self):
        s = dem.serie(self.t, "SIN")
        self.assertEqual(len(s[s["serie"] == "Real"]), 6)
        self.assertEqual(len(s[s["serie"] == "Pronóstico"]), 24)

    def test_tramo_y_frescura(self):
        self.assertEqual(dem.tramo(1), "00:00–01:00")
        self.assertEqual(dem.tramo(24), "23:00–24:00")
        f = dem.frescura("2026-11-28T12:10:05Z", date(2026, 11, 28), ahora=A_LAS_0630)
        self.assertEqual((f["estado"], f["minutos"], f"{f['lectura_cdmx']:%H:%M}"), ("al_dia", 19, "06:10"))
        tarde = datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(dem.frescura("2026-11-28T12:10:05Z", date(2026, 11, 28), ahora=tarde)["estado"], "atrasada")
        manana = datetime(2026, 11, 29, 7, 0, tzinfo=timezone.utc)  # 01:00 del 29 en CDMX
        self.assertEqual(dem.frescura("2026-11-29T05:55:00Z", date(2026, 11, 28), ahora=manana)["estado"], "otro_dia")
        self.assertEqual(dem.hace(19), "hace 19 min")
        self.assertEqual(dem.hace(125), "hace 2 h 05 min")


class Panel(unittest.TestCase):
    def correr(self, url=None):
        from streamlit.testing.v1 import AppTest
        import streamlit as st
        st.cache_data.clear()
        anterior = dem.URL_BASE
        if url:
            dem.URL_BASE = url
        try:
            app = AppTest.from_file(APP, default_timeout=120).run()
        finally:
            dem.URL_BASE = anterior
        self.assertFalse(app.exception)
        return app

    @staticmethod
    def html(app):
        return "\n".join(m.value for m in app.markdown)

    def test_panel_con_lo_publicado(self):
        app = self.correr()
        texto = self.html(app)
        self.assertIn("Operación · Demanda", texto)
        self.assertIn("Demanda real · hora 6 (05:00–06:00)", texto)
        self.assertIn("34,475 MW · h1", texto)  # máxima real del SIN
        self.assertIn("Indicativo, no para liquidación", texto)
        hoy = datetime.now(timezone.utc).astimezone(dem.MEXICO).date()
        self.assertEqual("Todavía no hay lectura de hoy" in texto, hoy != date(2026, 11, 28))
        region = app.selectbox(key="dem_gerencia")
        self.assertEqual(region.value, "SIN")
        self.assertEqual(region.options[0], "SEN (SIN + BCA + BCS)")
        region.set_value("SEN").run()
        r = dem.resumen(dem.con_sen(dem.leer(*publicado())[1]), "SEN")
        self.assertIn(f"{r['demanda']:,.0f}<small>MW</small>", self.html(app))

    def test_sin_publicacion_no_muestra_cifras(self):
        app = self.correr(Path(tempfile.mkdtemp()).as_uri())
        texto = self.html(app)
        self.assertIn("La demanda no está disponible", texto)
        self.assertNotIn("dem-cifra", texto)
        self.assertEqual([s for s in app.selectbox if s.key == "dem_gerencia"], [])

    def test_publicacion_rota_no_muestra_cifras(self):
        tmp = Path(tempfile.mkdtemp())
        shutil.copy(FIX / "metadata.json", tmp)
        (tmp / "2026-11-28.csv").write_text("fecha,otra\n2026-11-28,1\n", encoding="utf-8")
        texto = self.html(self.correr(tmp.as_uri()))
        self.assertIn("La demanda no está disponible", texto)
        self.assertNotIn("dem-cifra", texto)


if __name__ == "__main__":
    unittest.main()

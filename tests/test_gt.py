"""Guatemala Price Explorer v0.1 (edarji/edarji.net#8): datos, ticker, CSV, enlaces y recorrido de la app.

Paquetes gt-1 ficticios en carpetas temporales: no se lee `gt/` real, ni `data/`, ni `pnd/`.
Las pruebas con parquet o AppTest se saltan si falta pyarrow o streamlit (ambos están en requirements.txt).
"""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gt_datos as gd  # noqa: E402
import gt_ticker as gtk  # noqa: E402

try:
    import pyarrow  # noqa: F401
    HAY_PARQUET = True
except ImportError:
    HAY_PARQUET = False
try:
    from streamlit.testing.v1 import AppTest
    HAY_ST = HAY_PARQUET
except ImportError:
    HAY_ST = False

RAIZ = Path(__file__).resolve().parents[1]


def horario(precios):
    """{fecha: [24 precios] o lista parcial} -> poe_horario con periodo, como lo deja gd.leer."""
    filas = [{"fecha": d, "hora": h, "poe_usd_mwh": p, "generador_marginal": "GENOR" if h % 2 else "CHIXOY"}
             for d, ps in precios.items() for h, p in enumerate(ps)]
    df = pd.DataFrame(filas)
    df["periodo"] = pd.to_datetime(df["fecha"]) + pd.to_timedelta(df["hora"], unit="h")
    return df


def diario(h):
    g = h.groupby("fecha")["poe_usd_mwh"]
    return pd.DataFrame({"horas_validas": g.count(), "promedio": g.mean(), "mediana": g.median(),
                         "minimo": g.min(), "maximo": g.max()}).reset_index()


D, D1, D2 = date(2026, 11, 26), date(2026, 11, 25), date(2026, 11, 24)


class Ticker(unittest.TestCase):
    def test_sube_con_minimo_y_maximo(self):
        f = gtk.ficha(diario(horario({D1: [100.0] * 24, D: [100.0] * 23 + [124.0]})))
        self.assertEqual((f["dia"], f["dia_previo"], f["precio"], f["delta"]), (D, D1, 101.0, 1.0))
        self.assertEqual((f["direccion"], f["minimo"], f["maximo"]), ("sube", 100.0, 124.0))
        self.assertEqual(gtk.cambio(f), "▲ +1.00")

    def test_previo_ausente_no_busca_un_dia_anterior(self):
        f = gtk.ficha(diario(horario({D2: [90.0] * 24, D: [100.0] * 24})))
        self.assertEqual((f["estado"], f["delta"], f["direccion"]), ("sin_comparacion", None, None))
        self.assertIn("sin comparación", gtk.cambio(f))

    def test_cero_y_negativos_sin_porcentaje(self):
        f = gtk.ficha(diario(horario({D1: [0.0] * 24, D: [-5.0] * 24})))
        self.assertEqual((f["delta"], f["direccion"]), (-5.0, "baja"))
        self.assertNotIn("%", gtk.cambio(f))

    def test_parcial_sin_flecha(self):
        f = gtk.ficha(diario(horario({D1: [100.0] * 20, D: [100.0] * 24})))
        self.assertEqual((f["estado"], f["direccion"]), ("parcial", None))
        self.assertIn("parcial 24/20 h", gtk.cambio(f))

    def test_igualdad_ticker_detalle_agregados_csv(self):
        h = horario({D1: [100.0 + x for x in range(24)], D: [150.5 + x for x in range(24)]})
        f = gtk.ficha(diario(h))
        s = gd.serie(h, D, D, "diaria")
        texto, _ = gd.csv(h, D, D, "diaria")
        fila = texto.decode("utf-8-sig").splitlines()[1].split(",")
        self.assertEqual(round(s["poe"].iloc[0], 2), f["precio"])
        self.assertEqual(float(fila[1]), f["precio"])
        self.assertEqual(round(gd.estadisticas(h, D, D)["promedio"], 2), f["precio"])


class Consultas(unittest.TestCase):
    def test_mensual_sobre_horas_no_promedio_de_promedios(self):
        h = horario({D1: [100.0] * 24, D: [200.0] * 12})
        self.assertEqual(gd.serie(h, D1, D, "mensual")["poe"].iloc[0], (100 * 24 + 200 * 12) / 36)

    def test_hueco_parte_la_serie_diaria(self):
        h = horario({D2: [1.0] * 24, D: [2.0] * 24})
        s = gd.serie(h, D2, D, "diaria")
        self.assertEqual(list(s["periodo"].dt.date), [D2, D])       # D1 sin fila: no se rellena
        e = gd.estadisticas(h, D2, D)
        self.assertEqual((e["horas"], e["horas_rango"], e["cobertura_pct"]), (48, 72, 66.7))

    def test_csv_horario_con_hora_de_inicio_y_formula_neutralizada(self):
        h = horario({D: [10.0] * 24})
        h.loc[0, "generador_marginal"] = "=HYPERLINK(1)"
        texto, nombre = gd.csv(h, D, D, "horaria")
        lineas = texto.decode("utf-8-sig").splitlines()
        self.assertEqual(lineas[0], "fecha,hora_inicio_gt,poe_usd_mwh,generador_marginal")
        self.assertTrue(lineas[1].startswith("2026-11-26,0,10.0,'=HYPERLINK"))
        self.assertEqual(nombre, "gt_amm_poe_posdespacho_usd_mwh_horaria_2026-11-26_2026-11-26.csv")

    def test_url(self):
        lim = {"desde": D2, "hasta": D}
        self.assertEqual(gd.leer_url({"desde": "2026-11-25", "hasta": "2026-11-26", "resolucion": "diaria"}, lim),
                         (D1, D, "diaria"))
        self.assertEqual(gd.leer_url({"desde": "2026-11-26", "hasta": "2026-11-24", "resolucion": "x"}, lim),
                         (None, None, None))
        self.assertEqual(gd.leer_url({"desde": "2020-01-01"}, lim), (None, None, None))

    def test_frescura_no_marca_atraso_antes_de_la_publicacion(self):
        meta = {"desde": "2026-11-01", "hasta": "2026-11-25"}
        antes = datetime(2026, 11, 27, 10, 0, tzinfo=gd.ZONA_GT)
        despues = datetime(2026, 11, 27, 15, 0, tzinfo=gd.ZONA_GT)
        self.assertEqual(gd.frescura(meta, antes), ("al_dia", D1))
        self.assertEqual(gd.frescura(meta, despues), ("atrasado", D))


def escribir_paquete(carpeta, h):
    """Paquete gt-1 como lo escribe power-market-lab/scripts/gt_publico.py."""
    carpeta.mkdir(parents=True, exist_ok=True)
    tablas = {"poe_horario": h[["fecha", "hora", "poe_usd_mwh", "generador_marginal"]], "poe_diario": diario(h)}
    g = h.assign(mes=pd.to_datetime(h["fecha"]).dt.strftime("%Y-%m")).groupby("mes")
    tablas["poe_mensual"] = pd.DataFrame({"dias_con_dato": g["fecha"].nunique(), "horas_validas": g["poe_usd_mwh"].count(),
                                          "promedio": g["poe_usd_mwh"].mean(), "minimo": g["poe_usd_mwh"].min(),
                                          "maximo": g["poe_usd_mwh"].max()}).reset_index()
    archivos = {}
    for n, df in tablas.items():
        r = carpeta / f"{n}.parquet"
        df.to_parquet(r, index=False)
        archivos[r.name] = {"filas": len(df), "sha256": hashlib.sha256(r.read_bytes()).hexdigest()}
    meta = {"version_esquema": "gt-1", "generado_utc": "2026-11-27T18:30:00Z", "desde": str(min(h["fecha"])),
            "hasta": str(max(h["fecha"])), "dias_sin_dato": [], "archivos": archivos,
            "fuente": {"nombre": "AMM - Posdespacho Diario, hoja POE", "url": "https://www.amm.org.gt/",
                       "nota": "Datos preliminares."}}
    (carpeta / "metadata.json").write_text(json.dumps(meta))


@unittest.skipUnless(HAY_PARQUET, "requiere pyarrow")
class Paquete(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_lectura_valida_y_corrupcion(self):
        escribir_paquete(self.tmp, horario({D1: [100.0] * 24, D: [110.0] * 24}))
        p = gd.leer(self.tmp)
        self.assertEqual(len(p["poe_horario"]), 48)
        (self.tmp / "poe_diario.parquet").write_bytes(b"danado")
        with self.assertRaisesRegex(gd.PaqueteInvalido, "sha256"):
            gd.leer(self.tmp)

    def test_correccion_misma_fecha_cambia_huella(self):
        escribir_paquete(self.tmp, horario({D: [110.0] * 24}))
        antes = gd.huella(self.tmp)
        escribir_paquete(self.tmp, horario({D: [111.0] * 24}))
        self.assertNotEqual(gd.huella(self.tmp), antes)


@unittest.skipUnless(HAY_ST, "requiere streamlit y pyarrow")
class App(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        dias = {date(2026, 1, 1) + timedelta(days=i): [100.0 + i] * 24 for i in range(330)}
        escribir_paquete(self.tmp, horario(dias))
        self.p = mock.patch.object(gd, "GT_DIR", self.tmp)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        shutil.rmtree(self.tmp)

    def app(self, **params):
        at = AppTest.from_file(str(RAIZ / "gt_app.py"), default_timeout=30)
        for k, v in params.items():
            at.query_params[k] = v
        return at.run()

    def test_carga_con_fuente_preliminar_y_ticker(self):
        at = self.app()
        self.assertFalse(at.exception)
        textos = " ".join(m.value for m in at.markdown)
        self.assertIn("Datos preliminares", textos)
        self.assertIn("POE posdespacho", textos)

    def test_ytd_y_vuelta_a_1d_horaria(self):
        at = self.app()
        at.button(key="rango_YTD").click().run()
        self.assertEqual(at.session_state.inicio, date(2026, 1, 1))
        at.button(key="rango_1D").click().run()
        self.assertEqual((at.session_state.inicio, at.session_state.resolucion), (date(2026, 11, 26), "horaria"))

    def test_enlace_reproducible(self):
        at = self.app(desde="2026-03-01", hasta="2026-03-31", resolucion="diaria")
        self.assertEqual((at.session_state.inicio, at.session_state.fin, at.session_state.resolucion),
                         (date(2026, 3, 1), date(2026, 3, 31), "diaria"))

    def test_paquete_danado_sin_cifras(self):
        (self.tmp / "poe_horario.parquet").write_bytes(b"x")
        at = self.app()
        self.assertTrue(any("no pasó la validación" in e.value for e in at.error))
        self.assertEqual(len(at.metric), 0)


if __name__ == "__main__":
    unittest.main()

"""v0.9.2 · Chaly's Bebop 🎷 para zonas de carga PND (Issue #46).

- Datos: `pnd.acumulados_diarios_pnd` da exactamente el promedio diario y las horas de `pnd.serie_pnd(..., "diaria")`
  (todas las fechas del paquete, varias zonas). El 8 de mayo de 2026 (sin dato) es un hueco; el 29 de febrero sale.
- Lógica pura con acumuladores PND sintéticos: negativos, la columna `promedio` manda, zonas con 0 o 1 años.
- Enlace `modalidad=pnd&zona=…&vista=estacional&anio=…`; un enlace PND sin `vista` sigue abriendo el histórico.
- En la app: Monterrey 2026 con banda 2023–2025 (3 de 5), línea Y azul PND, CSV `pnd_bebop_<zona>_<año>.csv`.
"""
from datetime import date
import io
import json
from pathlib import Path
import sys
import time
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import estacional as es
import pnd
from enlaces import VISTAS_PND, construir_enlace, leer_enlace

APP = str(Path(pnd.__file__).with_name("app.py"))
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()
AZUL = "#0A84FF"


def acumulados_pnd(valores):
    """{fecha ISO: (promedio, horas)} -> acumuladores PND (suma_pnd, horas_validas, promedio)."""
    filas = [(date.fromisoformat(f), p * h, h, p) for f, (p, h) in valores.items()]
    return pd.DataFrame(filas, columns=["fecha", "suma_pnd", "horas_validas", "promedio"])


def fila(t, mes_dia):
    return t[t["mes_dia"] == mes_dia].iloc[0]


@unittest.skipUnless(HAY_PND, "Sin paquete público en pnd/")
class DatosPublicados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = pnd.metadata_pnd()
        cls.desde, cls.hasta = date.fromisoformat(m["desde"]), date.fromisoformat(m["hasta"])

    def test_igual_que_serie_pnd_diaria(self):
        for zona in ("MONTERREY", "VDM CENTRO", "RIVIERA MAYA", "CABORCA"):
            with self.subTest(zona=zona):
                a = pnd.acumulados_diarios_pnd(zona, self.desde, self.hasta)
                s = pnd.serie_pnd(zona, self.desde, self.hasta, "diaria")
                self.assertEqual(len(a), len(s))
                self.assertEqual(list(pd.to_datetime(a["fecha"])), list(s["periodo"]))
                self.assertEqual(a["promedio"].tolist(), s["pnd_promedio"].tolist())  # exacto, sin tolerancia
                self.assertEqual(a["horas_validas"].tolist(), s["horas"].tolist())

    def test_hueco_del_8_de_mayo_de_2026(self):
        a = pnd.acumulados_diarios_pnd("MONTERREY", date(2026, 5, 1), date(2026, 5, 31))
        fechas = set(pd.to_datetime(a["fecha"]).dt.date)
        self.assertNotIn(date(2026, 5, 8), fechas)
        self.assertIn(date(2026, 5, 7), fechas)
        self.assertIn(date(2026, 5, 9), fechas)
        t = es.tabla(a, 2026)
        self.assertTrue(pd.isna(fila(t, "05-08")["y"]))  # ni cero ni copia del 7 o del 9
        tramos = es.tramos(t, "y")
        self.assertNotEqual(tramos[t["mes_dia"] == "05-07"].iloc[0], tramos[t["mes_dia"] == "05-09"].iloc[0])

    def test_29_de_febrero_fuera_y_1_de_marzo_en_su_lugar(self):
        a = pnd.acumulados_diarios_pnd("MONTERREY", date(2024, 1, 1), date(2024, 12, 31))
        self.assertIn(date(2024, 2, 29), set(pd.to_datetime(a["fecha"]).dt.date))  # el paquete sí lo tiene
        t = es.tabla(a, 2024)
        self.assertEqual(len(t), 365)
        self.assertNotIn("02-29", set(t["mes_dia"]))
        marzo = a[pd.to_datetime(a["fecha"]).dt.date == date(2024, 3, 1)]["promedio"].iloc[0]
        self.assertEqual(fila(t, "03-01")["y"], marzo)

    def test_anio_inicial_sin_banda(self):
        a = pnd.acumulados_diarios_pnd("MONTERREY", date(2018, 1, 1), date(2023, 12, 31))
        t = es.tabla(a, 2023)
        self.assertEqual(int(t["n"].max()), 0)  # nada de 2018–2022: no se inventan años
        self.assertTrue(t["banda_min"].isna().all())
        self.assertTrue(t["y_1"].isna().all() and t["y_2"].isna().all())

    def test_seis_anios_en_menos_de_dos_segundos(self):
        inicio, fin = es.rango_consulta(2026, {"desde": self.desde, "hasta": self.hasta})
        t0 = time.perf_counter()
        a = pnd.acumulados_diarios_pnd("VDM CENTRO", inicio, fin)
        self.assertLess(time.perf_counter() - t0, 2.0)
        self.assertGreater(len(a), 1000)


class LogicaPND(unittest.TestCase):
    def test_negativos_y_la_columna_promedio_manda(self):
        valores = {"2023-04-02": (-35.5, 24), "2024-04-02": (120.0, 24), "2025-04-02": (-2.25, 23),
                   "2026-04-02": (-40.0, 24)}
        a = acumulados_pnd(valores)
        a.loc[a["fecha"] == date(2024, 4, 2), "suma_pnd"] = 120.004 * 24  # suma/horas redondearía distinto
        t = es.tabla(a, 2026)
        abril = fila(t, "04-02")
        self.assertEqual((abril["banda_min"], abril["banda_max"], abril["n"]), (-35.5, 120.0, 3))
        self.assertEqual((abril["y"], abril["y_1"], abril["y_2"]), (-40.0, -2.25, 120.0))
        self.assertEqual(abril["fuera"], "abajo")

    def test_resumen_pondera_con_suma_pnd(self):
        a = acumulados_pnd({"2025-01-01": (100.0, 24), "2026-01-01": (200.0, 12), "2026-01-02": (50.0, 24)})
        r = es.resumen(es.tabla(a, 2026), a, 2026)
        self.assertEqual((r["promedio_y"], r["promedio_y_1"], r["dias_comunes"]), (200.0, 100.0, 1))

    def test_zona_con_cero_o_un_anio_previo(self):
        nueva = acumulados_pnd({"2026-06-01": (300.0, 24)})
        t = es.tabla(nueva, 2026)
        self.assertEqual(int(t["n"].max()), 0)
        un_anio = acumulados_pnd({"2025-06-01": (280.0, 24), "2026-06-01": (300.0, 24)})
        t = es.tabla(un_anio, 2026)
        self.assertEqual(int(fila(t, "06-01")["n"]), 1)
        self.assertTrue(pd.isna(fila(t, "06-01")["banda_min"]))  # una observación no es un rango
        self.assertIsNone(fila(t, "06-01")["fuera"])

    def test_csv_con_columnas_pnd(self):
        a = acumulados_pnd({"2025-06-01": (280.0, 24), "2026-06-01": (300.0, 24)})
        c = es.tabla_csv(es.tabla(a, 2026), 2026, "pnd")
        self.assertEqual(list(c.columns)[:5], ["fecha_calendario", "pnd_2026", "horas_2026", "pnd_2025", "pnd_2024"])


class Enlace(unittest.TestCase):
    L = {"desde": date(2023, 1, 1), "hasta": date(2026, 11, 19)}
    Z = ["MONTERREY", "VDM CENTRO"]

    def leer(self, **p):
        return leer_enlace({k: [v] for k, v in p.items()}, ["01AAN-85"], self.L, self.Z, self.L)

    def test_ida_y_vuelta(self):
        estado = {"modalidad": "pnd", "zona": "MONTERREY", "vista_pnd": VISTAS_PND["estacional"], "anio": 2025,
                  "desde": date(2026, 11, 19), "hasta": date(2026, 11, 19), "resolucion": "horaria", "yoy": True}
        enlace = construir_enlace(estado)
        self.assertEqual((enlace["vista"], enlace["anio"]), ("estacional", "2025"))
        self.assertNotIn("yoy", enlace)  # YoY es del histórico
        leido, problemas, faltantes = self.leer(**enlace)
        self.assertEqual((leido["vista_pnd"], leido["anio"], leido["zona"]), (VISTAS_PND["estacional"], 2025,
                                                                              "MONTERREY"))
        self.assertEqual((problemas, faltantes), ([], []))

    def test_sin_fechas_no_falta_nada(self):
        _, problemas, faltantes = self.leer(modalidad="pnd", zona="MONTERREY", vista="estacional")
        self.assertEqual((problemas, faltantes), ([], []))

    def test_enlace_pnd_de_siempre_es_el_historico(self):
        estado = {"modalidad": "pnd", "zona": "MONTERREY", "desde": date(2026, 11, 19), "hasta": date(2026, 11, 19),
                  "resolucion": "horaria", "yoy": True}
        self.assertEqual(construir_enlace(estado), {"modalidad": "pnd", "zona": "MONTERREY", "desde": "2026-11-19",
                                                    "hasta": "2026-11-19", "resolucion": "horaria", "yoy": "1"})
        leido, problemas, _ = self.leer(modalidad="pnd", zona="MONTERREY", desde="2026-11-19", hasta="2026-11-19",
                                        resolucion="horaria")
        self.assertNotIn("vista_pnd", leido)
        self.assertEqual(problemas, [])

    def test_vista_invalida_y_anio_fuera_del_paquete_pnd(self):
        _, problemas, _ = self.leer(modalidad="pnd", zona="MONTERREY", vista="componentes")
        self.assertIn("no existe para zonas de carga", problemas[0])
        _, problemas, _ = self.leer(modalidad="pnd", zona="MONTERREY", vista="estacional", anio="2022")
        self.assertIn("2023 y 2026", problemas[0])


def abrir(**parametros):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    return app


def spec(app):
    return json.loads(app.get("vega_lite_chart")[0].proto.spec)


def colores(s):
    return [c.get("mark", {}).get("color") for c in s["layer"]]


@unittest.skipUnless(HAY_PND, "Sin paquete público en pnd/")
class EnLaApp(unittest.TestCase):
    def test_monterrey_2026(self):
        app = abrir(modalidad="pnd", zona="MONTERREY", vista="estacional")
        self.assertEqual(app.radio(key="vista_pnd").value, VISTAS_PND["estacional"])
        self.assertEqual(app.subheader[0].value, "Chaly's Bebop · Monterrey · 2026")
        ficha = {m.label: m.value for m in app.metric}
        self.assertEqual(ficha["Años en la banda"], "3 de 5")
        textos = " ".join(m.value for m in app.markdown)
        self.assertIn("Banda Mín–Máx 2021–2025: 3 de 5 años con dato (2023, 2024, 2025)", textos)
        self.assertIn("PND promedio diario (MXN/MWh)", textos)
        self.assertIn(AZUL, colores(spec(app)))
        self.assertNotIn("#FFB000", colores(spec(app)))  # nada de ámbar PML
        captions = " ".join(c.value for c in app.caption)
        self.assertIn("pnd_bebop_MONTERREY_2026.csv", captions)
        self.assertIn("2026-05-08", captions)  # el día sin dato, dicho
        self.assertEqual(app.query_params["vista"], "estacional")
        self.assertEqual(app.query_params["anio"], "2026")

    def test_cambiar_anio_y_zona(self):
        app = abrir(modalidad="pnd", zona="VDM CENTRO", vista="estacional", anio="2024")
        self.assertEqual(app.subheader[0].value, "Chaly's Bebop · Vdm Centro · 2024")
        self.assertEqual({m.label: m.value for m in app.metric}["Años en la banda"], "1 de 5")  # solo 2023: sin banda
        app.radio(key="anio").set_value(2025).run()
        self.assertEqual({m.label: m.value for m in app.metric}["Años en la banda"], "2 de 5")
        self.assertEqual(app.query_params["anio"], "2025")

    def test_pestanas_historico_y_bebop(self):
        app = abrir(modalidad="pnd", zona="MONTERREY", desde="2026-11-13", hasta="2026-11-19", resolucion="diaria")
        self.assertEqual(app.radio(key="vista_pnd").value, VISTAS_PND["historico"])
        self.assertIn("precio de zona de carga (PND)", app.subheader[0].value)
        self.assertNotIn("vista", app.query_params)
        app.radio(key="vista_pnd").set_value(VISTAS_PND["estacional"]).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.subheader[0].value.startswith("Chaly's Bebop · Monterrey"))
        app.radio(key="vista_pnd").set_value(VISTAS_PND["historico"]).run()
        self.assertEqual(app.query_params["desde"], "2026-11-13")  # las fechas del histórico se conservan

    def test_pml_bebop_sigue_en_ambar(self):
        app = abrir(vista="estacional", nodo="01LCP-400", anio="2026")
        self.assertIn("#FFB000", colores(spec(app)))
        self.assertNotIn("vista_pnd", [r.key for r in app.radio])


if __name__ == "__main__":
    unittest.main()

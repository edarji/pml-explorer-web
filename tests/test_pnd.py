"""v0.7.0 · Precio de zona de carga (PND): contrato, consultas, enlaces, CSV e interfaz.

Usa un paquete PND sintético en una carpeta temporal (no es dato publicado ni se escribe en el repo).
Las pruebas de interfaz usan además el paquete PML real de data/ y se omiten si no está.
"""
from datetime import date, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import enlaces
import exportar as x
import pnd
import vista1 as v

APP = str(Path(v.__file__).with_name("app.py"))
ZONAS = ["CENTRO ORIENTE", "MONTERREY", "VDM CENTRO"]
DESDE, HASTA = date(2026, 11, 1), date(2026, 11, 5)
SIN_DATO = [date(2026, 11, 3)]


def armar_paquete(carpeta, desde=DESDE, hasta=HASTA, sin_dato=SIN_DATO, zonas=ZONAS):
    """Paquete con la forma del contrato PND v1 (como lo escribe exportar_pnd.py), con precios ficticios.

    PND de la hora h en la zona i: 100*i + h (energía 90*i + h, pérdidas 6*i, congestión 4*i); la hora 3 de
    MONTERREY el 2026-11-01 es negativa (-50) para probar el conteo de horas negativas.
    """
    carpeta = Path(carpeta)
    (carpeta / "hourly").mkdir(parents=True)
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1) if desde + timedelta(days=i) not in sin_dato]
    filas = []
    for d in dias:
        for i, z in enumerate(zonas, start=1):
            for h in range(1, 25):
                pnd_ = -50.0 if (z == "MONTERREY" and d == desde and h == 3) else 100.0 * i + h
                filas.append(("SIN", "MDA", z, d, h, pnd_, pnd_ - 10.0 * i, 6.0 * i, 4.0 * i))
    df = pd.DataFrame(filas, columns=["sistema", "mercado", "zona_carga", "fecha", "hora", "pnd", "energia",
                                      "perdidas", "congestion"])
    con = duckdb.connect()
    con.register("df", df)
    for d in dias:
        con.execute(f"""COPY (SELECT sistema::VARCHAR sistema, mercado::VARCHAR mercado, zona_carga::VARCHAR zona_carga,
                                     fecha::DATE fecha, hora::INTEGER hora, pnd::DOUBLE pnd, energia::DOUBLE energia,
                                     perdidas::DOUBLE perdidas, congestion::DOUBLE congestion
                              FROM df WHERE fecha = DATE '{d}' ORDER BY zona_carga, hora)
                        TO '{carpeta}/hourly/{d}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (SELECT zona_carga::VARCHAR zona_carga, MIN(fecha)::DATE primera_fecha, MAX(fecha)::DATE ultima_fecha
                          FROM df GROUP BY 1 ORDER BY 1) TO '{carpeta}/zonas.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    escribir_metadata(carpeta, desde, hasta, sin_dato, len(zonas))
    return carpeta


FIXTURE_SIN_DATO = Path(__file__).with_name("fixtures") / "pnd_dias_sin_dato.json"
# Copia exacta de power-market-lab config/pnd_dias_sin_dato.json (rama pnd-descarga, 6e0af8d): el mismo esquema que
# exportar_pnd.py escribe en metadata.dias_sin_dato. Las pruebas no usan otro esquema de fixture.
ENTRADA_REAL = json.loads(FIXTURE_SIN_DATO.read_text(encoding="utf-8"))[0]


def evidencia(dia):
    """Entrada con el esquema real, trasladada a otro día (solo cambian la fecha y la ruta de la URL)."""
    entrada = json.loads(json.dumps(ENTRADA_REAL))
    entrada["fecha"] = str(dia)
    for c in entrada["consultas"]:
        c["url"] = c["url"].replace("/2026/05/08/2026/05/08/", f"/{dia:%Y/%m/%d}/{dia:%Y/%m/%d}/")
    return entrada


def escribir_metadata(carpeta, desde, hasta, sin_dato, n_zonas, **extra):
    archivos = {}
    for p in sorted(carpeta.rglob("*.parquet")):
        archivos[p.relative_to(carpeta).as_posix()] = {
            "filas": duckdb.sql(f"SELECT COUNT(*) FROM '{p}'").fetchall()[0][0],
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    meta = {"version_esquema": "1", "generado_utc": "2026-11-20T05:30:00Z", "fuente": "CENACE SW-PEND, MDA, SIN",
            "unidades": "MXN/MWh", "convencion_hora": "1-24 hora final", "desde": str(desde), "hasta": str(hasta),
            "zonas": n_zonas, "dias_corregidos": [], "dias_sin_dato": [evidencia(d) for d in sin_dato],
            "archivos": archivos} | extra
    (carpeta / "metadata.json").write_text(json.dumps(meta))


class Contrato(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = armar_paquete(self.tmp / "pnd")

    def test_paquete_valido(self):
        limites = pnd.inspeccionar_pnd(self.dir)
        self.assertEqual((limites["desde"], limites["hasta"], limites["zonas"]), (DESDE, HASTA, 3))
        self.assertEqual(limites["dias_sin_dato"], SIN_DATO)
        self.assertEqual(list(pnd.zonas(self.dir)), ZONAS)

    def test_sin_paquete(self):
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.tmp / "no-existe")

    def test_hueco_no_declarado_se_rechaza(self):
        (self.dir / "hourly" / "2026-11-04.parquet").unlink()
        escribir_metadata(self.dir, DESDE, HASTA, SIN_DATO, 3)
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.dir)

    def test_archivo_alterado_o_extra_se_rechaza(self):
        extra = self.dir / "hourly" / "2026-11-03.parquet"  # día declarado sin dato
        shutil.copy(self.dir / "hourly" / "2026-11-02.parquet", extra)
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.dir)
        extra.unlink()
        with open(self.dir / "hourly" / "2026-11-02.parquet", "ab") as f:
            f.write(b"x")
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.dir)

    def test_entrada_real_de_config_se_acepta(self):
        """Integración: paquete alrededor del 2026-05-08 con la entrada idéntica a config/pnd_dias_sin_dato.json."""
        real = armar_paquete(self.tmp / "real", desde=date(2026, 5, 6), hasta=date(2026, 5, 10),
                             sin_dato=[date(2026, 5, 8)])
        escribir_metadata(real, date(2026, 5, 6), date(2026, 5, 10), [], 3, dias_sin_dato=[ENTRADA_REAL])
        limites = pnd.inspeccionar_pnd(real)
        self.assertEqual(limites["dias_sin_dato"], [date(2026, 5, 8)])
        self.assertEqual(limites["evidencia_sin_dato"][date(2026, 5, 8)]["consultado_utc"], "2026-11-20T12:18:26Z")

    def test_evidencia_invalida_se_rechaza(self):
        def con(**cambio):
            e = evidencia(SIN_DATO[0])
            e["consultas"][0].update(cambio)
            return e
        casos = {"http 500": con(http=500), "status ERROR": con(status="ERROR"), "http 204": con(http=204),
                 "hora sin Z": con(consultado_utc="2026-11-20 12:18:26"), "hora inválida": con(consultado_utc="ayer"),
                 "url de otro día": con(url="https://ws01.cenace.gob.mx:8082/SWPEND/SIM/SIN/MDA/2026/11/04/2026/11/04/JSON"),
                 "url de otro servicio": con(url="https://example.com/2026/11/03/JSON"),
                 "sin respuesta": con(respuesta=""), "http texto": con(http="200")}
        for caso, entrada in casos.items():
            with self.subTest(caso=caso):
                escribir_metadata(self.dir, DESDE, HASTA, [], 3, dias_sin_dato=[entrada])
                with self.assertRaises(pnd.PndNoDisponible):
                    pnd.inspeccionar_pnd(self.dir)

    def test_metadata_malformada_es_pnd_no_disponible(self):
        dia = str(SIN_DATO[0])
        sin_fecha = evidencia(SIN_DATO[0])
        del sin_fecha["fecha"]
        archivos = json.loads((self.dir / "metadata.json").read_text())["archivos"]
        primero = next(iter(archivos))
        casos = {
            "entrada con consulta sin fecha": {"dias_sin_dato": [sin_fecha]},
            "fecha no texto": {"dias_sin_dato": [evidencia(SIN_DATO[0]) | {"fecha": 20261103}]},
            "consultas no lista": {"dias_sin_dato": [evidencia(SIN_DATO[0]) | {"consultas": {"x": 1}}]},
            "dias_sin_dato ausente": {"dias_sin_dato": None},
            "dias_sin_dato no lista": {"dias_sin_dato": dia},
            "archivos no dict": {"archivos": list(archivos)},
            "info no dict": {"archivos": archivos | {primero: "x"}},
            "filas texto": {"archivos": archivos | {primero: archivos[primero] | {"filas": "72"}}},
            "filas bool": {"archivos": archivos | {primero: archivos[primero] | {"filas": True}}},
            "sha256 corto": {"archivos": archivos | {primero: archivos[primero] | {"sha256": "abc"}}},
            "zonas texto": {"zonas": "3"},
            "generado sin Z": {"generado_utc": "2026-11-20"},
            "corregidos con números": {"dias_corregidos": [1]},
        }
        for caso, cambio in casos.items():
            with self.subTest(caso=caso):
                escribir_metadata(self.dir, DESDE, HASTA, SIN_DATO, 3, **cambio)
                if cambio.get("dias_sin_dato", 0) is None:
                    meta = json.loads((self.dir / "metadata.json").read_text())
                    del meta["dias_sin_dato"]
                    (self.dir / "metadata.json").write_text(json.dumps(meta))
                with self.assertRaises(pnd.PndNoDisponible):
                    pnd.inspeccionar_pnd(self.dir)
        escribir_metadata(self.dir, DESDE, HASTA, SIN_DATO, 3)
        meta = json.loads((self.dir / "metadata.json").read_text())
        for campo, valor in (("desde", "2026-13-01"), ("hasta", 20261105), ("desde", None)):
            with self.subTest(campo=campo, valor=valor):
                (self.dir / "metadata.json").write_text(json.dumps(meta | {campo: valor}))
                with self.assertRaises(pnd.PndNoDisponible):
                    pnd.inspeccionar_pnd(self.dir)
        (self.dir / "metadata.json").write_text("[1, 2]")
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.dir)

    def test_dia_sin_dato_sin_evidencia_se_rechaza(self):
        dia = str(SIN_DATO[0])
        error = evidencia(SIN_DATO[0])["consultas"][0] | {"http": 500, "status": "ERROR"}
        for entrada in (dia, {"fecha": dia}, {"fecha": dia, "status": "ZERO_RESULTS"}, {"fecha": dia, "consultas": [error]},
                        {"fecha": dia, "consultas": []}):
            with self.subTest(entrada=entrada):
                escribir_metadata(self.dir, DESDE, HASTA, [], 3, dias_sin_dato=[entrada])
                with self.assertRaises(pnd.PndNoDisponible):
                    pnd.inspeccionar_pnd(self.dir)

    def test_dia_sin_dato_repetido_o_en_un_extremo_se_rechaza(self):
        for lista in ([evidencia(SIN_DATO[0])] * 2, [evidencia(SIN_DATO[0]), evidencia(HASTA)]):
            with self.subTest(lista=lista):
                escribir_metadata(self.dir, DESDE, HASTA, [], 3, dias_sin_dato=lista)
                with self.assertRaises(pnd.PndNoDisponible):
                    pnd.inspeccionar_pnd(self.dir)

    def test_version_de_esquema_desconocida(self):
        escribir_metadata(self.dir, DESDE, HASTA, SIN_DATO, 3, version_esquema="2")
        with self.assertRaises(pnd.PndNoDisponible):
            pnd.inspeccionar_pnd(self.dir)

    def test_huella_cambia_con_metadata(self):
        antes = pnd.huella_pnd(self.dir)
        escribir_metadata(self.dir, DESDE, HASTA, SIN_DATO, 3, generado_utc="2026-11-21T05:30:00Z")
        self.assertNotEqual(antes, pnd.huella_pnd(self.dir))


class Consultas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_estadisticas_y_cobertura_con_dia_sin_dato(self):
        e = pnd.estadisticas_pnd("MONTERREY", DESDE, HASTA, self.dir).iloc[0]
        self.assertEqual((e["horas_con_dato"], e["horas_del_rango"]), (4 * 24, 5 * 24))
        self.assertEqual(e["cobertura_pct"], 80.0)
        self.assertEqual(e["horas_negativas"], 1)
        self.assertEqual(e["minimo"], -50.0)
        self.assertEqual((e["perdidas"], e["congestion"]), (12.0, 8.0))

    def test_serie_diaria_promedio_simple_y_sin_fila_para_el_hueco(self):
        df = pnd.serie_pnd("CENTRO ORIENTE", DESDE, HASTA, "diaria", self.dir)
        self.assertEqual(len(df), 4)  # el 2026-11-03 no tiene fila: no es cero
        self.assertNotIn(pd.Timestamp("2026-11-03"), set(df["periodo"]))
        self.assertTrue((df["pnd_promedio"] == 112.5).all())  # promedio de 101..124
        self.assertTrue((df["horas"] == 24).all())

    def test_mensual_ponderado_por_horas_validas(self):
        df = pnd.serie_pnd("MONTERREY", DESDE, HASTA, "mensual", self.dir)
        self.assertEqual(df["horas"].tolist(), [96])  # 4 días con dato; el día sin dato no aporta horas
        # promedio simple de las 96 horas (una de ellas -50), no promedio de promedios diarios
        esperado = round((3 * sum(200 + h for h in range(1, 25)) + sum(200 + h for h in range(1, 25)) - 203 - 50) / 96, 2)
        self.assertEqual(df["pnd_promedio"].iloc[0], esperado)
        marcado = v.marcar_periodos(df, DESDE, HASTA, "mensual")
        self.assertTrue(marcado["parcial"].iloc[0])

    def test_csv_sin_filas_inventadas(self):
        df = v.marcar_periodos(pnd.serie_pnd("MONTERREY", DESDE, HASTA, "horaria", self.dir), DESDE, HASTA, "horaria")
        tabla = x.tabla_pnd(df, "MONTERREY", "horaria")
        self.assertEqual(len(tabla), 96)
        self.assertNotIn(str(SIN_DATO[0]), set(tabla["fecha_operacion"]))
        self.assertFalse(tabla["pnd"].isna().any())

    def test_serie_horaria_hora_final(self):
        df = pnd.serie_pnd("VDM CENTRO", DESDE, DESDE, "horaria", self.dir)
        self.assertEqual(df["periodo"].iloc[0], pd.Timestamp("2026-11-01 00:00"))  # hora 1 = 00:00–01:00
        self.assertEqual(df["pnd_promedio"].iloc[0], 301.0)

    def test_rango_solo_con_dia_sin_dato(self):
        dia = SIN_DATO[0]
        self.assertEqual(pnd.estadisticas_pnd("MONTERREY", dia, dia, self.dir).iloc[0]["horas_con_dato"], 0)
        self.assertTrue(pnd.serie_pnd("MONTERREY", dia, dia, "diaria", self.dir).empty)

    def test_regiones_de_zonas(self):
        catalogo = pd.DataFrame({"region_control": ["ORIENTAL", "CENTRAL", "NORESTE", None],
                                 "zona_carga": ["CENTRO ORIENTE", "CENTRO ORIENTE", "MONTERREY", None]})
        self.assertEqual(pnd.regiones_de_zonas(catalogo),
                         {"CENTRAL": ["CENTRO ORIENTE"], "NORESTE": ["MONTERREY"], "ORIENTAL": ["CENTRO ORIENTE"]})


class Enlaces(unittest.TestCase):
    NODOS = ["01AAN-85"]
    LIMITES = {"desde": date(2026, 1, 1), "hasta": date(2026, 11, 20)}
    LIMITES_PND = {"desde": DESDE, "hasta": HASTA}

    def leer(self, **parametros):
        return enlaces.leer_enlace({k: [v] for k, v in parametros.items()}, self.NODOS, self.LIMITES,
                                   ZONAS, self.LIMITES_PND)

    def test_enlace_pnd_completo(self):
        estado, problemas, faltantes = self.leer(modalidad="pnd", zona="VDM CENTRO", desde="2026-11-01",
                                                 hasta="2026-11-05", resolucion="diaria")
        self.assertEqual(estado, {"modalidad": "pnd", "zona": "VDM CENTRO", "desde": DESDE, "hasta": HASTA,
                                  "resolucion": "diaria"})
        self.assertEqual((problemas, faltantes), ([], []))
        self.assertEqual(enlaces.construir_enlace(estado), {"modalidad": "pnd", "zona": "VDM CENTRO",
                                                           "desde": "2026-11-01", "hasta": "2026-11-05",
                                                           "resolucion": "diaria"})

    def test_fechas_se_validan_contra_el_paquete_pnd(self):
        _, problemas, _ = self.leer(modalidad="pnd", zona="MONTERREY", desde="2026-10-01", hasta="2026-11-05",
                                    resolucion="diaria")
        self.assertTrue(any("no está en el paquete público" in p for p in problemas))

    def test_zona_o_modalidad_inexistente(self):
        self.assertTrue(self.leer(modalidad="pnd", zona="ATLANTIDA")[1])
        self.assertTrue(self.leer(modalidad="pml", nodo="01AAN-85")[1])

    def test_publicacion_sin_pnd_avisa(self):
        _, problemas, _ = enlaces.leer_enlace({"modalidad": ["pnd"], "zona": ["MONTERREY"]}, self.NODOS, self.LIMITES)
        self.assertIn("PND", problemas[0])

    def test_enlace_pml_no_cambia(self):
        estado = {"vista": enlaces.VISTAS_URL["historico"], "nodo": "01AAN-85", "desde": date(2026, 11, 4),
                  "hasta": date(2026, 11, 4), "resolucion": "horaria", "modalidad": "pml", "zona": "MONTERREY"}
        self.assertEqual(enlaces.construir_enlace(estado), {"vista": "historico", "nodo": "01AAN-85",
                                                           "desde": "2026-11-04", "hasta": "2026-11-04",
                                                           "resolucion": "horaria"})


class Csv(unittest.TestCase):
    def test_tabla_y_nombre(self):
        df = pd.DataFrame({"periodo": pd.to_datetime(["2026-11-01", "2026-11-02"]), "pnd_promedio": [112.5, -1.25],
                           "energia": [100.0, -10.0], "perdidas": [6.0, 4.75], "congestion": [6.5, 4.0], "horas": [24, 24]})
        tabla = x.tabla_pnd(v.marcar_periodos(df, DESDE, date(2026, 11, 2), "diaria"), "CENTRO ORIENTE", "diaria")
        self.assertEqual(list(tabla.columns), ["fecha_operacion", "zona_carga", "pnd", "energia", "perdidas", "congestion"])
        leido = pd.read_csv(io.BytesIO(x.a_csv(tabla)))
        self.assertEqual(leido["pnd"].tolist(), [112.5, -1.25])
        self.assertEqual(x.nombre_archivo("pnd", ["CENTRO ORIENTE"], DESDE, date(2026, 11, 2), "diaria"),
                         "pnd_historico_CENTRO_ORIENTE_2026-11-01_2026-11-02_diaria.csv")


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class Interfaz(unittest.TestCase):
    """La app con el paquete PML real y el PND sintético (pnd.PND_DIR apunta a la carpeta temporal)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def abrir(self, carpeta=None, **parametros):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120)
        if not parametros:  # v0.8.0: sin enlace la app abre ENSEMBLE; estas pruebas son de la vista SOLO
            app.session_state["escena"] = "solo"
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        with mock.patch.object(pnd, "PND_DIR", carpeta or self.dir):
            app.run()
        self.assertFalse(app.exception, app.exception)
        return app

    def correr(self, app):
        with mock.patch.object(pnd, "PND_DIR", self.dir):
            app.run()
        self.assertFalse(app.exception, app.exception)
        return app

    def test_sin_pnd_la_app_es_la_de_pml(self):
        app = self.abrir(self.tmp / "no-existe")
        self.assertNotIn("modalidad", [r.key for r in app.radio])
        self.assertEqual(app.radio(key="vista").value, "1. PML histórico")

    def test_enlace_pnd_abre_la_zona(self):
        app = self.abrir(modalidad="pnd", zona="VDM CENTRO", desde="2026-11-01", hasta="2026-11-05", resolucion="diaria")
        self.assertEqual(app.radio(key="modalidad").value, "pnd")
        self.assertNotIn("vista", [r.key for r in app.radio])  # sin pestañas PML
        self.assertTrue(app.caption[0].value.startswith("Precio de zona de carga (PND) · Mercado del Día en Adelanto"))
        self.assertIn("Vdm Centro: precio de zona de carga (PND), 2026-11-01 a 2026-11-05", app.subheader[0].value)
        metricas = {m.label: m.value for m in app.metric}
        self.assertEqual(metricas["Promedio horario"], "312.50")
        self.assertIn("2026-11-03", " ".join(w.value for w in app.warning))
        self.assertEqual(dict(app.query_params), {"modalidad": "pnd", "zona": "VDM CENTRO", "desde": "2026-11-01",
                                                  "hasta": "2026-11-05", "resolucion": "diaria"})

    def test_cambio_de_modalidad_acota_fechas_y_conserva_pml(self):
        app = self.abrir()
        nodo = app.selectbox(key="nodo").value
        app.radio(key="vista").set_value("3. Componentes del PML")
        self.correr(app)
        app.radio(key="modalidad").set_value("pnd")
        self.correr(app)
        self.assertTrue(DESDE <= app.date_input(key="desde").value <= HASTA)
        self.assertEqual(app.query_params["modalidad"], "pnd")
        self.assertNotIn("vista", app.query_params)
        app.radio(key="modalidad").set_value("pml")
        self.correr(app)
        self.assertEqual(app.radio(key="vista").value, "3. Componentes del PML")
        self.assertEqual(app.selectbox(key="nodo").value, nodo)
        self.assertNotIn("modalidad", app.query_params)
        self.assertEqual(app.query_params["vista"], "componentes")
        self.assertTrue(app.caption[0].value.startswith("Precio Marginal Local · "))

    def test_dia_sin_dato_no_muestra_cifras(self):
        app = self.abrir(modalidad="pnd", zona="MONTERREY", desde="2026-11-03", hasta="2026-11-03", resolucion="diaria")
        self.assertEqual(len(app.metric), 0)
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertIn("Sin datos de PND", app.warning[0].value)
        self.assertIn("no equivale a precio cero", app.warning[0].value)
        self.assertIn("consulta verificada", app.warning[0].value)

    def test_rango_con_hueco_cobertura_y_aviso(self):
        app = self.abrir(modalidad="pnd", zona="MONTERREY", desde="2026-11-01", hasta="2026-11-05", resolucion="mensual")
        self.assertIn("80.0% (96 de 120 horas con dato)", " ".join(m.value for m in app.markdown))
        aviso = " ".join(w.value for w in app.warning)
        self.assertIn("2026-11-03 (consulta verificada 2026-11-20T12:18:26Z)", aviso)
        self.assertNotIn("permanente", aviso)
        self.assertEqual({m.label: m.value for m in app.metric}["Mínimo horario"], "-50.00")

    def test_metadata_pnd_malformada_no_tumba_pml(self):
        roto = armar_paquete(self.tmp / "roto")
        escribir_metadata(roto, DESDE, HASTA, SIN_DATO, 3, archivos={"zonas.parquet": {"filas": "x"}},
                          dias_sin_dato=[{"consultas": [{"http": 200}]}])
        app = self.abrir(roto)
        self.assertNotIn("modalidad", [r.key for r in app.radio])
        self.assertEqual(app.radio(key="vista").value, "1. PML histórico")
        self.assertGreater(len(app.metric), 0)

    def test_enlace_pnd_sin_paquete_avisa_y_no_muestra_cifras(self):
        app = self.abrir(self.tmp / "no-existe", modalidad="pnd", zona="MONTERREY")
        self.assertEqual(len(app.metric), 0)
        self.assertIn("PND", app.error[0].value)


@unittest.skipUnless(os.environ.get("PND_LABORATORIO"), "Define PND_LABORATORIO con un clon de power-market-lab")
class ExportadorReal(unittest.TestCase):
    """Integración con el exportador y el validador reales de power-market-lab, con su config/pnd_dias_sin_dato.json.

    PND_LABORATORIO=<clon en la rama pnd-descarga> python -m pytest tests/test_pnd.py -k ExportadorReal
    """

    def test_paquete_del_exportador_real_lo_acepta_la_app(self):
        lab = Path(os.environ["PND_LABORATORIO"])
        sys.path.insert(0, str(lab / "scripts"))
        import descargar_pnd as dl
        import exportar_pnd as ex
        import validar_pnd as va
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        origen = tmp / "parquet"
        origen.mkdir()
        inicio, fin, hueco = date(2026, 5, 6), date(2026, 5, 10), date(2026, 5, 8)
        fuente = armar_paquete(tmp / "fuente", desde=inicio, hasta=fin, sin_dato=[hueco])
        for archivo in (fuente / "hourly").glob("*.parquet"):
            shutil.copy(archivo, origen / f"pnd_mda_sin_{archivo.stem}.parquet")
        config = lab / "config" / "pnd_dias_sin_dato.json"
        self.assertEqual(json.loads(config.read_text(encoding="utf-8"))[0], ENTRADA_REAL)  # fixture = config real
        parches = [mock.patch.object(ex, "CARPETA_PARQUET", origen),
                   mock.patch.object(ex, "CARPETA_PUBLICA", tmp / "publico"),
                   mock.patch.object(ex, "ARCHIVO_CORREGIDOS", tmp / "corregidos.json"),
                   mock.patch.object(ex, "ARCHIVO_SIN_DATO", config), mock.patch.object(dl, "ARCHIVO_SIN_DATO", config),
                   mock.patch.object(ex, "INICIO", inicio), mock.patch.object(va, "INICIO", inicio)]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        ex.main()
        errores, _ = va.validar(tmp / "publico", referencia=set(ZONAS))
        self.assertEqual(errores, [])
        limites = pnd.inspeccionar_pnd(tmp / "publico")
        self.assertEqual((limites["desde"], limites["hasta"], limites["dias_sin_dato"]), (inicio, fin, [hueco]))
        e = pnd.estadisticas_pnd("MONTERREY", hueco, hueco, tmp / "publico").iloc[0]
        self.assertEqual(e["horas_con_dato"], 0)


if __name__ == "__main__":
    unittest.main()

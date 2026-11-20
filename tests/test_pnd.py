"""v0.7.0 · Precio de zona de carga (PND): contrato, consultas, enlaces, CSV e interfaz.

Usa un paquete PND sintético en una carpeta temporal (no es dato publicado ni se escribe en el repo).
Las pruebas de interfaz usan además el paquete PML real de data/ y se omiten si no está.
"""
from datetime import date, timedelta
import hashlib
import io
import json
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


def evidencia(dia):
    """Forma de una entrada de dias_sin_dato: el día y el resultado de la consulta real al servicio."""
    return {"fecha": str(dia), "consultado_utc": "2026-11-20T12:30:00Z", "http": 200, "status": "ZERO_RESULTS",
            "resumen": '{"status":"ZERO_RESULTS"}', "url": f"https://ws01.cenace.gob.mx:8082/SWPEND/SIM/SIN/MDA/{dia:%Y/%m/%d}/{dia:%Y/%m/%d}/JSON"}


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

    def test_dia_sin_dato_sin_evidencia_se_rechaza(self):
        for entrada in (str(SIN_DATO[0]), {"fecha": str(SIN_DATO[0])}, {"fecha": str(SIN_DATO[0]), "status": "ZERO_RESULTS"}):
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
        self.assertIn("2026-11-03 (consulta verificada 2026-11-20T12:30:00Z)", aviso)
        self.assertNotIn("permanente", aviso)
        self.assertEqual({m.label: m.value for m in app.metric}["Mínimo horario"], "-50.00")

    def test_enlace_pnd_sin_paquete_avisa_y_no_muestra_cifras(self):
        app = self.abrir(self.tmp / "no-existe", modalidad="pnd", zona="MONTERREY")
        self.assertEqual(len(app.metric), 0)
        self.assertIn("PND", app.error[0].value)


if __name__ == "__main__":
    unittest.main()

"""Pruebas sin datos ficticios ni escritura de Parquet.

La comparación numérica se omite hasta indicar PML_REFERENCE_GLOB con una
fuente horaria real autorizada. Todos los derivados de prueba son CTE en RAM.
"""
from datetime import date
import copy
import hashlib
import io
from types import SimpleNamespace
import glob
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vista1 as v


class Preparacion(unittest.TestCase):
    def test_paquete_ausente_bloquea(self):
        with tempfile.TemporaryDirectory() as vacio:
            with self.assertRaises(v.DatosNoDisponibles):
                v.inspeccionar_paquete(vacio)

    def test_rango_invertido(self):
        with self.assertRaises(ValueError):
            v._rango("2026-01-02", "2026-01-01")

    def test_limites_horarios_inclusivos(self):
        with patch.object(v, "metadata", return_value={"horario_desde": "2026-01-01", "horario_hasta": "2026-01-31"}):
            self.assertTrue(v.cobertura_horaria("2026-01-01", "2026-01-31"))
            self.assertFalse(v.cobertura_horaria("2025-12-31", "2026-01-31"))
            self.assertFalse(v.cobertura_horaria("2026-01-01", "2026-02-01"))


class ContratoV1(unittest.TestCase):
    def setUp(self):
        # Metadatos de prueba; no se guardan archivos ni se crean precios.
        self.m = {
            "version_esquema": "1", "generado_utc": "2026-10-26T05:00:12Z",
            "fuente": "CENACE SW-PML, MDA, SIN", "unidades": "MXN/MWh",
            "convencion_hora": "1-24 hora final", "horario_desde": "2026-10-26",
            "horario_hasta": "2026-10-26", "diario_desde": "2026-10-26",
            "diario_hasta": "2026-10-26", "nodos": 1,
            "archivos": {p: {"filas": 1, "sha256": "0" * 64} for p in
                         ("hourly/2026-10-26.parquet", "daily/2026-10.parquet", "nodes.parquet")},
        }

    def test_metadata_y_actualizacion_cdmx(self):
        self.assertEqual(v.validar_metadata(self.m), self.m)
        self.assertEqual(v.actualizado_cdmx(self.m['generado_utc']), '2026-10-25 23:00:12 CST')

    def test_rechaza_metadata_incompatible(self):
        for campo, valor in (("version_esquema", "2"), ("generado_utc", "2026-10-26T05:00:12"),
                             ("unidades", "USD/MWh"), ("diario_hasta", "2026-10-25")):
            with self.subTest(campo=campo):
                m = copy.deepcopy(self.m)
                m[campo] = valor
                with self.assertRaises(v.DatosNoDisponibles):
                    v.validar_metadata(m)
        m = copy.deepcopy(self.m)
        m['archivos']['../privado.parquet'] = m['archivos'].pop('nodes.parquet')
        with self.assertRaises(v.DatosNoDisponibles):
            v.validar_metadata(m)

    def test_rechaza_checksum_o_conteo_alterado(self):
        root = Path('/paquete-de-prueba')
        payload = b'Prueba de integridad, sin precios ni Parquet'
        def particiones(tipo, *args):
            return [str(root / n) for n in self.m['archivos'] if n.startswith(tipo + '/')]
        with patch.object(v, 'metadata', return_value=self.m), \
             patch.object(v, '_archivos', side_effect=particiones), \
             patch.object(Path, 'rglob', return_value=[root/n for n in self.m['archivos']]), \
             patch.object(Path, 'open', side_effect=lambda *a, **kw: io.BytesIO(payload)):
            with self.assertRaisesRegex(v.DatosNoDisponibles, 'SHA-256'):
                v.inspeccionar_paquete(root)
            for info in self.m['archivos'].values():
                info['sha256'] = hashlib.sha256(payload).hexdigest()
            footer = SimpleNamespace(metadata=SimpleNamespace(num_rows=2))
            with patch.object(v.pq, 'ParquetFile', return_value=footer):
                with self.assertRaisesRegex(v.DatosNoDisponibles, 'Conteo de filas'):
                    v.inspeccionar_paquete(root)


@unittest.skipUnless(os.environ.get("PML_REFERENCE_GLOB"), "Pendiente fuente horaria real autorizada")
class ReferenciaReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archivos = sorted(glob.glob(os.environ["PML_REFERENCE_GLOB"]))
        if not archivos:
            raise ValueError("La fuente horaria indicada no tiene archivos")
        cls.con = duckdb.connect(":memory:")
        cls.con.read_parquet(archivos).create_view("fuente")
        cls.desde, cls.hasta = cls.con.execute("SELECT MIN(fecha)::DATE, MAX(fecha)::DATE FROM fuente").fetchone()
        cls.nodos = [r[0] for r in cls.con.execute("""
            SELECT nodo FROM fuente GROUP BY nodo
            ORDER BY MIN(fecha) DESC, nodo LIMIT 1
        """).fetchall()]
        cls.nodos += [r[0] for r in cls.con.execute("""
            SELECT nodo FROM fuente GROUP BY nodo
            ORDER BY MIN(fecha), nodo LIMIT 2
        """).fetchall() if r[0] not in cls.nodos]
        if len(cls.nodos) != 3:
            raise ValueError("La referencia requiere tres nodos distintos")
        # Materializar solo las tres series reales en memoria; no escribir archivos.
        cls.con.execute("CREATE TEMP TABLE horas AS SELECT nodo,fecha,hora,pml FROM fuente WHERE nodo IN (SELECT unnest(?))", [cls.nodos])
        cls.con.execute(f"""CREATE TEMP VIEW diarios AS
            SELECT nodo,fecha,COUNT(*)::BIGINT AS horas_validas,SUM(pml) AS suma_pml,
                   SUM(pml*pml) AS suma_pml_cuadrado,MIN(pml) AS {v.MIN_DIARIO},MAX(pml) AS {v.MAX_DIARIO},
                   COUNT(*) FILTER (WHERE pml<0) AS horas_negativas
            FROM horas GROUP BY nodo,fecha""")

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def consulta_memoria(self, sql, parametros):
        # El primer parámetro es la lista de rutas; la sustituye una vista real en RAM.
        return self.con.execute(sql.replace("read_parquet(?)", self.tabla), parametros[1:]).df()

    def test_diario_equivale_a_horario_en_tres_nodos(self):
        for nodo in self.nodos:
            with self.subTest(nodo=nodo):
                with patch.object(v, "_archivos", return_value=[]), patch.object(v, "_consulta", side_effect=self.consulta_memoria):
                    self.tabla = "horas"
                    with patch.object(v, "cobertura_horaria", return_value=True):
                        # La consulta horaria antepone fin/inicio antes de las rutas.
                        def horaria(sql, parametros):
                            if "AS horas_del_rango" in sql:
                                return self.con.execute(sql.replace("read_parquet(?)", "horas"), parametros[:2]+parametros[3:]).df()
                            return self.consulta_memoria(sql, parametros)
                        with patch.object(v, "_consulta", side_effect=horaria):
                            original = v.estadisticas(nodo, self.desde, self.hasta)
                            series = {r:v.serie(nodo,self.desde,self.hasta,r) for r in ("horaria","diaria","mensual")}
                    self.tabla = "diarios"
                    derivado = v.estadisticas_diarias(nodo,self.desde,self.hasta)
                    columnas = [c for c in original.columns if c not in ("mediana","p10","p90")]
                    pd.testing.assert_frame_equal(original[columnas],derivado[columnas],check_dtype=False,atol=0.005,rtol=0)
                    self.assertTrue(derivado[["mediana","p10","p90"]].isna().all().all())
                    for resolucion in ("diaria","mensual"):
                        pd.testing.assert_frame_equal(series[resolucion],v.serie_diaria(nodo,self.desde,self.hasta,resolucion),check_dtype=False,atol=0.005,rtol=0)
                    with patch.object(v, "cobertura_horaria", return_value=False):
                        with self.assertRaises(v.DatosNoDisponibles):
                            v.serie(nodo,self.desde,self.hasta,"horaria")

    def test_interfaz_con_series_reales_en_memoria(self):
        from streamlit.testing.v1 import AppTest
        # Se sustituye solo el transporte del paquete pendiente, usando las
        # mismas observaciones reales de la prueba numérica, sin escribir datos.
        self.tabla = "diarios"
        nodo = self.nodos[0]
        with patch.object(v, '_archivos', return_value=[]), patch.object(v, '_consulta', side_effect=self.consulta_memoria):
            estadistica = v.estadisticas_diarias(nodo, self.desde, self.hasta)
            serie = v.serie_diaria(nodo, self.desde, self.hasta, 'diaria')
        limites = {'desde': self.desde, 'hasta': self.hasta,
                   'horario_desde': self.hasta, 'horario_hasta': self.hasta,
                   'generado_utc': '2026-10-26T05:00:12Z'}
        is_file_real = Path.is_file
        def existe(path):
            return True if path == v.DATA_DIR / 'metadata.json' else is_file_real(path)
        with patch.object(Path, 'is_file', existe), \
             patch.object(v, 'huella_paquete', return_value='prueba-ui-con-fuente-real'), \
             patch.object(v, 'inspeccionar_paquete', return_value=limites), \
             patch.object(v, 'catalogo', return_value=[nodo]), \
             patch.object(v, 'cobertura_horaria', return_value=False), \
             patch.object(v, 'estadisticas', return_value=estadistica), \
             patch.object(v, 'serie', return_value=serie):
            app = AppTest.from_file(str(Path(v.__file__).with_name('app.py'))).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.date_input[0].value, self.desde)
            self.assertEqual(app.date_input[1].value, self.hasta)
            self.assertEqual(app.metric[1].value, '—')
            self.assertTrue(any('2026-10-25 23:00:12 CST' in c.value for c in app.caption))


if __name__ == "__main__":
    unittest.main()

"""v0.8.8 · Pulido visual (Issue #31): línea limpia sin puntos permanentes, huecos sin unir y canvas más ancho.

- `tramos` parte la serie en periodos consecutivos: tras un faltante empieza otro tramo (la línea no lo cruza).
- En el spec real (AppTest con el paquete público) ninguna capa de puntos dibuja todos los periodos: solo los
  parciales (▼), los aislados entre faltantes o el punto del cursor (invisible hasta que se acerca).
- Con el hueco documentado de PND (2026-05-08 sin archivo) la serie diaria tiene dos tramos.
"""
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pnd
import vista1 as v

APP = str(Path(v.__file__).with_name("app.py"))
HAY_PML = (v.DATA_DIR / "metadata.json").is_file()
HAY_PND = (pnd.PND_DIR / "metadata.json").is_file()


def modulo_app():
    """Importa las funciones de app.py sin ejecutar la página (solo hasta las definiciones)."""
    import ast
    fuente = Path(APP).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    nodos = [n for n in arbol.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))
             and not (isinstance(n, ast.Assign) and "st." in ast.unparse(n.value))]
    espacio = {}
    exec(compile(ast.Module(body=[n for n in nodos if isinstance(n, (ast.Import, ast.ImportFrom))]
                            + [n for n in nodos if isinstance(n, ast.Assign) and ast.unparse(n).startswith("PASO_PERIODO")]
                            + [n for n in nodos if isinstance(n, ast.FunctionDef) and n.name == "tramos"],
                            type_ignores=[]), APP, "exec"), espacio)
    return espacio


def graficas(**parametros):
    """[(spec, {nombre: DataFrame})] de las gráficas de la escena abierta con esos parámetros de URL."""
    from streamlit.testing.v1 import AppTest
    import pyarrow as pa
    app = AppTest.from_file(APP, default_timeout=180)
    for clave, valor in parametros.items():
        app.query_params[clave] = valor
    app.run()
    assert not app.exception, app.exception
    salida = []
    for grafica in app.get("vega_lite_chart"):
        datos = {d.name: pa.ipc.open_stream(io.BytesIO(d.data.data)).read_pandas() for d in grafica.proto.datasets}
        salida.append((json.loads(grafica.proto.spec), datos))
    return salida


def capas(spec):
    return spec.get("layer", [spec])


def tipo(capa):
    marca = capa.get("mark", {})
    return marca if isinstance(marca, str) else marca.get("type")


class Tramos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tramos = staticmethod(modulo_app()["tramos"])

    def test_dias_consecutivos_un_tramo(self):
        tramo, aislado = self.tramos(pd.date_range("2026-11-01", periods=7, freq="D"), "diaria")
        self.assertEqual(tramo.nunique(), 1)
        self.assertFalse(aislado.any())

    def test_hueco_parte_la_linea(self):
        dias = pd.to_datetime(["2026-05-06", "2026-05-07", "2026-05-09", "2026-05-10"])
        tramo, aislado = self.tramos(dias, "diaria")
        self.assertEqual(tramo.tolist(), [0, 0, 1, 1])
        self.assertFalse(aislado.any())

    def test_periodo_aislado_entre_faltantes(self):
        dias = pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-04", "2026-05-06", "2026-05-07"])
        tramo, aislado = self.tramos(dias, "diaria")
        self.assertEqual(tramo.tolist(), [0, 0, 1, 2, 2])
        self.assertEqual(aislado.tolist(), [False, False, True, False, False])

    def test_horaria_y_mensual(self):
        horas = pd.to_datetime(["2026-11-01 00:00", "2026-11-01 01:00", "2026-11-01 03:00"])
        self.assertEqual(self.tramos(horas, "horaria")[0].tolist(), [0, 0, 1])
        meses = pd.to_datetime(["2025-12-01", "2026-01-01", "2026-03-01"])  # cambio de año sin hueco; febrero falta
        self.assertEqual(self.tramos(meses, "mensual")[0].tolist(), [0, 0, 1])

    def test_vacio(self):
        tramo, aislado = self.tramos(pd.Series([], dtype="datetime64[ns]"), "diaria")
        self.assertTrue(tramo.empty and aislado.empty)


@unittest.skipUnless(HAY_PML and HAY_PND, "Sin paquete público en data/ o pnd/")
class LineaLimpia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pml_hasta = date.fromisoformat(v.metadata()["diario_hasta"])

    def sin_puntos_permanentes(self, spec):
        """Cada capa de puntos está filtrada (parciales o aislados) o es el punto del cursor (opacidad condicional)."""
        puntos = [c for c in capas(spec) if tipo(c) == "point"]
        self.assertTrue(puntos, "debe existir al menos el punto del cursor")
        for capa in puntos:
            filtrada = any("filter" in t for t in capa.get("transform", []))
            cursor = "condition" in capa.get("encoding", {}).get("opacity", {})
            self.assertTrue(filtrada or cursor, capa)
        cursor = [c for c in puntos if "condition" in c.get("encoding", {}).get("opacity", {})]
        self.assertTrue(cursor and "tooltip" in cursor[0]["encoding"], "el recuadro sigue en el punto del cursor")
        for linea in (c for c in capas(spec) if tipo(c) == "line"):
            self.assertEqual(linea["encoding"].get("detail", {}).get("field"), "tramo")

    def test_pml_diaria_mes(self):
        g = graficas(vista="historico", nodo="01AAN-85", resolucion="diaria",
                     desde=str(self.pml_hasta - timedelta(days=30)), hasta=str(self.pml_hasta))
        self.sin_puntos_permanentes(g[0][0])

    def test_pml_mensual_y_horaria(self):
        for resolucion, dias in (("mensual", 364), ("horaria", 2)):
            with self.subTest(resolucion=resolucion):
                g = graficas(vista="historico", nodo="01AAN-85", resolucion=resolucion,
                             desde=str(self.pml_hasta - timedelta(days=dias)), hasta=str(self.pml_hasta))
                self.sin_puntos_permanentes(g[0][0])

    def test_spread_y_componentes(self):
        for vista in ("comparacion", "componentes"):
            with self.subTest(vista=vista):
                g = graficas(vista=vista, nodo="01AAN-85", nodo_a="01AAN-85", nodo_b="01AGU-230", resolucion="diaria",
                             desde=str(self.pml_hasta - timedelta(days=30)), hasta=str(self.pml_hasta))
                lineas = [s for s, _ in g if any(tipo(c) == "line" for c in capas(s))]
                self.assertTrue(lineas)
                for spec in lineas:
                    self.sin_puntos_permanentes(spec)

    @unittest.skipUnless((pnd.PND_DIR / "hourly" / "2026-05-07.parquet").is_file()
                         and not (pnd.PND_DIR / "hourly" / "2026-05-08.parquet").is_file(),
                         "El paquete PND ya no tiene el hueco del 2026-05-08")
    def test_pnd_hueco_no_se_une(self):
        """PND diaria 2026-05-01..05-15: el 08 no tiene archivo; la línea son dos tramos, sin fila inventada."""
        spec, datos = graficas(modalidad="pnd", zona="MONTERREY", resolucion="diaria",
                               desde="2026-05-01", hasta="2026-05-15")[0]
        self.sin_puntos_permanentes(spec)
        df = next(d for d in datos.values() if "tramo" in d.columns)
        self.assertEqual(len(df), 14)
        self.assertEqual(df["tramo"].nunique(), 2)
        self.assertFalse(df["pnd_promedio"].isna().any())


class Canvas(unittest.TestCase):
    def test_ancho_maximo_y_margenes(self):
        fuente = Path(APP).read_text(encoding="utf-8")
        self.assertIn(".block-container{max-width:1640px;padding-left:clamp(1rem,2.2vw,2rem)", fuente)


if __name__ == "__main__":
    unittest.main()

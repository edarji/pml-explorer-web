"""Catálogo geográfico de NodosP (v0.6.0): contrato, join sin pérdidas y filtros.

Dos grupos: (1) casos pequeños inventados para cada regla (duplicados, ausentes, «No Aplica»,
zona en dos regiones) y (2) el catálogo publicado en referencia/ contra el paquete real.
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalogo as cat
import vista1 as v


def fila(nodo, nombre, region, zona, kv=115.0, inegi="19", estado="NUEVO LEON"):
    return {"nodo": nodo, "nombre": nombre, "region_control": region, "zona_carga": zona,
            "tension_kv": kv, "estado_inegi": inegi, "estado": estado}


EJEMPLO = pd.DataFrame([
    fila("01AAA-85", "Alfa", "CENTRAL", "CENTRO ORIENTE"),
    fila("02BBB-85", "Beta", "ORIENTAL", "CENTRO ORIENTE"),  # misma zona en otra región (caso real)
    fila("02CCC-115", "Alfa", "ORIENTAL", "XALAPA"),          # nombre repetido con otra clave
    fila("09ZZZ-230", "Frontera", None, None, inegi=None, estado=None),  # internacional
])
MANIFIESTO = {"fuente": "prueba", "version_catalogo": "2026-10-23", "sha256_origen": "x", "filas": 4}


class Reglas(unittest.TestCase):
    def test_ejemplo_valido(self):
        cat.validar(EJEMPLO, MANIFIESTO)

    def test_clave_duplicada_se_rechaza(self):
        df = pd.concat([EJEMPLO, EJEMPLO.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(cat.CatalogoInvalido, "duplicadas"):
            cat.validar(df, MANIFIESTO | {"filas": 5})

    def test_clave_con_espacio_se_rechaza(self):
        df = EJEMPLO.copy()
        df.loc[0, "nodo"] = "01AAA-85 "
        with self.assertRaisesRegex(cat.CatalogoInvalido, "espacios"):
            cat.validar(df, MANIFIESTO)

    def test_region_sin_zona_se_rechaza(self):
        df = EJEMPLO.copy()
        df.loc[0, "zona_carga"] = None
        with self.assertRaisesRegex(cat.CatalogoInvalido, "región sin zona"):
            cat.validar(df, MANIFIESTO)

    def test_filas_distintas_al_manifiesto(self):
        with self.assertRaisesRegex(cat.CatalogoInvalido, "filas"):
            cat.validar(EJEMPLO, MANIFIESTO | {"filas": 3})

    def test_join_conserva_todos_los_nodos(self):
        """AC-03: un nodo con precios y sin fila en el catálogo no desaparece."""
        nodos = ["01AAA-85", "02BBB-85", "02CCC-115", "09ZZZ-230", "03NUE-115"]
        u = cat.unir(nodos, EJEMPLO)
        self.assertEqual(u["nodo"].tolist(), nodos)
        sin = u.loc[~u["clasificado"], "nodo"].tolist()
        self.assertEqual(sin, ["09ZZZ-230", "03NUE-115"])

    def test_catalogo_sin_precios_no_agrega_nodos(self):
        u = cat.unir(["01AAA-85"], EJEMPLO)
        self.assertEqual(u["nodo"].tolist(), ["01AAA-85"])

    def test_filtros(self):
        u = cat.unir(EJEMPLO["nodo"], EJEMPLO)
        self.assertEqual(cat.regiones(u), ["CENTRAL", "ORIENTAL"])
        self.assertEqual(cat.zonas(u, "ORIENTAL"), ["CENTRO ORIENTE", "XALAPA"])
        self.assertEqual(cat.filtrar(u, "ORIENTAL", "CENTRO ORIENTE"), ["02BBB-85"])
        self.assertEqual(cat.filtrar(u, None, "CENTRO ORIENTE"), ["01AAA-85", "02BBB-85"])
        self.assertEqual(len(cat.filtrar(u)), 4)  # «Todas» incluye los sin clasificación

    def test_etiqueta(self):
        nombres = {"01AAA-85": "Alfa"}
        self.assertEqual(cat.etiqueta("01AAA-85", nombres), "01AAA-85 · Alfa")
        self.assertEqual(cat.etiqueta("03NUE-115", nombres), "03NUE-115")

    def test_archivo_alterado_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(cat.REFERENCIA_DIR / cat.ARCHIVO, d)
            m = json.loads((cat.REFERENCIA_DIR / cat.MANIFIESTO).read_text(encoding="utf-8"))
            m["sha256_parquet"] = "0" * 64
            (Path(d) / cat.MANIFIESTO).write_text(json.dumps(m), encoding="utf-8")
            with self.assertRaisesRegex(cat.CatalogoInvalido, "SHA-256"):
                cat.cargar(d)

    def test_sin_catalogo_publicado(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(cat.CatalogoInvalido):
            cat.cargar(d)


@unittest.skipUnless((cat.REFERENCIA_DIR / cat.ARCHIVO).is_file(), "Sin catálogo en referencia/")
class CatalogoPublicado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.m = cat.cargar()

    def test_procedencia(self):
        """AC-01: fuente, versión y huella del Excel documentadas."""
        self.assertEqual(self.m["version_catalogo"], "2026-10-23")
        self.assertEqual(len(self.m["sha256_origen"]), 64)
        self.assertEqual(self.m["sistema"], "SIN")

    def test_nombres_sin_espacios_sobrantes(self):
        self.assertFalse(self.df["nombre"].str.contains("  ").any())
        self.assertTrue((self.df["nombre"] == self.df["nombre"].str.strip()).all())

    def test_sin_no_aplica_como_texto(self):
        for c in ("region_control", "zona_carga", "estado"):
            self.assertNotIn("No Aplica", set(self.df[c].dropna()))

    @unittest.skipUnless((v.DATA_DIR / "nodes.parquet").is_file(), "Sin paquete público en data/")
    def test_correspondencia_con_el_paquete(self):
        """AC-02: todas las claves con precios tienen fila; 7 internacionales sin región."""
        nodos = v.catalogo()
        u = cat.unir(nodos, self.df)
        self.assertEqual(len(u), len(nodos))
        self.assertTrue(u["nombre"].notna().all())
        self.assertEqual(sorted(u.loc[~u["clasificado"], "nodo"]), self.m["sin_region"])
        self.assertEqual(len(self.m["sin_region"]), 7)

    def test_region_coincide_con_prefijo_en_clasificados(self):
        """Comprobación cruzada, no regla de la app: la región sale del catálogo, no de la clave."""
        prefijo = {"01": "CENTRAL", "02": "ORIENTAL", "03": "OCCIDENTAL", "04": "NOROESTE",
                   "05": "NORTE", "06": "NORESTE", "08": "PENINSULAR"}
        c = self.df.dropna(subset=["region_control"])
        self.assertTrue((c["nodo"].str[:2].map(prefijo) == c["region_control"]).all())


if __name__ == "__main__":
    unittest.main()

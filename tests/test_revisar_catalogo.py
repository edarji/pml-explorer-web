"""v0.6.1: revisión automática del catálogo de NodosP (detección, bloqueos, propuesta).

Ninguna prueba sale a internet: la página de CENACE y los Excel se crean aquí, pequeños.
"""
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest

import openpyxl
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
import catalogo as cat  # noqa: E402
import catalogo_diferencias as dif  # noqa: E402
import preparar_catalogo as prep  # noqa: E402
import revisar_catalogo as rev  # noqa: E402

COLS = list(prep.ORIGEN)


def nodo(clave, nombre, region="ORIENTAL", zona="XALAPA", inegi="30", estado="VERACRUZ"):
    kv = clave.rsplit("-", 1)[1]
    return {"SISTEMA": "SIN", "CENTRO DE CONTROL REGIONAL": region, "ZONA DE CARGA": zona,
            "CLAVE": clave, "NOMBRE": nombre, "NIVEL DE TENSIÓN (kV)": kv,
            "CLAVE DE ENTIDAD FEDERATIVA (INEGI)": inegi, "ENTIDAD FEDERATIVA (INEGI)": estado}


BASE_NODOS = [nodo(f"02A{c}A-115", f"Nodo {c}") for c in "ABCDEFGHJKLMNPQRSTUVWXYZ"] + [
    nodo("02ZZB-230", "Otro", zona="VERACRUZ"),
    nodo("09LBR-230", "Frontera", region="No Aplica", zona="No Aplica", inegi="No Aplica",
         estado="No Aplica"),
]  # 26 nodos: el 2 % es 0.52, así que 1 reclasificado ya rebasa el umbral en las pruebas que lo buscan


def excel(ruta, filas, version="2026-11-20", control=()):
    """Excel con la forma del de CENACE: fila 1 de grupos, encabezado en la fila 2."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Catalogo de NodosP V{version.replace('-', '')}"
    ws.append(["Ubicación"] + [None] * (len(COLS) - 1))
    ws.append(COLS)
    for f in filas:
        ws.append([f[c] for c in COLS])
    cc = wb.create_sheet("Control de Cambios")
    cc.append(["Número de cambio", "Descripción del cambio", "Versión de cátalogo", "Responsable"])
    for i, (texto, fecha) in enumerate(control, 1):
        cc.append([i, texto, datetime.strptime(fecha, "%Y-%m-%d"), "USO"])
    wb.save(ruta)
    return Path(ruta)


class Entorno(unittest.TestCase):
    """Un repo falso (referencia/ aprobada + data/nodes.parquet) y una carpeta de trabajo vacía."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = Path(self._tmp.name)
        self.repo, self.base, self.xls = t / "repo", t / "trabajo", t / "xls"
        self.xls.mkdir()
        aprobado = excel(self.xls / "Catálogo (v2026-10-23).xlsx", BASE_NODOS, "2026-10-23")
        df, m, _, _ = prep.construir(aprobado)
        prep.escribir(df, m, self.repo / "referencia")
        (self.repo / "data").mkdir()
        df[["nodo"]].to_parquet(self.repo / "data" / "nodes.parquet")
        self.aprobado_xlsx = aprobado

    def tearDown(self):
        self._tmp.cleanup()

    def simular(self, filas, version="2026-11-20", control=()):
        ruta = excel(self.xls / f"Catálogo (v{version}).xlsx", filas, version, control)
        return rev.revisar(self.base, self.repo, simular=ruta, ahora=datetime(2026, 11, 23, 8, 15))


class Deteccion(Entorno):
    def test_mismo_archivo_sin_cambios(self):
        """AC-03: mismo Excel que el aprobado: nada en pendiente/."""
        r = rev.revisar(self.base, self.repo, simular=self.aprobado_xlsx)
        self.assertEqual(r["resultado"], "sin_cambios")
        self.assertFalse((self.base / "pendiente").exists())

    def test_archivo_distinto_mismo_contenido(self):
        """AC-02: otro Excel (otra versión) con los mismos datos."""
        r = self.simular(BASE_NODOS)
        self.assertEqual(r["resultado"], "archivo_distinto_mismo_contenido")
        self.assertFalse((self.base / "pendiente").exists())

    def test_alta_explicada_genera_propuesta(self):
        filas = BASE_NODOS + [nodo("02NUE-115", "Nueva")]
        r = self.simular(filas, control=[("Alta del nuevo NodoP 02NUE-115", "2026-11-20")])
        self.assertEqual(r["resultado"], "propuesta")
        self.assertEqual(r["altas"], 1)
        df, m = cat.cargar(self.base / "pendiente")  # la propuesta pasa la validación de la app
        self.assertIn("02NUE-115", set(df["nodo"]))
        self.assertEqual(m["version_catalogo"], "2026-11-20")
        informe = (self.base / "pendiente" / "informe.md").read_text(encoding="utf-8")
        self.assertIn("explicados por «Control de Cambios»", informe)
        self.assertIn("aún sin precios", informe)
        self.assertTrue((self.base / "PENDIENTE_DE_REVISION.txt").is_file())

    def test_alta_sin_explicar_es_advertencia(self):
        r = self.simular(BASE_NODOS + [nodo("02NUE-115", "Nueva")])
        self.assertEqual(r["resultado"], "propuesta")
        self.assertEqual(r["advertencias"], 1)

    def test_control_de_cambios_viejo_no_explica(self):
        """Solo cuentan las entradas posteriores a la versión aprobada."""
        r = self.simular(BASE_NODOS + [nodo("02NUE-115", "Nueva")],
                         control=[("Alta del nuevo NodoP 02NUE-115", "2026-09-23")])
        self.assertEqual(r["advertencias"], 1)


class Bloqueos(Entorno):
    def assertBloqueado(self, r, texto):
        self.assertEqual(r["resultado"], "bloqueado")
        self.assertTrue(any(texto in m for m in r["motivos"]), r["motivos"])
        self.assertFalse((self.base / "pendiente").exists())
        cat.cargar(self.repo / "referencia")  # el catálogo aprobado sigue intacto

    def test_nodo_con_precios_desaparece(self):
        self.assertBloqueado(self.simular(BASE_NODOS[1:]), "precios publicados")

    def test_internacional_recibe_region(self):
        filas = BASE_NODOS[:-1] + [nodo("09LBR-230", "Frontera", region="NORTE", zona="JUAREZ",
                                        inegi="08", estado="CHIHUAHUA")]
        self.assertBloqueado(self.simular(filas), "internacionales")

    def test_reclasificacion_masiva(self):
        filas = [dict(f) for f in BASE_NODOS]
        filas[0]["ZONA DE CARGA"] = "VERACRUZ"
        self.assertBloqueado(self.simular(filas), "más del 2%")

    def test_clave_duplicada(self):
        self.assertBloqueado(self.simular(BASE_NODOS + [BASE_NODOS[0]]), "duplicadas")

    def test_columna_faltante(self):
        filas = [{k: v for k, v in f.items()} for f in BASE_NODOS]
        ruta = self.xls / "Catálogo (v2026-11-20).xlsx"
        excel(ruta, filas, "2026-11-20")
        wb = openpyxl.load_workbook(ruta)
        wb.active.cell(row=2, column=COLS.index("ZONA DE CARGA") + 1, value="ZONA")
        wb.save(ruta)
        self.assertBloqueado(rev.revisar(self.base, self.repo, simular=ruta), "columnas esperadas")

    def test_hoja_y_archivo_con_versiones_distintas(self):
        ruta = excel(self.xls / "Catálogo (v2026-11-21).xlsx", BASE_NODOS, "2026-11-20")
        with self.assertRaisesRegex(cat.CatalogoInvalido, "La hoja dice"):
            rev.revisar(self.base, self.repo, simular=ruta)

    def test_pagina_de_error_guardada_como_excel(self):
        ruta = self.xls / "Catálogo (v2026-11-20).xlsx"
        ruta.write_text("<html>Error</html>")
        with self.assertRaisesRegex(cat.CatalogoInvalido, "Excel legible"):
            rev.revisar(self.base, self.repo, simular=ruta)


HTML = """<a href="/Docs/01_MECP/CatalogoNodosP/2026/Catálogo NodosP Sistema Eléctrico Nacional (v2026-10-23).xlsx">x</a>
<a href="/Docs/01_MECP/CatalogoNodosP/2026/Catálogo NodosP Sistema Eléctrico Nacional (v2026-09-23).xlsx">y</a>
<a href='/Docs/01_MECP/CatalogoNodosP/2027/Catálogo NodosP Sistema Eléctrico Nacional (v2027-01-15).xlsx'>z</a>"""


class Pagina(Entorno):
    def test_enlaces_mas_reciente_primero_y_cambio_de_anio(self):
        lista = rev.enlaces(HTML)
        self.assertEqual([v for v, _ in lista], ["2027-01-15", "2026-10-23", "2026-09-23"])
        self.assertTrue(lista[0][1].startswith("https://www.cenace.gob.mx/Docs/01_MECP/CatalogoNodosP/2027/"))
        self.assertNotIn(" ", lista[0][1])  # espacios y acentos codificados para curl

    def test_version_ya_aprobada_no_descarga(self):
        html = HTML.split("\n")[0]
        def no_bajar(*a):
            raise AssertionError("No debía descargar")
        r = rev.revisar(self.base, self.repo, obtener_pagina=lambda: html, bajar=no_bajar)
        self.assertEqual(r["resultado"], "sin_cambios")

    def test_version_nueva_descarga_y_propone(self):
        nuevo = excel(self.xls / "fuente.xlsx", BASE_NODOS + [nodo("02NUE-115", "Nueva")], "2027-01-15")
        def bajar(url, destino):
            Path(destino).write_bytes(nuevo.read_bytes())
            return Path(destino)
        r = rev.revisar(self.base, self.repo, obtener_pagina=lambda: HTML, bajar=bajar)
        self.assertEqual(r["resultado"], "propuesta")
        self.assertTrue((self.base / "originales" / "catalogo_v2027-01-15.xlsx").is_file())

    def test_pagina_sin_enlaces_es_error(self):
        with self.assertRaisesRegex(rev.ErrorRevision, "no trae enlaces"):
            rev.revisar(self.base, self.repo, obtener_pagina=lambda: "<html></html>")

    def test_reintentos_y_error_limpio(self):
        esperas = []
        with self.assertRaisesRegex(rev.ErrorRevision, "4 intentos"):
            rev.descargar("http://127.0.0.1:9/no-existe.xlsx", self.base / "x.xlsx",
                          dormir=esperas.append)
        self.assertEqual(esperas, list(rev.ESPERAS))
        self.assertFalse((self.base / "x.xlsx.parcial").exists())


class Estado(Entorno):
    def test_main_dos_veces_es_idempotente(self):
        """AC-14: la segunda corrida con el mismo archivo no vuelve a proponer."""
        ruta = excel(self.xls / "Catálogo (v2026-11-20).xlsx", BASE_NODOS + [nodo("02NUE-115", "Nueva")])
        def corrida():
            r = rev.revisar(self.base, self.repo, simular=ruta)
            est = rev.combinar_estado(rev.leer_estado(self.base), r)
            rev.escribir_json(self.base / "estado.json", est)
            return est
        primera = corrida()
        segunda = corrida()
        self.assertEqual(primera["resultado"], "propuesta")
        self.assertEqual(segunda["resultado"], "sin_cambios")
        self.assertEqual(segunda["ultimo_hallazgo"]["resultado"], "propuesta")  # no se oculta
        self.assertEqual(len(list((self.base / "originales").glob("*.xlsx"))), 1)

    def test_simulacion_no_escribe_estado(self):
        codigo = rev.main(["--base", str(self.base), "--repo", str(self.repo),
                           "--simular", str(self.aprobado_xlsx)])
        self.assertEqual(codigo, 0)
        self.assertFalse((self.base / "estado.json").exists())
        self.assertIn("sin_cambios", (self.base / "logs" / "catalogo.log").read_text(encoding="utf-8"))

    def test_original_no_se_sobrescribe(self):
        a = excel(self.xls / "a.xlsx", BASE_NODOS, "2026-11-20")
        b = excel(self.xls / "b.xlsx", BASE_NODOS + [nodo("02NUE-115", "Nueva")], "2026-11-20")
        d1, _ = rev.guardar_original(self.base, a, "2026-11-20")
        d2, _ = rev.guardar_original(self.base, b, "2026-11-20")
        self.assertNotEqual(d1, d2)
        self.assertEqual(rev.sha256(d1), rev.sha256(a))


class Diferencias(unittest.TestCase):
    def test_huella_ignora_orden(self):
        df, _, _, _ = prep.construir(excel(Path(tempfile.mkdtemp()) / "x (v2026-10-23).xlsx",
                                           BASE_NODOS, "2026-10-23"))
        self.assertEqual(dif.huella_contenido(df), dif.huella_contenido(df.iloc[::-1]))

    def test_claves_mencionadas(self):
        textos = ["Cambio de nomenclatura NodoP: Antes 03JTC-115 Ahora: 03JTD-115",
                  "Baja de los nodos 01PMX1115, 01PMX2115 y 06IND-115"]
        self.assertEqual(dif.claves_mencionadas(textos),
                         {"03JTC-115", "03JTD-115", "01PMX1115", "01PMX2115", "06IND-115"})

    def test_comparar_campos(self):
        a = pd.DataFrame([{"nodo": "01A-85", "nombre": "X", "region_control": "C", "zona_carga": "Z",
                           "tension_kv": 85.0, "estado_inegi": "09", "estado": "CDMX"}])
        b = a.assign(nombre="Y", zona_carga="W")
        d = dif.comparar(a, b)
        self.assertEqual(sorted(d["cambios"]["campo"]), ["nombre", "zona_carga"])

    @unittest.skipUnless((cat.REFERENCIA_DIR / cat.ARCHIVO).is_file(), "Sin catálogo publicado")
    def test_huella_del_catalogo_publicado_es_estable(self):
        df, _ = cat.cargar()
        self.assertEqual(len(dif.huella_contenido(df)), 64)


if __name__ == "__main__":
    unittest.main()

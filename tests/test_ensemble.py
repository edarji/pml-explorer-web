"""v0.8.0 · Consultas de ENSEMBLE: cada promedio del ranking es el mismo que la vista SOLO del elemento (AC-G06).

Con el paquete público real de data/ y pnd/ (se omiten si no están) y con un paquete PND de prueba.
"""
from datetime import date, timedelta
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ensemble as ens
import pnd
import vista1 as v
from test_pnd import DESDE, HASTA, SIN_DATO, ZONAS, armar_paquete


def etiqueta_rail(label):
    """v0.8.3 · Fila del rail «*clave* **precio**» → (clave, precio)."""
    m = re.fullmatch(r"\*(.+)\* \*\*(.+?)\*\*", label)
    return m.group(1).replace("\\", ""), m.group(2).split(" · ")[0]


def muestra(ranking, n=12):
    """Extremos, mitad y una muestra fija: el ranking completo tarda más sin aportar casos distintos."""
    elementos = list(ranking["elemento"])
    elegidos = elementos[:3] + elementos[-3:] + [elementos[len(elementos) // 2]]
    return elegidos + random.Random(19).sample(elementos, min(n, len(elementos)))


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class RankingPml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = v.metadata()
        cls.lim = {"desde": date.fromisoformat(m["diario_desde"]), "hasta": date.fromisoformat(m["diario_hasta"])}
        cls.horario_desde = date.fromisoformat(m["horario_desde"])

    def comparar(self, dia):
        ranking = ens.ranking_pml(dia)
        self.assertGreater(len(ranking), 0)
        self.assertTrue(ranking["promedio"].is_monotonic_decreasing)
        self.assertTrue((ranking["horas"] > 0).all())  # sin dato no entra al ranking (AC-G08)
        filas = ranking.set_index("elemento")
        for nodo in muestra(ranking):
            with self.subTest(dia=dia, nodo=nodo):
                e = v.estadisticas(nodo, dia, dia).iloc[0]
                self.assertEqual(filas.loc[nodo, "promedio"], e["promedio"])
                self.assertEqual(filas.loc[nodo, "horas"], e["horas_con_dato"])
                self.assertEqual(filas.loc[nodo, "minimo"], e["minimo"])
                self.assertEqual(filas.loc[nodo, "maximo"], e["maximo"])
                self.assertEqual(filas.loc[nodo, "horas_negativas"], e["horas_negativas"])

    def test_dia_en_ventana_horaria_igual_que_solo(self):  # AC-G06
        self.comparar(self.lim["hasta"])

    def test_dia_fuera_de_ventana_igual_que_solo(self):  # AC-G06, fórmula del diario
        self.comparar(self.horario_desde - timedelta(days=30))

    def test_dia_de_referencia_acotado_al_paquete(self):
        self.assertEqual(ens.dia_pml(date(2099, 1, 1), self.lim), self.lim["hasta"])
        self.assertEqual(ens.dia_pml(date(2000, 1, 1), self.lim), self.lim["desde"])

    def test_nodos_sin_dato_se_cuentan_aparte(self):  # AC-G08
        ranking = ens.ranking_pml(self.lim["hasta"])
        total = len(v.catalogo())
        r = ens.resumen(ranking, total)
        self.assertEqual(r["con_dato"] + r["sin_dato"], total)
        self.assertEqual(r["caro"]["promedio"], ranking["promedio"].max())
        self.assertEqual(r["barato"]["promedio"], ranking["promedio"].min())


@unittest.skipUnless((pnd.PND_DIR / "metadata.json").is_file(), "Sin paquete público en pnd/")
class RankingPndReal(unittest.TestCase):
    def test_igual_que_solo(self):  # AC-G06
        lim = pnd.inspeccionar_pnd()
        dia = ens.dia_pnd(lim["hasta"], lim, pnd.PND_DIR)
        ranking = ens.ranking_pnd(dia, pnd.PND_DIR)
        self.assertEqual(len(ranking), lim["zonas"])
        filas = ranking.set_index("elemento")
        for zona in muestra(ranking):
            with self.subTest(zona=zona):
                e = pnd.estadisticas_pnd(zona, dia, dia, pnd.PND_DIR).iloc[0]
                self.assertEqual(filas.loc[zona, "promedio"], e["promedio"])
                self.assertEqual(filas.loc[zona, "horas"], e["horas_con_dato"])

    def test_dia_sin_dato_usa_el_anterior(self):  # 2026-05-08 no tiene archivo (sin dato documentado)
        lim = pnd.inspeccionar_pnd()
        self.assertEqual(ens.dia_pnd(date(2026, 5, 8), lim, pnd.PND_DIR), date(2026, 5, 7))


class RankingPndPrueba(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")
        cls.lim = {"desde": DESDE, "hasta": HASTA}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_orden_y_valores(self):
        ranking = ens.ranking_pnd(DESDE, self.dir)
        self.assertEqual(list(ranking["elemento"]), list(reversed(ZONAS)))  # PND = 100*i + h
        mty = ranking.set_index("elemento").loc["MONTERREY"]
        self.assertEqual(mty["horas_negativas"], 1)
        self.assertEqual(mty["promedio"], pnd.estadisticas_pnd("MONTERREY", DESDE, DESDE, self.dir).iloc[0]["promedio"])

    def test_dia_sin_dato_no_es_cero(self):  # AC-G08
        self.assertEqual(ens.dia_pnd(SIN_DATO[0], self.lim, self.dir), SIN_DATO[0] - timedelta(days=1))
        self.assertIsNone(ens.dia_pnd(DESDE - timedelta(days=1), self.lim, self.dir))
        self.assertEqual(ens.dia_pnd(date(2099, 1, 1), self.lim, self.dir), HASTA)


if __name__ == "__main__":
    unittest.main()


APP = str(Path(v.__file__).with_name("app.py"))


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class EscenasApp(unittest.TestCase):
    """Recorridos ENSEMBLE ↔ SOLO con el paquete público real (AC-G01 a AC-G07)."""

    def abrir(self, **parametros):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120)
        for clave, valor in parametros.items():
            app.query_params[clave] = valor
        app.run()
        self.assertFalse(app.exception, app.exception)
        return app

    def boton(self, app, clave):
        return next(b for b in app.button if b.key == clave)

    def test_sin_enlace_abre_ensemble(self):  # AC-G01
        app = self.abrir()
        self.assertEqual(app.session_state["escena"], "ensemble")
        self.assertNotIn("Vista y filtros", [e.label for e in app.expander])
        self.assertNotIn("vista", [r.key for r in app.radio])
        self.assertEqual(set(app.query_params), {"desde", "hasta", "resolucion"})
        textos = " ".join(m.value for m in app.markdown)
        self.assertIn("PML · NodoP", textos)
        self.assertEqual(len(app.metric), 0)  # los indicadores del tablero no son los de SOLO

    def test_solo_fechas_abre_ensemble_con_esas_fechas(self):  # AC-G01
        hasta = v.metadata()["diario_hasta"]
        app = self.abrir(desde=hasta, hasta=hasta, resolucion="diaria")
        self.assertEqual(app.session_state["escena"], "ensemble")
        self.assertEqual(app.radio(key="resolucion").value, "diaria")
        self.assertEqual(dict(app.query_params), {"desde": hasta, "hasta": hasta, "resolucion": "diaria"})

    def test_enlace_con_nodo_abre_solo(self):  # AC-G02
        app = self.abrir(vista="historico", nodo="01AGU-230")
        self.assertEqual(app.session_state["escena"], "solo")
        self.assertEqual(app.radio(key="vista").value, "1. PML histórico")
        self.assertIn("01AGU-230", " ".join(m.value for m in app.markdown if "solista" in m.value))
        self.assertTrue(any(b.key == "volver" for b in app.button))

    def test_ranking_abre_solo_y_volver_conserva_filtros(self):  # AC-G04, AC-G05, AC-G06
        app = self.abrir()
        app.radio(key="resolucion").set_value("diaria").run()
        filtros = {k: app.query_params[k] for k in ("desde", "hasta", "resolucion")}
        boton = self.boton(app, "rk_pml_caros_0")
        nodo, valor = boton.label.split(" · ")[:2]
        boton.click().run()
        self.assertEqual(app.session_state["escena"], "solo")
        self.assertEqual(dict(app.query_params), {"vista": "historico", "nodo": nodo, **filtros})
        self.assertEqual(app.selectbox(key="nodo").value, nodo)
        self.assertEqual({m.label: m.value for m in app.metric}["Promedio horario"], valor)  # mismo valor que SOLO
        self.boton(app, "volver").click().run()
        self.assertEqual(app.session_state["escena"], "ensemble")
        self.assertEqual(dict(app.query_params), filtros)
        self.assertEqual(app.session_state["nodo"], nodo)  # última selección conservada

    def test_comparar_usa_al_solista_como_nodo_a(self):  # D3
        app = self.abrir()
        boton = self.boton(app, "rk_pml_baratos_0")
        nodo = boton.label.split(" · ")[0]
        boton.click().run()
        app.radio(key="vista").set_value("2. Comparar nodos (spread)").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="nodo_a").value, nodo)

    def test_panel_derecho_abre_solo(self):  # AC-G04 · v0.8.2: la búsqueda de la lista permanente
        app = self.abrir()
        app.segmented_control(key="nodo_tension").set_value("230 kV").run()
        app.selectbox(key="buscar_pml").set_value("01AGU-230").run()
        self.assertEqual(app.session_state["escena"], "solo")
        self.assertEqual(app.query_params["nodo"], "01AGU-230")

    def test_tension_inicial_400_con_catalogo_oficial(self):  # 2.ª iteración: filtro de tensión
        import catalogo as cat
        df, _ = cat.cargar()
        kv = dict(zip(df["nodo"], df["tension_kv"]))
        app = self.abrir(vista="historico", nodo="01AAN-85")
        self.assertEqual(app.segmented_control(key="nodo_tension").value, "400 kV")
        # v0.8.2 · La búsqueda de la lista permanente es aparte del selector del detalle: solo nodos de 400 kV según
        # el catálogo, y el nodo del detalle (01AAN-85, 85 kV) no cambia por filtrar la lista.
        opciones = app.selectbox(key="buscar_pml").options
        self.assertTrue(all(kv[o.split(" · ")[0]] == 400.0 for o in opciones))
        self.assertEqual(len(opciones), sum(1 for v in kv.values() if v == 400.0))
        filas = [b for b in app.button if b.key.startswith("wl_pml_")]
        self.assertTrue(0 < len(filas) <= 6)  # lista corta: no se dibujan miles de botones
        app.segmented_control(key="nodo_tension").set_value("Todas").run()
        self.assertEqual(app.selectbox(key="nodo").value, "01AAN-85")  # filtrar la lista no pierde el nodo

    def test_watchlist_abre_solo_con_el_mismo_precio(self):
        app = self.abrir()
        fila = next(b for b in app.button if b.key == "wl_pml_0")
        nodo, valor = etiqueta_rail(fila.label)
        fila.click().run()
        self.assertEqual(app.query_params["nodo"], nodo)
        self.assertEqual({m.label: m.value for m in app.metric}["Promedio horario"], valor)

    def test_fechas_invertidas_en_enlace_del_tablero(self):  # AC-G03: mismo aviso que en SOLO
        app = self.abrir(desde="2020-01-01", hasta="2020-01-02")
        self.assertIn("no está en el paquete público", app.error[0].value)
        self.assertEqual(len([m for m in app.markdown if "kpis" in m.value]), 0)


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class SolistaAlFrente(unittest.TestCase):
    """v0.8.1 · Una sola página: el detalle aparece arriba y el mismo ENSEMBLE sigue debajo (Issue #25, A1–A6)."""

    abrir = EscenasApp.abrir
    boton = EscenasApp.boton

    def secciones(self, app):
        return [m.value for m in app.markdown if "seccion-et" in m.value]

    def test_sin_seleccion_solo_mercado(self):  # A1
        app = self.abrir()
        self.assertNotIn("volver", [b.key for b in app.button])
        self.assertIn("buscar_pml", [s.key for s in app.selectbox])  # v0.8.2: la lista es permanente
        self.assertTrue(self.secciones(app))

    def test_enlace_con_nodo_muestra_detalle_y_mercado(self):  # A2, deep link
        app = self.abrir(vista="historico", nodo="01AGU-230")
        self.assertEqual(app.session_state["escena"], "solo")
        self.assertIn("Promedio horario", [m.label for m in app.metric])  # el detalle
        self.assertTrue(self.secciones(app))                               # y la banda debajo
        self.assertTrue(any(b.key.startswith("wl_pml_") for b in app.button))
        self.assertEqual(dict(app.query_params)["nodo"], "01AGU-230")      # la URL es la del detalle
        claves = [s.key for s in app.selectbox]
        self.assertEqual(claves.count("nodo"), 1)                          # sin claves repetidas
        self.assertIn("buscar_pml", claves)

    def test_cambiar_de_solista_conserva_filtros_y_mercado(self):  # A3
        app = self.abrir(vista="historico", nodo="01AGU-230")
        app.radio(key="resolucion").set_value("diaria").run()
        filtros = {k: app.query_params[k] for k in ("desde", "hasta", "resolucion")}
        boton = self.boton(app, "rk_pml_baratos_0")
        nodo, valor = boton.label.split(" · ")[:2]
        boton.click().run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual(dict(app.query_params), {"vista": "historico", "nodo": nodo, **filtros})
        self.assertEqual({m.label: m.value for m in app.metric}["Promedio horario"], valor)
        self.assertTrue(self.secciones(app))
        self.assertEqual(self.boton(app, "rk_pml_baratos_0").proto.type, "primary")  # el solista resaltado
        self.boton(app, "volver").click().run()
        self.assertEqual(app.session_state["escena"], "ensemble")
        self.assertEqual(dict(app.query_params), filtros)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(self.secciones(app))

    def test_busqueda_del_tablero_cambia_solo_el_protagonista(self):  # A3
        app = self.abrir(vista="componentes", nodo="01AAN-85")
        app.segmented_control(key="nodo_tension").set_value("230 kV").run()
        app.selectbox(key="buscar_pml").set_value("01AGU-230").run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual(app.query_params["nodo"], "01AGU-230")
        self.assertEqual(app.query_params["vista"], "historico")
        self.assertIsNone(app.selectbox(key="buscar_pml").value)  # la búsqueda vuelve a quedar vacía

    def test_zona_desde_detalle_pml_abre_detalle_pnd(self):  # A4
        app = self.abrir(vista="historico", nodo="01AAN-85")
        if not any(b.key.startswith("rk_pnd_caras") for b in app.button):
            self.skipTest("Sin PND publicado en data/")
        boton = self.boton(app, "rk_pnd_caras_0")
        boton.click().run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual(app.query_params["modalidad"], "pnd")
        etiquetas = [m.label for m in app.metric]
        self.assertIn("Horas con PND < 0", etiquetas)
        self.assertNotIn("Horas con PML < 0", etiquetas)  # PML y PND no se mezclan
        self.assertEqual(len(self.secciones(app)), 2)     # la banda sigue con sus dos secciones separadas

    def test_detalle_sin_datos_no_oculta_el_mercado(self):  # A6: los avisos del detalle siguen; el tablero también
        app = self.abrir(vista="historico", nodo="99XXX-999")
        self.assertTrue(app.error or app.warning)
        self.assertTrue(self.secciones(app))


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class TerminalPersistente(unittest.TestCase):
    """v0.8.2 · Barra superior con precio, rangos (1D/7D/Mes/YTD) y fechas; lista permanente a la derecha (Issue #27)."""

    abrir = EscenasApp.abrir

    def test_controles_una_sola_vez_en_ambas_escenas(self):  # sin widgets duplicados
        for parametros in ({}, {"vista": "historico", "nodo": "01AAN-85"}, {"vista": "comparacion"}):
            with self.subTest(parametros=parametros):
                app = self.abrir(**parametros)
                self.assertEqual([d.key for d in app.date_input], ["desde", "hasta"])
                self.assertEqual([r.key for r in app.radio].count("resolucion"), 1)
                rangos = [b.key for b in app.button if b.key.startswith("rango_")]
                self.assertEqual(rangos, [f"rango_{o}" for o in ("Último día", "Últimos 7 días", "Mes en curso",
                                                                   "Año en curso")])
                self.assertIn("buscar_pml", [s.key for s in app.selectbox])  # la lista siempre está

    def test_ytd_es_1_de_enero_al_ultimo_dia_y_enlace_reproducible(self):  # A4
        hasta = date.fromisoformat(v.metadata()["diario_hasta"])
        app = self.abrir(vista="historico", nodo="01AAN-85")
        app.button(key="rango_Año en curso").click().run()
        self.assertFalse(app.exception, app.exception)
        esperado = {"desde": str(max(hasta.replace(month=1, day=1),
                                     date.fromisoformat(v.metadata()["diario_desde"]))),
                    "hasta": str(hasta), "resolucion": "diaria"}  # YTD en horaria pasa a diaria
        self.assertEqual({k: app.query_params[k] for k in esperado}, esperado)
        self.assertEqual(app.button(key="rango_Año en curso").proto.type, "primary")
        enlace = self.abrir(**dict(app.query_params))  # el enlace abre el mismo análisis
        self.assertEqual({m.label: m.value for m in enlace.metric}, {m.label: m.value for m in app.metric})


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class RailIzquierdo(unittest.TestCase):
    """v0.8.3 · Rail izquierdo con «Nodos | Zonas» en el mismo panel, sincronizado con «Precio» de la cabecera (#29)."""

    abrir = EscenasApp.abrir

    def con_pnd(self, app):
        if "rail_modo" not in [s.key for s in app.segmented_control]:
            self.skipTest("Sin PND publicado en pnd/")

    def test_un_solo_selector_de_modalidad_y_rail_sin_claves_repetidas(self):
        for parametros in ({}, {"vista": "historico", "nodo": "01AAN-85"}, {"modalidad": "pnd", "zona": "MONTERREY"}):
            with self.subTest(parametros=parametros):
                app = self.abrir(**parametros)
                self.con_pnd(app)
                self.assertEqual([r.key for r in app.radio].count("modalidad"), 1)
                self.assertEqual([s.key for s in app.segmented_control].count("rail_modo"), 1)
                claves = [w.key for w in list(app.button) + list(app.selectbox) + list(app.segmented_control) if w.key]
                self.assertEqual(len(claves), len(set(claves)))

    def test_zonas_en_el_rail_cambia_la_cabecera_y_la_lista(self):
        app = self.abrir()
        self.con_pnd(app)
        self.assertEqual(app.segmented_control(key="rail_modo").value, "Nodos")
        app.segmented_control(key="rail_modo").set_value("Zonas").run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual(app.radio(key="modalidad").value, "pnd")
        botones = [b.key for b in app.button]
        self.assertTrue(any(k.startswith("wl_pnd_") for k in botones))
        self.assertFalse(any(k.startswith("wl_pml_") for k in botones))  # PML y PND no se mezclan
        self.assertIn("buscar_pnd", [s.key for s in app.selectbox])
        self.assertNotIn("nodo_tension", [s.key for s in app.segmented_control])
        app.segmented_control(key="rail_modo").set_value("Nodos").run()
        self.assertEqual(app.radio(key="modalidad").value, "pml")
        self.assertTrue(any(b.key.startswith("wl_pml_") for b in app.button))

    def test_cabecera_mueve_las_pestanas_del_rail(self):
        app = self.abrir()
        self.con_pnd(app)
        app.radio(key="modalidad").set_value("pnd").run()
        self.assertEqual(app.segmented_control(key="rail_modo").value, "Zonas")
        app.radio(key="modalidad").set_value("pml").run()
        self.assertEqual(app.segmented_control(key="rail_modo").value, "Nodos")

    def test_zonas_con_detalle_pml_abre_pnd_y_conserva_el_nodo(self):
        app = self.abrir(vista="historico", nodo="01AAN-85")
        self.con_pnd(app)
        app.segmented_control(key="rail_modo").set_value("Zonas").run()
        self.assertEqual(app.query_params["modalidad"], "pnd")
        self.assertIn("Horas con PND < 0", [m.label for m in app.metric])
        fila = next(b for b in app.button if b.key == "wl_pnd_0")
        zona, valor = etiqueta_rail(fila.label)
        fila.click().run()
        self.assertEqual(app.query_params["zona"].title(), zona)
        self.assertEqual({m.label: m.value for m in app.metric}["Promedio horario"], valor)  # mismo precio
        app.segmented_control(key="rail_modo").set_value("Nodos").run()
        self.assertEqual(app.query_params["nodo"], "01AAN-85")  # la selección PML se conserva

    def test_quitar_la_pestana_activa_no_cambia_la_modalidad(self):
        app = self.abrir()
        self.con_pnd(app)
        app.segmented_control(key="rail_modo").set_value(None).run()
        self.assertFalse(app.exception, app.exception)
        self.assertEqual(app.radio(key="modalidad").value, "pml")
        self.assertEqual(app.segmented_control(key="rail_modo").value, "Nodos")


@unittest.skipUnless((v.DATA_DIR / "metadata.json").is_file(), "Sin paquete público en data/")
class EnsembleConPndDePrueba(unittest.TestCase):
    """AC-G07: PML y PND en secciones separadas; sin PND publicado, el tablero es solo PML."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.dir = armar_paquete(cls.tmp / "pnd")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def abrir(self, carpeta):
        from unittest import mock
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP, default_timeout=120)
        with mock.patch.object(pnd, "PND_DIR", carpeta):
            app.run()
        self.assertFalse(app.exception, app.exception)
        return app

    def test_secciones_separadas(self):
        app = self.abrir(self.dir)
        secciones = [m.value for m in app.markdown if "seccion-et" in m.value]
        self.assertEqual(len(secciones), 2)
        self.assertIn("PML · NodoP", secciones[0])
        self.assertIn("PND · Zona de carga", secciones[1])
        self.assertIn(f"día {HASTA}", secciones[1])  # su propio día de referencia
        etiquetas = [b.label for b in app.button if b.key.startswith("rk_pnd_caras")]
        self.assertEqual(etiquetas[0], "Vdm Centro · 312.50")

    def test_sin_pnd_solo_pml(self):
        app = self.abrir(self.tmp / "no-existe")
        secciones = [m.value for m in app.markdown if "seccion-et" in m.value]
        self.assertEqual(len(secciones), 1)
        self.assertNotIn("modalidad", [r.key for r in app.radio])

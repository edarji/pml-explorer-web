"""Rangos rápidos (v0.4.1): aritmética de fechas pura, sin Streamlit ni datos."""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rangos import RANGOS_RAPIDOS, rango_rapido


def limites(desde, hasta):
    return {"desde": desde, "hasta": hasta}


class RangosRapidos(unittest.TestCase):
    L = limites(date(2023, 1, 1), date(2026, 11, 3))

    def test_ultimo_dia(self):
        self.assertEqual(rango_rapido("Último día", self.L), (date(2026, 11, 3), date(2026, 11, 3)))

    def test_ultimos_7_dias_son_inclusivos(self):
        inicio, fin = rango_rapido("Últimos 7 días", self.L)
        self.assertEqual((inicio, fin), (date(2026, 10, 28), date(2026, 11, 3)))
        self.assertEqual((fin - inicio).days + 1, 7)

    def test_mes_en_curso_es_parcial(self):
        self.assertEqual(rango_rapido("Mes en curso", self.L), (date(2026, 11, 1), date(2026, 11, 3)))

    def test_mes_en_curso_el_dia_1_es_un_solo_dia(self):
        L = limites(date(2023, 1, 1), date(2026, 12, 1))
        self.assertEqual(rango_rapido("Mes en curso", L), (date(2026, 12, 1), date(2026, 12, 1)))

    def test_7_dias_cruzan_fin_de_anio(self):
        L = limites(date(2023, 1, 1), date(2027, 1, 3))
        self.assertEqual(rango_rapido("Últimos 7 días", L)[0], date(2026, 12, 28))

    def test_7_dias_cruzan_29_de_febrero(self):
        L = limites(date(2023, 1, 1), date(2028, 3, 2))
        self.assertEqual(rango_rapido("Últimos 7 días", L)[0], date(2028, 2, 25))

    def test_recorta_si_el_paquete_empieza_despues(self):
        L = limites(date(2026, 11, 1), date(2026, 11, 3))
        self.assertEqual(rango_rapido("Últimos 7 días", L), (date(2026, 11, 1), date(2026, 11, 3)))
        L = limites(date(2026, 11, 2), date(2026, 11, 3))
        self.assertEqual(rango_rapido("Mes en curso", L), (date(2026, 11, 2), date(2026, 11, 3)))

    def test_nunca_sale_del_paquete(self):
        for opcion in RANGOS_RAPIDOS:
            inicio, fin = rango_rapido(opcion, self.L)
            self.assertTrue(self.L["desde"] <= inicio <= fin <= self.L["hasta"], opcion)

    def test_opcion_desconocida_falla(self):
        with self.assertRaises(ValueError):
            rango_rapido("Ayer", self.L)


if __name__ == "__main__":
    unittest.main()

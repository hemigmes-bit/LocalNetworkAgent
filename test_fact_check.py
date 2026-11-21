#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del verificador determinista de cifras (fact_check.py).

Cubre el fallo real: Emma lee una noticia y añade una cifra que no está en
la fuente. El verificador debe detectarla sin romper las cifras correctas.

Run with: python -m unittest test_fact_check
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import fact_check


CONTEXT = (
    "El paro se situo en el 8,5 % en 2025. "
    "El presupuesto del programa es de 1.200 millones de euros. "
    "La ayuda maxima por pyme es de 12.000 euros."
)


class TestSupportedClaims(unittest.TestCase):
    def test_same_percentage_is_kept(self):
        text = "El paro bajo al 8,5 % en 2025."
        result, hedges, dropped, flagged = fact_check.filter_text(text, CONTEXT)
        self.assertEqual(result, text)
        self.assertEqual((hedges, dropped, flagged), (0, 0, []))

    def test_thousands_format_is_normalized(self):
        text = "El presupuesto es de 1200 millones de euros."
        result, hedges, _, _ = fact_check.filter_text(text, CONTEXT)
        self.assertEqual(result, text)
        self.assertEqual(hedges, 0)

    def test_currency_without_separators(self):
        text = "La ayuda maxima es de 12000 euros."
        result, hedges, _, _ = fact_check.filter_text(text, CONTEXT)
        self.assertEqual(result, text)
        self.assertEqual(hedges, 0)

    def test_scale_is_not_confused_with_thousands(self):
        # 1.200 millones (1.200.000.000) no es 1.200.000.
        result, hedges, _, _ = fact_check.filter_text(
            "El presupuesto es de 1.200 millones.",
            "El presupuesto es de 1.200.000 euros.",
        )
        self.assertEqual(hedges, 1)
        self.assertNotIn("1.200 millones", result)

    def test_year_only_is_removed_without_losing_the_date(self):
        result, hedges, _, flagged = fact_check.filter_text(
            "La cumbre sera el 29 de noviembre de 2027.",
            "La cumbre se celebro el 29 de noviembre.",
        )
        self.assertEqual(result, "La cumbre sera el 29 de noviembre.")
        self.assertEqual(hedges, 0)
        self.assertEqual(flagged, ["2027"])

    def test_year_inside_sentence_keeps_the_rest(self):
        result, hedges, _, _ = fact_check.filter_text(
            "El ano 2027 fue clave.", "Sin cifras."
        )
        self.assertEqual(result, "El ano fue clave.")
        self.assertEqual(hedges, 0)


class TestUnsupportedClaims(unittest.TestCase):
    def test_wrong_percentage_is_replaced(self):
        result, hedges, dropped, flagged = fact_check.filter_text(
            "El paro bajo al 12,7 %.", CONTEXT
        )
        self.assertEqual(hedges, 1)
        self.assertEqual(dropped, 0)
        self.assertNotIn("12,7", result)
        self.assertIn("no aparece en la fuente", result)
        self.assertIn("12,7", flagged[0])

    def test_wrong_amount_is_replaced(self):
        result, hedges, _, _ = fact_check.filter_text(
            "La ayuda es de 18.000 euros.", CONTEXT
        )
        self.assertEqual(hedges, 1)
        self.assertNotIn("18.000", result)

    def test_only_one_hedge_per_turn(self):
        result, hedges, dropped, _ = fact_check.filter_text(
            "Crecimos un 45 %. Tambien un 60 %.", CONTEXT, hedges_left=1
        )
        self.assertEqual(hedges, 1)
        self.assertEqual(dropped, 1)

    def test_english_hedge(self):
        result, hedges, _, _ = fact_check.filter_text(
            "It grew 45 %.", CONTEXT, language="en"
        )
        self.assertEqual(hedges, 1)
        self.assertIn("does not appear in the source", result)


class TestSafeCases(unittest.TestCase):
    def test_empty_context_does_nothing(self):
        text = "Crecimos un 45 %."
        result, hedges, _, _ = fact_check.filter_text(text, "")
        self.assertEqual(result, text)
        self.assertEqual(hedges, 0)

    def test_incomplete_streaming_sentence_is_untouched(self):
        result, hedges, _, _ = fact_check.filter_text("Crecimos un 45", CONTEXT)
        self.assertEqual(result, "Crecimos un 45")
        self.assertEqual(hedges, 0)

    def test_question_numbers_are_allowed(self):
        result, hedges, _, _ = fact_check.filter_text(
            "En 2026 subio todo.", "Sin cifras.", allowed="que paso en 2026"
        )
        self.assertEqual(result, "En 2026 subio todo.")
        self.assertEqual(hedges, 0)

    def test_historical_years_are_general_knowledge(self):
        result, hedges, _, _ = fact_check.filter_text(
            "En 1989 cayo el Muro.", "Sin cifras."
        )
        self.assertEqual(result, "En 1989 cayo el Muro.")
        self.assertEqual(hedges, 0)

    def test_small_numbers_are_not_policed(self):
        result, hedges, _, _ = fact_check.filter_text(
            "Hay 3 puntos clave.", CONTEXT
        )
        self.assertEqual(result, "Hay 3 puntos clave.")
        self.assertEqual(hedges, 0)


if __name__ == "__main__":
    unittest.main()

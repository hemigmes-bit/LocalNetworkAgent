#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del detector de cambio de idioma de Emma.

Cubre el fallo real: "why don't you ... English voice?" guardaba espanol
como preferencia y Kokoro leia la respuesta inglesa con voz espanola.

Run with: python -m unittest test_language_routing
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import emma_state


class TestDetectLanguageRequest(unittest.TestCase):
    def test_complaint_about_english_voice_is_not_spanish(self):
        text = (
            "Get back... Yeah, you listen? Alright, why don't you just get "
            "back to your first voice? English voice."
        )
        self.assertEqual(emma_state.detect_language_request(text), "en")

    def test_question_with_negation_is_not_a_spanish_request(self):
        self.assertEqual(
            emma_state.detect_language_request("Why don't you just speak English?"),
            "en",
        )

    def test_negative_spanish_in_short_message(self):
        self.assertEqual(
            emma_state.detect_language_request("I don't want any Spanish"), "en"
        )
        self.assertEqual(
            emma_state.detect_language_request(
                "no quiero oir ni una palabra en espanol"
            ),
            "en",
        )

    def test_negative_english_in_short_message(self):
        self.assertEqual(
            emma_state.detect_language_request("don't speak English"), "es"
        )
        self.assertEqual(
            emma_state.detect_language_request("no me hables en ingles"), "es"
        )

    def test_plain_english_does_not_change_language(self):
        self.assertIsNone(
            emma_state.detect_language_request(
                "Anyway, could we have your old boys? I prefer the old one."
            )
        )
        self.assertIsNone(
            emma_state.detect_language_request("English is not difficult to learn")
        )

    def test_explicit_phrases(self):
        self.assertEqual(
            emma_state.detect_language_request("speak in English please"), "en"
        )
        self.assertEqual(
            emma_state.detect_language_request("hablemos en espanol"), "es"
        )
        self.assertEqual(
            emma_state.detect_language_request("back to your English voice"), "en"
        )
        self.assertEqual(
            emma_state.detect_language_request("vuelve a tu voz en espanol"), "es"
        )


if __name__ == "__main__":
    unittest.main()

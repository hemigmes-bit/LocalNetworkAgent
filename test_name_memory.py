#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas offline de la memoria de personas de Emma.

Cubren el fallo de la sesion 70 ("I'm not Henry, I'm Victor" borraba Henry y
no guardaba Victor) y el soporte de varias personas: Henry sigue siendo el
usuario principal y Victor se reconoce como hablante sin borrar a Henry.

Run with: python -m unittest test_name_memory
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import emma_memory
import emma_state


class TestNameDetection(unittest.TestCase):
    def test_positive_declaration(self):
        self.assertEqual(emma_state.detect_user_name("My name is Henry"), "Henry")
        self.assertEqual(emma_state.detect_user_name("I'm Henry"), "Henry")
        self.assertEqual(emma_state.detect_user_name("Me llamo Henry"), "Henry")
        self.assertEqual(
            emma_state.detect_user_name("It's Victor speaking"), "Victor"
        )
        self.assertEqual(
            emma_state.detect_user_name("Victor's my name"), "Victor"
        )
        self.assertEqual(emma_state.detect_user_name("I go by Victor"), "Victor")

    def test_replacement_after_correction(self):
        self.assertEqual(
            emma_state.detect_user_name("I'm not Henry, I'm Victor, his son."),
            "Victor",
        )
        self.assertEqual(
            emma_state.detect_user_name("No me llamo Henry, me llamo Víctor"),
            "Víctor",
        )

    def test_negated_name_is_not_a_declaration(self):
        self.assertIsNone(emma_state.detect_user_name("I'm not Henry"))
        self.assertIsNone(emma_state.detect_user_name("No me llamo Henry"))
        self.assertIsNone(emma_state.detect_user_name("Why you call me Henry?"))
        self.assertIsNone(emma_state.detect_user_name("Don't call me Alex"))

    def test_question_then_declaration(self):
        self.assertEqual(
            emma_state.detect_user_name("What's your name? My name is Henry"),
            "Henry",
        )
        self.assertEqual(emma_state.detect_user_name("No, I'm Henry"), "Henry")
        self.assertEqual(
            emma_state.detect_user_name("Don't call me Alex, call me Henry"),
            "Henry",
        )


class TestPersonMemory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "emma.db")
        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        emma_state.set_active_speaker(None)
        emma_state.set_user_name("Henry")

    def tearDown(self):
        emma_state.set_active_speaker(None)
        emma_memory._STORE = None
        self.tmpdir.cleanup()

    def _reload_store(self):
        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        emma_state.set_active_speaker(None)

    def test_primary_name_persists_across_restart(self):
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry"])

        self._reload_store()
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry"])

    def test_second_person_is_recognized_without_replacing_primary(self):
        status = emma_state.update_user_name_from_text(
            "I'm not Henry, I'm Victor, his son."
        )
        self.assertEqual(status["event"], "saved")
        self.assertEqual(status["name"], "Victor")
        self.assertFalse(status["is_primary"])
        self.assertEqual(status["primary"], "Henry")

        # Henry sigue siendo el principal; Victor es quien habla ahora.
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Victor")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry", "Victor"])

        # Tras reiniciar se conservan ambos; el hablante vuelve al principal.
        self._reload_store()
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry", "Victor"])

    def test_switch_back_to_primary(self):
        emma_state.update_user_name_from_text("I'm Victor")
        self.assertEqual(emma_state.get_active_speaker(), "Victor")

        status = emma_state.update_user_name_from_text("My name is Henry")
        self.assertEqual(status["event"], "saved")
        self.assertTrue(status["is_primary"])
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry", "Victor"])

    def test_first_declaration_becomes_primary(self):
        emma_state.clear_user_name()
        self.assertIsNone(emma_state.get_user_name())

        status = emma_state.update_user_name_from_text("My name is Henry")
        self.assertEqual(status["event"], "saved")
        self.assertTrue(status["is_primary"])
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")

    def test_primary_correction_without_replacement_clears_name(self):
        status = emma_state.update_user_name_from_text("I'm not Henry")
        self.assertEqual(status["event"], "cleared")
        self.assertEqual(status["previous"], "Henry")
        self.assertIsNone(emma_state.get_user_name())
        self.assertIsNone(emma_state.get_active_speaker())

        self._reload_store()
        self.assertIsNone(emma_state.get_user_name())

    def test_secondary_correction_does_not_clear_primary(self):
        emma_state.update_user_name_from_text("I'm Victor")
        status = emma_state.update_user_name_from_text("I'm not Victor")

        self.assertEqual(status["event"], "cleared")
        self.assertEqual(status["previous"], "Victor")
        self.assertEqual(status["primary"], "Henry")
        self.assertEqual(emma_state.get_user_name(), "Henry")
        self.assertEqual(emma_state.get_active_speaker(), "Henry")
        self.assertEqual(emma_state.get_known_user_names(), ["Henry"])

    def test_known_names_persist_in_sqlite(self):
        emma_memory.add_known_name("Victor")
        self._reload_store()
        self.assertEqual(emma_state.get_known_user_names(), ["Henry", "Victor"])
        self.assertEqual(emma_memory.get_known_names(), ["Henry", "Victor"])

    def test_known_name_from_stt_in_lowercase(self):
        self.assertEqual(emma_state.detect_user_name("my name is henry"), "Henry")
        emma_state.add_known_user_name("Victor")
        self.assertEqual(emma_state.detect_user_name("i'm victor"), "Victor")

    def test_prompt_block_mentions_primary_and_current_speaker(self):
        block = emma_state.build_name_memory_block()
        self.assertIn('usuario principal es "Henry"', block)

        emma_state.update_user_name_from_text("I'm Victor")
        block = emma_state.build_name_memory_block()
        self.assertIn('"Henry"', block)
        self.assertIn('"Victor"', block)
        self.assertIn('habla "Victor"', block)

    def test_startup_log_reports_primary_and_known(self):
        emma_state.update_user_name_from_text("I'm Victor")
        primary = emma_state.get_user_name() or "(no detectado)"
        known = emma_state.get_known_user_names()
        line = f"[MEM] Nombre del usuario: {primary}"
        if known:
            line += f" | reconocidos: {', '.join(known)}"
        self.assertEqual(
            line,
            "[MEM] Nombre del usuario: Henry | reconocidos: Henry, Victor",
        )


if __name__ == "__main__":
    unittest.main()

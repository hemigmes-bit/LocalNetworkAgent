#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas offline de la memoria del nombre de Emma.

Cubren el fallo de la sesion 70: "I'm not Henry, I'm Victor, his son."
borraba Henry y no guardaba Victor, asi que al reiniciar el log decia
"[MEM] Nombre del usuario: (no detectado)".

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


class TestNamePersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "emma.db")
        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        emma_memory.set_user_name("Henry")

    def tearDown(self):
        emma_memory._STORE = None
        self.tmpdir.cleanup()

    def test_correction_with_replacement_saves_new_name(self):
        status = emma_state.update_user_name_from_text(
            "I'm not Henry, I'm Victor, his son."
        )
        self.assertEqual(status["event"], "saved")
        self.assertEqual(status["name"], "Victor")
        self.assertEqual(emma_state.get_user_name(), "Victor")

        # El nombre sobrevive a un reinicio (nueva conexion a SQLite).
        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        self.assertEqual(emma_state.get_user_name(), "Victor")

    def test_declaration_persists_across_restart(self):
        emma_state.clear_user_name()
        status = emma_state.update_user_name_from_text("My name is Henry")
        self.assertEqual(status["event"], "saved")
        self.assertEqual(status["name"], "Henry")

        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        self.assertEqual(emma_state.get_user_name(), "Henry")

    def test_correction_without_replacement_clears_name(self):
        status = emma_state.update_user_name_from_text("I'm not Henry")
        self.assertEqual(status["event"], "cleared")
        self.assertEqual(status["previous"], "Henry")
        self.assertEqual(emma_state.get_user_name() or "", "")

        emma_memory._STORE = None
        emma_memory.get_store(self.db_path)
        self.assertEqual(emma_state.get_user_name() or "", "")

    def test_startup_log_reports_saved_name(self):
        emma_state.set_user_name("Henry")
        current = emma_state.get_user_name()
        self.assertEqual(current or "(no detectado)", "Henry")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del filtro de la palabra clave "Emma".

Extrae las funciones reales de voice_loop.py con AST, para no cargar STT/TTS.
Comprueba que las variantes tipicas del STT se aceptan y que las frases de la
television o de la familia se siguen ignorando.

Run with: python -m unittest test_wake_word
"""
import ast
import os
import re
import time
import unittest
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
VOICE_LOOP = os.path.join(ROOT, "python", "src", "main", "python", "voice_loop.py")

WANTED_ASSIGNS = {
    "_WAKE_RE",
    "_WAKE_NAMES",
    "_WAKE_EXTRA",
    "WAKE_WORD_ENABLED",
}
WANTED_FUNCTIONS = {
    "_edit_distance_le_one",
    "_is_wake_variant",
    "mentions_wake_word",
    "wake_word_allows",
}


def load_wake_block():
    with open(VOICE_LOOP, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & WANTED_ASSIGNS:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in WANTED_FUNCTIONS:
            nodes.append(node)

    found = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    missing = WANTED_FUNCTIONS - found
    if missing:
        raise RuntimeError(f"Faltan funciones en voice_loop.py: {sorted(missing)}")

    namespace = {"re": re, "time": time, "Optional": Optional, "AUDIO_CONFIG": {}}
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, "<wake-word>", "exec"), namespace)
    return namespace


class TestWakeWord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = load_wake_block()

    def mentions(self, text):
        return self.ns["mentions_wake_word"](text)

    def test_plain_name(self):
        self.assertTrue(self.mentions("Emma, cambia tu voz"))
        self.assertTrue(self.mentions("ema, hola"))

    def test_stt_variants_are_accepted(self):
        for text in (
            "enma, como estas",
            "emna, cuentame un cuento",
            "hemma, que hora es",
            "emmma, hablemos",
            "emma's voice is nice",
            "Emmy, listen",
        ):
            with self.subTest(text=text):
                self.assertTrue(self.mentions(text))

    def test_family_and_tv_are_ignored(self):
        for text in (
            "Mario, no te voy a dar el parque",
            "We'll be right back.",
            "y los otros numeros casi no se entienden",
            "Ves? Vamos, desastro. Por ahi.",
            "Let's go",
            "ella dijo que si",
            "la mesa esta puesta",
            "que hora es",
        ):
            with self.subTest(text=text):
                self.assertFalse(self.mentions(text))

    def test_variant_must_be_near_the_start(self):
        long_text = "bueno pues resulta que ayer por la tarde " * 3
        # La variante difusa solo se busca al principio, para no aceptar ruido.
        self.assertFalse(self.mentions(long_text + "enma"))
        # El nombre exacto se acepta en cualquier posicion.
        self.assertTrue(self.mentions(long_text + "Emma"))

    def test_followup_window_allows_without_name(self):
        allows = self.ns["wake_word_allows"]
        self.assertTrue(allows("y despues que paso", wake_until=time.time() + 30))
        self.assertFalse(allows("y despues que paso", wake_until=time.time() - 1))
        self.assertTrue(allows("Emma, y despues que paso", wake_until=time.time() - 1))
        self.assertTrue(allows("cualquier cosa", from_barge=True, wake_until=0.0))


if __name__ == "__main__":
    unittest.main()

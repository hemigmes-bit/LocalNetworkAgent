#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del permiso expreso para cambiar de voz.

Extrae el bloque real de voice_loop.py y lo ejecuta con un estado falso, sin
cargar STT/TTS/VAD. Comprueba que Emma pregunta, no cambia nada sin un "si"
y mantiene la voz cuando el usuario dice "no".

Run with: python -m unittest test_voice_permission
"""
import ast
import os
import re
import sys
import time
import unicodedata
import unittest
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "python", "src", "main", "python"))

import emma_state


class FakeState:
    """Estado en memoria: nunca toca emma_prefs.json."""

    def __init__(self):
        self.prefs = {
            "profile": "warm",
            "speed": 0.95,
            "voice_en": "af_heart",
            "voice_es": "ef_dora",
        }

    def detect_voice_request(self, text):
        return emma_state.detect_voice_request(text)

    def get_voice_prefs(self):
        return dict(self.prefs)

    def cycle_voice_profile(self, step=1, language=None):
        self.prefs["profile"] = "soft"
        return dict(self.prefs)

    def set_voice_profile(self, profile):
        self.prefs["profile"] = profile
        return dict(self.prefs)

    def reset_voice_prefs(self):
        self.prefs["profile"] = "warm"
        self.prefs["speed"] = 0.95
        return dict(self.prefs)

    def set_voice_speed(self, speed):
        self.prefs["speed"] = round(speed, 2)
        return dict(self.prefs)

    def voice_profile_label(self, profile, language="es"):
        return f"label-{profile}-{language}"


class DummyTurn:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def load_permission_block():
    """Ejecuta las funciones reales del bloque de permiso de voice_loop.py."""
    path = os.path.join(ROOT, "python", "src", "main", "python", "voice_loop.py")
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    wanted_assigns = {
        "_VOICE_CONFIRM_TTL_S",
        "_VOICE_YES",
        "_VOICE_NO",
        "_PENDING_VOICE_REQUEST",
    }
    wanted_functions = {
        "_norm_voice_phrase",
        "_voice_confirmation",
        "_build_voice_permission_question",
        "_apply_voice_request",
        "_speak_voice_turn",
        "handle_voice_request",
    }

    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & wanted_assigns:
                nodes.append(node)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in wanted_assigns:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            nodes.append(node)

    found = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    missing = wanted_functions - found
    if missing:
        raise RuntimeError(f"Faltan funciones en voice_loop.py: {sorted(missing)}")

    fake = FakeState()
    applied = []

    namespace = {
        "emma_state": fake,
        "EMMA_STATE_AVAILABLE": True,
        "LANGUAGE_PREFERENCE": None,
        "apply_voice_prefs": lambda prefs: applied.append(dict(prefs)) or prefs,
        "build_voice_reply": lambda action, profile, language, already=False: (
            f"REPLY:{action}:{profile.get('profile')}"
        ),
        "ui_emit": lambda *args, **kwargs: None,
        "speak_text": lambda text, language: (1.0, 2.0),
        "FULL_DUPLEX": True,
        "POST_TTS_DELAY_MS": 0,
        "turn_results": [],
        "TurnResult": DummyTurn,
        "add_turn_to_history": lambda *args, **kwargs: None,
        "Optional": Optional,
        "Dict": Dict,
        "Any": Any,
        "time": time,
        "re": re,
        "unicodedata": unicodedata,
    }
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, "<voice-permission>", "exec"), namespace)
    return namespace, fake, applied


class TestVoicePermission(unittest.TestCase):
    def setUp(self):
        self.ns, self.state, self.applied = load_permission_block()
        self.handle = self.ns["handle_voice_request"]
        self.confirm = self.ns["_voice_confirmation"]

    def test_request_only_asks_and_does_not_change(self):
        result = self.handle("cambia tu voz", 0.0, "es", "es")
        self.assertIsNotNone(result)
        self.assertIn("permiso expreso", result.assistant_spoken)
        self.assertEqual(self.state.prefs["profile"], "warm")
        self.assertIsNotNone(self.ns["_PENDING_VOICE_REQUEST"])

    def test_yes_applies_the_change(self):
        self.handle("cambia tu voz", 0.0, "es", "es")
        self.handle("si", 0.0, "es", "es")
        self.assertEqual(self.state.prefs["profile"], "soft")
        self.assertIsNone(self.ns["_PENDING_VOICE_REQUEST"])
        self.assertEqual(len(self.applied), 1)

    def test_no_keeps_the_voice(self):
        self.handle("no me gusta tu voz", 0.0, "es", "es")
        result = self.handle("no", 0.0, "es", "es")
        self.assertEqual(self.state.prefs["profile"], "warm")
        self.assertIn("mantengo mi voz", result.assistant_spoken.lower())

    def test_like_does_not_change_or_ask(self):
        self.handle("me gusta tu voz", 0.0, "es", "es")
        self.assertEqual(self.state.prefs["profile"], "warm")
        self.assertIsNone(self.ns["_PENDING_VOICE_REQUEST"])

    def test_prohibition_does_not_even_propose(self):
        result = self.handle("no quiero que cambies de voz", 0.0, "es", "es")
        self.assertIsNone(result)
        self.assertIsNone(self.ns["_PENDING_VOICE_REQUEST"])

    def test_expired_pending_does_not_apply(self):
        self.ns["_PENDING_VOICE_REQUEST"] = {
            "request": {"action": "next"},
            "created": time.time() - 120,
        }
        self.handle("si", 0.0, "es", "es")
        self.assertEqual(self.state.prefs["profile"], "warm")

    def test_confirmation_parser(self):
        self.assertTrue(self.confirm("yes of course I like it"))
        self.assertTrue(self.confirm("si, cambiala"))
        self.assertFalse(self.confirm("no, gracias"))
        self.assertFalse(self.confirm("claro que no"))
        self.assertFalse(self.confirm("no se"))
        self.assertIsNone(self.confirm("que hora es"))


if __name__ == "__main__":
    unittest.main()

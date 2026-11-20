#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for emma_patches.py

Run with: python -m unittest test_emma_patches
"""
import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import emma_patches


class TestVerifyCorrections(unittest.TestCase):
    def test_no_change_discarded(self):
        """Corrections that don't change the text are dropped."""
        user = "I have 25 years"
        corrections = [
            {"original": "I have 25 years", "corrected": "I have 25 years"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 0)
        self.assertIn("no cambia nada", [r for _, r in dropped])

    def test_not_in_turn_discarded(self):
        """Corrections where original doesn't appear in user text are dropped."""
        user = "I have 25 years"
        corrections = [
            {"original": "I have not had any sleep", "corrected": "I haven't had any sleep"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 0)
        self.assertIn("no aparece en el turno", [r for _, r in dropped])

    def test_invalid_format_discarded(self):
        """Non-dict items are dropped."""
        user = "I have 25 years"
        corrections = ["basura", None, 123]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 0)
        self.assertIn("formato invalido", [r for _, r in dropped])

    def test_valid_correction_kept(self):
        """Valid correction is kept."""
        user = "I have 25 years"
        corrections = [
            {"original": "I have 25 years", "corrected": "I am 25 years old"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["original"], "I have 25 years")
        self.assertEqual(kept[0]["corrected"], "I am 25 years old")

    def test_max_items_limit(self):
        """Respects max_items limit."""
        user = "I have 25 years old. I have not sleep."
        corrections = [
            {"original": "I have 25 years old", "corrected": "I am 25 years old"},
            {"original": "I have not sleep", "corrected": "I have not slept"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections, max_items=1)
        self.assertEqual(len(kept), 1)
        self.assertIn("limite de correcciones", [r for _, r in dropped])

    def test_empty_input(self):
        """Empty corrections returns empty lists."""
        kept, dropped = emma_patches.verify_corrections("whatever", [])
        self.assertEqual(kept, [])
        self.assertEqual(dropped, [])

    def test_duplicates_discarded(self):
        """Duplicate corrections are dropped."""
        user = "I have 25 years"
        corrections = [
            {"original": "I have 25 years", "corrected": "I am 25 years old"},
            {"original": "I have 25 years", "corrected": "I am 25 years old"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 1)
        self.assertIn("duplicada", [r for _, r in dropped])

    def test_too_short_original_discarded(self):
        """Original too short is dropped."""
        user = "I am good"
        corrections = [
            {"original": "I", "corrected": "am"},
        ]
        kept, dropped = emma_patches.verify_corrections(user, corrections)
        self.assertEqual(len(kept), 0)
        self.assertIn("original demasiado corto", [r for _, r in dropped])


class TestAnswerProfileQuestion(unittest.TestCase):
    def test_spanish_name(self):
        r = emma_patches.answer_profile_question("¿Cómo me llamo?", "Henry")
        self.assertEqual(r["spoken"], "Te llamas Henry.")
        self.assertEqual(r["language"], "es")

    def test_english_name(self):
        r = emma_patches.answer_profile_question("What's my name?", "Henry")
        self.assertEqual(r["spoken"], "Your name is Henry.")
        self.assertEqual(r["language"], "en")

    def test_no_name_asks(self):
        r = emma_patches.answer_profile_question("¿Cómo me llamo?", "")
        self.assertIsNotNone(r)
        self.assertIn("nombre", r["spoken"].lower())

    def test_not_triggered_by_presentation(self):
        r = emma_patches.answer_profile_question("My name is Henry", "Henry")
        self.assertIsNone(r)

    def test_not_triggered_by_asking_emmas_name(self):
        r = emma_patches.answer_profile_question("¿Cómo te llamas?", "Henry")
        self.assertIsNone(r)


class TestStripVocative(unittest.TestCase):
    def test_head_vocative(self):
        self.assertEqual(
            emma_patches.strip_vocative("Emma, busca el tiempo en Madrid"),
            "busca el tiempo en Madrid"
        )

    def test_greeting_vocative(self):
        self.assertEqual(
            emma_patches.strip_vocative("Oye Emma, ¿qué hora es?"),
            "¿qué hora es?"
        )

    def test_tail_vocative(self):
        self.assertEqual(
            emma_patches.strip_vocative("¿Qué hora es, Emma?"),
            "¿Qué hora es"
        )

    def test_multiple_vocatives(self):
        self.assertEqual(
            emma_patches.strip_vocative("Emma, Emma, dime las noticias"),
            "dime las noticias"
        )

    def test_only_vocative_returns_empty(self):
        self.assertEqual(emma_patches.strip_vocative("Emma"), "")
        self.assertEqual(emma_patches.strip_vocative("Emma!"), "")

    def test_no_vocative_unchanged(self):
        self.assertEqual(
            emma_patches.strip_vocative("busca el tiempo"),
            "busca el tiempo"
        )

    def test_content_emma_preserved(self):
        self.assertEqual(
            emma_patches.strip_vocative("qué sabes de Emma"),
            "qué sabes de Emma"
        )
        self.assertEqual(
            emma_patches.strip_vocative("dile a Emma que venga"),
            "dile a Emma que venga"
        )

    def test_emmanuel_preserved(self):
        self.assertEqual(
            emma_patches.strip_vocative("Emmanuel, busca el tiempo"),
            "Emmanuel, busca el tiempo"
        )


if __name__ == "__main__":
    unittest.main()
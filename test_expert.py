#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas del modulo expert (ask_expert tool).

Cubre:
- Saneado de entradas (PII, truncamiento)
- Cache SQLite
- Control de cuota diaria
- Fallback de proveedores
- Validacion de argumentos

Run with: python -m unittest test_expert
"""

import os
import sys
import unittest
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import expert


class TestSanitize(unittest.TestCase):
    def test_email_redaction(self):
        text = "Email me at user@example.com"
        result = expert.sanitize_text(text)
        self.assertIn("[email]", result)
        self.assertNotIn("user@example.com", result)

    def test_phone_redaction(self):
        text = "Call me at +1-555-123-4567"
        result = expert.sanitize_text(text)
        self.assertIn("[phone]", result)

    def test_url_redaction(self):
        text = "Visit https://example.com/page"
        result = expert.sanitize_text(text)
        self.assertIn("[url]", result)

    def test_truncation(self):
        long_text = "x" * 2000
        result = expert.sanitize_text(long_text, max_chars=100)
        self.assertLessEqual(len(result), 103)  # 100 + "..."


class TestNormalizeQuestion(unittest.TestCase):
    def test_case_insensitive(self):
        h1 = expert.normalize_question("What is Python?", "context")
        h2 = expert.normalize_question("what is python?", "context")
        self.assertEqual(h1, h2)

    def test_context_included(self):
        h1 = expert.normalize_question("What is Python?", "context A")
        h2 = expert.normalize_question("What is Python?", "context B")
        self.assertNotEqual(h1, h2)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        expert.DB_PATH = Path(self.temp_db.name)
        expert._init_expert_db()

    def tearDown(self):
        import gc
        gc.collect()
        time.sleep(0.1)
        Path(expert.DB_PATH).unlink(missing_ok=True)

    def test_cache_set_get(self):
        qh = expert.normalize_question("test question", "test context")
        expert.cache_answer(qh, "cached answer", "test_provider")
        cached = expert.get_cached_answer(qh)
        self.assertEqual(cached, "cached answer")

    def test_cache_miss(self):
        qh = expert.normalize_question("unknown", "context")
        cached = expert.get_cached_answer(qh)
        self.assertIsNone(cached)


class TestQuota(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        expert.DB_PATH = Path(self.temp_db.name)
        expert._init_expert_db()

    def tearDown(self):
        # Force garbage collection to close any open connections
        import gc
        gc.collect()
        time.sleep(0.1)
        Path(expert.DB_PATH).unlink(missing_ok=True)

    def test_quota_check(self):
        self.assertTrue(expert.check_daily_quota("test_provider", 10))
        expert.log_expert_call("test_provider", True, 100)
        self.assertTrue(expert.check_daily_quota("test_provider", 10))
        for _ in range(10):
            expert.log_expert_call("test_provider", True, 100)
        self.assertFalse(expert.check_daily_quota("test_provider", 10))

    def test_daily_usage(self):
        self.assertEqual(expert.get_daily_usage("test_provider"), 0)
        expert.log_expert_call("test_provider", True, 100)
        expert.log_expert_call("test_provider", True, 100)
        self.assertEqual(expert.get_daily_usage("test_provider"), 2)


class TestValidateAskExpert(unittest.TestCase):
    def test_valid_args(self):
        args, error = expert.validate_ask_expert({"question": "What is Python?"})
        self.assertEqual(error, "")
        self.assertEqual(args["question"], "What is Python?")
        self.assertEqual(args["language"], "es")

    def test_missing_question(self):
        args, error = expert.validate_ask_expert({"context": "some context"})
        self.assertIsNotNone(error)
        self.assertIn("question", error.lower())

    def test_language_validation(self):
        args, error = expert.validate_ask_expert({"question": "test", "language": "fr"})
        self.assertEqual(error, "")
        self.assertEqual(args["language"], "es")  # defaults to es


class TestExecuteAskExpert(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        expert.DB_PATH = Path(self.temp_db.name)
        expert._init_expert_db()

    def tearDown(self):
        import gc
        gc.collect()
        time.sleep(0.1)
        Path(expert.DB_PATH).unlink(missing_ok=True)

    def test_execute_requires_question(self):
        result = expert.execute_ask_expert({"context": "some context"})
        self.assertFalse(result["ok"])
        self.assertIn("question", result["error"].lower())


class TestSanitizeText(unittest.TestCase):
    def test_pii_removal(self):
        text = "Call me at 555-123-4567 or email user@domain.com or visit https://site.com"
        result = expert.sanitize_text(text)
        self.assertIn("[phone]", result)
        self.assertIn("[email]", result)
        self.assertIn("[url]", result)


if __name__ == "__main__":
    unittest.main()
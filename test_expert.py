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
from unittest import mock
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


# ---------------------------------------------------------------------------
# Cadena de reserva, cache y cuota, todo con mocks (sin red)
# ---------------------------------------------------------------------------

def _provider(name: str, limit: int = 10) -> dict:
    return {
        "name": name,
        "base_url": f"https://{name}.example/v1",
        "model": "test-model",
        "api_key": "test-key",
        "daily_limit": limit,
    }


class _ExpertTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self._db_file = handle.name
        self._original_db = expert.DB_PATH
        expert.DB_PATH = Path(self._db_file)
        expert._init_expert_db()
        expert._reset_cooldowns()
        self.config = {
            "providers": {
                "gemini": _provider("gemini"),
                "groq": _provider("groq"),
            },
            "fallback_order": ["gemini", "groq"],
            "timeout_seconds": 1,
            "max_tokens": 50,
            "temperature": 0.0,
        }

    def tearDown(self):
        expert.DB_PATH = self._original_db
        expert._reset_cooldowns()
        import gc
        gc.collect()
        try:
            Path(self._db_file).unlink(missing_ok=True)
        except OSError:
            pass


class TestFallbackChain(_ExpertTestBase):
    async def test_429_falls_through_to_next_provider(self):
        calls = []

        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            calls.append(provider["name"])
            if provider["name"] == "gemini":
                return {"error": "rate_limit", "kind": "rate"}
            return {"ok": True, "content": "respuesta de groq"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            result = await expert.ask_expert("pregunta 429 unica", "", "es")

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "groq")
        self.assertEqual(result["answer"], "respuesta de groq")
        self.assertEqual(calls, ["gemini", "groq"])

    async def test_all_providers_fail_returns_expert_unavailable(self):
        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            return {"error": "timeout", "kind": "timeout"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            result = await expert.ask_expert("pregunta que falla siempre", "", "es")

        self.assertFalse(result.get("ok"))
        self.assertEqual(result["error"], "expert_unavailable")

    async def test_auth_error_cools_down_provider(self):
        calls = []

        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            calls.append(provider["name"])
            if provider["name"] == "gemini":
                return {"error": "auth", "kind": "auth"}
            return {"ok": True, "content": "ok"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            await expert.ask_expert("primera pregunta auth", "", "es")
            await expert.ask_expert("segunda pregunta auth", "", "es")

        # Gemini solo se intenta la primera vez: la clave invalida entra en
        # enfriamiento y la segunda llamada va directa a Groq.
        self.assertEqual(calls.count("gemini"), 1)
        self.assertEqual(calls.count("groq"), 2)

    async def test_5xx_cools_down_provider(self):
        calls = []

        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            calls.append(provider["name"])
            if provider["name"] == "gemini":
                return {"error": "servidor_503", "kind": "server"}
            return {"ok": True, "content": "ok"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            await expert.ask_expert("primera pregunta saturada", "", "es")
            await expert.ask_expert("segunda pregunta saturada", "", "es")

        # Un 503 aparta al proveedor 90 s: no se paga el fallo cada turno.
        self.assertEqual(calls.count("gemini"), 1)
        self.assertEqual(calls.count("groq"), 2)

    async def test_empty_answer_is_not_success(self):
        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            if provider["name"] == "gemini":
                return {"error": "respuesta_vacia", "kind": "empty"}
            return {"ok": True, "content": "contenido valido"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            result = await expert.ask_expert("pregunta vacia unica", "", "es")

        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "contenido valido")


class TestCacheAndQuota(_ExpertTestBase):
    async def test_second_identical_question_uses_cache(self):
        calls = []

        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            calls.append(1)
            return {"ok": True, "content": "respuesta cacheable"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            first = await expert.ask_expert("Que es una hash map?", "", "es")
            second = await expert.ask_expert("que es una HASH MAP?", "", "es")

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(second["provider"], "cache")
        self.assertEqual(len(calls), 1)

    async def test_daily_limit_skips_provider(self):
        self.config["providers"]["gemini"]["daily_limit"] = 1
        for _ in range(1):
            expert.log_expert_call("gemini", True, 5)
        calls = []

        async def fake_call(provider, messages, timeout, max_tokens, temperature):
            calls.append(provider["name"])
            return {"ok": True, "content": "desde el segundo"}

        with mock.patch.object(expert, "load_providers", return_value=self.config), \
                mock.patch.object(expert, "_call_provider", side_effect=fake_call):
            result = await expert.ask_expert("pregunta con cuota agotada", "", "es")

        self.assertTrue(result["ok"])
        self.assertEqual(calls, ["groq"])


class TestProviderConfig(unittest.TestCase):
    def test_provider_without_key_is_skipped(self):
        import json as _json

        handle = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        _json.dump(
            {
                "providers": [
                    {"name": "sinclave", "base_url": "https://a.example/v1",
                     "model": "m", "api_key_env": "EMMA_TEST_NO_EXISTE",
                     "daily_limit": 5, "enabled": True},
                    {"name": "conclave", "base_url": "https://b.example/v1",
                     "model": "m2", "api_key_env": "EMMA_TEST_SI_EXISTE",
                     "daily_limit": 5, "enabled": True},
                ],
                "fallback_order": ["sinclave", "conclave"],
            },
            handle,
        )
        handle.close()

        with mock.patch.dict(os.environ, {"EMMA_TEST_SI_EXISTE": "abc"}, clear=False):
            with mock.patch.object(expert, "PROVIDERS_FILE", Path(handle.name)):
                config = expert.load_providers()

        Path(handle.name).unlink(missing_ok=True)
        self.assertEqual(list(config["providers"].keys()), ["conclave"])
        self.assertEqual(config["fallback_order"], ["conclave"])

    def test_missing_file_returns_empty_dict_not_list(self):
        missing = Path(tempfile.gettempdir()) / "no-existe-providers.json"
        with mock.patch.object(expert, "PROVIDERS_FILE", missing):
            config = expert.load_providers()
        self.assertEqual(config["providers"], {})
        self.assertEqual(config["fallback_order"], [])

    def test_per_provider_timeout_overrides_global(self):
        import json as _json

        handle = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        _json.dump(
            {
                "providers": [
                    {"name": "lento", "base_url": "https://a.example/v1",
                     "model": "m", "api_key_env": "EMMA_TEST_SI_EXISTE",
                     "daily_limit": 5, "timeout_seconds": 6, "enabled": True},
                    {"name": "normal", "base_url": "https://b.example/v1",
                     "model": "m2", "api_key_env": "EMMA_TEST_SI_EXISTE",
                     "daily_limit": 5, "enabled": True},
                ],
                "fallback_order": ["lento", "normal"],
                "timeout_seconds": 15,
            },
            handle,
        )
        handle.close()

        with mock.patch.dict(os.environ, {"EMMA_TEST_SI_EXISTE": "abc"}, clear=False):
            with mock.patch.object(expert, "PROVIDERS_FILE", Path(handle.name)):
                config = expert.load_providers()

        Path(handle.name).unlink(missing_ok=True)
        self.assertEqual(config["timeout_seconds"], 15)
        self.assertEqual(config["providers"]["lento"]["timeout_seconds"], 6)
        self.assertEqual(config["providers"]["normal"]["timeout_seconds"], 15)


if __name__ == "__main__":
    unittest.main()

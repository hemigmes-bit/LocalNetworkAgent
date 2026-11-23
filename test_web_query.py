#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas offline de consultas web: limpieza, seguimientos y relevancia.

Cubren los dos fallos vistos en la sesion 67: mezclar el tema anterior con uno
nuevo y buscar la frase literal de un seguimiento ("find it"), que devolvia
paginas sin relacion (Dustin Hoffman) o ninguna.

Run with: python -m unittest test_web_query
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import emma_tools
import web_tools


class TestCleanQuery(unittest.TestCase):
    def test_strips_filler_before_new_topic(self):
        text = (
            "Yeah, sure, I like that thing. Cool. Just tell me more about it. "
            "AI safety rules for chatbots that came out today. Come on, bring it on."
        )
        self.assertEqual(
            web_tools.clean_query(text),
            "AI safety rules for chatbots that came out today",
        )

    def test_backreference_without_topic_is_empty(self):
        text = (
            "No, no, no, no. Just find that specific news you told me about it. "
            "Okay, just find it."
        )
        self.assertEqual(web_tools.clean_query(text), "")

    def test_trailing_conjunction_removed(self):
        text = (
            "Alright, any other subject?  Instead housing and decrease and "
            "stuff like this"
        )
        self.assertEqual(web_tools.clean_query(text), "housing decrease")

    def test_keeps_real_question(self):
        text = "Who can access this digital literacy program?"
        self.assertEqual(
            web_tools.clean_query(text), "access this digital literacy program"
        )


class TestFollowup(unittest.TestCase):
    def setUp(self):
        emma_tools._LAST_WEB_QUERY = ""
        emma_tools._LAST_WEB_TIME = 0.0

    def tearDown(self):
        emma_tools._LAST_WEB_QUERY = ""
        emma_tools._LAST_WEB_TIME = 0.0

    def _remember(self, query):
        emma_tools._LAST_WEB_QUERY = query
        emma_tools._LAST_WEB_TIME = time.time()

    def test_new_topic_does_not_mix_with_previous(self):
        self._remember("decreto vivienda gobierno")
        text = (
            "Yeah, sure, I like that thing. Cool. Just tell me more about it. "
            "AI safety rules for chatbots that came out today. Come on, bring it on."
        )
        query = emma_tools.build_followup_query(text)
        self.assertEqual(query, "AI safety rules for chatbots that came out today")
        self.assertNotIn("vivienda", query)

    def test_backreference_reuses_last_topic(self):
        self._remember("AI safety rules for chatbots")
        text = (
            "No, no, no, no. Just find that specific news you told me about it. "
            "Okay, just find it."
        )
        self.assertTrue(emma_tools.needs_followup(text))
        self.assertEqual(
            emma_tools.build_followup_query(text), "AI safety rules for chatbots"
        )

    def test_expansion_appends_new_words(self):
        self._remember("digital literacy program adults")
        query = emma_tools.build_followup_query(
            "Who can access this digital literacy program?"
        )
        self.assertIn("digital literacy program adults", query)
        self.assertIn("access", query)

    def test_no_previous_query_returns_empty(self):
        self.assertEqual(emma_tools.build_followup_query("tell me more"), "")


class TestEmptySearch(unittest.TestCase):
    def test_blank_query_never_hits_network(self):
        result = emma_tools.execute_tool("web_search", {"query": "", "lang": "en"}, {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "empty_query")

    def test_meta_only_query_never_hits_network(self):
        result = emma_tools.execute_tool(
            "web_search", {"query": "find it", "lang": "en"}, {}
        )
        self.assertFalse(result["ok"])

    def test_no_result_message_is_explicit(self):
        text = emma_tools._compact_result(
            "web_search", {"ok": True, "result": []}, 1100
        )
        self.assertIn("Sin resultados", text)

    def test_empty_search_web_returns_empty(self):
        self.assertEqual(web_tools.search_web(""), [])


class TestNewsRouting(unittest.TestCase):
    def test_announcement_today_is_news(self):
        self.assertEqual(
            web_tools.detect_intent(
                "AI safety rules for chatbots that came out today"
            ),
            "news",
        )

    def test_plain_fact_is_not_news(self):
        self.assertNotEqual(
            web_tools.detect_intent("who was Alan Turing"), "news"
        )

    def test_news_flag_survives_validation(self):
        args, error = emma_tools.validate_arguments(
            "web_search", {"query": "elecciones generales", "news": True}
        )
        self.assertEqual(error, "")
        self.assertTrue(args.get("news"))

    def test_default_query_has_no_news_flag(self):
        args, error = emma_tools.validate_arguments(
            "web_search", {"query": "Alan Turing"}
        )
        self.assertEqual(error, "")
        self.assertNotIn("news", args)

    def test_news_query_drops_importance_filler(self):
        self.assertEqual(
            web_tools.news_query(
                "What is the most important news in Spain today?", "en"
            ),
            "Spain news today",
        )


class TestGatherRouting(unittest.TestCase):
    """Routing sin red: comprueba la consulta que llega al buscador."""

    CFG = {
        "search_engine": "searxng",
        "searxng_url": "http://localhost:8080",
        "max_results": 3,
        "page_chars": 0,
        "timeout_s": 4,
    }

    def setUp(self):
        emma_tools._LAST_WEB_QUERY = ""
        emma_tools._LAST_WEB_TIME = 0.0
        emma_tools._LAST_WEB_NEWS = False

    def tearDown(self):
        emma_tools._LAST_WEB_QUERY = ""
        emma_tools._LAST_WEB_TIME = 0.0
        emma_tools._LAST_WEB_NEWS = False

    def _run(self, text, lang="en"):
        from unittest import mock

        calls = []

        def fake_search(query, **kwargs):
            calls.append((query, kwargs.get("news")))
            return []

        with mock.patch.object(web_tools, "search_web", side_effect=fake_search), \
                mock.patch.object(emma_tools, "select_tool_calls", return_value=[]):
            emma_tools.gather_tool_context(
                text, lang=lang, model="qwen3.5:9b",
                config=self.CFG, timeout=5,
            )
        return calls

    def test_new_topic_does_not_mix_previous_query(self):
        emma_tools._LAST_WEB_QUERY = "decreto vivienda gobierno"
        emma_tools._LAST_WEB_TIME = time.time()
        calls = self._run(
            "Yeah, sure, I like that thing. Cool. Just tell me more about it. "
            "AI safety rules for chatbots that came out today. Come on, bring it on."
        )
        self.assertEqual(len(calls), 1)
        query, news = calls[0]
        self.assertNotIn("vivienda", query)
        self.assertIn("AI safety rules", query)
        self.assertTrue(news)

    def test_backreference_reuses_last_news_query(self):
        emma_tools._LAST_WEB_QUERY = "AI safety rules for chatbots"
        emma_tools._LAST_WEB_TIME = time.time()
        emma_tools._LAST_WEB_NEWS = True
        calls = self._run(
            "No, no, no, no. Just find that specific news you told me about it. "
            "Okay, just find it."
        )
        self.assertEqual(len(calls), 1)
        query, news = calls[0]
        self.assertEqual(query, "AI safety rules for chatbots")
        self.assertTrue(news)

    def test_no_search_without_topic(self):
        calls = self._run(
            "Alright, any other subject?  Instead housing and decrease and "
            "stuff like this"
        )
        self.assertEqual(calls, [])

    def test_news_intent_uses_news_query(self):
        calls = self._run("What is the most important news in Spain today?")
        self.assertEqual(len(calls), 1)
        query, news = calls[0]
        self.assertEqual(query, "Spain news today")
        self.assertTrue(news)


class TestRelevance(unittest.TestCase):
    def test_irrelevant_result_rejected(self):
        result = {
            "title": "Dustin Hoffman - Wikipedia",
            "snippet": "American actor",
            "url": "https://en.wikipedia.org/wiki/Dustin_Hoffman",
        }
        self.assertFalse(
            web_tools._is_relevant("AI safety rules for chatbots", result)
        )

    def test_topic_in_title_accepted(self):
        result = {
            "title": "OpenAI announces new AI safety rules for chatbots",
            "snippet": "The rules cover chatbots.",
            "url": "https://example.com/news",
        }
        self.assertTrue(
            web_tools._is_relevant("AI safety rules for chatbots", result)
        )

    def test_snippet_only_match_needs_two_keywords(self):
        # Con dos o mas palabras clave, el titular debe aportar una: una
        # portada que solo repite el tema en el snippet no vale.
        result = {
            "title": "Meta Platforms",
            "snippet": "AI safety rules for chatbots",
            "url": "https://en.wikipedia.org/wiki/Meta_Platforms",
        }
        self.assertFalse(
            web_tools._is_relevant("AI safety rules for chatbots", result)
        )


if __name__ == "__main__":
    unittest.main()

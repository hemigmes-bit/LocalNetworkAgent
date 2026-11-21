#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de las herramientas deterministas de Emma.

`calculate` y `current_date` no deben depender del modelo: un 9B falla en
aritmética y no conoce la fecha real. Estas pruebas fijan el contrato.

Run with: python -m unittest test_local_tools
"""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "python", "src", "main", "python"
))

import emma_tools


class TestDetectLocalIntent(unittest.TestCase):
    def test_percentage(self):
        intent = emma_tools.detect_local_intent("¿Cuánto es 15% de 200?")
        self.assertEqual(intent["name"], "calculate")
        self.assertEqual(intent["arguments"]["expression"], "(15/100)*200")

    def test_multiplication_with_x(self):
        intent = emma_tools.detect_local_intent("cuanto es 23 x 17")
        self.assertEqual(intent["arguments"]["expression"], "23*17")

    def test_power(self):
        intent = emma_tools.detect_local_intent("2 elevado a 10")
        self.assertEqual(intent["arguments"]["expression"], "2**10")

    def test_square_root(self):
        intent = emma_tools.detect_local_intent("raiz cuadrada de 144")
        self.assertEqual(intent["arguments"]["expression"], "sqrt(144)")

    def test_date_question(self):
        intent = emma_tools.detect_local_intent("¿Qué día es hoy?")
        self.assertEqual(intent["name"], "current_date")

    def test_time_question(self):
        intent = emma_tools.detect_local_intent("what time is it")
        self.assertEqual(intent["name"], "current_date")

    def test_web_question_is_not_math(self):
        self.assertIsNone(emma_tools.detect_local_intent("cuanto cuesta el kit digital"))

    def test_general_question_is_not_math(self):
        self.assertIsNone(emma_tools.detect_local_intent("what is the capital of France"))


class TestExecuteCalculate(unittest.TestCase):
    def test_sum(self):
        result = emma_tools.execute_tool("calculate", {"expression": "2+2"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["formatted"], "4")

    def test_decimal_comma(self):
        result = emma_tools.execute_tool("calculate", {"expression": "15,5 + 4,5"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["formatted"], "20")

    def test_division(self):
        result = emma_tools.execute_tool("calculate", {"expression": "10/4"})
        self.assertEqual(result["result"]["formatted"], "2.5")

    def test_rejects_code(self):
        result = emma_tools.execute_tool("calculate", {"expression": "__import__('os')"})
        self.assertFalse(result["ok"])

    def test_rejects_huge_exponent(self):
        result = emma_tools.execute_tool("calculate", {"expression": "2**100000"})
        self.assertFalse(result["ok"])

    def test_rejects_division_by_zero(self):
        result = emma_tools.execute_tool("calculate", {"expression": "1/0"})
        self.assertFalse(result["ok"])


class TestCurrentDate(unittest.TestCase):
    def test_returns_real_date(self):
        result = emma_tools.execute_tool("current_date", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["date"], datetime.now().strftime("%Y-%m-%d"))

    def test_requires_no_arguments(self):
        args, error = emma_tools.validate_arguments("current_date", {})
        self.assertEqual(args, {})
        self.assertEqual(error, "")

    def test_router_marks_date_as_tool_turn(self):
        self.assertTrue(emma_tools.needs_tools("¿qué día es hoy?"))
        self.assertTrue(emma_tools.should_consult("¿qué día es hoy?"))


if __name__ == "__main__":
    unittest.main()

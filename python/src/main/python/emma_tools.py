#!/usr/bin/env python3
"""Herramientas generales de Emma: web + memoria, con validacion de argumentos.

El objetivo es no inflar el contexto del modelo de 9B: en vez de inyectar
paginas enteras en el prompt, el modelo pide una herramienta, el codigo la
ejecuta y solo se devuelven resultados compactos (recortados).

Flujo:

  1. ``needs_tools(text)`` decide si el turno puede necesitar la web.
  2. ``select_tool_calls(...)`` hace una llamada corta a Ollama con las 5
     herramientas (``think: false``) y devuelve las llamadas pedidas.
  3. Cada llamada se valida; si los argumentos vienen mal, se reintenta UNA
     vez pidiendo al modelo que los corrija. Si sigue mal, se usa un respaldo
     seguro (por ejemplo, la propia frase del usuario como consulta).
  4. ``format_tool_messages(...)`` devuelve mensajes ``tool`` compactos para
     la llamada final, ya con el esquema JSON de respuesta de Emma.

Se puede probar por separado:

    python emma_tools.py --selftest
    python emma_tools.py "que ha pasado hoy en espana"
"""

from __future__ import annotations

import asyncio
import ast
import json
import math
import re
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import emma_memory
import web_tools

MAX_TOOL_RESULT_CHARS = 1100
MAX_TOOL_CALLS = 3
SELECTION_NUM_PREDICT = 180

# Ultima consulta web de la sesion: permite responder "cuentame mas" o
# "amplia la informacion" reutilizando el tema en vez de buscar la frase.
_LAST_WEB_QUERY = ""
_LAST_WEB_TIME = 0.0
_FOLLOWUP_TTL_S = 900.0

_EXPANSION_RE = re.compile(
    r"\b("
    r"mas detalles|m[aá]s detalles|ampl[ií]a|ampliar|profundiza|profundizar|"
    r"desarrolla|desarrollar|explica mejor|expl[ií]came m[aá]s|"
    r"cu[eé]ntame m[aá]s|dime m[aá]s|sigue explicando|m[aá]s informaci[oó]n|"
    r"tell me more|tell me something more|more details?|more information|"
    r"deepen|elaborate|go deeper|expand|explain further|what else|"
    r"source|fuente|newspaper|peri[oó]dico|diario|medio|de donde|"
    r"where from|which paper|which source|que fuente|que peri[oó]dico|"
    r"\bfrom\b"
    r")\b",
    re.IGNORECASE,
)

# Preguntas cortas que solo tienen sentido como seguimiento ("Where is it?").
_REFERENCE_RE = re.compile(
    r"^\s*(y|e|and|pero|but|then|entonces)?\s*"
    r"(donde|cuando|quien|quienes|como|que|cuanto|cuanta|por que|a que|"
    r"where|when|who|how|what|why|which|it|that|this|eso|esto|el|ella|ellos)\b",
    re.IGNORECASE,
)

# Palabras que no identifican un tema: aparecen en cualquier seguimiento.
_TOPIC_STOP = {
    "this", "that", "these", "those", "about", "more", "details", "detail",
    "tell", "please", "much", "very", "what", "where", "when", "which",
    "there", "their", "have", "with", "from", "just", "okay", "also",
    "could", "would", "should", "does", "doing", "give", "know", "like",
    "sobre", "este", "esta", "esto", "estos", "estas", "mas", "como",
    "donde", "cuando", "quien", "quienes", "para", "porque", "puede",
    "puedo", "tiene", "tienen", "hace", "otra", "otro", "algo", "algun",
    "dime", "cuentame", "explica", "informacion", "tema", "detalles",
}

_WORD_RE = re.compile(r"[0-9a-záéíóúüñ]{4,}", re.IGNORECASE)


def _significant_words(text: str) -> set:
    words = {word.lower() for word in _WORD_RE.findall(str(text or ""))}
    return words - _TOPIC_STOP


def _topic_overlap(text: str, query: str) -> int:
    return len(_significant_words(text) & _significant_words(query))


def needs_followup(text: str) -> bool:
    """True si el turno amplia la ultima consulta web (dentro de la ventana)."""
    if not _LAST_WEB_QUERY or (time.time() - _LAST_WEB_TIME) > _FOLLOWUP_TTL_S:
        return False
    raw = str(text or "")
    if _EXPANSION_RE.search(raw):
        return True
    # "Who can get access to this digital literacy program?" no dice "more",
    # pero comparte el tema con la consulta anterior.
    if _topic_overlap(raw, _LAST_WEB_QUERY) >= 2:
        return True
    # "Where is it?" / "y donde nacio": pregunta corta que remite al tema.
    # Se exige pronombre o conjuncion para no secuestrar una pregunta nueva
    # ("who can apply for a passport?") y responder del tema anterior.
    words = re.findall(r"\S+", raw)
    if len(words) <= 7 and _REFERENCE_RE.match(raw):
        pronoun = re.search(
            r"\b(it|that|this|they|them|those|eso|esto|estos|estas|ellos|ellas|"
            r"ella|aquel|aquella)\b",
            raw,
            re.IGNORECASE,
        )
        conjunction = re.match(
            r"^\s*(y|e|and|pero|but|then|entonces)\b", raw, re.IGNORECASE
        )
        if pronoun or conjunction or len(words) <= 4:
            return True
    return False


def should_consult(text: str) -> bool:
    """Decide si el turno debe pagar la llamada de herramientas."""
    return needs_tools(text) or needs_followup(text) or bool(detect_local_intent(text))


# ---------------------------------------------------------------------------
# Herramientas deterministas (sin modelo): calculo y fecha
# ---------------------------------------------------------------------------

_MATH_PREFIX_RE = re.compile(
    r"^\s*(?:emma[,\s]+)?"
    r"(?:cu[aá]nto(?:s)?\s+(?:es|son|vale|da)|qu[eé]\s+es|what(?:'s| is)|"
    r"how much is|calcula|calculate|resuelve|compute)\s+",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"\b(?:qu[eé]\s+d[ií]a\s+es\s+hoy|qu[eé]\s+fecha\s+es\s+hoy|"
    r"fecha\s+de\s+hoy|d[ií]a\s+de\s+hoy|"
    r"what\s+day\s+is\s+(?:it|today)|what(?:'s|\s+is)\s+the\s+date(?:\s+today)?|"
    r"what\s+date\s+is\s+(?:it|today)?)\b",
    re.IGNORECASE,
)

_TIME_RE = re.compile(
    r"\b(?:qu[eé]\s+hora\s+es|hora\s+actual|what\s+time\s+is\s+it|current\s+time)\b",
    re.IGNORECASE,
)

_DATE_CALC_RE = re.compile(
    r"\b(?:qu[eé]\s+d[ií]a\s+(?:es|ser[aá]|caer[aá]|cae)\s+"
    r"(?:el\s+)?\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+(?:de\s+)?\d{4})?|"
    r"what\s+(?:day\s+(?:is|will\s+be)|day\s+of\s+week\s+(?:is|will\s+be))\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}"
    r"(?:st|nd|rd|th)?(?:\s+\d{4})?(?:\s+day\s+of\s+week)?|"
    r"when\s+is\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}"
    r"(?:st|nd|rd|th)?(?:\s+\d{4})?|"
    r"next\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}"
    r"(?:st|nd|rd|th)?\s+(?:what\s+day|day\s+of\s+week|will\s+be|which\s+day|day\s+will\s+be)|"
    r"(?:when|what\s+day).+?(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\s+next\s+year|"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?\s+day\s+of\s+week|"
    r"qu[eé]\s+d[ií]a\s+(?:es|ser[aá]|caer[aá]|cae)\s+el\s+\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_MONTHS_ALL = {**_MONTHS_ES, **_MONTHS_EN}

_DATE_PATTERNS = [
    # YYYY-MM-DD
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    # D de MES de YYYY / D de MES YYYY
    re.compile(
        r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de\s+)?(\d{4})\b", re.IGNORECASE
    ),
    # MES D, YYYY / MES D YYYY
    re.compile(
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.IGNORECASE
    ),
    # "next MES D" or "MES D next year"
    re.compile(
        r"\bnext\s+([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.IGNORECASE
    ),
    # D MES (current/next year implied)
    re.compile(
        r"\b(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\b", re.IGNORECASE
    ),
    # "when is MES D next year" / "what day is MES D next year"
    re.compile(
        r"(?:when|what day).+?\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+next\s+year\b", re.IGNORECASE
    ),
    # "MES D day of week" / "day of week MES D"
    re.compile(
        r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+week\b", re.IGNORECASE
    ),
    # Spanish: "que dia cae el D de MES de YYYY"
    re.compile(
        r"qu[eé]\s+d[ií]a\s+(?:es|ser[aá]|caer[aá])\s+el\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE
    ),
]


def _extract_date_from_text(text: str) -> Optional[str]:
    """Extrae una fecha del texto y la normaliza a YYYY-MM-DD."""
    from datetime import datetime, date
    t = str(text or "").strip()
    if not t:
        return None

    # Intentar patrones explícitos con año
    for pattern in _DATE_PATTERNS[:4]:
        m = pattern.search(t)
        if m:
            groups = m.groups()
            if len(groups) == 3:
                if pattern == _DATE_PATTERNS[0]:  # YYYY-MM-DD
                    y, mth, d = groups
                elif pattern == _DATE_PATTERNS[1]:  # DD/MM/YYYY
                    d, mth, y = groups
                elif pattern == _DATE_PATTERNS[2]:  # D de MES de YYYY
                    d, mth_name, y = groups
                    mth = _MONTHS_ALL.get(mth_name.lower())
                    if not mth:
                        continue
                elif pattern == _DATE_PATTERNS[3]:  # MES D, YYYY
                    mth_name, d, y = groups
                    mth = _MONTHS_ALL.get(mth_name.lower())
                    if not mth:
                        continue
                try:
                    return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
                except (ValueError, TypeError):
                    continue

    # "next MES D" -> next occurrence of this month/day
    m = _DATE_PATTERNS[4].search(t)
    if m:
        mth_name, d = m.groups()
        mth = _MONTHS_ALL.get(mth_name.lower())
        if mth:
            now = datetime.now()
            y = now.year
            # "next MES" conventionally means the next occurrence.
            # If we are in or past that month this year, next is next year.
            if mth <= now.month:
                y += 1
            try:
                return f"{y:04d}-{int(mth):02d}-{int(d):02d}"
            except ValueError:
                pass

    # "D de MES" sin año -> asumir año actual o siguiente
    m = _DATE_PATTERNS[5].search(t)
    if m:
        d, mth_name = m.groups()
        mth = _MONTHS_ALL.get(mth_name.lower())
        if mth:
            now = datetime.now()
            y = now.year
            if mth < now.month or (mth == now.month and int(d) < now.day):
                y += 1
            try:
                return f"{y:04d}-{int(mth):02d}-{int(d):02d}"
            except ValueError:
                pass

    # "when is MES D next year" / "what day is MES D next year"
    m = _DATE_PATTERNS[6].search(t)
    if m:
        mth_name, d = m.groups()
        mth = _MONTHS_ALL.get(mth_name.lower())
        if mth:
            now = datetime.now()
            y = now.year + 1  # next year
            try:
                return f"{y:04d}-{int(mth):02d}-{int(d):02d}"
            except ValueError:
                pass

    # "MES D day of week" / "day of week MES D" (assume current or next year)
    m = _DATE_PATTERNS[7].search(t)
    if m:
        mth_name, d = m.groups()
        mth = _MONTHS_ALL.get(mth_name.lower())
        if mth:
            now = datetime.now()
            y = now.year
            if mth < now.month or (mth == now.month and int(d) < now.day):
                y += 1
            try:
                return f"{y:04d}-{int(mth):02d}-{int(d):02d}"
            except ValueError:
                pass

    # Spanish: "que dia cae el D de MES de YYYY"
    m = _DATE_PATTERNS[8].search(t)
    if m:
        d, mth_name, y = m.groups()
        mth = _MONTHS_ALL.get(mth_name.lower())
        if mth:
            try:
                return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
            except (ValueError, TypeError):
                pass

    return None


_MATH_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
}

def detect_local_intent(text: str) -> Optional[Dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return None
    if _DATE_RE.search(raw) or _TIME_RE.search(raw):
        return {"name": "current_date", "arguments": {}}
    if _DATE_CALC_RE.search(raw):
        date_str = _extract_date_from_text(raw)
        if date_str:
            return {"name": "date_calculate", "arguments": {"date": date_str}}
    expression = _math_expression(raw)
    if expression:
        return {"name": "calculate", "arguments": {"expression": expression}}
    return None

def _normalize_math(expression: str) -> str:
    """Convierte una expresion natural sencilla en aritmetica segura.

    Acepta ``23 x 17``, ``15% de 200``, ``2 elevado a 10`` o ``10 entre 4``.
    Devuelve ``""`` si quedan letras o no hay ninguna operacion.
    """
    expr = str(expression or "").strip().rstrip("?.!¡¿ ")
    expr = _MATH_PREFIX_RE.sub("", expr).strip()
    if not expr:
        return ""

    # 15% de 200 -> (15/100)*200
    expr = re.sub(
        r"(?<=\d)\s*%\s*de\s*(?=\d)", "/100*", expr, flags=re.IGNORECASE
    )
    # La coma es decimal salvo dentro de min()/max()/round(), donde separa
    # argumentos. En ese caso se deja tal cual.
    if not re.search(r"\b(?:sqrt|abs|round|min|max)\s*\(", expr, re.IGNORECASE):
        expr = re.sub(r"(?<=\d),(?=\d)", ".", expr)
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    expr = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", expr)

    replacements = (
        (r"\bdividido\s+(?:entre|por)\b", "/"),
        (r"\bdivided\s+by\b", "/"),
        (r"\belevado\s+(?:a|al)\b", "**"),
        (r"\bto\s+the\s+power\s+of\b", "**"),
        (r"\bpor\s+ciento\s+de\b", "/100*"),
        (r"\bpercent\s+of\b", "/100*"),
        (r"\bmultiplicado\s+por\b", "*"),
        (r"\bmultiplied\s+by\b", "*"),
        (r"\btimes\b", "*"),
        (r"\bpor\b", "*"),
        (r"\bm[aá]s\b", "+"),
        (r"\bplus\b", "+"),
        (r"\bmenos\b", "-"),
        (r"\bminus\b", "-"),
        (r"\bentre\b", "/"),
    )
    for pattern, replacement in replacements:
        expr = re.sub(pattern, replacement, expr, flags=re.IGNORECASE)

    expr = re.sub(r"\s+", "", expr)
    expr = expr.replace("%", "/100")

    # Se permiten las funciones conocidas; el resto de letras invalida.
    probe = re.sub(r"\b(?:sqrt|abs|round|min|max)\b", "", expr, flags=re.IGNORECASE)
    if not re.fullmatch(r"[0-9.+\-*/(),]+", probe):
        return ""
    if not re.search(r"[+\-*/]", expr) and not re.search(
        r"\b(?:sqrt|abs|round|min|max)\s*\(", expr, re.IGNORECASE
    ):
        return ""
    return expr


def _math_expression(text: str) -> str:
    """Extrae una expresion aritmetica de una pregunta, o ``""``."""
    candidate = str(text or "").strip().rstrip("?.!¡¿ ")
    candidate = candidate.lstrip("¿¡ ")
    candidate = re.sub(r"^(?:emma[,\s]+)", "", candidate, flags=re.IGNORECASE).strip()
    stripped = _MATH_PREFIX_RE.sub("", candidate).strip()
    stripped = re.sub(r"^(?:la\s+)", "", stripped, flags=re.IGNORECASE)

    root = re.fullmatch(
        r"(?:ra[ií]z\s+cuadrada\s+de|square\s+root\s+of)\s+"
        r"(\d+(?:[.,]\d+)?)",
        stripped,
        re.IGNORECASE,
    )
    if root:
        return f"sqrt({root.group(1).replace(',', '.')})"

    percent = re.fullmatch(
        r"(?:el\s+)?(\d+(?:[.,]\d+)?)\s*(?:%|por\s+ciento|percent)"
        r"\s+de\s+(\d+(?:[.,]\d+)?)",
        stripped,
        re.IGNORECASE,
    )
    if percent:
        left = percent.group(1).replace(",", ".")
        right = percent.group(2).replace(",", ".")
        return f"({left}/100)*{right}"

    return _normalize_math(candidate)


class _MathValidator(ast.NodeVisitor):
    """Solo permite aritmetica y las funciones de ``_MATH_FUNCS``."""

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, (int, float)):
            raise ValueError("constante no numerica")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id not in _MATH_FUNCS:
            raise ValueError(f"nombre no permitido: {node.id}")

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name) or node.func.id not in _MATH_FUNCS:
            raise ValueError("funcion no permitida")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            try:
                if abs(float(node.right.value)) > 100:
                    raise ValueError("exponente demasiado grande")
            except (TypeError, ValueError):
                raise ValueError("exponente invalido")
        self.generic_visit(node)


def _safe_eval(expression: str) -> float:
    if len(expression) > 200:
        raise ValueError("expresion demasiado larga")
    tree = ast.parse(expression, mode="eval")
    _MathValidator().visit(tree)
    value = eval(  # noqa: S307 - AST validado y sin builtins
        compile(tree, "<calculate>", "eval"),
        {"__builtins__": {}},
        dict(_MATH_FUNCS),
    )
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("resultado no finito")
    return number


def _format_result(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def detect_local_intent(text: str) -> Optional[Dict[str, Any]]:
    """Herramientas que no necesitan al modelo: calculo, fecha/hora y calculo de fechas."""
    raw = str(text or "").strip()
    if not raw:
        return None
    if _DATE_RE.search(raw) or _TIME_RE.search(raw):
        return {"name": "current_date", "arguments": {}}
    if _DATE_CALC_RE.search(raw):
        # Extraer la fecha de la pregunta
        date_str = _extract_date_from_text(raw)
        if date_str:
            return {"name": "date_calculate", "arguments": {"date": date_str}}
    expression = _math_expression(raw)
    if expression:
        return {"name": "calculate", "arguments": {"expression": expression}}
    return None


# ---------------------------------------------------------------------------
# Definicion de herramientas
# ---------------------------------------------------------------------------
# Herramientas que el MODEL puede llamar (tool calling real).
# Solo las que necesitan razonamiento: busqueda web, memoria, perfil.
MODEL_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca en la web. Usala para noticias, datos actuales o cualquier tema externo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Consulta breve."},
                    "lang": {"type": "string", "enum": ["es", "en"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Lee una pagina web concreta por su URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL http(s)."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Perfil del alumno: nivel, objetivos e intereses.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_due_reviews",
            "description": "Repasos de hoy (errores y vocabulario).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "1-10."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_sessions",
            "description": "Busca en conversaciones anteriores por palabras clave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Tema a buscar."},
                    "limit": {"type": "integer", "description": "1-5."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_review",
            "description": "Registra si el alumno acerto un repaso (error o vocab).",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "ID del repaso."},
                    "correct": {"type": "boolean", "description": "True si acerto."},
                },
                "required": ["item_id", "correct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_expert",
            "description": (
                "Pregunta a un experto online cuando la duda se sale de ensenar "
                "ingles: tecnologia, ciencia, codigo o datos que no tienes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "La pregunta concreta para el experto.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto opcional de la conversación.",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["es", "en"],
                        "description": "Idioma de la respuesta.",
                    },
                },
                "required": ["question"],
            },
        },
    },
]

# Herramientas LOCALES (deterministas): se resuelven ANTES de llamar al modelo.
# El 9B falla en aritmetica y no sabe la fecha real; no vale la pena gastar
# tokens del contexto ni VRAM en que el modelo las llame.
LOCAL_TOOLS = ("calculate", "current_date", "date_calculate", "fetch_weather", "ask_expert")

# Conjunto de nombres validos para validacion (solo MODEL_TOOLS).
_TOOL_NAMES = {tool["function"]["name"] for tool in MODEL_TOOLS}

# Para compatibilidad: TOOLS apunta a MODEL_TOOLS (lo que ve el modelo).
TOOLS = MODEL_TOOLS

_TOOL_NAMES = {tool["function"]["name"] for tool in TOOLS}

SELECTION_SYSTEM = (
    "Eres Emma, una profesora bilingue. Decide si necesitas una herramienta. "
    "Usa web_search para noticias, datos actuales o temas externos; fetch_page "
    "solo si el usuario da una URL; calculate para operaciones aritmeticas y "
    "current_date para la fecha u hora; date_calculate para saber que dia cae "
    "una fecha; fetch_weather para el tiempo meteorologico; ask_expert solo si "
    "la duda se sale de la ensenanza de ingles, necesita informacion actual, "
    "razonamiento largo o codigo; las herramientas de memoria solo si pregunta "
    "por su perfil, sus repasos o conversaciones pasadas. Si no hace falta "
    "ninguna, responde con una frase normal y NO llames herramientas. "
    "No inventes datos: si no lo sabes, usa web_search."
)


class ToolArgumentError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _clean(text: Any, limit: int = 200) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[:limit]


def _arg_str(args: Dict[str, Any], key: str, required: bool = True, max_len: int = 200) -> str:
    value = args.get(key)
    if value is None:
        if required:
            raise ToolArgumentError(f"falta '{key}'")
        return ""
    if not isinstance(value, (str, int, float)):
        raise ToolArgumentError(f"'{key}' debe ser texto")
    text = _clean(value, max_len)
    if required and not text:
        raise ToolArgumentError(f"'{key}' esta vacio")
    return text


def _arg_int(args: Dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = args.get(key, default)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ToolArgumentError(f"'{key}' debe ser un entero")
    return max(low, min(high, number))


def _arg_url(args: Dict[str, Any]) -> str:
    url = _arg_str(args, "url", max_len=500)
    if not re.match(r"^https?://", url, re.IGNORECASE):
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", url, re.IGNORECASE):
            url = "https://" + url
        else:
            raise ToolArgumentError("'url' no es una URL valida")
    allowed, reason = web_tools._url_allowed(url)
    if not allowed:
        raise ToolArgumentError(f"URL no permitida: {reason}")
    return url


def _arg_lang(args: Dict[str, Any], fallback: str) -> str:
    value = str(args.get("lang") or fallback or "es").lower()
    return "en" if value.startswith("en") else "es"


def validate_arguments(name: str, args: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """Devuelve (argumentos_limpios, error). Nunca lanza."""
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return None, "los argumentos no son JSON valido"
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return None, "los argumentos deben ser un objeto JSON"
    # Permitir herramientas locales (no estan en _TOOL_NAMES pero son validas)
    if name not in _TOOL_NAMES and name not in LOCAL_TOOLS:
        return None, f"herramienta desconocida: {name}"
    try:
        if name == "web_search":
            return {
                "query": _arg_str(args, "query", max_len=200),
                "lang": _arg_lang(args, "es"),
            }, ""
        if name == "fetch_page":
            return {"url": _arg_url(args)}, ""
        if name == "calculate":
            return {"expression": _arg_str(args, "expression", max_len=200)}, ""
        if name == "current_date":
            return {}, ""
        if name == "date_calculate":
            date_str = _arg_str(args, "date", max_len=50)
            if not date_str:
                return None, "falta el parametro date"
            # Validar formato basico YYYY-MM-DD
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                return None, "formato de fecha invalido, use YYYY-MM-DD"
            # Validar que es una fecha real
            from datetime import date
            try:
                y, m, d = map(int, date_str.split("-"))
                date(y, m, d)
            except ValueError:
                return None, "fecha invalida"
            return {"date": date_str}, ""
        if name == "get_profile":
            return {}, ""
        if name == "get_due_reviews":
            return {"limit": _arg_int(args, "limit", 3, 1, 10)}, ""
        if name == "search_sessions":
            return {
                "query": _arg_str(args, "query", max_len=200),
                "limit": _arg_int(args, "limit", 2, 1, 5),
            }, ""
        if name == "record_review":
            return {
                "item_id": _arg_int(args, "item_id", 0, 1),
                "correct": _arg_bool(args, "correct"),
            }, ""
        if name == "fetch_weather":
            lat = float(args.get("lat", 40.42))
            lon = float(args.get("lon", -3.70))
            lang = args.get("lang", "es")
            return {"lat": lat, "lon": lon, "lang": lang}, ""
        if name == "ask_expert":
            question = _arg_str(args, "question", max_len=1200)
            if not question:
                return None, "falta el parametro question"
            context = _arg_str(args, "context", required=False, max_len=300)
            lang = args.get("language", "es")
            if lang not in ("es", "en"):
                lang = "es"
            return {"question": question, "context": context, "language": lang}, ""
    except ToolArgumentError as exc:
        return None, str(exc)
    return None, "herramienta desconocida"


# ---------------------------------------------------------------------------
# Ollama: seleccion de herramientas y reparacion de argumentos
# ---------------------------------------------------------------------------

def _chat(
    model: str,
    messages: List[Dict[str, Any]],
    url: str,
    num_ctx: int,
    timeout: float,
    tools: Optional[List[Dict[str, Any]]] = None,
    num_predict: int = SELECTION_NUM_PREDICT,
    force_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
            "num_predict": max(24, int(num_predict)),
            "num_ctx": max(2048, int(num_ctx)),
        },
    }
    if tools:
        payload["tools"] = tools
    if force_format:
        payload["format"] = force_format
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


TOOL_RESULT_HINT = (
    "\n\nHERRAMIENTAS: en este turno has consultado herramientas y los mensajes "
    "'tool' traen resultados reales de internet o de tu memoria. Usalos como "
    "fuente principal, no digas que no tienes acceso a internet y no inventes "
    "datos que no aparezcan ahi. Si el usuario pide leer o resumir una pagina, "
    "EMPIEZA por el dato mas importante del texto (quien, que, donde, cuando) y "
    "sigue con 2 o 3 frases de detalle. No empieces con 'He leido' ni "
    "'He consultado': cuenta directamente lo que dice. Menciona la fuente una "
    "vez, de forma natural ('segun El Pais'). Si falta el dato, dilo con honestidad."
)

TOOL_SEARCH_HINT = (
    "\n\nHERRAMIENTAS: en este turno has consultado herramientas y los mensajes "
    "'tool' traen resultados reales de internet o de tu memoria. Usalos como "
    "fuente principal, no digas que no tienes acceso a internet y no inventes "
    "datos que no aparezcan ahi. Di lo que cuentan los titulares o fragmentos "
    "con 1 o 2 datos concretos (nombres, cifras, fechas) en 2-4 frases. "
    "Menciona la fuente una vez, de forma natural ('segun El Pais'). "
    "Si falta el dato, dilo con honestidad."
)


TOOL_REINFORCE_PAGE = (
    "Resume el contenido de la pagina en 2-4 frases con nombres y datos. "
    "No digas que la has leido."
)
TOOL_REINFORCE_SEARCH = (
    "Responde usando los resultados con 1 o 2 datos concretos en 2-4 frases."
)


def tool_result_hint(used: Optional[List[str]] = None) -> str:
    """Hint segun la herramienta: leer una pagina exige resumir su contenido."""
    used_set = set(used or [])
    if "calculate" in used_set:
        return (
            "\n\nCALCULO: el mensaje 'tool' trae el resultado exacto de una "
            "operacion. Usa esa cifra tal cual, no la recalcules de memoria."
        )
    if "current_date" in used_set:
        return (
            "\n\nFECHA: el mensaje 'tool' trae la fecha y hora reales del "
            "sistema. Usalas tal cual; no inventes otra fecha."
        )
    if "date_calculate" in used_set:
        return (
            "\n\nFECHA CALCULADA: el mensaje 'tool' trae el dia de la semana "
            "exacto para la fecha pedida. Usa ese dia, no lo calcules mentalmente."
        )
    if "fetch_weather" in used_set:
        return (
            "\n\nTIEMPO: el mensaje 'tool' trae el tiempo actual y pronostico "
            "exacto para la ubicacion pedida. Usa esos datos tal cual; no inventes "
            "el tiempo ni busques en otra fuente."
        )
    if "ask_expert" in used_set:
        return (
            "\n\nEXPERTO: el mensaje 'tool' trae la respuesta de un modelo experto "
            "online (gratis). Usa esa informacion tal cual; no la reescribas ni la "
            "inventes. Resume la respuesta para el alumno en tus propias palabras, "
            "no la pegues tal cual. Menciona la fuente una vez ('segun el experto')."
        )
    if "fetch_page" in used_set:
        return TOOL_RESULT_HINT
    return TOOL_SEARCH_HINT


def tool_reinforcement(used: Optional[List[str]] = None) -> str:
    """Recordatorio corto pegado al final: los modelos pequenos lo obedecen mejor."""
    used_set = set(used or [])
    if "calculate" in used_set:
        return "Responde con el resultado exacto de la herramienta, sin recalcular."
    if "current_date" in used_set:
        return "Responde con la fecha y hora del resultado, sin inventarlas."
    if "date_calculate" in used_set:
        return "Responde con el dia de la semana del resultado, sin inventarlo."
    if "fetch_weather" in used_set:
        return "Responde con el tiempo del resultado, sin inventarlo."
    if "ask_expert" in used_set:
        return "Responde resumiendo la respuesta del experto en tus palabras, no la pegues tal cual."
    if "fetch_page" in used_set:
        return TOOL_REINFORCE_PAGE
    return TOOL_REINFORCE_SEARCH


def tool_hint(text: str) -> str:
    """Devuelve 'web', 'memory', 'expert' o '' segun lo que pueda necesitar el turno."""
    raw = str(text or "")
    if re.search(
        r"\b(recuerdas|te acuerdas|do you remember|remember when|"
        r"hablamos de|we talked about|conversaciones anteriores)\b",
        raw,
        re.IGNORECASE,
    ):
        return "memory"
    # Detectar preguntas que requieren experto (fuera de ensenanza de ingles)
    # Se comprueba ANTES que web para priorizar experto en dudas tecnicas/complejas
    if re.search(
        r"\b(como funciona|how (does|do)|por que|why does|expliqueme|explain|"
        r"codigo|code|programa|algorithm|algoritmo|framework|library|api|"
        r"que significa|what means|define|definicion|"
        r"historia de|history of|origen de|origin of|"
        r"comparar|compare|diferencia entre|difference between|"
        r"ventajas|desventajas|pros|cons|pros and cons|"
        r"algoritmo|algorithm|complejidad|complexity|big-?o|"
        r"implementa|implement|debug|depurar|optimiza|optimize)\b",
        raw,
        re.IGNORECASE,
    ):
        return "expert"
    if web_tools.should_search(raw):
        return "web"
    return ""


def needs_tools(text: str) -> bool:
    """Solo los turnos que pueden necesitar la web o la memoria pagan la llamada extra."""
    return bool(tool_hint(text)) or bool(detect_local_intent(text))


def select_tool_calls(
    user_text: str,
    lang: str,
    model: str,
    url: str = "http://localhost:11434",
    num_ctx: int = 8192,
    timeout: float = 20.0,
) -> List[Dict[str, Any]]:
    """Pide al modelo que elija herramientas. Devuelve lista (puede ser vacia)."""
    messages = [
        {"role": "system", "content": SELECTION_SYSTEM},
        {"role": "user", "content": user_text},
    ]
    try:
        data = _chat(model, messages, url, num_ctx, timeout, tools=TOOLS)
    except Exception as exc:
        print(f"[TOOLS] Seleccion fallida: {exc}")
        return []
    message = data.get("message") or {}
    calls = message.get("tool_calls") or []
    if not isinstance(calls, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for call in calls[:MAX_TOOL_CALLS]:
        if not isinstance(call, dict):
            continue
        function = call.get("function") or {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        cleaned.append({
            "id": call.get("id") or "",
            "function": {
                "name": name,
                "arguments": function.get("arguments") or {},
            },
        })
    return cleaned


def _repair_arguments_once(
    name: str,
    arguments: Any,
    error: str,
    model: str,
    url: str,
    num_ctx: int,
    timeout: float,
) -> Optional[Dict[str, Any]]:
    """Una sola llamada para corregir argumentos mal formados."""
    schema = next(
        (tool["function"]["parameters"] for tool in TOOLS
         if tool["function"]["name"] == name),
        {"type": "object", "properties": {}},
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Corrige los argumentos de una llamada a herramienta. "
                "Devuelve SOLO JSON valido con la forma del esquema dado."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Herramienta: {name}\n"
                f"Esquema: {json.dumps(schema, ensure_ascii=False)}\n"
                f"Argumentos recibidos: {json.dumps(arguments, ensure_ascii=False)[:500]}\n"
                f"Error: {error}\n"
                "Devuelve solo el objeto de argumentos corregido."
            ),
        },
    ]
    try:
        data = _chat(
            model, messages, url, num_ctx, timeout,
            num_predict=160, force_format=schema,
        )
        raw = str((data.get("message") or {}).get("content") or "").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        print(f"[TOOLS] Reparacion fallida para {name}: {exc}")
    return None


def _fallback_arguments(name: str, user_text: str, lang: str) -> Dict[str, Any]:
    """Respaldo seguro cuando ni la reparacion arregla los argumentos."""
    if name == "web_search":
        return {"query": web_tools.clean_query(user_text) or _clean(user_text), "lang": lang}
    if name == "fetch_page":
        urls = web_tools.extract_urls(user_text)
        return {"url": urls[0]} if urls else {}
    if name == "calculate":
        expression = _math_expression(user_text)
        return {"expression": expression} if expression else {}
    if name == "current_date":
        return {}
    if name == "date_calculate":
        date_str = _extract_date_from_text(user_text)
        return {"date": date_str} if date_str else {}
    if name == "fetch_weather":
        city_coords = {
            "logrono": (42.46, -2.45), "logroño": (42.46, -2.45),
            "madrid": (40.42, -3.70), "barcelona": (41.38, 2.17),
            "valencia": (39.47, -0.38), "sevilla": (37.38, -5.98),
            "bilbao": (43.26, -2.93), "malaga": (36.72, -4.42),
        }
        lat, lon = 40.42, -3.70
        q_lower = user_text.lower()
        for city, coords in city_coords.items():
            if city in q_lower:
                lat, lon = coords
                break
        return {"lat": lat, "lon": lon, "lang": lang}
    if name == "ask_expert":
        return {"question": user_text, "context": "", "language": lang}
    if name == "get_due_reviews":
        return {"limit": 3}
    if name == "search_sessions":
        return {"query": web_tools.clean_query(user_text) or _clean(user_text), "limit": 2}
    return {}


# ---------------------------------------------------------------------------
# Ejecucion
# ---------------------------------------------------------------------------

def execute_tool(
    name: str,
    args: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ejecuta una herramienta ya validada. Devuelve ok/result/error."""
    cfg = config or {}
    timeout = float(cfg.get("timeout_s", 8))
    try:
        if name == "web_search":
            global _LAST_WEB_QUERY, _LAST_WEB_TIME
            _LAST_WEB_QUERY = str(args["query"])
            _LAST_WEB_TIME = time.time()
            results = web_tools.search_web(
                args["query"],
                lang=args.get("lang", "es"),
                max_results=int(cfg.get("max_results", 4)),
                timeout=timeout,
                config=cfg,
            )

            # El titular y el snippet no bastan para "quien", "donde" o
            # "como acceder": se descarga el articulo y se adjunta. Si el
            # primero falla (portada, muro de cookies), se prueba el siguiente.
            page_chars = int(cfg.get("page_chars", 1800))
            if page_chars > 0:
                tried: set = set()
                for _ in range(min(3, len(results))):
                    pending = [r for r in results if r.get("url") not in tried]
                    candidate = _best_fetch_candidate(pending)
                    if not candidate:
                        break
                    tried.add(candidate)
                    try:
                        page = web_tools.fetch_page(
                            candidate, timeout=timeout, max_chars=page_chars
                        )
                    except Exception as fetch_error:
                        print(f"[TOOLS] No se pudo leer el articulo: {fetch_error}")
                        continue
                    body = str(page.get("text") or "").strip()
                    if len(body) < 300:
                        # Muro de cookies, portada o error: siguiente fuente.
                        continue
                    for item in results:
                        if item.get("url") == candidate:
                            item["text"] = body
                            item["title"] = page.get("title") or item.get("title")
                            break
                    break

            compact = [
                {
                    "title": _clean(item.get("title"), 140),
                    "url": item.get("url", ""),
                    "site": item.get("site", ""),
                    "snippet": _clean(item.get("snippet"), 220),
                    "text": str(item.get("text") or "").strip(),
                    "kind": item.get("kind", "search"),
                }
                for item in results
            ]
            return {"ok": True, "result": compact}

        if name == "fetch_page":
            page = web_tools.fetch_page(
                args["url"], timeout=timeout, max_chars=int(cfg.get("page_chars", 1200))
            )
            if page.get("error") and not page.get("text"):
                return {"ok": False, "error": page["error"], "result": page}
            return {"ok": True, "result": page}

        if name == "calculate":
            expression = _normalize_math(str(args.get("expression") or ""))
            if not expression:
                return {"ok": False, "error": "expresion no valida"}
            try:
                value = _safe_eval(expression)
            except Exception as exc:
                return {"ok": False, "error": f"no se pudo calcular: {exc}"}
            return {
                "ok": True,
                "result": {
                    "expression": expression,
                    "value": value,
                    "formatted": _format_result(value),
                },
            }

        if name == "current_date":
            now = datetime.now()
            weekdays_es = (
                "lunes", "martes", "miércoles", "jueves",
                "viernes", "sábado", "domingo",
            )
            months_es = (
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
            )
            weekdays_en = (
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            )
            months_en = (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            )
            return {
                "ok": True,
                "result": {
                    "iso": now.isoformat(timespec="seconds"),
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M"),
                    "weekday_es": weekdays_es[now.weekday()],
                    "weekday_en": weekdays_en[now.weekday()],
                    "month_es": months_es[now.month - 1],
                    "month_en": months_en[now.month - 1],
                    "year": now.year,
                    "spoken_es": (
                        f"Hoy es {weekdays_es[now.weekday()]}, {now.day} de "
                        f"{months_es[now.month - 1]} de {now.year}, y son las "
                        f"{now.strftime('%H:%M')}."
                    ),
                    "spoken_en": (
                        f"Today is {weekdays_en[now.weekday()]}, "
                        f"{months_en[now.month - 1]} {now.day}, {now.year}, "
                        f"and it is {now.strftime('%H:%M')}."
                    ),
                },
            }

        if name == "date_calculate":
            from datetime import date
            date_str = args["date"]
            y, m, d = map(int, date_str.split("-"))
            target = date(y, m, d)
            weekdays_es = (
                "lunes", "martes", "miércoles", "jueves",
                "viernes", "sábado", "domingo",
            )
            weekdays_en = (
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            )
            months_es = (
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
            )
            months_en = (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            )
            return {
                "ok": True,
                "result": {
                    "date": date_str,
                    "weekday_es": weekdays_es[target.weekday()],
                    "weekday_en": weekdays_en[target.weekday()],
                    "month_es": months_es[target.month - 1],
                    "month_en": months_en[target.month - 1],
                    "year": target.year,
                    "spoken_es": (
                        f"El {d} de {months_es[target.month - 1]} de {target.year} "
                        f"cae en {weekdays_es[target.weekday()]}."
                    ),
                    "spoken_en": (
                        f"{months_en[target.month - 1]} {d}, {target.year} "
                        f"falls on a {weekdays_en[target.weekday()]}."
                    ),
                },
            }


        if name == "fetch_weather":
            # args: {"lat": float, "lon": float, "lang": "es"}
            lat = float(args.get("lat", 40.42))
            lon = float(args.get("lon", -3.70))
            lang = args.get("lang", "es")
            # Extract city from query if available for better UX
            city = args.get("city", "")
            weather_data = asyncio.run(web_tools.fetch_weather(lat, lon, lang))
            if weather_data.get("error"):
                return {"ok": False, "error": weather_data["error"]}
            summary = web_tools.extract_weather_summary(weather_data, lang)
            return {
                "ok": True,
                "result": {
                    "lat": lat,
                    "lon": lon,
                    "city": city,
                    "summary": summary,
                    "raw": weather_data,
                },
            }

        if name == "ask_expert":
            # args: {"question": str, "context": str, "language": "es"}
            question = str(args.get("question", ""))
            context = str(args.get("context", ""))
            lang = args.get("language", "es")
            if lang not in ("es", "en"):
                lang = "es"
            try:
                from expert import ask_expert_sync
                expert_result = ask_expert_sync(question, context, lang)
            except Exception as exc:
                return {"ok": False, "error": f"expert error: {exc}"}
            if not expert_result.get("ok"):
                return {
                    "ok": False,
                    "error": expert_result.get("error") or "expert_unavailable",
                }
            answer = str(expert_result.get("answer") or "").strip()
            return {
                "ok": True,
                "result": {
                    "answer": answer,
                    "provider": expert_result.get("provider") or "",
                    "latency_ms": expert_result.get("latency_ms") or 0,
                },
            }

        # Memoria: reutiliza la validacion existente.
        result = emma_memory.execute_tool(name, args)
        return result
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _best_fetch_candidate(results: List[Dict[str, Any]]) -> Optional[str]:
    """Prefiere un articulo (ruta profunda) antes que una portada."""
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for item in results:
        url = str(item.get("url") or "")
        if not url.startswith("http"):
            continue
        if "news.google.com/rss/articles" in url:
            # Es un redirect de Google News: en navegador abre, pero el
            # servidor recibe una pagina de consentimiento.
            continue
        path = re.sub(r"^https?://[^/]+", "", url)
        score = path.count("/")
        if re.search(r"/\d{4}-\d{2}-\d{2}/", path):
            score += 3
        if score > best_score:
            best, best_score = item, score
    return str(best["url"]) if best else None


def _compact_result(name: str, result: Dict[str, Any], limit: int) -> str:
    if not result.get("ok"):
        return f"Error: {result.get('error') or 'sin resultado'}"
    data = result.get("result")
    if name == "web_search":
        lines = []
        for item in data or []:
            lines.append(
                f"- {item.get('title') or '(sin titulo)'} "
                f"[{item.get('site') or item.get('url')}]: "
                f"{item.get('snippet') or ''} ({item.get('url')})"
            )
            body = str(item.get("text") or "").strip()
            if body:
                lines.append(f"  Extracto: {body}")
        text = "\n".join(lines)
    elif name == "fetch_page":
        text = f"{data.get('title') or data.get('site')}: {data.get('text') or data.get('snippet') or ''}"
    elif name == "calculate":
        text = f"{data.get('expression')} = {data.get('formatted')}"
    elif name == "current_date":
        text = (
            f"{data.get('spoken_es')} ({data.get('iso')}). "
            f"{data.get('spoken_en')}"
        )
    elif name == "fetch_weather":
        text = data.get("summary") or json.dumps(data, ensure_ascii=False)
    elif name == "ask_expert":
        text = data.get("answer") or json.dumps(data, ensure_ascii=False)
    else:
        text = json.dumps(data, ensure_ascii=False)
    return text[:limit]


def gather_tool_context(
    user_text: str,
    lang: str = "es",
    model: str = "qwen3.5:9b",
    url: str = "http://localhost:11434",
    num_ctx: int = 8192,
    previous: str = "",
    config: Optional[Dict[str, Any]] = None,
    max_calls: int = MAX_TOOL_CALLS,
    max_result_chars: int = MAX_TOOL_RESULT_CHARS,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Selecciona, valida y ejecuta herramientas; devuelve mensajes compactos.

    Resultado:
      ``messages``: mensajes assistant/tool listos para la llamada final.
      ``sources``: fuentes web para la UI (enlaces clicables).
      ``used``: nombres de herramientas ejecutadas.
    """
    # Calculo y fecha se resuelven sin llamar al modelo: son deterministas y
    # no deben depender de que un 9B acierte con la aritmetica.
    local = detect_local_intent(user_text)
    calls = []
    if local:
        calls.append({
            "function": {
                "name": local["name"],
                "arguments": local["arguments"],
            }
        })

    # Ademas de la herramienta local, si el turno pide busqueda web,
    # la anadimos (ej: "what day is today AND when is the election in spain").
    needs_web = needs_tools(user_text) and (not local or tool_hint(user_text) == "web")
    if needs_web:
        # Detectar si es consulta meteorologica o de experto para usar herramienta dedicada
        hint = tool_hint(user_text)
        if hint == "expert":
            # Consulta a experto para dudas tecnicas/complejas
            calls.append({
                "function": {
                    "name": "ask_expert",
                    "arguments": {"question": user_text, "context": "", "language": lang},
                }
            })
        else:
            # Detectar si es consulta meteorologica para usar herramienta dedicada
            intent = web_tools.detect_intent(user_text)
            if intent == "weather":
                # Extraer coordenadas aproximadas
                city_coords = {
                    "logrono": (42.46, -2.45), "logroño": (42.46, -2.45),
                    "madrid": (40.42, -3.70), "barcelona": (41.38, 2.17),
                    "valencia": (39.47, -0.38), "sevilla": (37.38, -5.98),
                    "bilbao": (43.26, -2.93), "malaga": (36.72, -4.42),
                }
                lat, lon = 40.42, -3.70  # default Madrid
                city = "madrid"
                q_lower = user_text.lower()
                for known_city, coords in city_coords.items():
                    if known_city in q_lower:
                        lat, lon = coords
                        city = known_city
                        break
                calls.append({
                    "function": {
                        "name": "fetch_weather",
                        "arguments": {"lat": lat, "lon": lon, "lang": lang, "city": city},
                    }
                })
            else:
                base_query = web_tools.clean_query(user_text) or _clean(user_text)

            # Seguimiento ("cuentame mas", "tell me more", "who can access..."):
            # reutiliza el tema de la ultima busqueda web para ampliar con datos
            # nuevos, en vez de buscar la frase literal y quedarse sin contexto.
            reuse_query = needs_followup(user_text)
            query = ""

            if reuse_query:
                # El tema anterior manda; las palabras nuevas ("access", "history")
                # añaden otra cara del mismo asunto para no devolver lo mismo.
                extra = [
                    word
                    for word in sorted(
                        _significant_words(user_text) - _significant_words(_LAST_WEB_QUERY)
                    )
                    if len(word) > 4
                ][:3]
                query = " ".join([_LAST_WEB_QUERY] + extra).strip()
                calls.append({
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": query, "lang": lang},
                    }
                })
            else:
                calls.append({
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": base_query, "lang": lang},
                    }
                })

    # Si no hay local ni web pero el modelo deberia elegir, pedimos al modelo.
    if not calls:
        calls = select_tool_calls(user_text, lang, model, url, num_ctx, timeout)

        # Seguimiento...
        reuse_query = needs_followup(user_text)
        query = ""

        if reuse_query:
            extra = [
                word
                for word in sorted(
                    _significant_words(user_text) - _significant_words(_LAST_WEB_QUERY)
                )
                if len(word) > 4
            ][:3]
            query = " ".join([_LAST_WEB_QUERY] + extra).strip()
            calls = [{
                "function": {
                    "name": "web_search",
                    "arguments": {"query": query, "lang": lang},
                }
            }]

        # Si el modelo no llama ninguna herramienta pero el turno lo pide...
        if not calls and needs_tools(user_text):
            hint = tool_hint(user_text)
            if hint == "memory":
                calls = [{
                    "function": {
                        "name": "search_sessions",
                        "arguments": {
                            "query": web_tools.clean_query(user_text) or _clean(user_text),
                            "limit": 2,
                        },
                    }
                }]
            # Si el modelo no llama ninguna herramienta pero el turno lo pide...
        if not calls and needs_tools(user_text):
            hint = tool_hint(user_text)
            if hint == "memory":
                calls = [{
                    "function": {
                        "name": "search_sessions",
                        "arguments": {
                            "query": web_tools.clean_query(user_text) or _clean(user_text),
                            "limit": 2,
                        },
                    }
                }]
            elif hint == "expert":
                calls = [{
                    "function": {
                        "name": "ask_expert",
                        "arguments": {
                            "question": user_text,
                            "context": "",
                            "language": lang,
                        },
                    }
                }]
            else:
                # Usar weather_query si es consulta meteorologica
                intent = web_tools.detect_intent(user_text)
                if intent == "weather":
                    city_coords = {
                        "logrono": (42.46, -2.45), "logroño": (42.46, -2.45),
                        "madrid": (40.42, -3.70), "barcelona": (41.38, 2.17),
                        "valencia": (39.47, -0.38), "sevilla": (37.38, -5.98),
                        "bilbao": (43.26, -2.93), "malaga": (36.72, -4.42),
                    }
                    lat, lon = 40.42, -3.70
                    q_lower = user_text.lower()
                    for city, coords in city_coords.items():
                        if city in q_lower:
                            lat, lon = coords
                            break
                    calls = [{
                        "function": {
                            "name": "fetch_weather",
                            "arguments": {"lat": lat, "lon": lon, "lang": lang, "city": city},
                        }
                    }]
                else:
                    base_query = web_tools.weather_query(user_text, lang)
                calls = [{
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": base_query, "lang": lang},
                    }
                }]

    sources: List[Dict[str, Any]] = []
    used: List[str] = []
    cfg = config or {}
    assistant_calls: List[Dict[str, Any]] = []
    tool_messages: List[Dict[str, Any]] = []

    for call in calls[:max_calls]:
        function = call.get("function") or {}
        name = str(function.get("name") or "").strip()
        raw_args = function.get("arguments") or {}

        args, error = validate_arguments(name, raw_args)
        if args is None:
            print(f"[TOOLS] Argumentos invalidos en {name}: {error}; reintento")
            repaired = _repair_arguments_once(
                name, raw_args, error, model, url, num_ctx, timeout
            )
            if repaired is not None:
                args, error = validate_arguments(name, repaired)
            if args is None:
                fallback = _fallback_arguments(name, user_text, lang)
                args, error = validate_arguments(name, fallback)
            if args is None:
                print(f"[TOOLS] {name} descartada: {error}")
                continue

        result = execute_tool(name, args, config)
        used.append(name)
        assistant_calls.append({
            "type": "function",
            "function": {"name": name, "arguments": args},
        })
        compact = _compact_result(name, result, max_result_chars)
        tool_messages.append({
            "role": "tool",
            "tool_name": name,
            "content": compact,
        })

        payload = result.get("result")
        if name == "web_search" and isinstance(payload, list):
            for item in payload:
                if item.get("url"):
                    sources.append({
                        "title": item.get("title") or item.get("site") or item["url"],
                        "url": item["url"],
                        "site": item.get("site") or "",
                        "snippet": item.get("snippet") or "",
                        "kind": "search",
                        "error": "",
                    })

            # El cuerpo del articulo ya lo adjunta ``execute_tool`` dentro del
            # propio resultado de ``web_search`` (campo ``text``), asi que no
            # se vuelve a descargar aqui: duplicaria contexto y anadiria una
            # fuente repetida a la UI.
        elif name == "fetch_page" and isinstance(payload, dict) and payload.get("url"):
            sources.append({
                "title": payload.get("title") or payload.get("site") or payload["url"],
                "url": payload["url"],
                "site": payload.get("site") or "",
                "snippet": payload.get("snippet") or "",
                "kind": "page",
                "error": payload.get("error") or "",
            })
        elif name == "fetch_weather" and isinstance(payload, dict):
            sources.append({
                "title": payload.get("summary") or f"Weather for {payload.get('city', 'location')}",
                "url": f"https://wttr.in/{payload.get('lat', '')},{payload.get('lon', '')}",
                "site": "wttr.in",
                "snippet": payload.get("summary", "")[:300],
                "kind": "weather",
                "error": "",
            })
        elif name == "ask_expert":
            # La respuesta del experto va en el mensaje 'tool'; no es una fuente
            # web, asi que no se añade a la lista de enlaces de la UI.
            pass

    # Fuentes unicas y acotadas.
    unique: List[Dict[str, Any]] = []
    seen = set()
    for source in sources:
        key = source.get("url")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(source)

    messages: List[Dict[str, Any]] = []
    if assistant_calls:
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": assistant_calls,
        })
        messages.extend(tool_messages)

    return {
        "messages": messages,
        "sources": unique[: int((config or {}).get("max_results", 4))],
        "used": used,
    }


# ---------------------------------------------------------------------------
# CLI / pruebas
# ---------------------------------------------------------------------------

def _selftest() -> None:
    assert validate_arguments("web_search", {"query": "noticias"})[0] == {
        "query": "noticias", "lang": "es"
    }
    assert validate_arguments("web_search", {})[0] is None
    assert validate_arguments("fetch_page", {"url": "elpais.com"})[0]["url"].startswith("https://")
    assert validate_arguments("fetch_page", {"url": "file:///etc/passwd"})[0] is None
    assert validate_arguments("get_due_reviews", {"limit": "99"})[0]["limit"] == 10
    assert validate_arguments("search_sessions", {"query": "playa"})[0]["limit"] == 2
    assert validate_arguments("nope", {})[0] is None
    assert validate_arguments("web_search", '{"query": "Dune"}')[0]["query"] == "Dune"
    assert needs_tools("Busca noticias de Espana")
    assert not needs_tools("Hola Emma, como estas?")
    assert _normalize_math("23 x 17") == "23*17"
    assert detect_local_intent("cuanto es 15% de 200")["arguments"]["expression"] == "(15/100)*200"
    assert execute_tool("calculate", {"expression": "(15/100)*200"})["result"]["formatted"] == "30"
    assert execute_tool("calculate", {"expression": "sqrt(144)"})["result"]["formatted"] == "12"
    assert detect_local_intent("que dia es hoy")["name"] == "current_date"
    assert detect_local_intent("what time is it")["name"] == "current_date"
    assert needs_tools("cuanto es 2+2")
    assert execute_tool("calculate", {"expression": "__import__('os')"})["ok"] is False
    print("SELFTEST OK")


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        _selftest()
    else:
        query = " ".join(sys.argv[1:]) or "que ha pasado hoy en espana"
        out = gather_tool_context(query, lang="es")
        print("Usadas:", out["used"])
        print("Fuentes:", [s["url"] for s in out["sources"]])
        for message in out["messages"]:
            print(message.get("role"), str(message.get("content"))[:300])
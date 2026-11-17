"""Parches de calidad para las respuestas de Emma.

`verify_corrections` filtra las correcciones que el LLM inventa o que no
corrigen nada real. El modelo pequeno tiende a rellenar el array
"corrections" del esquema aunque el turno del usuario sea correcto; esas
correcciones acaban en la memoria de errores y en el SRS, asi que conviene
descartarlas antes de guardarlas.

Uso:
    from emma_patches import verify_corrections

    corrections, dropped = verify_corrections(user_text, corrections)
    for item, reason in dropped:
        print(f"   [CORR] descartada ({reason}): {item[:80]}")
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Sequence, Tuple

__all__ = ["answer_profile_question", "verify_corrections", "normalize_text"]

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

# Tipos aceptados por el esquema de voice_loop.py
_ALLOWED_TYPES = {"grammar", "vocabulary", "pronunciation"}

# Palabras sin carga semantica: no sirven para comprobar si el usuario
# dijo realmente la frase que el modelo dice corregir.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on",
    "at", "for", "with", "is", "are", "was", "were", "be", "been", "am",
    "do", "does", "did", "have", "has", "had", "i", "you", "he", "she",
    "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
    "me", "him", "us", "them", "this", "that", "these", "those", "so",
    "very", "just", "not", "no", "yes", "ok", "okay", "well", "oh",
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "y", "o", "pero", "si", "que", "en", "por", "para", "con", "es",
    "son", "fue", "ser", "estar", "mi", "tu", "su", "me", "te", "se",
    "lo", "le", "nos", "os", "muy", "no", "ya",
}


def normalize_text(text: Any) -> str:
    """Minusculas, sin acentos, sin puntuacion y con espacios simples."""
    if text is None:
        return ""
    value = unicodedata.normalize("NFKD", str(text))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = _NON_WORD_RE.sub(" ", value)
    return _SPACE_RE.sub(" ", value).strip()


def _content_words(text: str) -> List[str]:
    return [
        word
        for word in normalize_text(text).split()
        if word not in _STOPWORDS and len(word) >= 3
    ]


def _appears_in_turn(original: str, user_text: str) -> bool:
    """Comprueba que la frase original salga del turno real del usuario."""
    original_norm = normalize_text(original)
    user_norm = normalize_text(user_text)
    if not original_norm or not user_norm:
        return False
    if original_norm in user_norm:
        return True

    # Tolerancia a puntuacion, contracciones y pequenas variaciones del STT:
    # basta con que aparezcan las palabras con carga semantica.
    words = _content_words(original)
    if not words:
        return False
    user_words = set(user_norm.split())
    matches = sum(1 for word in words if word in user_words)
    if len(words) == 1:
        return matches == 1
    return (matches / len(words)) >= 0.8


def _already_correct(original: str, corrected: str) -> bool:
    """True si la 'correccion' no cambia nada salvo mayusculas o puntuacion."""
    return normalize_text(original) == normalize_text(corrected)


def _clean_field(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def verify_corrections(
    user_text: str,
    corrections: Iterable[Dict[str, Any]] | None,
    max_items: int = 3,
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """Devuelve las correcciones validas y las descartadas con su motivo.

    Se descarta una correccion cuando:
      - no es un diccionario o le faltan ``original``/``corrected``;
      - el texto original y el corregido son iguales (sobre-correccion);
      - el original no aparece en el turno del usuario (alucinacion);
      - el original es demasiado corto para ser un error real;
      - se repite una correccion ya aceptada en el mismo turno;
      - se supera ``max_items`` (evita avalanchas de correcciones).
    """
    kept: List[Dict[str, Any]] = []
    dropped: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    if not corrections:
        return kept, dropped

    try:
        total = max(0, int(max_items))
    except (TypeError, ValueError):
        total = 3

    for raw in corrections:
        if not isinstance(raw, dict):
            dropped.append((str(raw)[:120], "formato invalido"))
            continue

        original = _clean_field(raw.get("original"))
        corrected = _clean_field(raw.get("corrected"))
        label = original or corrected

        if not original:
            dropped.append((label, "sin texto original"))
            continue
        if not corrected:
            dropped.append((label, "sin correccion"))
            continue
        if len(_WORD_RE.findall(normalize_text(original))) == 0:
            dropped.append((label, "original sin palabras"))
            continue
        if len(normalize_text(original).replace(" ", "")) < 2:
            dropped.append((label, "original demasiado corto"))
            continue
        if _already_correct(original, corrected):
            dropped.append((label, "no cambia nada"))
            continue
        if not _appears_in_turn(original, user_text):
            dropped.append((label, "no aparece en el turno"))
            continue

        key = (normalize_text(original), normalize_text(corrected))
        if key in seen:
            dropped.append((label, "duplicada"))
            continue
        if len(kept) >= total:
            dropped.append((label, "limite de correcciones"))
            continue

        item = dict(raw)
        item["original"] = original
        item["corrected"] = corrected
        item_type = str(item.get("type", "")).strip().lower()
        item["type"] = item_type if item_type in _ALLOWED_TYPES else "grammar"
        item["explanation"] = _clean_field(item.get("explanation"))
        seen.add(key)
        kept.append(item)

    return kept, dropped


_PROFILE_NAME_ES_RE = re.compile(
    r"\b(?:como me llamo(?: yo)?|cual es mi nombre|"
    r"sabes (?:como me llamo|mi nombre)|"
    r"(?:te acuerdas|te acordas|recuerdas) (?:de )?mi nombre|"
    r"dime mi nombre|quien soy)\b",
    re.IGNORECASE,
)
_PROFILE_NAME_EN_RE = re.compile(
    r"\b(?:what (?:is|was) my name|what s my name|whats my name|"
    r"do you (?:know|remember) my name|"
    r"what am i called|tell me my name|who am i)\b",
    re.IGNORECASE,
)


def answer_profile_question(
    user_text: str,
    user_name: Any,
    language: str = "",
) -> Dict[str, str] | None:
    """Contesta preguntas sobre el nombre del usuario sin llamar al LLM.

    Devuelve ``{"spoken": ..., "language": "es"|"en"}`` cuando el turno es
    una pregunta de perfil ("¿cómo me llamo?", "what's my name?"). Devuelve
    ``None`` en cualquier otro caso para que siga el flujo normal.

    Si todavia no hay nombre guardado, pide el nombre en vez de inventarlo.
    """
    normalized = normalize_text(user_text)
    if not normalized:
        return None

    spanish = bool(_PROFILE_NAME_ES_RE.search(normalized))
    english = bool(_PROFILE_NAME_EN_RE.search(normalized))
    if not spanish and not english:
        return None

    # El idioma de la pregunta manda sobre la preferencia guardada: si el
    # usuario pregunta en espanol, la respuesta sale en espanol.
    if english and not spanish:
        reply_language = "en"
    elif spanish and not english:
        reply_language = "es"
    else:
        requested = str(language or "").strip().lower()
        reply_language = "en" if requested.startswith("en") else "es"

    name = _SPACE_RE.sub(" ", str(user_name or "")).strip(" .,!?\"'")
    if not name:
        if reply_language == "en":
            spoken = "You haven't told me your name yet. What should I call you?"
        else:
            spoken = "Todavía no me has dicho tu nombre. ¿Cómo te llamas?"
        return {"spoken": spoken, "language": reply_language}

    if reply_language == "en":
        spoken = f"Your name is {name}."
    else:
        spoken = f"Te llamas {name}."
    return {"spoken": spoken, "language": reply_language}


def _selftest() -> None:
    user = "I have not had any sleep at all. Okay. Sounds good"
    corrections = [
        {
            "original": "I have not had any sleep at all",
            "corrected": "I have not had any sleep at all",
            "type": "grammar",
            "explanation": "repeticion",
        },
        {
            "original": "I have 25 years",
            "corrected": "I am 25 years old",
            "type": "grammar",
            "explanation": "edad",
        },
        {
            "original": "I have not had any sleep",
            "corrected": "I haven't had any sleep",
            "type": "grammar",
            "explanation": "contraccion",
        },
        "basura",
    ]
    kept, dropped = verify_corrections(user, corrections)
    assert len(kept) == 1, kept
    assert kept[0]["original"] == "I have not had any sleep"
    reasons = {reason for _item, reason in dropped}
    assert "no cambia nada" in reasons
    assert "no aparece en el turno" in reasons
    assert "formato invalido" in reasons

    kept2, dropped2 = verify_corrections("I have 25 years", [
        {"original": "I have 25 years", "corrected": "I am 25 years old"},
    ])
    assert kept2 and not dropped2

    kept_empty, dropped_empty = verify_corrections("", corrections)
    assert kept_empty == []
    assert len(dropped_empty) == len(corrections)

    # Preguntas de nombre: respuesta directa desde el perfil, sin LLM.
    assert answer_profile_question("¿Cómo me llamo?", "Henry") == {
        "spoken": "Te llamas Henry.", "language": "es",
    }
    assert answer_profile_question("¿Sabes cómo me llamo?", "Henry") == {
        "spoken": "Te llamas Henry.", "language": "es",
    }
    assert answer_profile_question("What's my name?", "Henry") == {
        "spoken": "Your name is Henry.", "language": "en",
    }
    assert answer_profile_question("Do you remember my name?", "Henry") == {
        "spoken": "Your name is Henry.", "language": "en",
    }
    # No debe dispararse cuando el usuario se presenta ni cuando pregunta
    # por el nombre de Emma.
    assert answer_profile_question("My name is Henry", "Henry") is None
    assert answer_profile_question("¿Cómo te llamas?", "Henry") is None
    assert answer_profile_question("What is your name?", "Henry") is None
    missing = answer_profile_question("¿Cómo me llamo?", "")
    assert missing and missing["language"] == "es"
    assert "nombre" in missing["spoken"]

    print("SELFTEST OK")


if __name__ == "__main__":
    _selftest()

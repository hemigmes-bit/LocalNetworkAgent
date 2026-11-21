#!/usr/bin/env python3
"""Verificador determinista de cifras para las respuestas de Emma.

No llama a ningun modelo: extrae numeros "fuertes" (anos, porcentajes,
dinero y cantidades con escala) de una frase y comprueba si el mismo valor
aparece en el contexto que Emma acaba de descargar. Si no aparece, la frase
se sustituye por un aviso honesto o se omite.

Objetivo: que un 9B no pueda colar una cifra inventada aunque el prompt
falle. Es deliberadamente conservador:

- Solo actua cuando hay contexto web (nunca en charla o cuentos).
- Solo vigila cifras dificiles de justificar por sentido comun.
- Maximo un aviso por turno; el resto de frases sin respaldo se omiten.
- Los anos anteriores a 2000 se consideran conocimiento general.

Se puede probar por separado:

    python fact_check.py --selftest
"""

from __future__ import annotations

import re
from typing import Iterable, List, NamedTuple, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Extraccion de numeros
# ---------------------------------------------------------------------------

# Numero seguido de una escala ("millones") y/o una unidad ("%", "euros").
# El lookbehind evita capturar digitos dentro de palabras o identificadores.
_NUM_TOKEN_RE = re.compile(
    r"(?<![\w])"
    r"(?P<num>\d(?:[\d.,]*\d)?)"
    r"(?:\s*(?P<scale>mil\s+millones|millones|millon|millardo(?:s)?|billion|bn|mil|k)\b)?"
    r"(?:\s*(?P<unit>%|por\s+ciento|percent|euros?|d[oó]lares?|dollars?|€|\$))?",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"\d[\d.,]*")

_SCALES = {
    "mil": 1e3,
    "k": 1e3,
    "millon": 1e6,
    "millones": 1e6,
    "millardo": 1e9,
    "millardos": 1e9,
    "mil millones": 1e9,
    "billion": 1e9,
    "bn": 1e9,
}

_CURRENCY = ("euro", "dolar", "dollar", "€", "$")

_TERMINAL_RE = re.compile(r"[.!?…][\"'»”)]*$")

_HEDGE = {
    "es": "Esa cifra no aparece en la fuente que he consultado.",
    "en": "That figure does not appear in the source I checked.",
}

# Palabras con las que una frase no puede terminar tras quitar una cifra.
_STOPWORDS = {
    "de", "del", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "y", "o", "u", "en", "al", "a", "por", "para", "con", "sin", "que",
    "es", "son", "era", "eran", "esta", "estan", "fue", "fueron", "ha",
    "han", "hay", "como", "mas", "entre", "desde", "hasta", "sobre",
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "is", "are", "was", "were", "has", "have", "had", "that",
    "which", "as", "by", "from", "worth", "about", "around", "than",
    "into", "over", "under", "its", "their",
}


def _fold(text: str) -> str:
    """Minusculas y sin acentos, para comparar escalas y unidades."""
    text = (text or "").lower()
    for source, target in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"),
    ):
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _number_variants(raw: str) -> List[float]:
    """Interpretaciones plausibles de un numero con separadores es/en.

    ``1.200`` puede ser 1200 (miles, espanol) o 1.2 (decimal, ingles).
    Devolver ambas evita falsos avisos cuando la fuente usa otro formato.
    """
    raw = (raw or "").strip().replace(" ", "")
    if not raw:
        return []
    values: List[float] = []

    def add(value: float) -> None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if number != number or number in (float("inf"), float("-inf")):
            return
        if not any(abs(number - known) <= max(1e-9, abs(number) * 1e-9) for known in values):
            values.append(number)

    if re.fullmatch(r"\d+", raw):
        add(int(raw))
        return values

    # Todos los separadores son de miles: 1.200.000 / 1,200,000.
    # Es el patron inequivoco en espanol e ingles; no se anade la lectura
    # decimal para no dar por buena una cifra mil veces mayor.
    # EXCEPCION: 1 digito + 3 decimales (ej: 1,595) tipico de precios.
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        add(int(re.sub(r"[.,]", "", raw)))
        # Si es 1 digito seguido de grupos de 3, anadir lectura decimal.
        if re.fullmatch(r"\d[.,]\d{3}", raw):
            integer, decimal = raw.split(raw[1], 1)[0], raw.split(raw[1], 1)[1].replace(".", "").replace(",", "")
            add(float(integer + "." + decimal))
        return values

    # Varios separadores con decimal final: 1.200,5 / 1,200.5
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})*[.,]\d+", raw):
        parts = re.split(r"([.,])", raw)
        integer = "".join(parts[:-2]).replace(".", "").replace(",", "")
        add(float(integer + "." + parts[-1]))

    # Un unico separador: decimal o miles.
    match = re.fullmatch(r"(\d+)[.,](\d+)", raw)
    if match:
        integer_part = match.group(1)
        decimal_part = match.group(2)
        # Si la parte entera es 1 digito y la decimal tiene 3 digitos,
        # es probable que sea un precio con 3 decimales (ej: 1,595 euros)
        # Añadimos AMBAS lecturas para cubrir ambos casos.
        if len(integer_part) == 1 and len(decimal_part) == 3:
            add(float(integer_part + "." + decimal_part))  # 1.595
            add(float(integer_part + decimal_part))        # 1595
        else:
            add(float(integer_part + "." + decimal_part))  # decimal
            if len(decimal_part) == 3:
                add(float(integer_part + decimal_part))    # miles

    if not values:
        add(int(re.sub(r"[.,]", "", raw)))

    return values


class Claim(NamedTuple):
    raw: str
    values: Tuple[float, ...]
    kind: str
    start: int
    end: int


def _claim_kind(num: str, scale: str, unit: str, values: Sequence[float]) -> str:
    if unit.startswith("%") or "por ciento" in unit or "percent" in unit:
        return "percent"
    if any(marker in unit for marker in _CURRENCY):
        return "currency"
    if scale:
        return "scaled"
    digits = re.sub(r"\D", "", num)
    if len(digits) == 4 and any(2000 <= value <= 2099 for value in values):
        return "year"
    # Anos anteriores a 2000: conocimiento general, no dato de actualidad.
    if len(digits) == 4 and any(1900 <= value < 2000 for value in values):
        return ""
    if any(value >= 1000 and float(value).is_integer() for value in values):
        return "count"
    return ""


def extract_claims(text: str) -> List[Claim]:
    """Devuelve solo las cifras que merece la pena verificar."""
    claims: List[Claim] = []
    for match in _NUM_TOKEN_RE.finditer(text or ""):
        num = match.group("num") or ""
        scale = _fold(match.group("scale") or "")
        unit = _fold(match.group("unit") or "")
        base = _number_variants(num)
        if not base:
            continue
        multiplier = _SCALES.get(scale, 1.0)
        # Si hay escala (millones, millardos, etc.), solo usar la interpretacion
        # de miles (base[0]) para no crear falsos positivos como "1.200 millones"
        # = 1,2 millones coincidiendo con "1.200.000".
        if multiplier > 1.0:
            values = (round(base[0] * multiplier, 6),)
        else:
            values = tuple(round(value * multiplier, 6) for value in base)
        kind = _claim_kind(num, scale, unit, base)
        if not kind:
            continue
        claims.append(
            Claim(
                raw=match.group(0).strip(),
                values=values,
                kind=kind,
                start=match.start(),
                end=match.end(),
            )
        )
    return claims


# ---------------------------------------------------------------------------
# Contexto y comprobacion
# ---------------------------------------------------------------------------

def _context_values(context: str) -> Set[float]:
    """Todos los valores numericos que aparecen en el contexto."""
    values: Set[float] = set()
    text = context or ""
    for match in _NUMBER_RE.finditer(text):
        for value in _number_variants(match.group(0)):
            values.add(round(value, 6))
    for claim in extract_claims(text):
        for value in claim.values:
            values.add(round(value, 6))
    return values


def _matches(value: float, pool: Iterable[float]) -> bool:
    # Tolerancia relativa 1% para permitir redondeos razonables.
    # Suelo absoluto de 0.01 para cifras pequenas (precios).
    tolerance = max(1e-6, abs(value) * 1e-2, 0.01)
    return any(abs(value - known) <= tolerance for known in pool)


def _looks_complete(text: str) -> bool:
    """¿Queda una frase con sentido tras quitar la cifra?"""
    cleaned = (text or "").strip()
    if not cleaned or cleaned[-1] in ",;:":
        return False
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", cleaned)
    if len(words) < 4:
        return False
    return words[-1].lower() not in _STOPWORDS


def _strip_claims(sentence: str, claims: Sequence[Claim]) -> str:
    """Quita del texto solo los datos sin respaldo, no la frase entera.

    Se procesan de derecha a izquierda para que los desplazamientos no se
    invaliden. Ademas se retira el complemento inmediato ("de euros",
    "millones de personas") y, en los anos, la preposicion que los introduce.
    """
    cleaned = sentence
    for claim in sorted(claims, key=lambda item: item.start, reverse=True):
        start, end = claim.start, claim.end
        before, after = cleaned[:start], cleaned[end:]

        if claim.kind in ("scaled", "currency"):
            after = re.sub(
                r"^\s+(?:de\s+)?"
                r"(?:euros?|d[oó]lares?|dollars?|millones|millon|billones?|"
                r"personas?|people|habitantes?|users?|residents?)\b",
                "",
                after,
                flags=re.IGNORECASE,
            )
        if claim.kind == "year":
            before = re.sub(
                r"(?:,?\s*(?:\b(?:de|del|en|in|of)\b\s*)?)$",
                "",
                before,
                flags=re.IGNORECASE,
            )
        elif claim.kind in ("percent", "count"):
            before = re.sub(
                r"\b(?:un|una|unos|unas|about|around)\s+$",
                "",
                before,
                flags=re.IGNORECASE,
            )

        cleaned = before + after

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"^[,;:]\s*", "", cleaned)
    cleaned = cleaned.strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def filter_text(
    text: str,
    context: str,
    allowed: str = "",
    language: str = "es",
    hedges_left: int = 1,
    final: bool = False,
) -> Tuple[str, int, int, List[str]]:
    """Sustituye u omite frases con cifras que no estan en el contexto.

    Devuelve ``(texto_filtrado, avisos, frases_omitidas, cifras_detectadas)``.
    Una frase incompleta al final (streaming) se deja pasar sin tocar: se
    verificara cuando llegue su final.
    """
    if not text or not str(context or "").strip():
        return text, 0, 0, []

    pool = _context_values(str(context) + "\n" + str(allowed or ""))
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    kept: List[str] = []
    hedges = 0
    dropped = 0
    flagged: List[str] = []

    for index, sentence in enumerate(sentences):
        incomplete = (
            index == len(sentences) - 1
            and not final
            and not _TERMINAL_RE.search(sentence)
        )
        if incomplete:
            kept.append(sentence)
            continue

        bad = [
            claim
            for claim in extract_claims(sentence)
            if not any(_matches(value, pool) for value in claim.values)
        ]
        if not bad:
            kept.append(sentence)
            continue

        flagged.extend(claim.raw for claim in bad[:3])
        candidate = _strip_claims(sentence, bad)
        if _looks_complete(candidate):
            kept.append(candidate)
            continue

        if hedges < max(0, int(hedges_left)):
            kept.append(_HEDGE.get(language, _HEDGE["es"]))
            hedges += 1
        else:
            dropped += 1

    return " ".join(kept).strip(), hedges, dropped, flagged


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------

def _selftest() -> None:
    context = "El paro se situo en el 8,5 % en 2025 y el presupuesto es de 1.200 millones."
    clean = "El paro bajo al 8,5 % en 2025."
    result, hedges, dropped, flagged = filter_text(clean, context)
    assert result == clean, result
    assert (hedges, dropped, flagged) == (0, 0, [])

    result, hedges, dropped, flagged = filter_text(
        "El paro bajo al 12,7 %.", context
    )
    assert hedges == 1 and dropped == 0
    assert "12,7" not in result
    assert "no aparece" in result

    # Mismo valor con otro formato de miles.
    result, hedges, _, _ = filter_text(
        "El presupuesto es de 1200 millones.", context
    )
    assert result == "El presupuesto es de 1200 millones.", result

    # Dos frases sin respaldo: un aviso y una omitida.
    result, hedges, dropped, _ = filter_text(
        "Crecimos un 45 %. Tambien un 60 %.", context
    )
    assert hedges == 1 and dropped == 1, (result, hedges, dropped)

    # Frase incompleta: no se toca hasta que termine.
    result, hedges, _, _ = filter_text("Crecimos un 45", context)
    assert result == "Crecimos un 45" and hedges == 0

    # El ano de la pregunta no cuenta como inventado.
    result, hedges, _, _ = filter_text(
        "En 2026 subio todo.", "Sin cifras.", allowed="que paso en 2026"
    )
    assert hedges == 0, result

    # Los anos anteriores a 2000 son conocimiento general: no se vigilan.
    result, hedges, _, _ = filter_text("En 1989 cayo el Muro.", "Sin cifras.")
    assert result == "En 1989 cayo el Muro." and hedges == 0

    # Ingles.
    result, hedges, _, _ = filter_text(
        "It grew 45 %.", context, language="en"
    )
    assert hedges == 1 and "does not appear" in result

    # Sin contexto no se verifica nada.
    result, hedges, _, _ = filter_text("Crecimos un 45 %.", "")
    assert result == "Crecimos un 45 %." and hedges == 0

    print("fact_check: OK")


if __name__ == "__main__":
    _selftest()

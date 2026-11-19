#!/usr/bin/env python3
"""Estado persistente de Emma: idioma preferido y perfil de aprendizaje.

Dos archivos pequenos e independientes de la memoria de conversaciones:

  - ``emma_prefs.json``    -> preferencia de idioma ("en", "es" o null).
  - ``emma_learning.json`` -> errores detectados, retos y ejercicios.

El modulo no depende de voice_loop ni de los modelos de voz, asi que se puede
probar por separado:

    python emma_state.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PREFS_PATH = "emma_prefs.json"
LEARNING_PATH = "emma_learning.json"

MAX_RECENT_CORRECTIONS = 40
MAX_CHALLENGES = 25
MAX_EXERCISES = 40
MAX_NOTES = 40

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return (text or "").translate(replacements).lower()


def _write_json(path: str, data: Any) -> None:
    """Escritura atomica para no corromper el archivo si se cierra Emma."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except Exception as exc:
        print(f"[WARN] No se pudo guardar {path}: {exc}")


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except Exception as exc:
        print(f"[WARN] No se pudo leer {path}: {exc}")
        return default


# ---------------------------------------------------------------------------
# Preferencia de idioma
# ---------------------------------------------------------------------------

_DEFAULT_VOICE_PROFILE = "warm"
_DEFAULT_VOICE_SPEED = 0.95

_DEFAULT_PREFS: Dict[str, Any] = {
    "language_preference": None,  # "en", "es" o None (automatico)
    "voice_profile": _DEFAULT_VOICE_PROFILE,
    "voice_speed": _DEFAULT_VOICE_SPEED,
    "user_name": "",  # nombre con el que Emma se dirige al usuario
    "updated": "",
}

# Frases que piden cambiar de idioma. Se comparan sin tildes y en minusculas.
_EN_PHRASES = (
    "speak english", "speak in english", "talk in english", "in english please",
    "english please", "only english", "english only", "no spanish",
    "without spanish", "stop speaking spanish", "stop talking spanish",
    "don't speak spanish", "do not speak spanish", "don't talk in spanish",
    "do not talk in spanish", "switch to english", "let's speak english",
    "let's speak in english", "lets speak english", "lets speak in english",
    "we speak english", "can we speak english", "can we talk in english",
    "could we speak english", "answer in english", "reply in english",
    "respond in english", "i want to speak english", "i want to talk in english",
    "i want to practice english", "practice english", "practise english",
    "habla en ingles", "hablame en ingles", "hablemos en ingles",
    "hablar en ingles", "conversar en ingles", "en ingles por favor",
    "solo ingles", "no hables espanol", "no me hables en espanol",
    "sin espanol", "cambia a ingles", "responde en ingles",
    "contestame en ingles", "quiero hablar en ingles",
    "quiero practicar ingles", "practiquemos ingles", "practicar ingles",
    "di todo en ingles", "a partir de ahora en ingles",
    "back to english", "return to english", "switch back to english",
    "english voice", "your english voice", "speak english again",
    "english again", "en ingles otra vez", "voz en ingles", "voz inglesa",
    "tu voz en ingles",
)
_ES_PHRASES = (
    "speak spanish", "speak in spanish", "talk in spanish", "in spanish please",
    "spanish please", "only spanish", "spanish only", "no english",
    "without english", "stop speaking english", "don't speak english",
    "do not speak english", "switch to spanish", "let's speak spanish",
    "let's speak in spanish", "lets speak spanish", "answer in spanish",
    "reply in spanish", "respond in spanish", "i want to speak spanish",
    "i want to talk in spanish", "habla en espanol", "hablame en espanol",
    "hablemos en espanol", "hablar en espanol", "conversar en espanol",
    "en espanol por favor", "solo espanol", "no hables ingles",
    "no me hables en ingles", "sin ingles", "cambia a espanol",
    "responde en espanol", "contestame en espanol", "quiero hablar en espanol",
    "di todo en espanol", "a partir de ahora en espanol",
    "back to spanish", "return to spanish", "switch back to spanish",
    "spanish voice", "your spanish voice", "speak spanish again",
    "spanish again", "en espanol otra vez", "voz en espanol", "voz espanola",
    "tu voz en espanol",
)

# "no quiero oir ni una palabra en espanol" / "I don't want any Spanish".
# La negacion debe preceder al idioma y quedar cerca (max. 6 palabras): asi
# "why don't you just get back to your first voice? English voice" no se
# confunde con una peticion de espanol.
_NEG_SPANISH_RE = re.compile(
    r"\b(no|not|don'?t|do not|stop|quit|never|without)\b"
    r"(?:\s+\w+){0,6}\s+(spanish|espanol)\b",
    re.IGNORECASE,
)
_NEG_ENGLISH_RE = re.compile(
    r"\b(no|not|don'?t|do not|stop|quit|never|without)\b"
    r"(?:\s+\w+){0,6}\s+(english|ingles)\b",
    re.IGNORECASE,
)


def detect_language_request(text: str) -> Optional[str]:
    """Devuelve 'en' o 'es' si el usuario pide cambiar de idioma.

    Es deliberadamente conservador: ante la duda devuelve None y Emma sigue
    con la preferencia que ya tuviera.
    """
    if not text or not text.strip():
        return None
    norm = _norm(text)

    # 1) Negaciones directas ("no me hables en espanol", "no Spanish").
    #    Solo en mensajes cortos y sin interrogacion: una pregunta del tipo
    #    "why don't you ... English voice?" es una queja, no una orden de
    #    cambiar a espanol.
    if "?" not in norm and len(norm.split()) <= 14:
        if _NEG_SPANISH_RE.search(norm):
            return "en"
        if _NEG_ENGLISH_RE.search(norm):
            return "es"

    # 2) Frases hechas (positivas o negativas ya listadas).
    for phrase in _EN_PHRASES:
        if phrase in norm:
            return "en"
    for phrase in _ES_PHRASES:
        if phrase in norm:
            return "es"
    return None


def load_prefs() -> Dict[str, Any]:
    prefs = dict(_DEFAULT_PREFS)
    data = _read_json(PREFS_PATH, {})
    if isinstance(data, dict):
        prefs.update(data)
    preference = prefs.get("language_preference")
    if preference not in ("en", "es", None):
        preference = None
    prefs["language_preference"] = preference

    profile = prefs.get("voice_profile")
    if profile not in VOICE_PROFILE_IDS:
        profile = _DEFAULT_VOICE_PROFILE
    prefs["voice_profile"] = profile
    try:
        speed = float(prefs.get("voice_speed", _DEFAULT_VOICE_SPEED))
    except (TypeError, ValueError):
        speed = _DEFAULT_VOICE_SPEED
    prefs["voice_speed"] = max(0.80, min(1.15, speed))
    return prefs


def save_prefs(prefs: Dict[str, Any]) -> None:
    prefs["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(PREFS_PATH, prefs)


def get_language_preference() -> Optional[str]:
    return load_prefs().get("language_preference")


def set_language_preference(language: Optional[str]) -> Dict[str, Any]:
    prefs = load_prefs()
    prefs["language_preference"] = language if language in ("en", "es") else None
    save_prefs(prefs)
    return prefs


# ---------------------------------------------------------------------------
# Nombre del usuario
# ---------------------------------------------------------------------------

def _sqlite_user_name() -> Optional[str]:
    """Lee el nombre de SQLite. Devuelve None si no se puede consultar."""
    try:
        import emma_memory
        return str(emma_memory.get_user_name() or "").strip()
    except Exception as exc:
        print(f"[WARN] No se pudo leer el nombre de SQLite: {exc}")
        return None


def get_user_name() -> Optional[str]:
    """Devuelve el nombre con el que Emma se dirige al usuario (o None).

    SQLite es la unica fuente de verdad.
    """
    name = _sqlite_user_name()
    if name and is_plausible_name(name):
        return name
    return None


def set_user_name(name: str) -> Optional[str]:
    """Guarda el nombre declarado por el usuario ("Me llamo Airman").

    Persiste en SQLite (fuente unica).
    """
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip().strip(" .,!?¿¡'\"")
    if not is_plausible_name(cleaned):
        return get_user_name()

    saved = ""
    try:
        import emma_memory
        saved = str(emma_memory.set_user_name(cleaned) or "").strip()
    except Exception as exc:
        print(f"[WARN] No se pudo guardar el nombre en SQLite: {exc}")

    return saved if saved else None


def clear_user_name() -> None:
    """Olvida el nombre guardado (p. ej. tras una correccion del usuario)."""
    try:
        import emma_memory
        emma_memory.clear_user_name()
    except Exception as exc:
        print(f"[WARN] No se pudo borrar el nombre de SQLite: {exc}")


# Palabras que nunca son un nombre: evitan guardar "not", "fine", "sorry"...
_NAME_STOPWORDS = {
    # ingles
    "a", "an", "the", "and", "or", "but", "if", "so", "to", "of", "in", "on",
    "at", "by", "for", "with", "from", "up", "down", "out", "off", "over",
    "not", "no", "yes", "yeah", "yep", "nope", "ok", "okay", "sure", "right",
    "wrong", "good", "bad", "fine", "great", "nice", "happy", "sad", "tired",
    "angry", "hungry", "busy", "ready", "done", "here", "there", "where",
    "when", "what", "why", "how", "who", "which", "this", "that", "these",
    "those", "it", "its", "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "have", "has", "had", "can", "could", "will",
    "would", "should", "may", "might", "must", "my", "your", "his", "her",
    "our", "their", "me", "you", "him", "us", "them", "i", "we", "they",
    "she", "he", "please", "thanks", "thank", "sorry", "hello", "hi", "hey",
    "bye", "goodbye", "now", "later", "again", "back", "still", "just",
    "only", "also", "too", "very", "really", "much", "more", "less", "all",
    "any", "some", "none", "never", "always", "sometimes", "maybe", "today",
    "tomorrow", "yesterday", "morning", "night", "emma", "assistant", "bot",
    "testing", "test", "joking", "kidding", "serious", "listening", "talking",
    # espanol
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "pero", "si", "sí", "que", "qué", "como", "cómo", "cuando",
    "cuándo", "donde", "dónde", "por", "para", "con", "sin", "muy", "mas",
    "más", "menos", "todo", "todos", "nada", "algo", "bien", "mal", "asi",
    "así", "vale", "bueno", "buena", "gracias", "hola", "adios", "adiós",
    "hasta", "luego", "ahora", "despues", "después", "otra", "vez", "tambien",
    "también", "solo", "sólo", "estoy", "eres", "soy", "es", "son", "esta",
    "está", "este", "esto", "eso", "esa", "ese", "mi", "mis", "tu", "tus",
    "su", "sus", "yo", "tú", "él", "ella", "nosotros", "ellos", "ellas",
    "no", "nunca", "siempre", "quizá", "quizás", "hoy", "mañana", "ayer",
    "noche", "dia", "día", "casa", "trabajo", "cansado", "cansada", "feliz",
    "triste", "enfadado", "enfadada", "contento", "contenta", "listo",
    "lista", "probando", "prueba", "broma", "bromas", "en serio",
}

# Expresiones que indican que el usuario esta corrigiendo el nombre guardado.
_NAME_NEGATION_PREFIX = re.compile(
    r"\b(?:why|who|what|how|when|where|not|never|don'?t|doesn'?t|isn'?t|"
    r"aren'?t|wrong)\b[^.!?]{0,24}$",
    re.IGNORECASE,
)


def is_plausible_name(candidate: str) -> bool:
    """True si la palabra parece un nombre propio y no una palabra comun."""
    text = str(candidate or "").strip().strip(" .,!?¿¡'\"")
    if not (2 <= len(text) <= 30):
        return False
    if text.isdigit():
        return False
    if text.lower() in _NAME_STOPWORDS:
        return False
    # Solo letras, espacios, guiones y apostrofes (nombres compuestos).
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' -]+", text):
        return False
    # Al menos una letra real; descarta signos sueltos.
    if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", text):
        return False
    return True


def detect_name_correction(text: str) -> Optional[str]:
    """Detecta que el usuario corrige el nombre que Emma tenia guardado.

    Devuelve ``"clear"`` cuando hay que olvidar el nombre actual.
    """
    if not text or not str(text).strip():
        return None
    t = str(text).lower()

    if re.search(r"\b(?:that'?s|that is|is|it'?s|it is)\s+not\s+my\s+name\b", t):
        return "clear"
    if re.search(r"\bno\s+(?:es|era)\s+mi\s+nombre\b", t):
        return "clear"
    if re.search(r"\byou(?:'re| are)?\s+(?:calling|call)\s+me\s+(?:wrong|bad)\b", t):
        return "clear"

    match = re.search(
        r"\b(?:no me llamo|my name is not|i'?m not|i am not|no soy)\s+"
        r"([a-záéíóúüñ][a-záéíóúüñ' -]{1,30})",
        t,
    )
    if match:
        other = match.group(1).strip().split()[0].strip(".,!?¿¡")
        stored = get_user_name()
        if stored and other and other.lower() == stored.lower():
            return "clear"
    return None



_USER_NAME_PATTERNS: List[tuple] = [
    # Español
    (re.compile(r"\bmi nombre es\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bme llamo\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bmi apodo es\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bsoy\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    # Inglés
    (re.compile(r"\bmy name is\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bthe name is\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bi am\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bi['’]m\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bcall me\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\byou can call me\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bthis is\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
    (re.compile(r"\bname['’]s\s+([a-záéíóúüñ]{2,})", re.IGNORECASE), False),
]


def detect_user_name(text: str) -> Optional[str]:
    """Detecta el nombre propio que el usuario acaba de declarar.

    Devuelve None si no se reconoce ninguna candidata razonable.
    """
    if not text or not text.strip():
        return None
    raw = str(text)
    for pattern, _unused in _USER_NAME_PATTERNS:
        for match in pattern.finditer(raw):
            # "why you call me not" / "don't call me Alex": no es una declaracion.
            prefix = raw[max(0, match.start() - 34):match.start()]
            if _NAME_NEGATION_PREFIX.search(prefix):
                continue
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?¿¡'\"")
            if is_plausible_name(candidate):
                return candidate
    return None


# ---------------------------------------------------------------------------
# Preferencia de voz
# ---------------------------------------------------------------------------

# Catalogo de voces Kokoro v1.0. ``en`` y ``es`` son los identificadores que
# entiende Kokoro. El perfil "warm" (af_heart) es la voz mas natural y calida
# del modelo; el resto son alternativas para cuando el usuario pide cambiarla.
VOICE_PROFILES: List[Dict[str, str]] = [
    {
        "id": "warm",
        "en": "af_heart",
        "es": "ef_dora",
        "label_en": "warm and friendly",
        "label_es": "cálida y cercana",
    },
    {
        "id": "soft",
        "en": "af_nicole",
        "es": "ef_dora",
        "label_en": "soft and calm",
        "label_es": "suave y tranquila",
    },
    {
        "id": "bright",
        "en": "af_bella",
        "es": "ef_dora",
        "label_en": "bright and expressive",
        "label_es": "brillante y expresiva",
    },
    {
        "id": "british",
        "en": "bf_emma",
        "es": "ef_dora",
        "label_en": "British and elegant",
        "label_es": "británica y elegante",
    },
    {
        "id": "male",
        "en": "am_michael",
        "es": "em_alex",
        "label_en": "calm male",
        "label_es": "masculina y serena",
    },
    {
        "id": "male_deep",
        "en": "am_onyx",
        "es": "em_santa",
        "label_en": "deep male",
        "label_es": "masculina y grave",
    },
]

VOICE_PROFILE_IDS = tuple(profile["id"] for profile in VOICE_PROFILES)
VOICE_PROFILE_INDEX = {profile["id"]: profile for profile in VOICE_PROFILES}

# En español solo existen tres voces Kokoro (ef_dora, em_alex, em_santa), asi
# que el ciclo en español salta los perfiles que comparten la misma voz.
_VOICE_CYCLE_ES = ("warm", "male", "male_deep")

# Ciclo solo de voces femeninas (en ingles son distintas; en espanol suenan igual).
_VOICE_CYCLE_FEMALE = ("warm", "soft", "bright", "british")

# Frases que piden cambiar de voz. Se comparan sin tildes y en minusculas.
_VOICE_DISLIKE = (
    "no me gusta tu voz", "no me gusta esta voz", "no me gusta la voz",
    "no me gusta como suenas", "no me gusta cómo suenas",
    "i don't like your voice", "i don't like this voice",
    "i do not like your voice", "i do not like this voice",
    "not this voice", "no me convence la voz",
)
# Prohibiciones: "no quiero que cambies de voz" contiene "cambies de voz";
# se comprueban antes que cualquier peticion de cambio.
_VOICE_KEEP = (
    "no cambies de voz", "no cambies tu voz", "no cambies la voz",
    "no quiero que cambies de voz", "no quiero que cambies tu voz",
    "no quiero que cambies la voz", "no quiero cambiar de voz",
    "no quiero otra voz", "no quiero que cambies", "deja tu voz",
    "deja la voz como esta", "manten tu voz", "manten la voz",
    "don't change your voice", "do not change your voice",
    "don't change the voice", "i don't want you to change your voice",
    "i don't want to change your voice", "keep your voice",
    "keep the voice", "leave your voice alone",
)
_VOICE_NEXT = (
    "otra voz", "voz diferente", "cambia tu voz", "cambia de voz",
    "cambiar tu voz", "cambiar de voz", "cambiate la voz",
    "cambies de voz", "cambies tu voz", "quiero que cambies de voz",
    "puedes cambiar tu voz", "podrias cambiar tu voz",
    "quiero otra voz", "prueba otra voz", "prueba con otra voz",
    "pon otra voz", "usa otra voz", "cambia la voz", "otra voz por favor",
    "change your voice", "change voice", "change the voice", "another voice",
    "different voice", "try another voice", "try a different voice",
    "new voice", "switch voices", "switch your voice",
)
_VOICE_LIKE = (
    "me gusta esta voz", "me gusta tu voz", "esta voz me gusta",
    "quedate con esta voz", "quédate con esta voz",
    "i like this voice", "i like your voice", "this voice is good",
    "this voice is nice", "keep this voice", "i love this voice",
)
_VOICE_RESET = (
    "voz normal", "voz por defecto", "voz de siempre", "vuelve a tu voz",
    "vuelve a tu voz normal", "reset your voice", "default voice",
    "normal voice", "go back to your normal voice",
)
_VOICE_NATURAL = (
    "voz mas natural", "voz más natural", "voz mas humana", "voz más humana",
    "voz mas empatica", "voz más empática", "voz mas calida",
    "voz más cálida", "voz robotica", "voz robótica", "suenas robotica",
    "suenas robótica", "suena robotica", "suena robótica",
    "suenas mas humana", "suenas más humana", "hablas mas humana",
    "hablas más humana", "como una persona real", "voz de persona",
    "more natural voice", "more human voice", "more empathetic voice",
    "empathetic voice", "human voice", "natural voice", "robotic voice",
    "sound robotic", "you sound robotic", "like a real person",
)
_VOICE_SLOWER = (
    "habla mas despacio", "habla más despacio", "mas despacio", "más despacio",
    "mas lento", "más lento", "voz mas lenta", "voz más lenta",
    "baja la velocidad", "slow down", "speak slower", "slower",
)
_VOICE_FASTER = (
    "habla mas rapido", "habla más rápido", "mas rapido", "más rápido",
    "voz mas rapida", "voz más rápida", "sube la velocidad",
    "speed up", "speak faster", "faster",
)
_VOICE_SPECIFIC = (
    ("male_deep", ("voz grave", "voz mas grave", "voz más grave", "deep voice", "deeper voice")),
    ("warm", ("voz de mujer", "voz femenina", "female voice", "woman's voice", "feminine voice")),
    ("male", (
        "voz de hombre", "voz masculina", "voz de chico", "male voice",
        "man's voice", "masculine voice",
    )),
    ("british", (
        "voz britanica", "voz británica", "acento britanico", "acento británico",
        "british voice", "british accent",
    )),
    ("soft", ("voz suave", "voz tranquila", "soft voice", "calm voice")),
    ("bright", (
        "voz alegre", "voz brillante", "voz expresiva", "bright voice",
        "cheerful voice", "expressive voice",
    )),
    ("warm", (
        "voz calida", "voz cálida", "voz cercana", "warm voice", "warmer voice",
    )),
)


def get_voice_profile(profile_id: Optional[str] = None) -> Dict[str, str]:
    if not profile_id:
        profile_id = load_prefs().get("voice_profile")
    return VOICE_PROFILE_INDEX.get(profile_id or "", VOICE_PROFILE_INDEX[_DEFAULT_VOICE_PROFILE])


def get_voice_prefs() -> Dict[str, Any]:
    """Devuelve el perfil y la velocidad activos, listos para el TTS."""
    prefs = load_prefs()
    profile = get_voice_profile(prefs["voice_profile"])
    return {
        "profile": profile["id"],
        "voice_en": profile["en"],
        "voice_es": profile["es"],
        "speed": float(prefs["voice_speed"]),
    }


def set_voice_profile(profile_id: str) -> Dict[str, Any]:
    prefs = load_prefs()
    if profile_id in VOICE_PROFILE_IDS:
        prefs["voice_profile"] = profile_id
        save_prefs(prefs)
    return get_voice_prefs()


def cycle_voice_profile(step: int = 1, language: Optional[str] = None) -> Dict[str, Any]:
    """Pasa al siguiente perfil de voz.

    En español se limita a los perfiles que suenan distinto (ef_dora, em_alex,
    em_santa) para que "otra voz" siempre cambie algo audible. En inglés
    recorre los seis perfiles.
    """
    prefs = load_prefs()
    if str(language or "").lower().startswith("es"):
        order = _VOICE_CYCLE_ES
        current_voice = get_voice_profile(prefs["voice_profile"])["es"]
        current = order[0]
        for profile_id in order:
            if VOICE_PROFILE_INDEX[profile_id]["es"] == current_voice:
                current = profile_id
                break
        index = order.index(current)
    else:
        order = VOICE_PROFILE_IDS
        current = prefs["voice_profile"] if prefs["voice_profile"] in order else order[0]
        index = order.index(current)
    new_profile = order[(index + step) % len(order)]
    return set_voice_profile(new_profile)


def cycle_female_voice_profile(step: int = 1, language: Optional[str] = None) -> Dict[str, Any]:
    """Pasa a la siguiente voz femenina.
    
    En inglés recorre: warm -> soft -> bright -> british.
    En español todas usan ef_dora, así que avisa pero no cambia el sonido.
    """
    prefs = load_prefs()
    order = _VOICE_CYCLE_FEMALE
    current = prefs["voice_profile"] if prefs["voice_profile"] in order else order[0]
    index = order.index(current)
    new_profile = order[(index + step) % len(order)]
    return set_voice_profile(new_profile)


def set_voice_speed(speed: float) -> Dict[str, Any]:
    prefs = load_prefs()
    try:
        prefs["voice_speed"] = max(0.80, min(1.15, float(speed)))
    except (TypeError, ValueError):
        prefs["voice_speed"] = _DEFAULT_VOICE_SPEED
    save_prefs(prefs)
    return get_voice_prefs()


def reset_voice_prefs() -> Dict[str, Any]:
    """Vuelve al perfil y la velocidad de fabrica."""
    prefs = load_prefs()
    prefs["voice_profile"] = _DEFAULT_VOICE_PROFILE
    prefs["voice_speed"] = _DEFAULT_VOICE_SPEED
    save_prefs(prefs)
    return get_voice_prefs()


def voice_profile_label(profile_id: Optional[str], language: str = "es") -> str:
    profile = get_voice_profile(profile_id)
    key = "label_en" if str(language).lower().startswith("en") else "label_es"
    return profile.get(key, profile["label_es"])


# 5b) Ciclo solo de voces femeninas (antes que perfiles concretos para
# evitar que "female voices only" coincida con "female voice" de warm).
_VOICE_FEMALE_CYCLE = (
    "cambia entre voces femeninas", "solo voces femeninas", "voces femeninas",
    "female voices only", "cycle female voices", "only female voices",
    "cambia de voz femenina", "siguiente voz femenina",
)

def detect_voice_request(text: str) -> Optional[Dict[str, str]]:
    """Detecta peticiones sobre la voz de Emma.

    Devuelve ``{"action": ...}`` o ``None``. Las acciones son ``next``,
    ``like``, ``natural``, ``reset``, ``slow``, ``fast``, ``cycle_female`` y ``set`` (con
    ``profile``). Es conservador para no cambiar la voz por frases sueltas.
    """
    if not text or not text.strip():
        return None
    norm = _norm(text)

    # 0) Prohibiciones ("no quiero que cambies de voz"): no es una peticion.
    if any(phrase in norm for phrase in _VOICE_KEEP):
        return None

    # 1) Negativas: "no me gusta tu voz" tambien contiene "me gusta tu voz".
    if any(phrase in norm for phrase in _VOICE_DISLIKE):
        return {"action": "next"}

    # 1b) Ciclo solo de voces femeninas (antes que perfiles concretos).
    if any(phrase in norm for phrase in _VOICE_FEMALE_CYCLE):
        return {"action": "cycle_female"}

    # 2) Perfiles concretos ("voz de hombre", "acento britanico").
    for profile_id, phrases in _VOICE_SPECIFIC:
        if any(phrase in norm for phrase in phrases):
            return {"action": "set", "profile": profile_id}

    # 3) Le gusta la voz actual: no cambiar nada.
    if any(phrase in norm for phrase in _VOICE_LIKE):
        return {"action": "like"}

    # 4) Volver a la voz por defecto.
    if any(phrase in norm for phrase in _VOICE_RESET):
        return {"action": "reset"}

    # 5) Mas natural / humana / menos robotica.
    if any(phrase in norm for phrase in _VOICE_NATURAL):
        return {"action": "natural"}

    # 6) Otra voz / cambiar de voz.
    if any(phrase in norm for phrase in _VOICE_NEXT):
        return {"action": "next"}

    # 7) Velocidad de habla.
    if any(phrase in norm for phrase in _VOICE_SLOWER):
        return {"action": "slow"}
    if any(phrase in norm for phrase in _VOICE_FASTER):
        return {"action": "fast"}

    return None



# ---------------------------------------------------------------------------
# Perfil de aprendizaje
# ---------------------------------------------------------------------------

def _empty_learning() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated": "",
        "totals": {"turns": 0, "corrections": 0, "by_type": {}},
        "recent_corrections": [],
        "by_pattern": {},
        "challenges": [],
        "exercises": [],
        "focus": [],
        "notes": [],
    }


def load_learning() -> Dict[str, Any]:
    profile = _empty_learning()
    data = _read_json(LEARNING_PATH, {})
    if not isinstance(data, dict):
        return profile
    profile.update({k: v for k, v in data.items() if v is not None})
    # Asegurar la forma esperada aunque el archivo venga de una version vieja.
    if not isinstance(profile.get("totals"), dict):
        profile["totals"] = {"turns": 0, "corrections": 0, "by_type": {}}
    profile["totals"].setdefault("turns", 0)
    profile["totals"].setdefault("corrections", 0)
    profile["totals"].setdefault("by_type", {})
    for key in ("recent_corrections", "challenges", "exercises", "focus", "notes"):
        if not isinstance(profile.get(key), list):
            profile[key] = []
    if not isinstance(profile.get("by_pattern"), dict):
        profile["by_pattern"] = {}
    return profile


def save_learning(profile: Dict[str, Any]) -> None:
    profile["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(LEARNING_PATH, profile)


def _trim(items: List[Any], limit: int) -> List[Any]:
    return items[:limit] if len(items) > limit else items


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_latin_text(text: str) -> bool:
    """False si el texto contiene letras de otro alfabeto (griego, cirilico...)."""
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        if "a" <= char.lower() <= "z" or 0x00C0 <= code <= 0x024F:
            continue
        return False
    return True


def _shares_words(original: str, user_text: str) -> bool:
    """Comprueba que la correccion se refiere a algo que dijo el usuario."""
    if not user_text:
        return True
    tokens = re.findall(r"[a-z0-9']+", _norm(original))
    if not tokens:
        return False
    user_tokens = set(re.findall(r"[a-z0-9']+", _norm(user_text)))
    if len(tokens) >= 3:
        matches = sum(1 for token in tokens if token in user_tokens)
        return matches / len(tokens) >= 0.4
    return all(token in user_tokens for token in tokens)


_FIRST_PERSON_MARKERS = {"i", "we", "my", "our", "me", "us"}
_SECOND_PERSON_MARKERS = {"you", "your", "yours"}


def _changes_person(original: str, corrected: str) -> bool:
    """True si la correccion cambia al usuario por 'you' (I -> you).

    El modelo a veces reescribe la frase dirigiendose al usuario en vez de
    corregirla en primera persona. Esas correcciones no sirven para el perfil.
    """
    if not original or not corrected:
        return False
    original_words = set(re.findall(r"[a-z']+", _norm(original)))
    corrected_words = set(re.findall(r"[a-z']+", _norm(corrected)))
    return bool(original_words & _FIRST_PERSON_MARKERS) and bool(
        corrected_words & _SECOND_PERSON_MARKERS
    )


def record_turn(
    profile: Dict[str, Any],
    corrections: Optional[List[Dict[str, Any]]] = None,
    learning: Optional[Dict[str, Any]] = None,
    user_text: str = "",
    assistant_text: str = "",
) -> Dict[str, Any]:
    """Actualiza el perfil con lo observado en un turno.

    ``learning`` es el bloque opcional que devuelve el LLM con el foco, el
    reto y el ejercicio propuestos en ese turno.
    """
    corrections = corrections or []
    learning = learning or {}
    stamp = time.strftime("%Y-%m-%d %H:%M")

    profile["totals"]["turns"] = int(profile["totals"].get("turns", 0)) + 1
    by_type = profile["totals"].setdefault("by_type", {})
    rejected = 0

    # El modelo a veces devuelve la frase completa y ademas un fragmento de la
    # misma frase con otra correccion. Se conserva solo la correccion mas
    # amplia para no duplicar ni contaminar el perfil.
    normalized_corrections = []
    for correction in corrections:
        if isinstance(correction, dict):
            original = _norm(str(correction.get("original") or "")).strip()
            normalized_corrections.append((correction, original))
    filtered_corrections = []
    for index, (correction, original) in enumerate(normalized_corrections):
        covered = False
        if original:
            covered = any(
                len(original) < len(other_original) and original in other_original
                for other_index, (_, other_original) in enumerate(normalized_corrections)
                if other_index != index
            )
        if not covered:
            filtered_corrections.append(correction)
    corrections = filtered_corrections

    for correction in corrections:
        if not isinstance(correction, dict):
            continue
        original = str(correction.get("original") or "").strip()
        corrected = str(correction.get("corrected") or "").strip()
        if not original and not corrected:
            continue
        # El modelo a veces inventa correcciones de otro idioma que el usuario
        # nunca dijo. Se descartan antes de contaminar el perfil.
        if not _is_latin_text(original) or not _shares_words(original, user_text):
            rejected += 1
            continue
        if _changes_person(original, corrected):
            rejected += 1
            continue
        ctype = str(correction.get("type") or "grammar").strip().lower()
        if ctype not in ("grammar", "vocabulary", "pronunciation"):
            ctype = "grammar"
        # Si el modelo devuelve "original" igual a "corrected" no es un error.
        if original and corrected and _norm(original) == _norm(corrected):
            continue
        by_type[ctype] = int(by_type.get(ctype, 0)) + 1
        profile["totals"]["corrections"] = int(
            profile["totals"].get("corrections", 0)
        ) + 1

        pattern = f"{original} -> {corrected}" if original and corrected else (original or corrected)
        pattern = re.sub(r"\s+", " ", pattern)[:90]
        counts = profile.setdefault("by_pattern", {})
        counts[pattern] = int(counts.get(pattern, 0)) + 1
        profile["recent_corrections"].insert(
            0,
            {
                "date": stamp,
                "original": original,
                "corrected": corrected,
                "type": ctype,
                "explanation": str(correction.get("explanation") or "").strip(),
            },
        )

    focus = _as_list(learning.get("focus"))
    challenge = str(learning.get("challenge") or "").strip()
    exercise = str(learning.get("exercise") or "").strip()
    focus = [item for item in focus if _is_latin_text(item)]
    if not _is_latin_text(challenge):
        challenge = ""
        exercise = ""
    if not _is_latin_text(exercise):
        exercise = ""

    if rejected:
        profile["totals"]["rejected"] = int(profile["totals"].get("rejected", 0)) + rejected

    if challenge:
        recent_challenges = [
            str(item.get("text") or "")
            for item in profile["challenges"][:5]
            if isinstance(item, dict)
        ]
        if challenge not in recent_challenges:
            profile["challenges"].insert(0, {"date": stamp, "text": challenge})
    if exercise:
        recent_exercises = [
            str(item.get("text") or "")
            for item in profile["exercises"][:5]
            if isinstance(item, dict)
        ]
        if exercise not in recent_exercises:
            profile["exercises"].insert(0, {"date": stamp, "text": exercise})
    if focus:
        existing = profile.get("focus") or []
        merged: List[str] = []
        for item in focus + existing:
            if item and item not in merged:
                merged.append(item)
        profile["focus"] = merged[:12]

    # Recalcular los patrones que mas se repiten.
    counts = profile.get("by_pattern") or {}
    top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    profile["focus"] = [pattern for pattern, count in top if count >= 2] or profile.get("focus", [])[:5]

    profile["recent_corrections"] = _trim(
        profile["recent_corrections"], MAX_RECENT_CORRECTIONS
    )
    profile["challenges"] = _trim(profile["challenges"], MAX_CHALLENGES)
    profile["exercises"] = _trim(profile["exercises"], MAX_EXERCISES)
    profile["notes"] = _trim(profile["notes"], MAX_NOTES)
    save_learning(profile)
    return profile


def _count_by_type(by_type: Dict[str, Any]) -> str:
    labels = {"grammar": "gramática", "vocabulary": "vocabulario", "pronunciation": "pronunciación"}
    parts = []
    for key in ("grammar", "vocabulary", "pronunciation"):
        count = int(by_type.get(key, 0) or 0)
        if count:
            parts.append(f"{labels[key]} {count}")
    return ", ".join(parts) if parts else "sin datos"


def build_learning_block(profile: Optional[Dict[str, Any]] = None, max_chars: int = 800) -> str:
    """Resumen compacto del perfil para inyectar en el prompt del LLM."""
    profile = profile if profile is not None else load_learning()
    totals = profile.get("totals") or {}
    turns = int(totals.get("turns", 0) or 0)
    if turns <= 0:
        return ""

    lines = ["PERFIL DE APRENDIZAJE DEL USUARIO (datos reales de sus conversaciones):"]
    lines.append(
        f"- Turnos observados: {turns}. Correcciones: "
        f"{int(totals.get('corrections', 0) or 0)} ({_count_by_type(totals.get('by_type') or {})})."
    )

    focus = [str(item) for item in (profile.get("focus") or []) if str(item).strip()][:4]
    if focus:
        lines.append("- Errores que más se repiten: " + "; ".join(focus))

    recent = [
        item for item in (profile.get("recent_corrections") or [])
        if isinstance(item, dict) and (item.get("original") or item.get("corrected"))
    ][:3]
    if recent:
        samples = []
        for item in recent:
            original = item.get("original") or ""
            corrected = item.get("corrected") or ""
            samples.append(f"{original} -> {corrected}" if original and corrected else (original or corrected))
        lines.append("- Últimos errores: " + "; ".join(samples))

    challenges = [
        item.get("text") for item in (profile.get("challenges") or [])
        if isinstance(item, dict) and item.get("text")
    ][:2]
    if challenges:
        lines.append("- Retos recientes: " + "; ".join(challenges))

    exercises = [
        item.get("text") for item in (profile.get("exercises") or [])
        if isinstance(item, dict) and item.get("text")
    ][:2]
    if exercises:
        lines.append("- Ejercicios recientes: " + "; ".join(exercises))

    lines.append(
        "- Adapta las preguntas a estos puntos y propone un reto corto cuando encaje. "
        "No repitas siempre el mismo ejercicio."
    )
    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[: max_chars - 3].rstrip() + "..."
    return block


def learning_summary(profile: Optional[Dict[str, Any]] = None, language: str = "es") -> str:
    """Frase corta de progreso, util para '¿cómo voy?' sin pasar por el LLM."""
    profile = profile if profile is not None else load_learning()
    totals = profile.get("totals") or {}
    turns = int(totals.get("turns", 0) or 0)
    corrections = int(totals.get("corrections", 0) or 0)
    if turns <= 0:
        return (
            "Todavía no tengo datos suficientes. Habla conmigo un rato y iré "
            "anotando tus errores y retos."
            if language != "en"
            else "I don't have enough data yet. Talk to me for a while and I'll track your mistakes and challenges."
        )

    focus = [str(item) for item in (profile.get("focus") or []) if str(item).strip()][:2]
    if language == "en":
        summary = f"We've had {turns} turns and I've noted {corrections} corrections."
        if focus:
            summary += " The patterns to review are: " + "; ".join(focus) + "."
        summary += " Keep practising a little every day."
        return summary

    summary = f"Llevamos {turns} turnos y he anotado {corrections} correcciones."
    if focus:
        summary += " Los puntos que más se repiten son: " + "; ".join(focus) + "."
    summary += " Sigue practicando un poco cada día."
    return summary


_RECALL_STOPWORDS = {
    "para", "como", "cuando", "donde", "porque", "sobre", "entre", "desde",
    "hasta", "tiene", "tengo", "puedo", "quiero", "sabes", "dime", "hazme",
    "what", "when", "where", "which", "about", "with", "from", "that",
    "this", "have", "does", "tell", "give", "please", "would", "could",
    "should", "there", "their", "your", "mine", "will", "just", "like",
}


def recall_memories(
    query: str, memoria: List[Dict[str, Any]], limit: int = 2
) -> List[str]:
    """Recupera turnos antiguos que comparten palabras clave con la pregunta.

    Devuelve lineas listas para inyectar en el prompt; nunca inventa datos.
    """
    if not memoria:
        return []
    raw = str(query or "")
    tokens = {
        t for t in re.findall(r"[a-záéíóúüñ]{4,}", raw.lower())
        if t not in _RECALL_STOPWORDS
    }
    if not tokens:
        return []

    # Nombres propios mencionados ("Victor", "Madrid"): valen por si solos.
    proper = {
        w.lower()
        for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]{2,}\b", raw)
    }
    first_word = re.match(r"\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", raw)
    if first_word:
        proper.discard(first_word.group(1).lower())

    scored = []
    for entry in list(memoria)[-300:]:
        blob = " ".join(
            str(entry.get(key) or "") for key in ("usuario", "asistente")
        ).lower()
        score = sum(1 for token in tokens if token in blob)
        has_proper = any(name in blob for name in proper)
        if score >= 2 or (score >= 1 and has_proper):
            scored.append((score + (2 if has_proper else 0), entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    lines: List[str] = []
    seen = set()
    for _score, entry in scored:
        user_text = " ".join(str(entry.get("usuario") or "").split())[:140]
        assistant_text = " ".join(str(entry.get("asistente") or "").split())[:140]
        key = (user_text.lower(), assistant_text.lower())
        if not user_text or key in seen:
            continue
        seen.add(key)
        lines.append(
            f'- El usuario dijo: "{user_text}"\n  Emma respondió: "{assistant_text}"'
        )
        if len(lines) >= limit:
            break
    return lines


if __name__ == "__main__":
    prefs = load_prefs()
    profile = load_learning()
    print("Preferencia de idioma:", prefs.get("language_preference"))
    print("Turnos registrados:", (profile.get("totals") or {}).get("turns", 0))
    print("\nBloque para el prompt:\n")
    print(build_learning_block(profile) or "(vacío)")
    print("\nResumen hablado:\n")
    print(learning_summary(profile))

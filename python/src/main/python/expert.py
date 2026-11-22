#!/usr/bin/env python3
"""Experto online de Emma: delega en LLMs gratuitos cuando el 9B local no llega.

Cadena de reserva (se salta los proveedores sin clave o agotados):

  1. Gemini     https://generativelanguage.googleapis.com/v1beta/openai/
  2. Groq       https://api.groq.com/openai/v1
  3. OpenRouter https://openrouter.ai/api/v1
  4. Cerebras   https://api.cerebras.ai/v1

La configuracion vive en ``providers.json`` (nombre, base_url, modelo,
variable de entorno de la clave y limite diario). Las claves NUNCA se
escriben en el codigo: solo se leen de variables de entorno.

Si todos fallan devuelve ``{"error": "expert_unavailable"}`` y el tutor
local responde por su cuenta.

Cache en SQLite (``expert_cache``) y cuota diaria por proveedor
(``expert_log``). Se puede probar suelto:

    python expert.py --selftest
    python expert.py "que es una hash map"
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

MAX_QUESTION_CHARS = 1200
MAX_CONTEXT_CHARS = 300          # 1200 + 300 = 1500 caracteres maximos
MAX_EXPERT_TOKENS = 400
DEFAULT_TIMEOUT = 15.0

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "emma.db"


def _find_providers_file() -> Path:
    """Busca providers.json en la raiz del repo, no junto al modulo."""
    override = os.getenv("EMMA_PROVIDERS_FILE")
    if override:
        return Path(override).expanduser()
    here = Path(__file__).resolve()
    # modulo -> ... -> raiz del repo; luego el cwd como ultimo recurso
    for parent in here.parents:
        candidate = parent / "providers.json"
        if candidate.is_file():
            return candidate
    candidate = Path.cwd() / "providers.json"
    return candidate if candidate.is_file() else here.parent / "providers.json"


PROVIDERS_FILE = _find_providers_file()

# Patrones de privacidad: nunca salen del equipo.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<![\w.])(\+?\d[\d\s\-().]{7,}\d)(?![\w.])")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Configuracion de proveedores
# ---------------------------------------------------------------------------

_EMPTY_CONFIG: Dict[str, Any] = {
    "providers": {},
    "fallback_order": [],
    "timeout_seconds": DEFAULT_TIMEOUT,
    "max_tokens": MAX_EXPERT_TOKENS,
    "temperature": 0.3,
}


def load_providers() -> Dict[str, Any]:
    """Lee providers.json y deja solo los proveedores con clave disponible.

    Devuelve siempre ``providers`` como dict {nombre: config}, para que el
    resto del modulo no tenga que distinguir entre lista y diccionario.
    """
    path = PROVIDERS_FILE
    if not path.is_file():
        return dict(_EMPTY_CONFIG, providers={}, fallback_order=[])

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[EXPERT] providers.json ilegible: {exc}")
        return dict(_EMPTY_CONFIG, providers={}, fallback_order=[])

    providers: Dict[str, Dict[str, Any]] = {}
    for item in raw.get("providers") or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        name = str(item.get("name") or "").strip()
        env_name = str(item.get("api_key_env") or "").strip()
        if not name or not env_name:
            continue
        api_key = (os.getenv(env_name) or "").strip()
        if not api_key:
            continue
        providers[name] = {
            "name": name,
            "base_url": str(item.get("base_url") or "").rstrip("/"),
            "model": str(item.get("model") or ""),
            "daily_limit": int(item.get("daily_limit") or 1000),
            "api_key": api_key,
        }

    ordered = [n for n in (raw.get("fallback_order") or []) if n in providers]
    ordered += [n for n in providers if n not in ordered]

    return {
        "providers": providers,
        "fallback_order": ordered,
        "timeout_seconds": float(raw.get("timeout_seconds") or DEFAULT_TIMEOUT),
        "max_tokens": int(raw.get("max_tokens") or MAX_EXPERT_TOKENS),
        "temperature": float(raw.get("temperature", 0.3)),
    }


# ---------------------------------------------------------------------------
# SQLite: cache y cuota
# ---------------------------------------------------------------------------

def _init_expert_db() -> None:
    """Crea las tablas del experto si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS expert_cache (
                question_hash TEXT PRIMARY KEY,
                answer TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL DEFAULT (date('now')),
                provider TEXT NOT NULL,
                ok INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_expert_log_date ON expert_log(date);
            CREATE INDEX IF NOT EXISTS idx_expert_log_provider ON expert_log(provider);
            """
        )


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_cached_answer(question_hash: str) -> Optional[str]:
    """Respuesta cacheada para esa pregunta (o None)."""
    with _db() as db:
        row = db.execute(
            "SELECT answer FROM expert_cache WHERE question_hash=?",
            (question_hash,),
        ).fetchone()
    return row["answer"] if row else None


def cache_answer(question_hash: str, answer: str, provider: str) -> None:
    with _db() as db:
        db.execute(
            """INSERT OR REPLACE INTO expert_cache
               (question_hash, answer, provider, created_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (question_hash, answer, provider),
        )


def get_daily_usage(provider_name: str) -> int:
    """Llamadas correctas de hoy para un proveedor."""
    with _db() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM expert_log WHERE date=? AND provider=? AND ok=1",
            (date.today().isoformat(), provider_name),
        ).fetchone()
    return int(row[0]) if row else 0


def check_daily_quota(provider_name: str, daily_limit: int) -> bool:
    return get_daily_usage(provider_name) < int(daily_limit)


def log_expert_call(provider_name: str, ok: bool, latency_ms: int) -> None:
    with _db() as db:
        db.execute(
            """INSERT INTO expert_log (date, provider, ok, latency_ms)
               VALUES (date('now'), ?, ?, ?)""",
            (provider_name, 1 if ok else 0, int(latency_ms)),
        )


# ---------------------------------------------------------------------------
# Privacidad
# ---------------------------------------------------------------------------

def sanitize_text(text: str, max_chars: int = MAX_QUESTION_CHARS) -> str:
    """Quita emails, telefonos y URLs, y recorta la longitud."""
    if not text:
        return ""
    value = str(text)
    value = EMAIL_RE.sub("[email]", value)
    value = URL_RE.sub("[url]", value)
    value = PHONE_RE.sub("[phone]", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rstrip() + "..."
    return value


def normalize_question(question: str, context: str = "") -> str:
    """Hash estable para cachear preguntas repetidas."""
    combined = f"{question.strip().lower()}|{context.strip().lower()}"
    combined = re.sub(r"\s+", " ", combined).strip()
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Prompt del experto
# ---------------------------------------------------------------------------

EXPERT_SYSTEM_PROMPT = (
    "You are a consultant for a language tutor. The tutor's local model could "
    "not answer this question and needs a short, correct answer to relay.\n"
    "Rules:\n"
    "- Answer in the SAME LANGUAGE as the question.\n"
    "- Maximum 150 words. Short paragraphs or bullets; no preamble.\n"
    "- Be factual. If you are unsure, say what is uncertain in one sentence.\n"
    "- Code: only the minimal runnable snippet.\n"
    "- Do not mention being an AI, a model or an expert; do not address a student."
)


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

# Enfriamiento por proveedor: evita pagar el mismo fallo en cada turno.
_COOLDOWN_UNTIL: Dict[str, float] = {}
_COOLDOWN_REASON: Dict[str, str] = {}

_AUTH_HINTS = ("api key not valid", "invalid api key", "incorrect api key",
               "pass a valid api key", "authentication", "unauthorized",
               "invalid_api_key")


def _cool_down(name: str, seconds: float, reason: str) -> None:
    if seconds <= 0:
        return
    _COOLDOWN_UNTIL[name] = time.time() + seconds
    _COOLDOWN_REASON[name] = reason


def _in_cooldown(name: str) -> bool:
    until = _COOLDOWN_UNTIL.get(name, 0.0)
    if until and until > time.time():
        return True
    if until:
        _COOLDOWN_UNTIL.pop(name, None)
        _COOLDOWN_REASON.pop(name, None)
    return False


def _reset_cooldowns() -> None:
    """Solo para tests."""
    _COOLDOWN_UNTIL.clear()
    _COOLDOWN_REASON.clear()


def _extract_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    # Modelos con razonamiento a veces dejan 'content' vacio.
    extra = getattr(message, "model_extra", None) or {}
    for key in ("reasoning", "reasoning_content"):
        value = extra.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _call_provider(
    provider: Dict[str, Any],
    messages: List[Dict[str, str]],
    timeout: float,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """Una llamada al proveedor. Devuelve {ok, content} o {error, kind}."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return {"error": "openai_no_instalado", "kind": "setup"}

    client = AsyncOpenAI(
        base_url=provider["base_url"],
        api_key=provider["api_key"],
        timeout=timeout,
        max_retries=0,
    )
    try:
        response = await client.chat.completions.create(
            model=provider["model"],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as exc:  # clasificacion por tipo, sin red adicional
        name = type(exc).__name__
        body = ""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                body = response.text or ""
            except Exception:
                body = ""
        detail = (str(exc) + " " + body).strip()[:240]
        low = detail.lower()
        status = getattr(exc, "status_code", None)

        if name in ("APITimeoutError", "TimeoutError"):
            return {"error": "timeout", "kind": "timeout", "detail": detail}
        if name in ("APIConnectionError", "ConnectError", "TransportError"):
            return {"error": "network", "kind": "network", "detail": detail}
        if name == "RateLimitError" or status == 429:
            return {"error": "rate_limit", "kind": "rate", "detail": detail}
        if name in ("AuthenticationError", "PermissionDeniedError") or status in (401, 403):
            return {"error": "auth", "kind": "auth", "detail": detail}
        if any(hint in low for hint in _AUTH_HINTS):
            return {"error": "auth", "kind": "auth", "detail": detail}
        if status == 402:
            return {"error": "sin_saldo", "kind": "billing", "detail": detail}
        if status == 404 or "does not exist" in low or "not found" in low:
            return {"error": "modelo_no_disponible", "kind": "model", "detail": detail}
        if name == "BadRequestError" or status == 400:
            return {"error": f"bad_request: {detail}", "kind": "request", "detail": detail}
        return {"error": f"{name}: {detail}", "kind": "other", "detail": detail}

    try:
        message = response.choices[0].message
    except (AttributeError, IndexError):
        return {"error": "respuesta_inesperada", "kind": "other", "detail": ""}

    text = _extract_text(message)
    if not text:
        return {"error": "respuesta_vacia", "kind": "empty", "detail": ""}
    return {"ok": True, "content": text}


async def call_expert_chain(
    question: str,
    context: str = "",
    language: str = "es",
) -> Dict[str, Any]:
    """Prueba los proveedores en orden hasta que uno conteste."""
    config = load_providers()
    providers = config["providers"]
    if not providers:
        print(f"[EXPERT] Sin proveedores con clave (revisa providers.json y el entorno)")
        return {"error": "expert_unavailable", "reason": "no_providers"}

    lang_name = "English" if str(language).lower().startswith("en") else "Spanish"
    system = EXPERT_SYSTEM_PROMPT + f"\n- Write the answer in {lang_name}."
    user = f"Question: {question}"
    if context:
        user += f"\nContext: {context}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    errors: List[str] = []
    for provider_name in config["fallback_order"]:
        provider = providers.get(provider_name)
        if not provider:
            continue
        if _in_cooldown(provider_name):
            errors.append(f"{provider_name}:cooldown")
            continue
        if not check_daily_quota(provider_name, provider["daily_limit"]):
            errors.append(f"{provider_name}:cuota")
            continue

        started = time.time()
        result = await _call_provider(
            provider,
            messages,
            config["timeout_seconds"],
            config["max_tokens"],
            config["temperature"],
        )
        latency_ms = int((time.time() - started) * 1000)

        if result.get("ok"):
            log_expert_call(provider_name, True, latency_ms)
            _COOLDOWN_UNTIL.pop(provider_name, None)
            print(f"[EXPERT] {provider_name} OK en {latency_ms} ms")
            return {
                "ok": True,
                "answer": result["content"],
                "provider": provider_name,
                "latency_ms": latency_ms,
            }

        log_expert_call(provider_name, False, latency_ms)
        kind = result.get("kind")
        reason = result.get("error", "error")
        errors.append(f"{provider_name}:{reason}")
        print(f"[EXPERT] {provider_name} falla ({kind}): {reason}")

        if kind == "auth":
            # Clave invalida/caducada: no se reintenta en una hora.
            _cool_down(provider_name, 3600, "auth")
        elif kind == "rate":
            _cool_down(provider_name, 60, "rate")
        elif kind == "billing":
            _cool_down(provider_name, 3600, "billing")
        elif kind == "timeout":
            _cool_down(provider_name, 45, "timeout")
        elif kind == "network":
            _cool_down(provider_name, 30, "network")
        elif kind == "model":
            _cool_down(provider_name, 1800, "model")
        elif kind == "request":
            # Payload fijo: un 400 suele ser clave/parametros, no del turno.
            _cool_down(provider_name, 300, "request")

    return {"error": "expert_unavailable", "reason": "; ".join(errors[-4:])}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

async def ask_expert(question: str, context: str = "", language: str = "es") -> Dict[str, Any]:
    """Respuesta del experto o ``{"ok": False, "error": ...}``."""
    _init_expert_db()

    clean_question = sanitize_text(question, MAX_QUESTION_CHARS)
    clean_context = sanitize_text(context, MAX_CONTEXT_CHARS)
    if not clean_question:
        return {"ok": False, "error": "empty_question"}

    question_hash = normalize_question(clean_question, clean_context)
    cached = get_cached_answer(question_hash)
    if cached:
        return {
            "ok": True,
            "answer": cached,
            "provider": "cache",
            "latency_ms": 0,
            "cached": True,
        }

    result = await call_expert_chain(clean_question, clean_context, language)
    if result.get("ok"):
        cache_answer(question_hash, result["answer"], result["provider"])
    return result


def ask_expert_sync(question: str, context: str = "", language: str = "es") -> Dict[str, Any]:
    """Version sincrona para el tool calling del bucle de voz."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ask_expert(question, context, language))

    # Ya hay un bucle activo: se ejecuta en un hilo aparte para no bloquearlo.
    box: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            box.update(asyncio.run(ask_expert(question, context, language)))
        except Exception as exc:  # nunca propagar al bucle de voz
            box.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    return box or {"ok": False, "error": "expert_unavailable"}


# ---------------------------------------------------------------------------
# Definicion y validacion de la herramienta
# ---------------------------------------------------------------------------

ASK_EXPERT_TOOL = {
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
                    "description": "Contexto breve de la conversacion (opcional).",
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
}


def validate_ask_expert(args: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Devuelve (argumentos limpios, error). Nunca lanza."""
    if not isinstance(args, dict):
        return None, "arguments must be an object"
    question = args.get("question")
    if not isinstance(question, str) or not question.strip():
        return None, "question is required"
    context = str(args.get("context") or "")
    language = str(args.get("language") or "es").lower()
    if language not in ("es", "en"):
        language = "es"
    return {
        "question": question.strip(),
        "context": context,
        "language": language,
    }, ""


def execute_ask_expert(args: Dict[str, Any]) -> Dict[str, Any]:
    validated, error = validate_ask_expert(args)
    if error:
        return {"ok": False, "error": error}
    return ask_expert_sync(
        validated["question"], validated["context"], validated["language"]
    )


# ---------------------------------------------------------------------------
# Pruebas rapidas sin red
# ---------------------------------------------------------------------------

def _selftest() -> None:
    import gc
    import tempfile

    global DB_PATH
    original_db = DB_PATH
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    DB_PATH = Path(handle.name)
    try:
        _init_expert_db()

        assert sanitize_text("Call me at 555-123-4567") == "Call me at [phone]"
        assert sanitize_text("Email test@example.com") == "Email [email]"
        assert sanitize_text("Visit https://example.com/x") == "Visit [url]"
        assert len(sanitize_text("x" * 5000, 100)) <= 103

        assert normalize_question("What is Python?", "ctx") == \
            normalize_question("what is python?", "ctx")
        assert normalize_question("What is Python?", "a") != \
            normalize_question("What is Python?", "b")

        cache_answer("h1", "respuesta", "test")
        assert get_cached_answer("h1") == "respuesta"
        assert get_cached_answer("nope") is None

        assert check_daily_quota("quota_provider", 2) is True
        log_expert_call("quota_provider", True, 10)
        log_expert_call("quota_provider", True, 10)
        assert check_daily_quota("quota_provider", 2) is False
        assert get_daily_usage("quota_provider") == 2

        assert validate_ask_expert({"question": "hola"})[0]["language"] == "es"
        assert validate_ask_expert({"question": "hi", "language": "fr"})[0]["language"] == "es"
        assert validate_ask_expert({"context": "x"})[1] != ""

        _reset_cooldowns()
        _cool_down("demo", 60, "rate")
        assert _in_cooldown("demo") is True
        _reset_cooldowns()
        assert _in_cooldown("demo") is False

        print("EXPERT SELFTEST OK")
    finally:
        gc.collect()
        time.sleep(0.1)
        DB_PATH = original_db
        try:
            Path(handle.name).unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        _selftest()
    elif "--providers" in sys.argv:
        cfg = load_providers()
        print(f"providers.json: {PROVIDERS_FILE} (existe={PROVIDERS_FILE.is_file()})")
        print(f"cadena: {cfg['fallback_order'] or '(vacia)'}")
        for name, prov in cfg["providers"].items():
            print(f"  - {name}: {prov['model']}  limite={prov['daily_limit']}")
    else:
        question = " ".join(sys.argv[1:]) or "What is a hash map?"
        print(json.dumps(ask_expert_sync(question, "", "es"), ensure_ascii=False, indent=2))

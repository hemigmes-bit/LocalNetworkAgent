#!/usr/bin/env python3
"""Expert tool for Emma: delegates to free online LLMs when local model cannot answer.

Providers (free tiers, checked 2025):
  - Gemini:   https://generativelanguage.googleapis.com/v1beta/openai/  (gemini-1.5-flash, 1500/day)
  - Groq:     https://api.groq.com/openai/v1                         (llama-3.1-8b-instant, 14400/day)
  - OpenRouter: https://openrouter.ai/api/v1                       (meta-llama/llama-3.1-8b-instruct:free, 50/day)
  - Cerebras: https://api.cerebras.ai/v1                            (llama3.1-8b, 10000/day)

Fallback chain: Gemini -> Groq -> OpenRouter -> Cerebras.
If all fail -> {"error": "expert_unavailable"} so local tutor answers.

Config in providers.json (name, base_url, model, api_key_env, daily_limit).
Keys ONLY via env vars. Providers without key are skipped.

Cache in SQLite: expert_cache (question_hash, answer, provider, date).
Daily quota: expert_log (date, provider, ok, ms) + daily counter per provider.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROVIDERS_FILE = Path(__file__).parent / "providers.json"
DB_PATH = Path(__file__).parent.parent.parent / "data" / "emma.db"

# Privacy: max chars before sending to expert
MAX_QUESTION_CHARS = 1200
MAX_CONTEXT_CHARS = 300

# Expert response limits
MAX_EXPERT_TOKENS = 300
MAX_EXPERT_WORDS = 150  # ~150 words for expert response

# Privacy patterns to redact
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")


# ---------------------------------------------------------------------------
# Providers configuration
# ---------------------------------------------------------------------------

def load_providers() -> Dict[str, Any]:
    """Load and validate providers from JSON config."""
    if not PROVIDERS_FILE.exists():
        return {"providers": [], "fallback_order": [], "timeout_seconds": 15}
    
    with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    providers = []
    for p in config.get("providers", []):
        if not p.get("enabled", True):
            continue
        api_key = os.getenv(p.get("api_key_env", ""))
        if not api_key:
            continue
        providers.append({
            "name": p["name"],
            "base_url": p["base_url"].rstrip("/"),
            "model": p["model"],
            "api_key": api_key,
            "daily_limit": p.get("daily_limit", 1000),
        })
    
    fallback_order = [name for name in config.get("fallback_order", []) 
                      if any(p["name"] == name for p in providers)]
    
    return {
        "providers": {p["name"]: p for p in providers},
        "fallback_order": fallback_order,
        "timeout_seconds": config.get("timeout_seconds", 15),
    }


PROVIDERS_CONFIG = load_providers()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _init_expert_db() -> None:
    """Create expert tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
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
        """)


@contextmanager
def _db() -> sqlite3.Connection:
    """Thread-safe database connection with WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Privacy: sanitize input
# ---------------------------------------------------------------------------

def sanitize_text(text: str, max_chars: int = MAX_QUESTION_CHARS) -> str:
    """Remove PII and truncate."""
    if not text:
        return ""
    text = str(text)
    # Redact emails
    text = EMAIL_RE.sub("[email]", text)
    # Redact phones
    text = PHONE_RE.sub("[phone]", text)
    # Redact URLs
    text = URL_RE.sub("[url]", text)
    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text.strip()


def normalize_question(question: str, context: str = "") -> str:
    """Create normalized hash for caching."""
    combined = f"{question.strip().lower()}|{context.strip().lower()}"
    combined = re.sub(r"\s+", " ", combined).strip()
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Expert system prompt
# ---------------------------------------------------------------------------

EXPERT_SYSTEM_PROMPT = """You are an expert consultant for an English tutor.
The tutor (a local 9B model) cannot answer this question and needs your help.

Constraints:
- Answer in the SAME LANGUAGE as the question.
- Be CONCISE: max 150 words, structured (bullets OK).
- Do NOT mention you are an AI or expert. Just answer directly.
- If unsure, say so briefly.
- No fluff, no meta-commentary.
- Code: include minimal, runnable snippets only.
- Technical topics: prioritize accuracy over brevity.

The tutor will summarize your answer for the student. Do not address the student directly."""


# ---------------------------------------------------------------------------
# Provider clients
# ---------------------------------------------------------------------------

import asyncio
import aiohttp


async def _call_provider(
    provider: Dict[str, Any],
    messages: List[Dict[str, str]],
    timeout: int,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """Call a single provider via OpenAI-compatible API."""
    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=timeout
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {text[:200]}"}
                data = await resp.json()
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    except aiohttp.ClientError as e:
        return {"error": f"network: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    
    try:
        content = data["choices"][0]["message"]["content"]
        return {"ok": True, "content": content.strip()}
    except (KeyError, IndexError, TypeError):
        return {"error": "unexpected_response"}


async def call_expert_chain(
    question: str,
    context: str = "",
    language: str = "es",
) -> Dict[str, Any]:
    """Try providers in fallback order until one succeeds."""
    config = load_providers()
    providers = config["providers"]
    fallback_order = config["fallback_order"]
    timeout = config["timeout_seconds"]
    
    # Build messages
    sanitized_q = sanitize_text(question, MAX_QUESTION_CHARS)
    sanitized_ctx = sanitize_text(context, MAX_CONTEXT_CHARS)
    
    messages = [
        {"role": "system", "content": EXPERT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {sanitized_q}\nContext: {sanitized_ctx}"},
    ]
    
    for provider_name in fallback_order:
        provider = config["providers"].get(provider_name)
        if not provider:
            continue
        
        # Check daily quota
        if not check_daily_quota(provider_name, provider["daily_limit"]):
            continue
        
        start = time.time()
        result = await _call_provider(
            provider,
            messages,
            config["timeout_seconds"],
            MAX_EXPERT_TOKENS,
            0.3,
        )
        latency_ms = int((time.time() - start) * 1000)
        
        if result.get("ok"):
            log_expert_call(provider_name, True, latency_ms)
            return {
                "ok": True,
                "answer": result["content"],
                "provider": provider_name,
                "latency_ms": latency_ms,
            }
        else:
            log_expert_call(provider_name, False, latency_ms)
            # If 429/rate limit, try next provider immediately
            if "429" in result.get("error", "") or "rate" in result.get("error", "").lower():
                continue
            # For other errors, also try next provider
            continue
    
    return {"error": "expert_unavailable"}


# ---------------------------------------------------------------------------
# Cache & Quota
# ---------------------------------------------------------------------------

def _init_expert_db() -> None:
    """Create expert tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
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
        """)


def get_cached_answer(question_hash: str) -> Optional[str]:
    """Return cached answer if exists."""
    with _db() as db:
        row = db.execute(
            "SELECT answer FROM expert_cache WHERE question_hash=?",
            (question_hash,),
        ).fetchone()
    return row["answer"] if row else None


def cache_answer(question_hash: str, answer: str, provider: str) -> None:
    """Store answer in cache."""
    with _db() as db:
        db.execute(
            """INSERT OR REPLACE INTO expert_cache
               (question_hash, answer, provider, created_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (question_hash, answer, provider),
        )


def check_daily_quota(provider_name: str, daily_limit: int) -> bool:
    """Check if provider has remaining quota today."""
    today = date.today().isoformat()
    with _db() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM expert_log WHERE date=? AND provider=? AND ok=1",
            (today, provider_name),
        ).fetchone()[0]
    return count < daily_limit


def log_expert_call(provider_name: str, ok: bool, latency_ms: int) -> None:
    """Log expert call for quota tracking."""
    with _db() as db:
        db.execute(
            """INSERT INTO expert_log (date, provider, ok, latency_ms)
               VALUES (date('now'), ?, ?, ?)""",
            (provider_name, 1 if ok else 0, latency_ms),
        )


def get_daily_usage(provider_name: str) -> int:
    """Get today's successful call count for a provider."""
    today = date.today().isoformat()
    with _db() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM expert_log WHERE date=? AND provider=? AND ok=1",
            (date.today().isoformat(), provider_name),
        ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def ask_expert(question: str, context: str = "", language: str = "es") -> Dict[str, Any]:
    """Main entry point for the expert tool.
    
    Returns:
        {"ok": True, "answer": "...", "provider": "...", "latency_ms": ...}
        or {"error": "expert_unavailable"}
    """
    # Initialize DB
    _init_expert_db()
    
    # Sanitize inputs
    question = sanitize_text(question, MAX_QUESTION_CHARS)
    context = sanitize_text(context, MAX_CONTEXT_CHARS)
    
    if not question:
        return {"error": "empty_question"}
    
    # Check cache
    q_hash = normalize_question(question, context)
    cached = get_cached_answer(question)
    if cached:
        return {"ok": True, "answer": cached, "provider": "cache", "latency_ms": 0}
    
    # Call expert chain
    result = await call_expert_chain(question, context)
    
    if result.get("ok"):
        # Cache successful answer
        cache_answer(normalize_question(question, context), result["answer"], result["provider"])
    
    return result


# ---------------------------------------------------------------------------
# Synchronous wrapper for tool calling
# ---------------------------------------------------------------------------

def ask_expert_sync(question: str, context: str = "", language: str = "es") -> Dict[str, Any]:
    """Synchronous wrapper for tool calling."""
    try:
        return asyncio.run(ask_expert(question, context, language))
    except RuntimeError:
        # Already in event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ask_expert(question, context, language))
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Tool definition for emma_tools
# ---------------------------------------------------------------------------

ASK_EXPERT_TOOL = {
    "type": "function",
    "function": {
        "name": "ask_expert",
        "description": (
            "Consulta a un modelo experto online (gratis) cuando la duda se sale de la "
            "enseñanza de inglés, necesita información actual, razonamiento largo o código. "
            "Úsalo solo si la duda se sale de la enseñanza de inglés, necesita información "
            "actual, razonamiento largo o código."
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
}


# ---------------------------------------------------------------------------
# Validation for tool calling
# ---------------------------------------------------------------------------

def validate_ask_expert(args: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Validate ask_expert arguments."""
    if not isinstance(args, dict):
        return None, "arguments must be an object"
    question = args.get("question")
    if not question or not isinstance(question, str):
        return None, "question is required"
    context = args.get("context", "")
    language = args.get("language", "es")
    if language not in ("es", "en"):
        language = "es"
    return {"question": question, "context": context, "language": language}, ""


def execute_ask_expert(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the ask_expert tool."""
    validated, error = validate_ask_expert(args)
    if error:
        return {"ok": False, "error": error}
    return ask_expert_sync(
        validated["question"],
        validated.get("context", ""),
        validated.get("language", "es"),
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> None:
    import tempfile
    import gc
    
    # Test with temporary DB
    import tempfile
    global DB_PATH
    original_db = DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = Path(f.name)
    DB_PATH = test_db
    
    try:
        _init_expert_db()
        
        # Test sanitize
        assert sanitize_text("Call me at 555-123-4567") == "Call me at [phone]"
        assert sanitize_text("Email me at test@example.com") == "Email me at [email]"
        assert sanitize_text("Visit https://example.com") == "Visit [url]"
        
        # Test normalize_question
        h1 = normalize_question("What is Python?", "context")
        h2 = normalize_question("what is python?", "context")
        assert h1 == h2
        
        # Test cache
        qh = normalize_question("test question", "test context")
        cache_answer("test hash", "cached answer", "test_provider")
        cached = get_cached_answer("test hash")
        assert cached == "cached answer"
        
        # Test quota - use unique provider name to avoid interference
        assert check_daily_quota("test_provider_selftest", 10) == True
        log_expert_call("test_provider_selftest", True, 100)
        log_expert_call("test_provider_selftest", True, 100)
        # After 2 calls with limit 2, we're at the limit - next check should be False
        assert check_daily_quota("test_provider_selftest", 2) == False
        # But with higher limit, still room
        assert check_daily_quota("test_provider_selftest", 3) == True
        log_expert_call("test_provider_selftest", True, 100)
        assert check_daily_quota("test_provider_selftest", 3) == False
        
        # Test sanitize
        assert "[email]" in sanitize_text("Contact me at user@domain.com")
        assert "[phone]" in sanitize_text("Call +1-555-123-4567")
        assert "[url]" in sanitize_text("Visit https://example.com/page")
        
        print("Expert selftest OK")
    finally:
        # Force close any open connections
        gc.collect()
        import time
        time.sleep(0.1)
        if test_db.exists():
            test_db.unlink()


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        # Quick manual test
        import asyncio
        async def test():
            result = await ask_expert("What is the capital of France?", language="en")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        asyncio.run(test())
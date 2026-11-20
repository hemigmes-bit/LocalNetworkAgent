import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "data" / "tutor.db"

DEFAULTS = {
    "provider": "ollama",
    "model": None,
    "temperature": 0.6,
    "student_name": "Usuario",
    "level": "B1",
    "native_language": "Spanish",
    "max_corrections_per_turn": 1,
    "voice": True,
    "stt_model": "small",
    "stt_language": None,
    "stt_languages": ["es", "en"],
    "tts_provider": "kokoro",
    "tts_voice": "af_heart",
    "tts_speed": 1.0,
    "voice_auto": True,
    "tts_edge_voice": "en-US-AvaMultilingualNeural",
    "tts_rate": "+40%",
    "tts_pitch": "+10Hz",
    "tts_model": "canopylabs/orpheus-v1-english",
    "tts_groq_voice": "hannah",
    "tts_es_voice": "es-ES-XimenaNeural",
    "tts_kokoro_es_voice": "ef_dora",
    "tts_speed_es": 1.0,
    "tts_rate_es": "+40%",
    "voice_max_seconds": 20,
    "level_progression": True,
    "auto_level_up": True,
}

PROVIDERS = {
    "ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "env": None,
        "default_model": "qwen2.5-coder:7b",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env": "OPENROUTER_API_KEY",
        "default_model": "qwen/qwen-2.5-coder-7b:free",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env": "GROQ_API_KEY",
        "default_model": "llama-3.1-70b-versatile",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "env": "GOOGLE_API_KEY",
        "default_model": "gemini-1.5-flash",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-haiku-20241022",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    },
}

# Fallback order: primary -> fallback1 -> fallback2 -> fallback3
# Only providers that are available (have valid config/env) will be used
FALLBACK_PROVIDERS = ["ollama", "openrouter", "groq", "google", "together", "anthropic", "openai"]

def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    provider = cfg.get("provider", "ollama")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Options: {', '.join(PROVIDERS)}")
    cfg["provider"] = provider
    cfg["model"] = cfg.get("model") or PROVIDERS[provider]["default_model"]
    return cfg


def api_key(provider):
    env = PROVIDERS[provider]["env"]
    if env is None:
        return "ollama"
    key = os.environ.get(env, "")
    if not key:
        raise RuntimeError(f"Missing environment variable {env} for provider {provider}")
    return key





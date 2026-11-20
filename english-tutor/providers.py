import json
import re

from openai import OpenAI

from config import PROVIDERS, FALLBACK_PROVIDERS, api_key


def _create_client_for_provider(provider, cfg):
    """Create an OpenAI client for a specific provider."""
    if provider not in PROVIDERS:
        return None
    provider_cfg = PROVIDERS[provider]
    base_url = provider_cfg.get("base_url")
    if not base_url:
        return None
    # Check if env is required but not set
    env_var = provider_cfg.get("env")
    if env_var and not api_key(provider):
        return None
    return OpenAI(
        base_url=provider_cfg["base_url"],
        api_key=api_key(provider),
        timeout=120,
    )


def make_client(cfg):
    """
    Create an OpenAI client with fallback support.
    Tries providers in FALLBACK_PROVIDERS order until one succeeds.
    """
    # First try the configured provider
    configured_provider = cfg.get("provider", "ollama")
    if configured_provider in PROVIDERS:
        client = _create_client_for_provider(configured_provider, cfg)
        if client:
            return client

    # Fallback: try providers in FALLBACK_PROVIDERS order
    for provider in FALLBACK_PROVIDERS:
        if provider == configured_provider:
            continue  # already tried
        client = _create_client_for_provider(provider, cfg)
        if client:
            print(f"[Fallback] Using provider: {provider}")
            return client

    # Last resort: try any available provider
    for provider in PROVIDERS:
        if provider in (configured_provider,) + tuple(FALLBACK_PROVIDERS):
            continue
        client = _create_client_for_provider(provider, cfg)
        if client:
            print(f"[Fallback] Using provider: {provider}")
            return client

    raise RuntimeError("No available LLM provider could be initialized")


def chat(client, cfg, messages, temperature=None, json_mode=True):
    kwargs = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"] if temperature is None else temperature,
    }
    if json_mode and cfg["provider"] != "ollama":
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def parse_json(text):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
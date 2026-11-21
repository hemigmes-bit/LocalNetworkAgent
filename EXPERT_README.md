# Expert Tool for Emma (ask_expert)

## Overview
The `ask_expert` tool allows Emma (local 9B tutor) to delegate questions outside her expertise to free online LLMs via OpenAI-compatible endpoints.

## Providers (Free Tiers)

| Provider | Endpoint | Model | Daily Limit | API Key Env |
|----------|----------|-------|-------------|-------------|
| **Gemini** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-1.5-flash` | 1,500 req/day | `GEMINI_API_KEY` |
| **Groq** | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` | 14,400 req/day | `GROQ_API_KEY` |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.1-8b-instruct:free` | 50 req/day | `OPENROUTER_API_KEY` |
| **Cerebras** | `https://api.cerebras.ai/v1` | `llama3.1-8b` | 10,000 req/day | `CEREBRAS_API_KEY` |

**Fallback order:** Gemini → Groq → OpenRouter → Cerebras

## Configuration

### providers.json
Place in project root:
```json
{
  "providers": [
    {"name": "gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-1.5-flash", "api_key_env": "GEMINI_API_KEY", "daily_limit": 1500, "enabled": true},
    {"name": "groq", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.1-8b-instant", "api_key_env": "GROQ_API_KEY", "daily_limit": 14400, "enabled": true},
    {"name": "openrouter", "base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.1-8b-instruct:free", "api_key_env": "OPENROUTER_API_KEY", "daily_limit": 50, "enabled": true},
    {"name": "cerebras", "base_url": "https://api.cerebras.ai/v1", "model": "llama3.1-8b", "api_key_env": "CEREBRAS_API_KEY", "daily_limit": 10000, "enabled": true}
  ],
  "fallback_order": ["gemini", "groq", "openrouter", "cerebras"],
  "timeout_seconds": 15,
  "max_tokens": 300,
  "temperature": 0.3
}
```

### Environment Variables
Set these in your environment (never in code):
```bash
export GEMINI_API_KEY="your_gemini_key"
export GROQ_API_KEY="your_groq_key"
export OPENROUTER_API_KEY="your_openrouter_key"
export CEREBRAS_API_KEY="your_cerebras_key"
```

Get free keys at:
- **Gemini**: https://aistudio.google.com/app/apikey
- **Groq**: https://console.groq.com/keys
- **OpenRouter**: https://openrouter.ai/keys
- **Cerebras**: https://cloud.cerebras.ai/platform/api-keys

## How It Works

1. **Intent Detection**: Emma detects when a question needs expert help (outside English teaching, needs current info, complex reasoning, code).
2. **Provider Selection**: Tries providers in fallback order, skipping those without API keys or exhausted quotas.
3. **Fallback Chain**: If provider returns 429/timeout/error → tries next provider.
3. **All Fail**: Returns `{"error": "expert_unavailable"}` → Emma answers locally.
4. **Cache**: Successful answers cached in SQLite (hash of normalized question + context). Repeated questions don't consume quota.
5. **Quota Tracking**: Daily limits per provider tracked in SQLite (`expert_log` table).
6. **Privacy**: Question & context sanitized (emails, phones, URLs redacted, max 1500 chars total).
6. **Response**: Expert returns ≤150 words, structured. Emma summarizes for student.

## Tool Definition (for Emma)

```json
{
  "name": "ask_expert",
  "description": "Consulta a un modelo experto online (gratis) cuando la duda se sale de la enseñanza de inglés, necesita información actual, razonamiento largo o código.",
  "parameters": {
    "type": "object",
    "properties": {
      "question": {"type": "string", "description": "La pregunta concreta para el experto."},
      "context": {"type": "string", "description": "Contexto opcional de la conversación."},
      "language": {"type": "string", "enum": ["es", "en"]}
    },
    "required": ["question"]
  }
}
```

## When Emma Uses It

Emma's system prompt includes:
> "Usa `ask_expert` solo si la duda se sale de la enseñanza de inglés, necesita información actual, razonamiento largo o código."

Examples:
- "How does a blockchain work?" → expert
- "Write a Python script to scrape a website" → expert  
- "What's the weather in Madrid?" → fetch_weather (local tool)
- "Correct my grammar: 'I go to beach'" → local (Emma handles)
- "What happened in the news today?" → web_search (local tool)

## Database Schema

```sql
-- expert_cache: deduplicates repeated questions
CREATE TABLE expert_cache (
    question_hash TEXT PRIMARY KEY,
    answer TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- expert_log: quota tracking
CREATE TABLE expert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL DEFAULT (date('now')),
    provider TEXT NOT NULL,
    ok INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## Testing

```bash
# Run expert tests
python -m unittest test_expert

# All tests
python -m unittest test_local_tools test_fact_check test_emma_patches test_voice_permission test_wake_word test_language_routing test_expert
```

## Files
- `python/src/main/python/expert.py` - Main implementation
- `providers.json` - Provider configuration
- `test_expert.py` - Unit tests (15 tests, offline mocks)
- `EXPERT_README.md` - This file

## Troubleshooting

| Issue | Solution |
|-------|----------|
| All providers fail | Check API keys in env vars, check internet connectivity |
| 429 errors | Daily limit reached, waits for next day or uses next provider |
| "expert_unavailable" | All providers failed, Emma answers locally |
| DB locked | Close other Emma instances, check file permissions |

## Privacy Notes
- **Never** sends student profile, emails, phones, URLs to experts
- Question + context truncated to 1500 chars total
- Emails → `[email]`, phones → `[phone]`, URLs → `[url]`
- No conversation history sent
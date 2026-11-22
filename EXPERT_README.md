# Experto online de Emma (`ask_expert`)

Cuando la duda se sale de enseñar inglés (tecnología, ciencia, código o datos que
el 9B local no tiene), Emma puede pedir ayuda a un LLM gratuito por API. Si todos
los proveedores fallan, Emma responde sola: nunca se queda bloqueada.

## Cadena de reserva

| Orden | Proveedor | Endpoint | Modelo por defecto | Límite diario |
|-------|-----------|----------|--------------------|---------------|
| 1 | Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.8-flash` | 500 |
| 2 | Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` | 1000 |
| 3 | OpenRouter | `https://openrouter.ai/api/v1` | `openrouter/free` | 50 |
| 4 | Cerebras | `https://api.cerebras.ai/v1` | `gpt-oss-120b` | 1000 |

Los modelos se comprobaron contra la documentación y contra `/models` de cada
proveedor en **noviembre de 2026**. Cambian a menudo: si ves
`modelo_no_disponible` en el log, actualiza el campo `model` de `providers.json`.

Se salta cualquier proveedor:

- sin variable de entorno con la clave,
- con la cuota diaria agotada,
- en enfriamiento tras un fallo (clave inválida 1 h, 429 60 s, timeout 45 s, red 30 s, modelo inexistente 30 min).

## Claves (solo variables de entorno)

```powershell
setx GEMINI_API_KEY     "..."   # https://aistudio.google.com/apikey
setx GROQ_API_KEY       "..."   # https://console.groq.com/keys
setx OPENROUTER_API_KEY "..."   # https://openrouter.ai/keys
setx CEREBRAS_API_KEY   "..."   # https://cloud.cerebras.ai/platform/api-keys
```

Tras `setx`, abre una consola nueva (o reinicia Emma) para que las variables
existan en el proceso.

Comprobar qué proveedores ve el proceso:

```powershell
python python\src\main\python\expert.py --providers
```

Debe imprimir la ruta de `providers.json` (`existe=True`) y la cadena real, por
ejemplo `['gemini', 'groq', 'openrouter']`. Si la cadena sale vacía, ninguna
clave está visible para ese proceso.

## Configuración (`providers.json`)

Se busca en la raíz del repositorio (subiendo desde el módulo) o en la ruta de
la variable `EMMA_PROVIDERS_FILE`.

```json
{
  "providers": [
    {"name": "groq", "base_url": "https://api.groq.com/openai/v1",
     "model": "openai/gpt-oss-20b", "api_key_env": "GROQ_API_KEY",
     "daily_limit": 1000, "enabled": true}
  ],
  "fallback_order": ["gemini", "groq", "openrouter", "cerebras"],
  "timeout_seconds": 15,
  "max_tokens": 400,
  "temperature": 0.3
}
```

`daily_limit` es el contador propio de Emma (se guarda en SQLite), no el límite
oficial del proveedor: ponlo igual o por debajo para no comerte un 429.

## Cómo funciona

1. `detect_local_intent` / `tool_hint` deciden si el turno necesita experto.
2. `ask_expert` normaliza la pregunta y mira la caché (`expert_cache`).
3. Si no está cacheada, recorre la cadena; cada intento se registra en
   `expert_log` (fecha, proveedor, ok, ms).
4. La respuesta se cachea y vuelve al bucle de voz como mensaje `tool`.
5. El prompt del sistema pide a Emma **resumirla con sus palabras**, no copiarla.

## Privacidad

- Pregunta ≤ 1200 caracteres y contexto ≤ 300 (1500 en total).
- Se sustituyen emails (`[email]`), teléfonos (`[phone]`) y URLs (`[url]`).
- Nunca se envía el perfil del alumno ni el historial de la sesión.

## Base de datos

```sql
CREATE TABLE expert_cache (
    question_hash TEXT PRIMARY KEY,
    answer TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE expert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL DEFAULT (date('now')),
    provider TEXT NOT NULL,
    ok INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## Pruebas

```powershell
python -m unittest test_expert              # 23 pruebas, sin red
python python\src\main\python\expert.py --selftest
python python\src\main\python\expert.py "que es una hash map"   # llamada real
```

## Diagnóstico rápido

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `expert_unavailable` con `reason=no_providers` | `providers.json` no encontrado o ninguna clave visible | `expert.py --providers` |
| `gemini falla (auth): Please pass a valid API key` | clave de Gemini inválida o revocada | generar una nueva en AI Studio |
| `groq falla (model)` | modelo retirado | mirar `/models` y actualizar `model` |
| `openrouter falla (rate)` | cuota gratuita agotada | esperar o usar otro proveedor |
| `respuesta_vacia` | modelo de razonamiento sin salida final | se prueba el siguiente proveedor |
| Todo falla y Emma contesta igual | comportamiento esperado | revisar `logs/engine_stdout.log` (`[EXPERT]`) |

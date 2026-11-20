# Emma 2.0 — Fase 1 (estabilización inicial)

Esta entrega es una **copia de trabajo**, no sustituye tu instalación actual. Conserva el pipeline original y corrige problemas acotados.

## Cambios incluidos
- Se elimina la primera implementación duplicada de `main()` (llamaba a `run_turn` con una firma incompatible y limitaba la sesión a 20 turnos).
- faster-whisper respeta `beam_size` y `vad_filter` de configuración; `language: null` activa autodetección y, si detecta un idioma ajeno (griego, ruso...), reintenta en español e inglés y elige la mejor transcripción.
- El modelo y URL de Ollama pasan a ser configurables en `config.yaml`, usando `qwen2.5:7b-instruct` como valor por defecto.
- Kokoro toma las voces de `config.yaml`, fonemiza cada voz en su idioma real (español incluido) y aplica la velocidad configurada; el cambio de voz actualiza el mapa activo y se guarda en `emma_prefs.json`.
- Se corrigen dos errores de `ProfileManager`: variable `item` inexistente en SRS y cadenas literales en vez de los textos reales al guardar resúmenes.
- Guardado JSON atómico para reducir el riesgo de corrupción por interrupción.
- Se añade importador JSON→SQLite idempotente que conserva los campos originales y no usa `turno` como clave única.

## Migración de memoria (NO automática)
1. Haz una copia de `memoria_emma.json`.
2. Ejecuta desde la raíz del proyecto: `python migrate_memory.py memoria_emma.json`.
3. Comprueba el número de registros importados y la base `data/emma_memory.db`.
4. No borres ni renombres el JSON. Esta fase **no cambia aún** el pipeline para leer/escribir SQLite; eso se hará después de validar la importación.

## Pendiente para la fase siguiente
- Streaming real LLM→TTS (ahora el LLM termina antes de que comience la síntesis).
- Interrupción de voz (barge-in) y cancelación real de generación.
- Reorganización modular y pruebas integrales con los modelos/dispositivos reales.
- Integrar SQLite como almacén activo solo después de validar los datos.

## Validación
Se comprueba sintaxis Python y se ejecutan pruebas locales de la capa SQLite. La reproducción con micrófono, CUDA, Ollama y Kokoro requiere probarlo en tu Windows.

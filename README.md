# Emma Bilingüe - Voice Loop

## Descripción
Pipeline de voz completo para tutor bilingüe de inglés/español:
- Detección de fin de frase (Silero VAD)
- Reconocimiento de voz (faster-whisper GPU)
- LLM streaming (OpenRouter API)
- Síntesis de voz (Kokoro TTS)
- Repetir hasta Ctrl+C

## Requisitos previos

### Hardware
- GPU NVIDIA con CUDA (recomendado para faster-whisper GPU)
- Micrófono y altavoces

### Software
- Python 3.12+
- Variable de entorno: `OPENROUTER_API_KEY`
- Modelos Kokoro (.onnx y .json)

## Instalación

### 1. Clonar / Verificar proyecto
```powershell
cd C:\Users\Usuario\LocalNetworkAgent
```

### 2. Instalar dependencias Python
```powershell
pip install faster-whisper silero-vad kokoro-onnx sounddevice requests pyyaml
```

### 3. Instalar dependencias de sistema (Kokoro)
```powershell
# En Windows, instala los requisitos de kokoro-onnx:
pip install numpy sounddevice

# Descargar modelos Kokoro:
# - kokoro-v1.0.onnx
# - voices.json
# Colocarlos en el directorio actual o configurar en config.yaml
```

### 4. Configurar API key OpenRouter
```powershell
# En Windows PowerShell:
$env:OPENROUTER_API_KEY="sk-or-...."

# O añade al archivo .env:
echo OPENROUTER_API_KEY=sk-or-.... > .env
```

### 5. Verificar configuración
```powershell
# Revisar config.yaml en la raíz
notepad config.yaml
```

### 6. Ejecutar Voice Loop
```powershell
cd C:\Users\Usuario\LocalNetworkAgent
python python\src\main\python\voice_loop.py
```

## Flujo de operación

1. El sistema inicia y espera a que hables
2. Silero VAD detecta el fin de tu frase (silencio > 500ms)
3. faster-whisper transcribe tu audio (GPU si está disponible)
4. OpenRouter LLM genera una respuesta bilingüe (formato JSON estructurado)
5. Kokoro TTS sintetiza la respuesta (voz inglesa o española según idioma)
6. Se reproduce la respuesta por altavoz
7. Se ignora el micrófono mientras suena (half-duplex)
8. Vuelta al paso 1

## Configuración (config.yaml)

### LLM
```yaml
llm:
  model: "openrouter/auto"           # Modelo OpenAI compatible
  temperature: 0.7
  max_tokens: 500
```

### STT (faster-whisper)
```yaml
stt:
  model_size: "base"                 # tiny, base, small, medium, large-v3
  device: "cuda"                     # cuda o cpu
  compute_type: "float16"
  language: "es"                     # idioma por defecto
  beam_size: 5
  vad_filter: true
  min_silence_ms: 500
```

### VAD (Silero)
```yaml
vad:
  threshold: 0.5
  min_silence_duration_ms: 400
  min_speech_duration_ms: 250
```

### TTS (Kokoro)
```yaml
tts:
  model_path: "kokoro-v1.0.onnx"
  voices_path: "voices.json"
  sample_rate: 24000
  voices:
    en: "af_bella"       # Voz inglés femenino
    es: "ef_dora"        # Voz español femenino
```

### Historial
```yaml
history:
  max_turns: 10                      # N turnos a mantener en contexto
```

### Audio
```yaml
audio:
  sample_rate: 16000
  channels: 1
  half_duplex: true
```

### System Prompt
```yaml
system_prompt: |
  Eres Emma, tutora bilingüe de inglés/español amable.
  ...
```

## Límites conocidos

- **Sin micrófono real**: Esta versión usa simulación de audio. Para micrófono real, integrar `sounddevice` con dispositivo específico.
- **Latencia**: Depende del modelo STT (base: ~1-2s en GPU, ~5-10s en CPU) y la latencia de OpenRouter API.
- **Idioma**: El sistema detecta inglés vs español basándose en conteo de palabras; detección imperfecta en mezclas.

## Archivos generados

- `logs/latency.csv` - Tiempos por turno (STT, LLM first/full, TTS first, total)
- `data/profile.db` - Base de datos SQLite del perfil del usuario
- `data/` - Otros datos de SRS y sesiones

## Desarrolladores

Para añadir nuevos modelos o voces, modificar `config.yaml`. El pipeline está diseñado para ser modular:
- Cambiar solo `stt/tts` en config.yaml sin tocar el código
- Añadir nuevas voces en `tts/voices` sección
- Cambiar modelo LLM en `llm/model`
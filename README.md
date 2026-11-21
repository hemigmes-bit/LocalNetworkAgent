# Emma Bilingüe — Voice Loop

**Emma** es una tutora bilingüe de inglés/español que conversa por voz en tiempo real.  
Escucha, entiende, busca en Internet si hace falta, corrige tus errores de forma natural y responde con voz propia.

> **Wake word:** «Emma»  
> **Seguimiento:** 90 s sin repetir la wake word  
> **Modo:** Full-duplex con barge-in (puedes interrumpirla mientras habla)

---

## ✨ Qué hace Emma

| Capacidad | Descripción |
|-----------|-------------|
| **Conversación por voz** | Pipeline VAD → STT → LLM → TTS en bucle continuo |
| **Bilingüe natural** | Detecta español/inglés y responde en el mismo idioma |
| **Corrección pedagógica** | Máx. 2 correcciones/turno, cita literal, tono alentador |
| **Vocabulario progresivo** | 1-2 palabras nuevas por turno, nivel adaptado |
| **Memoria persistente** | Perfil (nombre, nivel MCER, objetivos), SRS, historial SQLite |
| **Búsqueda web real** | `ddgs.news` (URL directa al medio), Wikipedia, SearXNG; descarga el artículo completo |
| **Verificación de cifras** | Contrasta años, porcentajes y cantidades con la fuente; si no aparecen, avisa en vez de inventar |
| **Herramientas exactas** | `calculate` (aritmética segura) y `current_date` (fecha/hora real del sistema) |
| **Seguimientos inteligentes** | "Tell me more", "Who can access?" reutilizan el tema y amplían con datos nuevos |
| **Noticias y actualidad** | Desarrolla temas hasta 5 frases: qué es, a quién afecta, cómo funciona/accede, por qué importa |
| **Cuentos** | Busca material curado y narra 350-400 palabras |
| **Reconocimiento musical** | Shazam (grabación) + tarareo/silbido (melodía) |
| **Control de voz** | Cambio de voz solo con permiso expreso; ciclo solo voces femeninas |
| **Anti-repetición** | Nunca repite la respuesta anterior; bloque explícito en prompt |
| **GUI de red** | `LocalNetworkAgent-GUI.ps1` para escaneo, WoL, monitor, explorador remoto |

---

## 🖥 Requisitos

### Hardware
- **GPU NVIDIA** con CUDA (recomendado: faster-whisper `large-v3-turbo` en GPU)
- Micrófono y altavoces

### Software
- **Windows 10/11** (PowerShell 7+ recomendado)
- **Python 3.12+**
- **Ollama** local (`ollama serve`) con modelo `qwen3.5:9b` (`ollama pull qwen3.5:9b`)
- **Modelos Kokoro**: `kokoro-v1.0.onnx` + `voices-v1.0.bin` en la raíz del proyecto

### Dependencias Python
```powershell
pip install faster-whisper silero-vad kokoro-onnx sounddevice requests pyyaml numpy
# Opcional: ddgs (para noticias), beautifulsoup4, lxml (para fetch_page)
```

---

## ⚡ Instalación rápida

```powershell
# 1. Clonar
git clone https://github.com/TU_USUARIO/Emma-Bilingue.git
cd Emma-Bilingue

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Modelos Kokoro (descargar y colocar en la raíz)
#    kokoro-v1.0.onnx
#    voices-v1.0.bin

# 4. Ollama
ollama serve
ollama pull qwen3.5:9b

# 5. Configurar (revisar config.yaml)
notepad config.yaml

# 6. ¡Arrancar!
python python\src\main\python\voice_loop.py
```

> **Acceso directo**: Ejecuta `install.ps1` para crear un acceso directo en el escritorio («Emma Bilingüe.lnk»).

---

## ⚙️ Configuración (`config.yaml`)

```yaml
# LLM local (Ollama)
llm:
  model: "qwen3.5:9b"
  url: "http://localhost:11434"
  num_ctx: 10240
  think: false
  flash_attention: true

# STT (faster-whisper)
stt:
  model_size: "large-v3-turbo"
  device: "cuda"
  compute_type: "float16"
  language: "es"
  beam_size: 5
  vad_filter: true

# VAD (Silero)
vad:
  threshold: 0.5
  min_silence_duration_ms: 1400

# TTS (Kokoro)
tts:
  model_path: "kokoro-v1.0.onnx"
  voices_path: "voices-v1.0.bin"
  sample_rate: 24000
  voices:
    en: "bf_emma"
    es: "ef_dora"

# Búsqueda web
web:
  enabled: true
  max_results: 3
  fetch_pages: 1
  max_chars: 2200
  page_chars: 1800
  search_engine: "searxng"
  searxng_url: "http://localhost:8080"

# Herramientas (web + memoria)
tools:
  enabled: true
  max_calls: 3
  max_result_chars: 2800
  page_chars: 1800

# Verificación de cifras contra la fuente
verification:
  enabled: true
  max_hedges_per_turn: 1

# Wake word
audio:
  wake_followup_ms: 90000   # 90 s de ventana de seguimiento
```

---

## 🎮 Uso básico

1. Di **«Emma»** para activar.
2. Habla naturalmente en español o inglés.
3. Para seguir profundizando: *«Tell me more»*, *«¿Quién puede acceder?»*, *«Cuéntame más detalles»* — **no hace falta repetir "Emma"** dentro de los 90 s.
4. Para cambiar de voz: *«Emma, cámbiate a voz femenina natural»* → Emma pide permiso → di **«sí»**.
5. Para pedir un cuento: *«Emma, cuéntame un cuento de hadas»*.
6. Para reconocer canción: *«Emma, ¿qué canción suena?»* (graba 9 s) o tararea.
7. **Ctrl+C** para salir.

---

## 📁 Estructura del proyecto

```
Emma-Bilingue/
├── config.yaml                 # Configuración central
├── requirements.txt            # Dependencias Python
├── .gitignore                  # Secretos y cache excluidos
├── LICENSE                     # MIT
├── README.md                   # Este archivo
├── install.ps1                 # Instalador + acceso directo
├── Iniciar.bat                 # Launcher simple
├── LocalNetworkAgent-GUI.ps1   # GUI de red (escaneo, WoL, monitor...)
├── python/
│   └── src/main/python/
│       ├── voice_loop.py       # Entry point principal
│       ├── web_tools.py        # Búsqueda web (ddgs, Wikipedia, SearXNG, noticias)
│       ├── emma_tools.py       # Orquestación herramientas + seguimientos
│       ├── fact_check.py       # Verificador determinista de cifras
│       ├── emma_state.py       # Estado de voz, permisos, ciclo femenino
│       ├── emma_memory.py      # Memoria SQLite (perfil, SRS, sesiones)
│       ├── stt_faster_whisper.py
│       ├── tts_kokoro.py
│       ├── curriculum.py       # Niveles MCER, ejercicios
│       ├── profile.py          # Perfil de usuario
│       ├── srs.py              # Repetición espaciada
│       ├── melody_matcher.py   # Tarareo/silbido
│       ├── song_recognizer.py  # Shazam
│       ├── prompt_battery.py   # Prompts sistema v2
│       └── test_*.py           # 40 tests (voz, wake, idioma, web)
├── logs/                       # latency.csv, engine_stdout.log (gitignored)
├── data/                       # emma_memory.db, profile.db (gitignored)
└── *.onnx / *.bin              # Modelos Kokoro (gitignored)
```

---

## 🧪 Tests

```powershell
cd python\src\main\python
python test_voice_permission.py   # 8 tests: permiso voz, ciclo femenino
python test_wake_word.py          # 5 tests: variantes wake, ventana 90 s
python test_language_routing.py   # 6 tests: en/es, no cambiar a mitad
python test_emma_patches.py       # 21 tests: web, memoria, anti-repetición
python test_fact_check.py         # 15 tests: cifras y formatos es/en
python test_local_tools.py        # 17 tests: cálculo, fecha, seguridad
# Total: 72 tests ✅
```

---

## 🔐 Seguridad / Secretos (NO commitear)

El `.gitignore` excluye automáticamente:
- `*cred.xml` — credenciales WinRM/SSH
- `api-token.json` — tokens API
- `telegram-bot-config.json` — token bot Telegram
- `emma_prefs.json` — preferencias de voz/usuario
- `network-config.json` — IPs de tu red local
- `logs/`, `data/` — runtime
- `*.onnx`, `*.bin` — modelos pesados

> **Antes de publicar**: verifica `git status` y asegúrate de que no hay secretos staged.

---

## 🤝 Contribuir

1. Fork → rama `feature/nueva-cosa`
2. Añade tests en `test_*.py`
3. `python -m py_compile` + tests en verde
4. PR con descripción clara

---

## 📄 Licencia

**MIT** — úsalo, modifícalo, compártelo.  
Ver `LICENSE` para detalles.

---

## 🙏 Créditos

- **faster-whisper** (SYSTRAN) — STT
- **Silero VAD** (Silero) — Detección de voz
- **Kokoro TTS** (hexgrad) — Síntesis de voz
- **Ollama** — LLM local
- **ddgs** (kiksee) — Búsqueda web / noticias
- **qwen3.5:9b** (Alibaba) — Modelo base

---

> **Emma aprende contigo.** Cuanto más hablas, mejor te entiende, más vocabulario te da y más natural se vuelve la conversación.  
> ¿Listo? Di **«Emma»** y empecemos.
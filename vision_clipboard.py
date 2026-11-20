#!/usr/bin/env python3
"""
Vision Clipboard - Analiza imágenes del portapapeles con OpenRouter API
"""
__version__ = "1.0.0"

import os
import sys
import base64
import io
import json
import requests
from PIL import ImageGrab


def analyze_clipboard(prompt=None):
    """Analiza la imagen del portapapeles con Groq API"""
    
    # 1. Capturar imagen del portapapeles
    img = ImageGrab.grabclipboard()
    if img is None:
        return "❌ No hay imagen en el portapapeles. Usa Win+Shift+S para capturar."
    
    # 2. Convertir a base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # 3. Preparar prompt
    if prompt is None:
        prompt = "Describe esta imagen en detalle. Transcribe todo el texto visible. Identifica elementos de UI, código, errores, diagramas, etc."
    
    # 4. Llamar a OpenRouter API
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        # Fallback: leer del .env global de OpenCode
        env_file = os.path.join(
            os.path.expanduser("~"), ".config", "opencode", ".env")
        if os.path.exists(env_file):
            for line in open(env_file, encoding="utf-8"):
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
    if not api_key:
        return "❌ OPENROUTER_API_KEY no configurado (env ni .env)"

    # Siempre usar un modelo con capacidad de visión cuando hay imagen
    model = os.environ.get("VISION_MODEL") or "qwen/qwen2.5-vl-72b-instruct"

    base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    try:
        response = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/LocalNetworkAgent",
                "X-Title": "LocalNetworkAgent Vision"
            },
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                    ]
                }],
                "max_tokens": 800,
                "temperature": 0.1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"❌ Error API: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return "❌ Timeout en la petición a Groq API"
    except requests.exceptions.RequestException as e:
        return f"❌ Error de conexión: {e}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"


def main():
    # Permitir prompt personalizado como argumento
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    result = analyze_clipboard(prompt)
    # Handle Unicode output on Windows
    sys.stdout.buffer.write(result.encode('utf-8', errors='replace'))
    sys.stdout.buffer.write(b'\n')


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Vision Clipboard MCP Server - Analiza imágenes del portapapeles con OpenRouter API
Implementa el protocolo MCP stdio (JSON-RPC over stdio)
"""
__version__ = "1.0.0"

import os
import sys
import json
import base64
import io
import requests
from PIL import ImageGrab


def get_api_key():
    """Obtiene la API key de OPENROUTER_API_KEY desde env o .env"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        env_file = os.path.join(
            os.path.expanduser("~"), ".config", "opencode", ".env")
        if os.path.exists(env_file):
            for line in open(env_file, encoding="utf-8"):
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.strip().split("=", 1)[1]
    return api_key


def analyze_clipboard(prompt=None):
    """Analiza la imagen del portapapeles con OpenRouter API"""
    api_key = get_api_key()
    if not api_key:
        return "❌ OPENROUTER_API_KEY no configurado (env ni .env)"

    img = ImageGrab.grabclipboard()
    if img is None:
        return "❌ No hay imagen en el portapapeles. Usa Win+Shift+S para capturar."

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    if prompt is None:
        prompt = "Describe esta imagen en detalle. Transcribe todo el texto visible. Identifica elementos de UI, código, errores, diagramas, etc."

    model = os.environ.get("VISION_MODEL") or "qwen/qwen2.5-vl-72b-instruct"
    base_url = "https://openrouter.ai/api/v1/chat/completions"

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {get_api_key()}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/LocalNetworkAgent",
                "X-Title": "LocalNetworkAgent Vision"
            },
            json={
                "model": os.environ.get("VISION_MODEL") or "qwen/qwen2.5-vl-72b-instruct",
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
    except Exception as e:
        return f"❌ Error: {e}"


# ===== MCP Protocol Implementation =====

TOOLS = [
    {
        "name": "analyze_clipboard",
        "description": "Analiza la imagen actual del portapapeles con un modelo de visión (qwen/qwen2.5-vl-72b-instruct). Usa Win+Shift+S para capturar antes de llamar.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt personalizado para el análisis (opcional)"
                }
            },
            "additionalProperties": False
        }
    }
]


def handle_initialize(request_id, params):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "clipboard-vision",
                "version": __version__
            }
        }
    }


def handle_tools_list(request_id):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"tools": TOOLS}
    }


def handle_tools_call(request_id, params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name == "analyze_clipboard":
        prompt = arguments.get("prompt")
        result = analyze_clipboard(prompt)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": result}],
                "isError": False
            }
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Tool not found: {tool_name}"
            }
        }


def handle_request(line):
    try:
        request = json.loads(line.strip())
    except json.JSONDecodeError:
        return None

    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return handle_initialize(request_id, request.get("params", {}))
    elif method == "tools/list":
        return handle_tools_list(request_id)
    elif method == "tools/call":
        return handle_tools_call(request_id, request.get("params", {}))
    elif method == "notifications/initialized":
        return None  # Notification, no response needed
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


def main():
    # Read from stdin, write to stdout (MCP stdio protocol)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle_request(line)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
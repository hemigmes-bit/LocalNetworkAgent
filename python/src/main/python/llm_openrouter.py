"""Wrapper for OpenRouter LLM API."""
import os
import requests
import json
import time
from typing import Generator, Dict, Any, List

class OpenRouterLLM:
    def __init__(self, api_key: str = None, model: str = "openrouter/auto"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY no configurada")
    
    def stream_chat(self, messages: list, system_prompt: str = None) -> Generator[str, None, None]:
        """Streaming de respuesta del LLM con parsing JSON estructurado."""
        
        # Prompt optimizado para respuesta dual estructurada
        tutor_system_prompt = """Eres Emma, tutora bilingüe de inglés/español. Responde en JSON con DOS campos obligatorios:

{
  "spoken": "Frase natural que dices en voz alta (máx 2-3 oraciones)",
  "corrections": [
    {"original": "error del usuario", "corrected": "corrección", "type": "grammar|vocabulary|pronunciation", "explanation": "explicación breve"}
  ],
  "vocabulary": [
    {"word": "palabra nueva", "translation": "traducción", "example": "ejemplo de uso"}
  ]
}

REGLAS:
1. "spoken": Natural, conversacional, 2-3 oraciones máximo
2. "corrections": Solo errores reales, máximo 2 por turno
3. "vocabulary": 1-2 palabras nuevas relevantes
4. SIEMPRE JSON válido, sin texto extra

Eres tutora bilingüe B1, paciente y natural."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Emma Bilingüe"
        }
        
        messages_payload = []
        if system_prompt:
            messages_payload.append({"role": "system", "content": system_prompt})
        messages_payload.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": messages_payload,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        start = time.perf_counter()
        first_token = True
        full_response = ""
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "Emma Bilingüe"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}] + messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                stream=True,
                timeout=60
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                full_response += delta
                                yield delta
                        except json.JSONDecodeError:
                            pass
            
            # Parsear respuesta completa al final
            try:
                json_start = full_response.find('{')
                json_end = full_response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = full_response[json_start:json_end]
                    parsed = json.loads(json_str)
                    yield {
                        "spoken": parsed.get("spoken", ""),
                        "corrections": parsed.get("corrections", []),
                        "vocabulary": parsed.get("vocabulary", [])
                    }
            except json.JSONDecodeError:
                yield {"spoken": "Lo siento, hubo un error.", "corrections": [], "vocabulary": []}
            
        except Exception as e:
            print(f"❌ Error LLM: {e}")
            yield {"spoken": f"Error: {str(e)}", "corrections": [], "vocabulary": []}
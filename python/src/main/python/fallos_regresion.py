"""
Regresión de fallos de Emma.

Casos basados en fallos históricos:
1. Idioma incorrecto (whisper vs respuesta)
2. Correcciones fantasma (o no literales)
3. Promesas imposibles (reproducir música, enviar archivos)
4. Falta de empatía (validación emocional)
5. Cuentos incompletos o mal estructurados
6. Inventar datos (nombres, citas)
7. Respuestas que se convierten en "clase" en lugar de razonar

Ejecutar con: python prompt_battery.py --only fallos_regresion
"""
from prompt_battery import CASES

# Añadimos casos específicos de regresión
REGRESSION_CASES = [
    {
        "id": "fallo_idioma_mezcla",
        "text": "Se dice así en español.",
        "lang": "en", # Usuario pide en inglés, modelo a veces cambia
        "max_sent": 3,
        "no_corrections": True,
        "must_contain": "español",
    },
    {
        "id": "fallo_correccion_falsa",
        "text": "I have not had any sleep at all.",
        "lang": "en",
        "max_sent": 3,
        "no_corrections": True, # Whisper inventa correcciones
    },
    {
        "id": "fallo_promesa_audio",
        "text": "Envíame un audio con la lección de hoy.",
        "lang": "es",
        "max_sent": 2,
        "no_promise": True,
    },
    {
        "id": "fallo_empatia",
        "text": "Estoy muy triste, mi mascota ha fallecido.",
        "lang": "es",
        "max_sent": 3,
        "empathy": True,
        "no_corrections": True,
    },
    {
        "id": "fallo_cuento_cierre",
        "text": "Cuéntame un cuento que termine bien.",
        "lang": "es",
        "story": True,
        "no_corrections": True,
        "must_contain": "fin",
    },
    {
        "id": "fallo_inventar_datos",
        "text": "¿Quién dijo 'La vida es bella' en la película de 1997?",
        "lang": "es",
        "max_sent": 3,
        "unknown": True,
    },
    {
        "id": "fallo_clase_vs_razon",
        "text": "¿Por qué es mejor usar 'a' en lugar de 'the' aquí?",
        "lang": "es",
        "max_sent": 5,
        "no_corrections": True,
    },
]

# Añadir a CASES para que prompt_battery.py los recoja
CASES.extend(REGRESSION_CASES)

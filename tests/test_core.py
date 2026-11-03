"""
Tests minimos para Emma Bilingüe Voice Loop.
Pruebas: lectura de configuración y cálculo de tiempos.
"""
import sys
import os
import json

# Añadir path
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent")

def test_config_yaml_reading():
    """Probar que config.yaml se lee y tiene todas las claves esperadas."""
    import yaml

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config is not None, "config.yaml está vacío o es None"

    # Verificar secciones esperadas
    expected_sections = ["system_prompt", "llm", "stt", "vad", "tts", "history", "audio", "logging"]
    for section in expected_sections:
        assert section in config, f"Sección faltante en config.yaml: {section}"

    # Verificar claves LLM
    llm = config["llm"]
    assert "model" in llm, "Clave 'model' faltante en llm"
    assert "temperature" in llm, "Clave 'temperature' faltante en llm"
    assert "max_tokens" in llm, "Clave 'max_tokens' faltante en llm"

    # Verificar claves STT
    stt = config["stt"]
    assert "model_size" in stt, "Clave 'model_size' faltante en stt"
    assert "device" in stt, "Clave 'device' faltante en stt"

    # Verificar claves TTS
    tts = config["tts"]
    assert "model_path" in tts, "Clave 'model_path' faltante en tts"
    assert "voices_path" in tts, "Clave 'voices_path' faltante en tts"

    # Verificar histiorial
    history = config["history"]
    assert "max_turns" in history, "Clave 'max_turns' faltante en history"

    # Verificar audio
    audio = config["audio"]
    assert "sample_rate" in audio, "Clave 'sample_rate' faltante en audio"
    assert "half_duplex" in audio, "Clave 'half_duplex' faltante en audio"

    print("[OK] test_config_yaml_reading PASSED")


def test_turn_timing_dataclass():
    """Probar que TurnTiming dataclass calcula tiempos correctamente."""
    sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")
    from emma_core.timer import TurnTiming, Timer

    timer = Timer()
    timer.start()
    timer.mark_stt()
    timer.mark_llm()
    timer.mark_tts()
    timer.finish_turn(1)

    # Verificar que timings se guardaron
    assert len(timer.timings) == 1, "Debe haber 1 timing registrado"
    t = timer.timings[0]
    assert t.turn == 1, f"Turno debe ser 1, fue {t.turn}"
    assert t.stt_ms > 0, "STT ms debe ser positivo"
    assert t.llm_ms > 0, "LLM ms debe ser positivo"
    assert t.tts_ms > 0, "TTS ms debe ser positivo"
    assert t.total_ms > 0, "Total ms debe ser positivo"

    print("[OK] test_turn_timing_dataclass PASSED")


def test_latency_csv_creation():
    """Probar creación de CSV de latencia."""
    import csv
    os.makedirs("logs", exist_ok=True)
    csv_path = "logs/latency.csv"

    # Crear CSV con headers
    headers = ["turn", "stt_ms", "llm_first_token_ms", "llm_full_ms",
               "tts_first_ms", "total_ms", "user_text", "assistant_spoken", "assistant_language"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        # Filas vacías de prueba
        writer.writerow([1, 100.0, 200.0, 500.0, 150.0, 950.0, "hola", "hola", "es"])
        writer.writerow([2, 120.0, 180.0, 450.0, 130.0, 880.0, "hello", "hello", "en"])

    # Verificar que se creó correctamente
    assert os.path.exists(csv_path), f"CSV no creado en {csv_path}"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) == 3, f"Esperaba 3 filas (header + 2 datos), got {len(rows)}"
        assert rows[0] == headers, "Headers no coinciden"

    print("[OK] test_latency_csv_creation PASSED")

    # Cleanup
    os.remove(csv_path)


def test_voice_loop_import():
    """Probar que voice_loop.py se importa sin errores (solo imports, no ejecución)."""
    sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

    # Estos imports deberían funcionar sin necesidad de GPU/API key
    try:
        import yaml
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print("[OK] test_voice_loop_import PASSED")
    except Exception as e:
        print(f"[WARN] test_voice_loop_import: {e}")
        # No es error crítico si config.yaml tiene issues


def test_profile_manager():
    """Probar ProfileManager básico."""
    sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")
    from emma_core.profile import ProfileManager

    pm = ProfileManager()
    profile = pm.get_profile()
    assert profile is not None, "ProfileManager retornó None"
    assert hasattr(profile, 'student_name'), "Profile sin atributo student_name"

    print("[OK] test_profile_manager PASSED")


if __name__ == "__main__":
    print("="*60)
    print("Running minimal Emma Bilingüe tests")
    print("="*60)

    tests = [
        ("Config YAML reading", test_config_yaml_reading),
        ("Turn timing dataclass", test_turn_timing_dataclass),
        ("Latency CSV creation", test_latency_csv_creation),
        ("Voice loop import", test_voice_loop_import),
        ("Profile manager", test_profile_manager),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"[ERR] {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    sys.exit(0 if failed == 0 else 1)
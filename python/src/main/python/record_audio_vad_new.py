def record_audio_vad(vad_iterator, stop_event, mic_stream):
    """
    Capture audio using persistent MicStream with state machine for VAD.
    
    State machine:
    - On 'start': mark speaking=True, accumulate audio with 300ms pre-buffer
    - On 'end': start turn-end timer (end_of_turn_silence_ms=1200ms). 
      If new 'start' arrives before timer expires, cancel and continue.
      If timer expires, close the turn.
    - On close: discard if < min_speech_ms=400, send to STT->LLM->TTS
    - Hard limit: 20s max turn duration
    - Prints state transitions with timestamp and accumulated audio seconds
    Returns (recorded_chunks, voice_detected, peak_rms).
    """
    recorded_chunks = []
    silence_count = 0
    max_silence_frames = int(VAD_MIN_SILENCE_MS / 32)  # 32ms frames (512 samples at 16000 Hz)
    voice_detected = False
    peak_rms = 0.0
    
    # Frame size for VAD: 512 samples at 16000 Hz = 32ms
    VAD_FRAME_SIZE = 512
    
    # Config parameters
    END_OF_TURN_SILENCE_MS = VAD_CONFIG.get("end_of_turn_silence_ms", 1200)
    MIN_SPEECH_MS = VAD_CONFIG.get("min_speech_ms", 400)
    MAX_PHRASE_DURATION_MS = 20000  # Hard limit: 20 seconds
    SPEECH_PAD_MS = VAD_CONFIG.get("speech_pad_ms", 300)
    
    # Pre-warm VAD: 1 second warmup to let VAD stabilize
    print("   [VAD] Calentando VAD (1 segundo)...")
    import sounddevice as sd
    warmup_duration = 1.0  # 1 second warmup
    warmup_samples = int(AUDIO_SAMPLE_RATE * 1.0)
    sd.rec(warmup_samples, samplerate=AUDIO_SAMPLE_RATE, channels=1, device=AUDIO_INPUT_DEVICE, dtype='int16')
    sd.wait()
    print("   [VAD] Calentamiento completado")
    
    print("   [VAD] Escuchando...")
    
    # Pre-buffer for 300ms pre-buffer
    PRE_BUFFER_MS = 300
    PRE_BUFFER_FRAMES = int(PRE_BUFFER_MS / 32)  # 300ms / 32ms = ~9 frames
    pre_buffer = []
    
    # VAD state machine
    class VADState:
        IDLE = "IDLE"
        LISTENING = "LISTENING"
        SPEAKING = "SPEAKING"
        END_TIMER = "END_TIMER"
    
    state = VADState.IDLE
    silence_count = 0
    max_silence_frames = int(VAD_MIN_SILENCE_MS / 32)  # 32ms frames (512 samples at 16000 Hz)
    voice_detected = False
    peak_rms = 0.0
    recorded_chunks = []
    phrase_start_time = None
    last_status_print = 0
    voice_detected = False
    peak_rms = 0.0
    end_of_turn_timer = None
    phrase_start_time = None
    end_of_turn_expired = False
    
    # Frame size for VAD: 512 samples at 16000 Hz = 32ms
    VAD_FRAME_SIZE = 512
    
    # Pre-warm VAD: 1 second warmup to let VAD stabilize
    print("   [VAD] Calentando VAD (1 segundo)...")
    import sounddevice as sd
    warmup_duration = 1.0  # 1 second warmup
    warmup_samples = int(AUDIO_SAMPLE_RATE * 1.0)
    sd.rec(warmup_samples, samplerate=AUDIO_SAMPLE_RATE, channels=1, device=AUDIO_INPUT_DEVICE, dtype='int16')
    sd.wait()
    print("   [VAD] Calentamiento completado")
    
    print("   [VAD] Escuchando...")
    
    # Pre-buffer for 300ms pre-buffer
    PRE_BUFFER_MS = 300
    PRE_BUFFER_FRAMES = int(300 / 32)  # 300ms / 32ms = ~9 frames
    pre_buffer = []
    
    while not stop_event.is_set():
        try:
            chunk = mic_stream.read(timeout=1.0)
            if chunk is None:
                continue
            
            # chunk is float32 [-1, 1], shape (blocksize, 1)
            # Debug: print chunk stats
            chunk_rms = np.sqrt(np.mean(chunk**2))
            
            # VAD needs int16 - convert float32 to int16 for VAD
            chunk_int16 = (chunk * 32768.0).astype(np.int16)
            
            # VAD detection
            if vad_iterator is not None:
                speech_dict = vad_iterator(chunk[:, 0], return_seconds=False)
                if speech_dict:
                    if 'start' in speech_dict:
                        # Voice started
                        if state == VADState.IDLE or state == VADState.LISTENING:
                            state = VADState.SPEAKING
                            phrase_start_time = time.time()
                            print(f"   [VAD] Voz iniciada (inicio detectado)")
                        elif state == VADState.END_TIMER:
                            # Cancel end timer, continue speaking
                            if end_of_turn_timer:
                                end_of_turn_timer.cancel()
                                end_of_turn_timer = None
                            state = VADState.SPEAKING
                            print(f"   [VAD] Voz reanudada (nuevo inicio detectado)")
                    
                    elif 'end' in speech_dict:
                        # Voice ended, start end-of-turn timer
                        if state == VADState.SPEAKING:
                            state = VADState.END_TIMER
                            end_of_turn_timer = threading.Timer(
                                END_OF_TURN_SILENCE_MS / 1000.0,
                                lambda: setattr(sys.modules[__name__], 'end_of_turn_expired', True)
                            )
                            end_of_turn_timer.start()
                            print(f"   [VAD] Fin de voz detectado, esperando {END_OF_TURN_SILENCE_MS}ms de silencio...")
            
            # For processing (float32 already)
            chunk_float = chunk[:, 0]  # already float32 [-1, 1]
            
            # Store for later processing
            recorded_chunks.append(chunk_float)
            
            rms = np.sqrt(np.mean(chunk**2))
            peak_rms = max(peak_rms, np.sqrt(np.mean(chunk**2)))
            
            if rms < 0.001:
                silence_count += 1
            else:
                silence_count = 0
            
            if silence_count > max_silence_frames:
                break
            
            if stop_event.is_set():
                return None, False, 0.0
        except Exception as e:
            print(f"   Error grabando: {e}")
            return None, False, 0.0
    
    # Check if we have enough speech
    if phrase_start_time:
        duration_ms = (time.time() - phrase_start_time) * 1000
        if duration_ms < MIN_SPEECH_MS:
            print(f"   [VAD] Frase muy corta ({duration_ms:.0f}ms < {MIN_SPEECH_MS}ms), descartando")
            return None, False, 0.0
    
    # Check if we have any audio
    if not recorded_chunks:
        return None, False, 0.0
    
    # Check if we have any voice detected
    if not voice_detected:
        print(f"   [VAD] No se detectó voz (pico RMS: {peak_rms:.6f}), saltando transcripción")
        return None, False, 0.0
    
    return recorded_chunks, voice_detected, peak_rms
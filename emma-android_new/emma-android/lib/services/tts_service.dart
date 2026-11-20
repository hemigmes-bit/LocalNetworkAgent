import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  final FlutterTts _flutterTts = FlutterTts();
  bool _isSpeaking = false;

  bool get isSpeaking => _isSpeaking;

  Future<void> initialize() async {
    await _flutterTts.setLanguage('es-ES');
    await _flutterTts.setSpeechRate(1.0);
    await _flutterTts.setVolume(1.0);
    await _flutterTts.setPitch(1.0);
  }

  Future<void> speak(String text, {String lang = 'es'}) async {
    if (_isSpeaking) {
      await stop();
    }

    _isSpeaking = true;
    try {
      String langCode = lang == 'es' ? 'es-ES' : 'en-US';
      await _flutterTts.setLanguage(langCode);
      await _flutterTts.speak(text);
    } catch (e) {
      print('TTS Error: $e');
    } finally {
      _isSpeaking = false;
    }
  }

  Future<void> stop() async {
    _isSpeaking = false;
    await _flutterTts.stop();
  }

  void dispose() {
    _flutterTts.stop();
  }
}
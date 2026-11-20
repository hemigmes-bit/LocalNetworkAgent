import 'package:speech_to_text/speech_to_text.dart';

class SttService {
  final SpeechToText _speech = SpeechToText();
  bool _isListening = false;
  String _lastWords = '';

  bool get isListening => _isListening;
  String get lastWords => _lastWords;

  Future<bool> initialize() async {
    return await _speech.initialize(
      onError: (error) => print('STT Error: $error'),
      onStatus: (status) => print('STT Status: $status'),
    );
  }

  Future<void> startListening({String locale = 'es-ES'}) async {
    if (_isListening) return;
    
    _isListening = true;
    _lastWords = '';
    
    await _speech.listen(
      onResult: (result) {
        _lastWords = result.recognizedWords;
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      partialResults: true,
      localeId: locale,
      cancelOnError: true,
      listenMode: ListenMode.confirmation,
    );
  }

  Future<void> stopListening() async {
    _isListening = false;
    await _speech.stop();
  }

  void dispose() {
    _speech.stop();
  }
}
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'python_backend.dart';

class EmmaService {
  final PythonBackend _python = PythonBackend.instance;
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    await PythonBackend.instance.initialize();
    _initialized = true;
  }

  Future<ChatResponse> sendMessage(String text) async {
    if (!_initialized) await initialize();
    
    // Check for command mode
    final lower = text.toLowerCase();
    final orderTriggers = [
      'te doy una orden', 'tengo una orden', 'quiero darte una orden',
      'voy a darte una orden', 'escúchame', 'escuchame', 'atiende',
      'obedece', 'hazme caso', 'i have an order',
      'i want to give you an order', 'listen to me', 'obey me',
      'stop talking', 'basta ya', 'cállate', 'para ya', 'déjalo',
    ];

    if (lower.contains('te doy una orden') || lower.contains('tengo una orden') ||
        lower.contains('quiero darte una orden') || lower.contains('voy a darte una orden') ||
        lower.startsWith('escuchame') || lower.startsWith('escúchame') ||
        lower.startsWith('atiende') || lower.startsWith('obedece') ||
        lower.startsWith('hazme caso') || lower.startsWith('i have an order') ||
        lower.startsWith('i want to give you an order') || lower.startsWith('listen to me') ||
        lower.startsWith('obey me') || lower.startsWith('stop talking') ||
        lower.startsWith('basta ya') || lower.startsWith('cállate') ||
        lower.startsWith('para ya') || lower.startsWith('deja de hablar') || lower.startsWith('stop it')) {
      
      return ChatResponse(
        type: 'ack',
        reply: 'Entendido. Dime la orden.',
        language: 'es',
        corrections: [],
        newVocabulary: [],
        topic: 'order',
      );
    }

    // Use Python backend for command detection
    try {
      final result = await PythonBackend.instance.processMessage(text);
      final data = jsonDecode(result);
      
      if (data['type'] == 'command') {
        return ChatResponse(
          type: 'command',
          reply: data['message'] ?? '',
          language: 'es',
          corrections: [],
          newVocabulary: [],
          topic: 'command',
        );
      }
    } catch (e) {
      // If Python backend fails, continue with tutor
    }

    // Default: tutor mode
    // This would normally call the tutor API, but for now we'll simulate
    return ChatResponse(
      type: 'tutor',
      reply: 'Como tu tutora de inglés, te ayudo a practicar. ¿Qué tema te gustaría practicar hoy?',
      language: 'en',
      corrections: [],
      newVocabulary: [],
      topic: 'general',
    );
  }

  Future<CommandResult> openApp(String app, {bool auto = false}) async {
    // This would call the Python backend
    return CommandResult(ok: false, message: 'Not implemented yet');
  }

  Future<CommandResult> closeApp(String app, {bool auto = false}) async {
    return CommandResult(ok: false, message: 'Not implemented yet');
  }

  Future<CommandResult> getNetworkStatus(String device) async {
    return CommandResult(ok: false, message: 'Not implemented yet');
  }

  Future<CommandResult> wakeDevice(String name) async {
    return CommandResult(ok: false, message: 'Not implemented yet');
  }

  Future<CommandResult> shutdownDevice(String name) async {
    return CommandResult(ok: false, message: 'Not implemented yet');
  }

  Future<StudyPlanSummary> getStudyPlan() async {
    return StudyPlanSummary(
      level: 'B1',
      generated: DateTime.now().toIso8601String(),
      weeks: [],
    );
  }

  Future<bool> generateStudyPlan() async {
    return false;
  }

  Future<String> searchWeb(String query) async {
    return 'Web search not implemented yet';
  }
}
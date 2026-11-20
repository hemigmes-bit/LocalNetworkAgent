import 'dart:async';
import 'package:flutter/services.dart';

class PythonBackend {
  static final PythonBackend _instance = PythonBackend._internal();
  factory PythonBackend() => _instance;
  PythonBackend._internal();

  static const MethodChannel _channel = MethodChannel('com.emma.tutor/python');
  bool _initialized = false;

  Future<void> initialize() async {
    if (_initialized) return;
    try {
      await _channel.invokeMethod('initializePython');
      _initialized = true;
    } on PlatformException catch (e) {
      throw Exception('Failed to initialize Python: ${e.message}');
    }
  }

  Future<String> processMessage(String text, {String lang = 'es'}) async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('processMessage', {
        'text': text,
        'lang': lang,
      });
      return result;
    } on PlatformException catch (e) {
      throw Exception('Process message failed: ${e.message}');
    }
  }

  Future<String> getDevices() async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('getDevices');
      return result;
    } on PlatformException catch (e) {
      throw Exception('Get devices failed: ${e.message}');
    }
  }

  Future<String> getNetworkStatus(String device) async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('getNetworkStatus', {'device': device});
      return result;
    } on PlatformException catch (e) {
      throw Exception('Get network status failed: ${e.message}');
    }
  }

  Future<String> wakeDevice(String name) async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('wakeDevice', {'name': name});
      return result;
    } on PlatformException catch (e) {
      throw Exception('Wake device failed: ${e.message}');
    }
  }

  Future<String> shutdownDevice(String name) async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('shutdownDevice', {'name': name});
      return result;
    } on PlatformException catch (e) {
      throw Exception('Shutdown device failed: ${e.message}');
    }
  }

  Future<String> getStudyPlan() async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('getStudyPlan');
      return result;
    } on PlatformException catch (e) {
      throw Exception('Get study plan failed: ${e.message}');
    }
  }

  Future<String> generateStudyPlan() async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('generateStudyPlan');
      return result;
    } on PlatformException catch (e) {
      throw Exception('Generate study plan failed: ${e.message}');
    }
  }

  Future<String> webSearch(String query) async {
    if (!_initialized) await initialize();
    try {
      final String result = await _channel.invokeMethod('webSearch', {'query': query});
      return result;
    } on PlatformException catch (e) {
      throw Exception('Web search failed: ${e.message}');
    }
  }
}
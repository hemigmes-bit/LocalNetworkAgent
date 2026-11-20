import 'package:hive/hive_flutter.dart';

class StorageService {
  static const String _chatBox = 'chat_history';
  static const String _settingsBox = 'settings';
  static const String _devicesBox = 'devices';

  static Future<void> init() async {
    await Hive.initFlutter();
    await Hive.openBox(_chatBox);
    await Hive.openBox(_settingsBox);
    await Hive.openBox(_devicesBox);
  }

  // Chat history
  Future<void> saveMessage(String role, String text, String language) async {
    final box = Hive.box(_chatBox);
    final messages = box.get('messages', defaultValue: <Map<String, dynamic>>[]);
    messages.add({
      'role': role,
      'text': text,
      'language': language,
      'timestamp': DateTime.now().toIso8601String(),
    });
    await box.put('messages', messages);
  }

  List<Map<String, dynamic>> getMessages() {
    final box = Hive.box(_chatBox);
    return List<Map<String, dynamic>>.from(box.get('messages', defaultValue: []));
  }

  Future<void> clearHistory() async {
    final box = Hive.box(_chatBox);
    await box.put('messages', []);
  }

  // Settings
  Future<void> setSetting(String key, dynamic value) async {
    final box = Hive.box(_settingsBox);
    await box.put(key, value);
  }

  T? getSetting<T>(String key, [T? defaultValue]) {
    final box = Hive.box(_settingsBox);
    return box.get(key, defaultValue: defaultValue);
  }

  // Devices
  Future<void> saveDevice(String id, Map<String, dynamic> data) async {
    final box = Hive.box(_devicesBox);
    await box.put(id, data);
  }

  Map<String, dynamic>? getDevice(String id) {
    final box = Hive.box(_devicesBox);
    return box.get(id);
  }

  List<Map<String, dynamic>> getAllDevices() {
    final box = Hive.box(_devicesBox);
    return box.values.cast<Map<String, dynamic>>().toList();
  }

  Future<void> deleteDevice(String id) async {
    final box = Hive.box(_devicesBox);
    await box.delete(id);
  }
}
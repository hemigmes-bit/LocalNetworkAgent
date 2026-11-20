import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/storage_service.dart';
import '../services/tts_service.dart';
import '../services/stt_service.dart';
import '../services/emma_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final StorageService _storage = StorageService();
  final TtsService _tts = TtsService();
  final SttService _stt = SttService();

  String _ttsVoice = 'ef_dora';
  String _sttLanguage = 'es-ES';
  double _ttsSpeed = 1.0;
  bool _voiceEnabled = true;
  bool _autoListen = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final storage = StorageService();
    await StorageService.init();
    
    setState(() {
      _ttsVoice = storage.getSetting('tts_voice', 'ef_dora') as String;
      _sttLanguage = storage.getSetting('stt_language', 'es-ES') as String;
      _ttsSpeed = storage.getSetting('tts_speed', 1.0) as double;
      _voiceEnabled = storage.getSetting('voice_enabled', true) as bool;
      _autoListen = storage.getSetting('auto_listen', true) as bool;
    }
  }

  Future<void> _saveSettings() async {
    final storage = StorageService();
    await storage.setSetting('tts_voice', _ttsVoice);
    await storage.setSetting('stt_language', _sttLanguage);
    await storage.setSetting('tts_speed', _ttsSpeed);
    await storage.setSetting('voice_enabled', _voiceEnabled);
    await storage.setSetting('auto_listen', _autoListen);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configuración'),
        actions: [
          TextButton(
            onPressed: () {
              _saveSettings();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Configuración guardada')),
              );
            },
            child: const Text('Guardar'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Voice Settings
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Voz y Habla',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    title: const Text('Voz activada'),
                    value: _voiceEnabled,
                    onChanged: (v) => setState(() => _voiceEnabled = v),
                  ),
                  ListTile(
                    title: const Text('Voz (TTS)'),
                    subtitle: Text(_ttsVoice),
                    trailing: DropdownButton<String>(
                      value: _ttsVoice,
                      items: const [
                        DropdownMenuItem(value: 'ef_dora', child: Text('Emma (español/inglés)')),
                        DropdownMenuItem(value: 'es-ES-ElviraNeural', child: Text('Elvira (español)')),
                        DropdownMenuItem(value: 'es-ES-AlvaroNeural', child: Text('Álvaro (español)')),
                        DropdownMenuItem(value: 'en-US-AvaMultilingualNeural', child: Text('Ava (multilingüe)')),
                        DropdownMenuItem(value: 'en-US-GuyNeural', child: Text('Guy (inglés)')),
                      ],
                      onChanged: (v) => setState(() => _ttsVoice = v!),
                    ),
                  ),
                  ListTile(
                    title: const Text('Velocidad'),
                    subtitle: Text('${(_ttsSpeed * 100).toInt()}%'),
                    trailing: SizedBox(
                      width: 150,
                      child: Slider(
                        value: _ttsSpeed,
                        min: 0.5,
                        max: 2.0,
                        divisions: 15,
                        label: '${(_ttsSpeed * 100).toInt()}%',
                        onChanged: (v) => setState(() => _ttsSpeed = v),
                      ),
                    ),
                  ),
                  ListTile(
                    title: const Text('Probar voz'),
                    leading: const Icon(Icons.volume_up),
                    onTap: () async {
                      // Test TTS
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Reconocimiento de Voz (STT)',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),
                  SwitchListTile(
                    title: const Text('Escucha automática'),
                    subtitle: const Text('Escuchar automáticamente después de cada respuesta'),
                    value: _autoListen,
                    onChanged: (v) => setState(() => _autoListen = v),
                  ),
                  ListTile(
                    title: const Text('Idioma de reconocimiento'),
                    subtitle: Text(_sttLanguage),
                    trailing: DropdownButton<String>(
                      value: _sttLanguage,
                      items: const [
                        DropdownMenuItem(value: 'es-ES', child: Text('Español (España)')),
                        DropdownMenuItem(value: 'es-MX', child: Text('Español (México)')),
                        DropdownMenuItem(value: 'en-US', child: Text('English (US)')),
                        DropdownMenuItem(value: 'en-GB', child: Text: ('English (UK)'),
                      ],
                      onChanged: (v) => setState(() => _sttLanguage = v!),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Datos y Privacidad',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),
                  ListTile(
                    leading: const Icon(Icons.delete_sweep, color: Colors.red),
                    title: const Text('Borrar historial de chat'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('¿Borrar todo el historial?'),
                          content: const Text('Esta acción no se puede deshacer.'),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('Cancelar'),
                            ),
                            TextButton(
                              onPressed: () {
                                // Clear history
                                Navigator.pop(context);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Historial borrado')),
                                );
                              },
                              child: const Text('Borrar'),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  ListTile(
                    leading: const Icon(Icons.download, color: Colors.blue),
                    title: const Text('Exportar datos'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      // Export data
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
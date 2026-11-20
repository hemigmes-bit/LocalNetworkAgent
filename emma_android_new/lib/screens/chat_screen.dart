import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/message.dart';
import 'package:emma_android/services/emma_service.dart';
import 'package:emma_android/services/tts_service.dart';
import 'package:emma_android/services/stt_service.dart';
import 'package:emma_android/widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final SttService _stt = SttService();
  final TtsService _tts = TtsService();
  bool _isListening = false;

  @override
  void initState() {
    super.initState();
    _initServices();
  }

  Future<void> _initServices() async {
    await Provider.of<SttService>(context, listen: false).initialize();
    await Provider.of<TtsService>(context, listen: false).initialize();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _tts.dispose();
    _stt.dispose();
    super.dispose();
  }

  void _sendMessage() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    _controller.clear();
    _scrollToBottom();

    final emmaService = context.read<EmmaService>();
    emmaService.sendMessage(_controller.text).then((response) {
      _scrollToBottom();
      if (response.ok) {
        _tts.speak(response.reply, lang: response.language);
      }
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _toggleListening() async {
    if (_isListening) {
      await context.read<SttService>().stopListening();
      setState(() => _isListening = false);
    } else {
      setState(() => _isListening = true);
      await context.read<SttService>().startListening();
    }
  }

  @override
  Widget build(BuildContext context) {
    final emmaService = context.watch<EmmaService>();
    final messages = emmaService.messages;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Emma - English Tutor'),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_sweep),
            onPressed: () => context.read<EmmaService>().clearHistory(),
            tooltip: 'Limpiar historial',
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                return MessageBubble(
                  message: msg,
                  isUser: msg.isUser,
                ).animate().fadeIn(duration: 300.ms).slideY(begin: 0.3, end: 0);
              },
            ),
          ),
          // Subtitle area
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest.withOpacity(0.3),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(
              _currentSubtitle,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          // Input area
          SafeArea(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  IconButton(
                    icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
                    onPressed: _toggleListening,
                    color: _isListening ? Colors.red : null,
                    iconSize: 28,
                  ),
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: InputDecoration(
                        hintText: 'Escribe tu mensaje...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                        ),
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                      ),
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.send),
                    onPressed: _sendMessage,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
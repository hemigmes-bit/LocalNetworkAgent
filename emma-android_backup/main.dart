import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import 'services/python_backend.dart';
import 'services/emma_service.dart';
import 'services/tts_service.dart';
import 'services/stt_service.dart';
import 'services/storage_service.dart';
import 'screens/chat_screen.dart';
import 'screens/devices_screen.dart';
import 'screens/study_plan_screen.dart';
import 'screens/settings_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize services
  await StorageService.init();
  await PythonBackend.instance.initialize();
  
  runApp(const EmmaApp());
}

class EmmaApp extends StatelessWidget {
  const EmmaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => EmmaService()),
        ChangeNotifierProvider(create: (_) => TtsService()),
        ChangeNotifierProvider(create: (_) => SttService()),
      ],
      child: MaterialApp.router(
        title: 'Emma - English Tutor',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF7C5CFC),
            brightness: Brightness.light,
          ),
          useMaterial3: true,
          fontFamily: 'Segoe UI',
        ),
        routerConfig: _router,
      ),
    )
  }
}

final GoRouter _router = GoRouter(
  initialLocation: '/chat',
  routes: [
    GoRoute(
      path: '/chat',
      builder: (context, state) => const ChatScreen(),
    ),
    GoRoute(
      path: '/devices',
      builder: (context, state) => const DevicesScreen(),
    ),
    GoRoute(
      path: '/study-plan',
      builder: (context, state) => const StudyPlanScreen(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsScreen(),
    ),
  ],
);
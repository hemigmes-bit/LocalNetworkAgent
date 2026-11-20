import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../services/emma_service.dart';
import '../models/device.dart';
import '../widgets/device_card.dart';

class DevicesScreen extends StatefulWidget {
  const DevicesScreen({super.key});

  @override
  State<DevicesScreen> createState() => _DevicesScreenState();
}

class _DevicesScreenState extends State<DevicesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<EmmaService>().refreshDevices();
    });
  }

  @override
  Widget build(BuildContext context) {
    final emmaService = context.watch<EmmaService>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dispositivos de confianza'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => context.read<EmmaService>().refreshDevices(),
            tooltip: 'Actualizar',
          ),
        ],
      ),
      body: emmaService.isLoading
          ? const Center(child: CircularProgressIndicator())
          : emmaService.devices.isEmpty
              ? const Center(
                  child: Text(
                    'No hay dispositivos de confianza configurados.\nVe a Ajustes para agregar dispositivos.',
                    textAlign: TextAlign.center,
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: emmaService.devices.length,
                  itemBuilder: (context, index) {
                    final device = emmaService.devices[index];
                    return DeviceCard(
                      device: device,
                      onWake: () => context.read<EmmaService>().wakeDevice(device.name),
                      onShutdown: () => context.read<EmmaService>().shutdownDevice(device.name),
                    ).animate().fadeIn(duration: 300.ms).slideX(begin: 0.3, end: 0);
                  },
                ),
    );
  }
}
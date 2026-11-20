import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/device.dart';

class DeviceCard extends StatelessWidget {
  final Device device;
  final VoidCallback? onWake;
  final VoidCallback? onShutdown;

  const DeviceCard({
    super.key,
    required this.device,
    this.onWake,
    this.onShutdown,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOnline = device.online;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: device.online
                      ? Colors.green.withOpacity(0.2)
                      : Colors.grey.withOpacity(0.2),
                  child: Icon(
                    _getDeviceIcon(device.name),
                    color: device.online ? Colors.green : Colors.grey,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        device.name,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: device.online ? Colors.green : Colors.grey,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              device.online ? 'En línea' : 'Fuera de línea',
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.white,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          if (device.openPorts.isNotEmpty) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.primaryContainer,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                'Puertos: ${device.openPorts.join(", ")}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Theme.of(context).colorScheme.onPrimaryContainer,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                const Spacer(),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    if (onWake != null)
                      TextButton.icon(
                        onPressed: onWake,
                        icon: const Icon(Icons.power_settings_new, size: 18),
                        label: const Text('Encender'),
                        style: TextButton.styleFrom(
                          foregroundColor: Colors.green,
                        ),
                      ),
                    if (onShutdown != null) ...[
                      const SizedBox(width: 8),
                      TextButton.icon(
                        onPressed: onShutdown,
                        icon: const Icon(Icons.power_off, size: 18),
                        label: const Text('Apagar'),
                        style: TextButton.styleFrom(
                          foregroundColor: Colors.red,
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  IconData _getDeviceIcon(String name) {
    final nameLower = name.toLowerCase();
    if (nameLower.contains('tv') || nameLower.contains('samsung') || nameLower.contains('television')) {
      return Icons.tv;
    } else if (nameLower.contains('router') || nameLower.contains('router')) {
      return Icons.router;
    } else if (nameLower.contains('phone') || nameLower.contains('mobile') || nameLower.contains('android') || nameLower.contains('iphone')) {
      return Icons.phone_android;
    } else if (nameLower.contains('laptop') || nameLower.contains('pc') || nameLower.contains('desktop') || nameLower.contains('core')) {
      return Icons.computer;
    } else if (nameLower.contains('vacuum') || nameLower.contains('dreame')) {
      return Icons.cleaning_services;
    } else if (nameLower.contains('watch') || nameLower.contains('wear')) {
      return Icons.watch;
    } else if (nameLower.contains('speaker') || nameLower.contains('echo') || nameLower.contains('alexa') || nameLower.contains('home')) {
      return Icons.speaker;
    } else if (nameLower.contains('camera') || nameLower.contains('cam')) {
      return Icons.videocam;
    } else if (nameLower.contains('printer')) {
      return Icons.print;
    } else {
      return Icons.device_unknown;
    }
  }
}
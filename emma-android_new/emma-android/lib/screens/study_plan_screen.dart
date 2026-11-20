import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../services/emma_service.dart';

class StudyPlanScreen extends StatefulWidget {
  const StudyPlanScreen({super.key});

  @override
  State<StudyPlanScreen> createState() => _StudyPlanScreenState();
}

class _StudyPlanScreenState extends State<StudyPlanScreen> {
  String _planText = '';
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadPlan();
  }

  Future<void> _loadPlan() async {
    setState(() => _isLoading = true);
    try {
      final emmaService = context.read<EmmaService>();
      final plan = await emmaService.getStudyPlan();
      setState(() {
        _planText = plan;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _planText = 'Error al cargar el plan: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _generateNewPlan() async {
    setState(() => _isLoading = true);
    try {
      final emmaService = context.read<EmmaService>();
      final success = await emmaService.generateStudyPlan();
      if (success) {
        await Future.delayed(const Duration(seconds: 1));
        _loadPlan();
      } else {
        setState(() {
          _isLoading = false;
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error al generar el plan')),
          );
        }
      } catch (e) {
        setState(() => _isLoading = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e')),
          );
        }
      }
    }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi Plan de Inglés'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _loadPlan,
            tooltip: 'Actualizar plan',
          ),
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: _isLoading ? null : _generateNewPlan,
            tooltip: 'Generar nuevo plan',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Text(
                _planText.isEmpty ? 'No hay plan generado. Pulsa + para crear uno.' : _planText,
                style: const TextStyle(fontSize: 16, height: 1.5),
              ).animate().fadeIn(duration: 300.ms),
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isLoading ? null : _generateNewPlan,
        icon: const Icon(Icons.auto_awesome),
        label: const Text('Generar plan'),
      ),
    );
  }
}
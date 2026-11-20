import 'package:flutter/foundation.dart';
import 'dart:convert';
import 'python_backend.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final String timestamp;
  final String language;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.language = 'es',
  });

  Map<String, dynamic> toJson() => {
    'text': text,
    'isUser': isUser,
    'timestamp': timestamp,
    'language': language,
  };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
    text: json['text'],
    isUser: json['isUser'],
    timestamp: json['timestamp'],
    language: json['language'] ?? 'es',
  );
}

class ChatResponse {
  final String type;
  final String reply;
  final String language;
  final List<dynamic> corrections;
  final List<dynamic> newVocabulary;
  final String topic;
  final bool ok;
  final String message;

  ChatResponse({
    required this.type,
    required this.reply,
    required this.language,
    required this.corrections,
    required this.newVocabulary,
    required this.topic,
    this.ok = true,
    this.message = '',
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) => ChatResponse(
    type: json['type'],
    reply: json['reply'] ?? '',
    language: json['language'] ?? 'es',
    corrections: json['corrections'] ?? [],
    newVocabulary: json['newVocabulary'] ?? [],
    topic: json['topic'] ?? '',
    ok: json['ok'] ?? true,
    message: json['message'] ?? '',
  );
}

class CommandResult {
  final bool ok;
  final String message;

  CommandResult({required this.ok, required this.message});

  factory CommandResult.fromJson(Map<String, dynamic> json) => CommandResult(
    ok: json['ok'] ?? false,
    message: json['message'] ?? '',
  );
}

class Device {
  final String name;
  final String ip;
  final String mac;
  final bool online;
  final List<int> openPorts;

  Device({
    required this.name,
    required this.ip,
    required this.mac,
    required this.online,
    required this.openPorts,
  });

  factory Device.fromJson(Map<String, dynamic> json) => Device(
    name: json['name'],
    ip: json['ip'],
    mac: json['mac'],
    online: json['online'] ?? false,
    openPorts: (json['openPorts'] as List<dynamic>?)?.map((e) => e as int).toList() ?? [],
  );
}

class StudyPlan {
  final int week;
  final String theme;
  final List<String> goals;
  final List<DailyActivity> daily;
  final List<String> vocab;
  final String milestone;

  StudyPlan({
    required this.week,
    required this.theme,
    required this.goals,
    required this.daily,
    required this.vocab,
    required this.milestone,
  });

  factory StudyPlan.fromJson(Map<String, dynamic> json) => StudyPlan(
    week: json['week'],
    theme: json['theme'] ?? '',
    goals: List<String>.from(json['goals'] ?? []),
    daily: (json['daily'] as List<dynamic>?)
        ?.map((d) => DailyActivity.fromJson(d))
        .toList() ?? [],
    vocab: List<String>.from(json['vocab'] ?? []),
    milestone: json['milestone'] ?? '',
  );
}

class DailyActivity {
  final String day;
  final String activity;
  final int minutes;

  DailyActivity({
    required this.day,
    required this.activity,
    required this.minutes,
  });

  factory DailyActivity.fromJson(Map<String, dynamic> json) => DailyActivity(
    day: json['day'] ?? '',
    activity: json['activity'] ?? '',
    minutes: json['minutes'] ?? 15,
  );
}

class StudyPlanSummary {
  final String level;
  final String generated;
  final List<StudyPlan> weeks;

  StudyPlanSummary({
    required this.level,
    required this.generated,
    required this.weeks,
  });

  factory StudyPlanSummary.fromJson(Map<String, dynamic> json) => StudyPlanSummary(
    level: json['level'] ?? '',
    generated: json['generated'] ?? '',
    weeks: (json['weeks'] as List<dynamic>?)
        ?.map((w) => StudyPlan.fromJson(w))
        .toList() ?? [],
  );
}
import 'vehicle.dart';
import 'dart:convert';

class ChatMessage {
  final String text;
  final bool isUser;
  final ChatReply? reply;
  const ChatMessage({required this.text, required this.isUser, this.reply});
}

class ChatRequest {
  final String message;
  final Vehicle? vehicle;
  final Map<String, dynamic>? context;
  final String? scopeType;
  final String? scopeId;
  final String? sessionId;
  final String? sessionToken;
  const ChatRequest({
    required this.message,
    this.vehicle,
    this.context,
    this.scopeType,
    this.scopeId,
    this.sessionId,
    this.sessionToken,
  });

  Map<String, dynamic> toJson() => {
    // The backend loads the current personal profile from the authenticated
    // account's active vehicle on every turn. Do not send cached profile data.
    // Existing FastAPI forbids unknown fields. Context is bounded, labelled
    // text in the existing message field, not a provider-specific parameter.
    'message': backendMessage,
    if (scopeType != null) 'scope_type': scopeType,
    if (scopeId != null) 'scope_id': scopeId,
    if (sessionId != null) 'session_id': sessionId,
    if (sessionToken != null) 'session_token': sessionToken,
    // History is loaded by the backend from this session. Sending old answers
    // can exceed the request's per-message limit after a long source excerpt.
  };

  String get backendMessage => context == null
      ? message
      : '${context!['kind']}: ${context!['title']}\nContext: ${jsonEncode(context!['details'])}\n\nQuestion: $message';
}

class ChatReply {
  final String text;
  final List<Map<String, dynamic>> videos;
  final List<Map<String, dynamic>> sources;
  final List<Map<String, dynamic>> attachments;
  final List<Map<String, dynamic>> manualLinks;
  final bool externalWarning;
  final bool manualRelevant;
  final String? route;
  final String? responseType;
  final String? sessionId;
  final String? sessionToken;
  const ChatReply(
    this.text, {
    this.videos = const [],
    this.sources = const [],
    this.attachments = const [],
    this.manualLinks = const [],
    this.externalWarning = false,
    this.manualRelevant = false,
    this.route,
    this.responseType,
    this.sessionId,
    this.sessionToken,
  });
  factory ChatReply.fromJson(Map<String, dynamic> json) {
    final reply = json['answer'];
    if (reply is! String || reply.trim().isEmpty) {
      throw const FormatException('Missing answer');
    }
    return ChatReply(
      reply,
      videos: (json['videos'] as List? ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      sources: (json['sources'] as List? ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      attachments: (json['attachments'] as List? ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      manualLinks: (json['manual_links'] as List? ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      externalWarning: json['external_warning'] == true,
      manualRelevant: json['manual_relevant'] == true,
      route: json['route'] as String?,
      responseType: json['response_type'] as String?,
      sessionId: json['session_id'] as String?,
      sessionToken: json['session_token'] as String?,
    );
  }
}

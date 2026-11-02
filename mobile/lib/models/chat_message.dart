import 'vehicle.dart';
import 'dart:convert';

class ChatMessage {
  final String text;
  final bool isUser;
  final ChatReply? reply;
  const ChatMessage({required this.text, required this.isUser, this.reply});
}

class ChatRequest {
  final String? requestId;
  final bool createSession;
  final String message;
  final Vehicle? vehicle;
  final Map<String, dynamic>? context;
  final String? scopeType;
  final String? scopeId;
  final String? sessionId;
  final String? sessionToken;
  final Map<String, dynamic>? activity;
  final String? assistance;
  const ChatRequest({
    this.requestId,
    this.createSession = false,
    required this.message,
    this.vehicle,
    this.context,
    this.scopeType,
    this.scopeId,
    this.sessionId,
    this.sessionToken,
    this.activity,
    this.assistance,
  });

  Map<String, dynamic> toJson() => {
    if (requestId != null) 'request_id': requestId,
    // The backend loads the current personal profile from the authenticated
    // account's active vehicle on every turn. Do not send cached profile data.
    // Existing FastAPI forbids unknown fields. Context is bounded, labelled
    // text in the existing message field, not a provider-specific parameter.
    'message': backendMessage,
    if (scopeType != null) 'scope_type': scopeType,
    if (scopeId != null) 'scope_id': scopeId,
    if (sessionId != null) 'session_id': sessionId,
    if (sessionToken != null) 'session_token': sessionToken,
    if (activity != null) 'activity': activity,
    if (assistance != null) 'assistance': assistance,
    // History is loaded by the backend from this session. Sending old answers
    // can exceed the request's per-message limit after a long source excerpt.
  };

  factory ChatRequest.restore(
    Map<String, dynamic> data,
    String token, {
    bool createSession = false,
  }) => ChatRequest(
    requestId: data['request_id'] as String,
    message: data['message'] as String,
    sessionId: data['session_id'] as String,
    sessionToken: token,
    createSession: createSession,
    activity: data['activity'] == null
        ? null
        : Map<String, dynamic>.from(data['activity'] as Map),
    assistance: data['assistance'] as String?,
  );

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
  final List<Map<String, dynamic>> recommendedGuides;
  final bool externalWarning;
  final bool manualRelevant;
  final String? route;
  final String? responseType;
  final String? sessionId;
  final String? sessionToken;
  final String? messageId;
  final bool suggestServicePlan;
  final String? activityNotice;
  const ChatReply(
    this.text, {
    this.videos = const [],
    this.sources = const [],
    this.attachments = const [],
    this.manualLinks = const [],
    this.recommendedGuides = const [],
    this.externalWarning = false,
    this.manualRelevant = false,
    this.route,
    this.responseType,
    this.sessionId,
    this.sessionToken,
    this.messageId,
    this.suggestServicePlan = false,
    this.activityNotice,
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
      recommendedGuides: (json['recommended_guides'] as List? ?? [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      externalWarning: json['external_warning'] == true,
      manualRelevant: json['manual_relevant'] == true,
      route: json['route'] as String?,
      responseType: json['response_type'] as String?,
      sessionId: json['session_id'] as String?,
      sessionToken: json['session_token'] as String?,
      messageId: json['message_id'] as String?,
      suggestServicePlan: json['suggested_activity'] == 'service_plan',
      activityNotice: json['activity_notice'] as String?,
    );
  }
}

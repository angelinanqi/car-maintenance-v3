import '../models/chat_message.dart';
import '../models/mechanic_preparation.dart';
import 'api_client.dart';
import 'account_repository.dart';

abstract class ChatRepository {
  Future<ChatReply> send(ChatRequest request);
}

class FastApiChatRepository implements ChatRepository {
  final ApiClient api;
  final AccountRepository? account;
  // One local generation call; allow cold model startup on modest hardware.
  final Duration timeout;
  FastApiChatRepository(
    this.api, {
    this.account,
    this.timeout = const Duration(minutes: 4),
  });

  Future<MechanicPreparation> prepareQuestions({
    required String question,
    String? vehicleId,
    String? sessionId,
    String? sessionToken,
    String? planId,
  }) async {
    _checkAccount();
    final data = await api.post(
      '/chat/mechanic-questions',
      {
        'question': question,
        'vehicle_id': vehicleId,
        if (sessionId != null) 'session_id': sessionId,
        if (sessionToken != null) 'session_token': sessionToken,
        if (planId != null) 'plan_id': planId,
      },
      token: account?.token,
      requestTimeout: const Duration(seconds: 55),
    );
    try {
      return MechanicPreparation.fromJson(data);
    } on FormatException {
      throw const ApiException(
        'The question list could not be read. Please retry.',
      );
    } on TypeError {
      throw const ApiException(
        'The question list could not be read. Please retry.',
      );
    }
  }

  @override
  Future<ChatReply> send(ChatRequest request) async {
    _checkAccount();
    try {
      if (request.createSession) {
        await api.put('/chat/sessions/${request.sessionId}', {
          'session_token': request.sessionToken,
        }, token: account?.token);
      }
      final reply = ChatReply.fromJson(
        await api.post(
          '/chat',
          request.toJson(),
          requestTimeout: timeout,
          token: account?.token,
        ),
      );
      if (reply.sessionId == null ||
          reply.sessionId!.isEmpty ||
          reply.sessionToken == null ||
          reply.sessionToken!.isEmpty) {
        throw const FormatException('Missing chat session capability');
      }
      if ([
        'generation_error',
        'retrieval_error',
      ].contains(reply.responseType)) {
        throw const ApiException(
          'The AI service could not complete this question. Retry shortly.',
          statusCode: 503,
        );
      }
      return reply;
    } on FormatException {
      throw const ApiException(
        'Chat response does not match the agreed contract.',
      );
    } on TypeError {
      throw const ApiException(
        'Chat response does not match the agreed contract.',
      );
    }
  }

  void _checkAccount() {
    if (account != null && account!.userId == null) {
      throw const ApiException(
        'Sign in and verify your account to continue.',
        statusCode: 401,
      );
    }
  }
}

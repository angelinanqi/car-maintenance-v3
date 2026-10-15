import '../models/chat_message.dart';
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
  @override
  Future<ChatReply> send(ChatRequest request) async {
    try {
      final reply = ChatReply.fromJson(
        await api.post(
          '/chat',
          request.toJson(historyLimit: api.historyLimit),
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
      return reply;
    } on FormatException {
      throw const ApiException(
        'Chat response does not match the agreed contract.',
      );
    }
  }
}

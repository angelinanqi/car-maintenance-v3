// Debug metadata only. This module never receives account IDs or credentials.
import 'dart:async';
import 'dart:math';
import 'package:http/http.dart' as http;

class LiveLogging {
  static bool enabled = false;
  static void Function(String) output = print;
  static bool _authenticated = false;
  static String? _session;
  static final _segments =
      ('api backend v1 auth token logout signup recover verify user health docs config accounts me admin documents guides categories emergency playbooks contacts dashboard knowledge vehicles manufacturers models catalogue maintenance-items maintenance-intervals schedules schedule-drafts maintenance-assistance mobile tasks records incidents plans service-plans preview bookmarks notes saved-items chat sessions resume activity sources image original pages media upload process extraction review publish unpublish coverage tags removal-impact archive restore delete-impact deactivate index indexing youtube channels videos sync status questions runs tests document-test-summaries chat-starters companion-settings companion progress recap recaps nearby workshops mechanic-questions configuration scopes profiles schedule-draft assets internal handoffs pending index-ready index-failed confirm-corrections corrections content')
          .split(' ')
          .toSet();

  static String? newId() {
    try {
      final random = Random.secure();
      final bytes = List<int>.generate(16, (_) => random.nextInt(256));
      bytes[6] = (bytes[6] & 15) | 64;
      bytes[8] = (bytes[8] & 63) | 128;
      final s = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      return '${s.substring(0, 8)}-${s.substring(8, 12)}-${s.substring(12, 16)}-${s.substring(16, 20)}-${s.substring(20)}';
    } catch (_) {
      return null;
    }
  }

  static void sessionChanged(bool authenticated, {bool newLogin = false}) {
    if (!enabled) return;
    if (_session == null || authenticated != _authenticated || newLogin) {
      _authenticated = authenticated;
      final value = newId()?.replaceAll('-', '').substring(0, 16);
      _session = value == null
          ? null
          : '${authenticated ? 'auth' : 'guest'}-$value';
    }
  }

  static String? get session {
    if (_session == null) sessionChanged(_authenticated);
    return _session;
  }

  static String safePath(String value) {
    try {
      final path = Uri.parse(value).path
          .split('/')
          .map((s) => s.isEmpty || _segments.contains(s) ? s : ':id')
          .join('/');
      return path.isEmpty ? '/' : path.substring(0, min(path.length, 240));
    } catch (_) {
      return '/unknown';
    }
  }

  static String? safeId(String? value) =>
      value != null && RegExp(r'^[a-fA-F0-9-]{32,36}$').hasMatch(value)
      ? value
      : null;

  static String failure(Object error) => error is TimeoutException
      ? 'TIMEOUT'
      : error is http.ClientException
      ? 'NETWORK'
      : error is FormatException
      ? 'INVALID_RESPONSE'
      : 'UNEXPECTED';
}

class HttpTrace {
  final String method, path, destination;
  final String? session = LiveLogging.session;
  final String? id = LiveLogging.newId();
  final Stopwatch _timer = Stopwatch()..start();
  int? status;
  String? responseId, error;
  bool _finished = false;
  HttpTrace(String path, String method, {this.destination = 'API'})
    : path = LiveLogging.safePath(path),
      method = method.toUpperCase();

  void finish() {
    if (_finished) return;
    _finished = true;
    if (!LiveLogging.enabled) return;
    try {
      final timestamp = DateTime.now().toUtc().toIso8601String();
      final success = status != null && status! < 400;
      final requestId = LiveLogging.safeId(responseId) ?? id;
      LiveLogging.output(
        '[$timestamp] [MOBILE] [HTTP] $method $path ${status ?? '—'} | '
        '${_timer.elapsedMilliseconds}ms | ${success ? 'SUCCESS' : 'ERROR'} | via=$destination'
        '${session == null ? '' : ' | session=$session'}'
        '${requestId == null ? '' : ' | id=$requestId'}'
        '${error == null ? '' : ' | app=ERROR | error=$error'}',
      );
    } catch (_) {
      /* Debug output must not affect a request. */
    }
  }
}

// Supabase traffic bypasses FastAPI. Observe its existing transport without
// adding application headers or consuming/changing the response stream.
class LoggedHttpClient extends http.BaseClient {
  final http.Client inner;
  final String destination;
  LoggedHttpClient({http.Client? inner, this.destination = 'SUPABASE'})
    : inner = inner ?? http.Client();
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final trace = HttpTrace(
      request.url.toString(),
      request.method,
      destination: destination,
    );
    try {
      final response = await inner.send(request);
      trace.status = response.statusCode;
      trace.responseId = response.headers['x-request-id'];
      return response;
    } catch (error) {
      trace.error = LiveLogging.failure(error);
      rethrow;
    } finally {
      trace.finish();
    }
  }

  @override
  void close() => inner.close();
}

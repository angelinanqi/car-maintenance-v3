import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final int? retryAfter;
  final String? requestId;
  const ApiException(
    this.message, {
    this.statusCode,
    this.retryAfter,
    this.requestId,
  });
  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  final http.Client client;
  final Duration timeout;
  int maxMessageLength = 4000;
  int pageSize = 100;
  int imageMaxBytes = 10485760;

  ApiClient({
    this.baseUrl = const String.fromEnvironment('API_BASE_URL'),
    http.Client? client,
    this.timeout = const Duration(seconds: 30),
  }) : client = client ?? http.Client();

  Uri endpoint(String path, {Map<String, String>? query}) {
    if (baseUrl.isEmpty) {
      throw const ApiException(
        'No backend URL configured. '
        'Build with --dart-define=API_BASE_URL=https://your-api-host.',
      );
    }
    final base = Uri.parse(baseUrl.endsWith('/') ? baseUrl : '$baseUrl/');
    if (!['http', 'https'].contains(base.scheme) || base.host.isEmpty) {
      throw const ApiException('The backend URL is invalid.');
    }
    final uri = base.resolve(path.replaceFirst(RegExp(r'^/'), ''));
    return query == null ? uri : uri.replace(queryParameters: query);
  }

  Future<http.Response> _request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? query,
    String? token,
    int maxBytes = 52428800,
    Uri? remote,
    Duration? requestTimeout,
  }) async {
    final logPath = remote == null ? path.split('?').first : 'external image';
    try {
      final request = http.Request(
        method,
        remote ?? endpoint(path, query: query),
      );
      if (body != null) {
        request.headers['Content-Type'] = 'application/json';
        request.body = jsonEncode(body);
      }
      if (token != null) request.headers['Authorization'] = 'Bearer $token';
      final response = await (() async {
        final streamed = await client.send(request);
        final bytes = BytesBuilder(copy: false);
        await for (final chunk in streamed.stream) {
          if (bytes.length + chunk.length > maxBytes) {
            throw const ApiException('The download exceeds the allowed size.');
          }
          bytes.add(chunk);
        }
        return http.Response.bytes(
          bytes.takeBytes(),
          streamed.statusCode,
          headers: streamed.headers,
        );
      })().timeout(requestTimeout ?? timeout);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        String? detail;
        try {
          final decoded = jsonDecode(response.body);
          final value = decoded is Map ? decoded['detail'] : null;
          if (value is String) detail = value;
          if (value is List) {
            detail = value
                .map(
                  (item) => item is Map && item['msg'] is String
                      ? item['msg'] as String
                      : 'Invalid input',
                )
                .join('; ');
          }
        } on FormatException {
          // Preserve the HTTP status for non-JSON failures.
        }
        throw ApiException(
          detail ?? 'Request failed (${response.statusCode}). Please retry.',
          statusCode: response.statusCode,
          retryAfter: int.tryParse(response.headers['retry-after'] ?? ''),
          requestId: response.headers['x-request-id'],
        );
      }
      return response;
    } on ApiException catch (error) {
      debugPrint(
        'ERROR [mobile-api] $method $logPath failed'
        '${error.statusCode == null ? '' : ' (HTTP ${error.statusCode})'}.',
      );
      rethrow;
    } on TimeoutException {
      debugPrint('ERROR [mobile-api] $method $logPath timed out.');
      throw const ApiException('The request timed out. Please retry.');
    } on http.ClientException {
      debugPrint('ERROR [mobile-api] $method $logPath could not connect.');
      throw const ApiException(
        'Could not reach the backend. Check your connection.',
      );
    } on FormatException {
      debugPrint(
        'ERROR [mobile-api] $method $logPath returned an invalid response.',
      );
      throw const ApiException('The backend returned an unexpected response.');
    }
  }

  Map<String, dynamic> _object(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      return decoded;
    } on FormatException {
      throw const ApiException('The backend returned an unexpected response.');
    }
  }

  Future<Map<String, dynamic>> post(
    String path,
    Map<String, dynamic> body, {
    String? token,
    Duration? requestTimeout,
  }) async => _object(
    await _request(
      path,
      method: 'POST',
      body: body,
      token: token,
      requestTimeout: requestTimeout,
    ),
  );

  Future<Map<String, dynamic>> get(String path, {String? token}) async =>
      _object(await _request(path, token: token));

  Future<Map<String, dynamic>> put(
    String path,
    Map<String, dynamic> body, {
    String? token,
  }) async =>
      _object(await _request(path, method: 'PUT', body: body, token: token));

  Future<void> delete(String path, {String? token}) async {
    await _request(path, method: 'DELETE', token: token);
  }

  Future<Map<String, dynamic>> patch(
    String path,
    Map<String, dynamic> body, {
    String? token,
  }) async =>
      _object(await _request(path, method: 'PATCH', body: body, token: token));

  Future<void> postEmpty(String path, {String? token}) async {
    await _request(path, method: 'POST', token: token);
  }

  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
    String? token,
  }) async {
    final response = await _request(path, query: query, token: token);
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! List ||
          decoded.any((item) => item is! Map<String, dynamic>)) {
        throw const FormatException();
      }
      return decoded.cast<Map<String, dynamic>>();
    } on FormatException {
      throw const ApiException(
        'The backend returned an unexpected list response.',
      );
    }
  }

  Future<List<Map<String, dynamic>>> listAll(
    String path, {
    Map<String, String> query = const {},
    String? token,
    Duration? totalTimeout,
  }) async {
    final rows = <Map<String, dynamic>>[];
    final timer = Stopwatch()..start();
    final identities = <String>{};
    if (pageSize < 1 || pageSize > 1000)
      throw const ApiException('Invalid pagination configuration.');
    while (true) {
      final remaining = totalTimeout == null
          ? null
          : totalTimeout - timer.elapsed;
      if (remaining != null && remaining <= Duration.zero) {
        throw const ApiException(
          'Loading the catalogue timed out. Please retry.',
        );
      }
      final operation = getList(
        path,
        query: {...query, 'offset': '${rows.length}', 'limit': '$pageSize'},
        token: token,
      );
      List<Map<String, dynamic>> page;
      try {
        page = remaining == null
            ? await operation
            : await operation.timeout(remaining);
      } on TimeoutException {
        throw const ApiException(
          'Loading the catalogue timed out. Please retry.',
        );
      }
      if (totalTimeout != null) {
        for (final row in page) {
          final id = row['id'];
          if (id is! String || id.isEmpty || !identities.add(id)) {
            throw const ApiException(
              'The catalogue returned invalid or repeating records. Please refresh.',
            );
          }
        }
      }
      rows.addAll(page);
      if (page.length < pageSize) return rows;
    }
  }

  Future<Uint8List> getBytes(String path) async =>
      (await _request(path)).bodyBytes;

  Future<Uint8List> chatImageBytes(String path, String? token) async {
    if (!path.startsWith('/chat/sessions/') ||
        !path.endsWith('/image') ||
        path.contains('..') ||
        path.contains('://') ||
        path.contains('\\')) {
      throw const ApiException('Invalid chat image reference.');
    }
    return (await _request(
      path,
      token: token,
      maxBytes: imageMaxBytes,
    )).bodyBytes;
  }

  Future<Uint8List> imageBytes(String url) async {
    final uri = Uri.parse(url);
    if (!['http', 'https'].contains(uri.scheme) || uri.host.isEmpty) {
      throw const ApiException('Invalid image URL.');
    }
    return (await _request('', remote: uri, maxBytes: imageMaxBytes)).bodyBytes;
  }

  Future<void> loadConfiguration() async {
    final data = await get('/config');
    final scopes = data['vehicle_scopes'];
    final knowledge = data['knowledge_scopes'] ?? [];
    if (scopes is! List ||
        scopes.any(
          (item) =>
              item is! Map ||
              item['value'] is! String ||
              item['label'] is! String,
        ) ||
        knowledge is! List ||
        knowledge.any((item) => item is! Map)) {
      throw const ApiException('Invalid backend configuration.');
    }
    final limits = [
      'chat_max_message_length',
      'chat_history_limit',
      'api_page_size',
      'image_max_bytes',
    ];
    if (limits.any((key) => data[key] is! int || data[key] <= 0) ||
        data['api_page_size'] > 1000) {
      throw const ApiException('Invalid backend configuration.');
    }
    maxMessageLength = data['chat_max_message_length'] as int;
    pageSize = data['api_page_size'] as int;
    imageMaxBytes = data['image_max_bytes'] as int;
  }

  void close() => client.close();
}

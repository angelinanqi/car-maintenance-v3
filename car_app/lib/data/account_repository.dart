import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api_client.dart';

class AccountSession {
  final String id, name, email;
  final DateTime expiresAt;
  const AccountSession(this.id, this.name, this.email, this.expiresAt);

  factory AccountSession.fromJson(Map<String, dynamic> data) {
    final user = data['user'] as Map<String, dynamic>;
    return AccountSession(
      user['id'] as String,
      user['display_name'] as String,
      user['email'] as String,
      DateTime.parse(data['expires_at'] as String),
    );
  }
}

class AccountRepository {
  static const storageKey = 'car_account_session';
  static const incidentOwnerKey = 'car_incident_owner';
  final ApiClient api;
  final FlutterSecureStorage storage;
  String? _token;
  DateTime? _expiresAt;
  String? _userId;
  String? incidentOwnerId;
  bool offlineSession = false;
  bool get hasSession => _token != null;
  String? get token => _token;
  String? get userId => _userId;

  AccountRepository(this.api, {FlutterSecureStorage? storage})
    : storage = storage ?? const FlutterSecureStorage();

  void _checkTransport() {
    if (kReleaseMode && api.endpoint('/accounts').scheme != 'https') {
      throw const ApiException('Account access requires an HTTPS backend.');
    }
  }

  Future<void> register(String name, String email, String password) async {
    _checkTransport();
    await api.post('/accounts/register', {
      'display_name': name.trim(),
      'email': email.trim(),
      'password': password,
    });
  }

  Future<AccountSession> login(String email, String password) async {
    _checkTransport();
    final data = await api.post('/accounts/login', {
      'email': email.trim(),
      'password': password,
      'session_transport': 'bearer',
    });
    final session = AccountSession.fromJson(data);
    final token = data['access_token'] as String;
    try {
      await storage.write(
        key: storageKey,
        value: jsonEncode({
          'token': token,
          'expires_at': session.expiresAt.toIso8601String(),
          'user': data['user'],
        }),
      );
      await storage.write(key: incidentOwnerKey, value: session.id);
    } catch (_) {
      try {
        await api.postEmpty('/accounts/logout', token: token);
      } catch (_) {
        /* Best effort if storage is unavailable. */
      }
      throw const ApiException(
        'Could not securely save the session. Please retry.',
      );
    }
    _token = token;
    _userId = session.id;
    incidentOwnerId = session.id;
    offlineSession = false;
    _expiresAt = session.expiresAt;
    return session;
  }

  Future<void> forget({bool clearIncidentOwner = true}) async {
    await storage.delete(key: storageKey);
    _token = null;
    _userId = null;
    _expiresAt = null;
    offlineSession = false;
    if (clearIncidentOwner) {
      await storage.delete(key: incidentOwnerKey);
      incidentOwnerId = null;
    }
  }

  Future<AccountSession?> restore() async {
    incidentOwnerId = await storage.read(key: incidentOwnerKey);
    offlineSession = false;
    final saved = await storage.read(key: storageKey);
    if (saved == null) {
      _token = null;
      _userId = null;
      _expiresAt = null;
      return null;
    }
    Map<String, dynamic>? cachedUser;
    try {
      final data = jsonDecode(saved) as Map<String, dynamic>;
      _token = data['token'] as String;
      _expiresAt = DateTime.parse(data['expires_at'] as String);
      cachedUser = data['user'] as Map<String, dynamic>?;
    } catch (_) {
      await forget();
      throw const ApiException(
        'The saved session is invalid. Please sign in again.',
        statusCode: 401,
      );
    }
    if (!_expiresAt!.isAfter(DateTime.now())) {
      await forget(clearIncidentOwner: false);
      throw const ApiException(
        'Your session expired. Please sign in again.',
        statusCode: 401,
      );
    }
    _checkTransport();
    try {
      final session = AccountSession.fromJson(
        await api.get('/accounts/me', token: _token),
      );
      _userId = session.id;
      return session;
    } on ApiException catch (error) {
      if (error.statusCode == 401) await forget();
      if (error.statusCode == null && cachedUser != null) {
        final session = AccountSession.fromJson({
          'user': cachedUser,
          'expires_at': _expiresAt!.toIso8601String(),
        });
        _userId = session.id;
        offlineSession = true;
        return session;
      }
      rethrow;
    }
  }

  Future<void> logout() async {
    final token = _token;
    await forget();
    if (token == null) return;
    try {
      _checkTransport();
      await api.postEmpty('/accounts/logout', token: token);
    } on ApiException catch (error) {
      if (error.statusCode != 401) {
        throw const ApiException(
          'Signed out on this device. Server revocation could not be confirmed; the session will expire automatically.',
        );
      }
    }
  }
}

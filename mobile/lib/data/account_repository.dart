import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'api_client.dart';
import 'supabase_auth_client.dart';

class AccountSession {
  final String id, name, email;
  final DateTime expiresAt;
  final bool accessAllowed, mfaRequired;
  final List<String> factorIds;
  const AccountSession(
    this.id,
    this.name,
    this.email,
    this.expiresAt, {
    this.accessAllowed = true,
    this.mfaRequired = false,
    this.factorIds = const [],
  });
  factory AccountSession.fromJson(Map<String, dynamic> data) {
    final user = data['user'] as Map<String, dynamic>;
    return AccountSession(
      user['id'] as String,
      user['display_name'] as String,
      user['email'] as String,
      DateTime.parse(data['expires_at'] as String),
      accessAllowed: data['access_allowed'] == true,
      mfaRequired: data['mfa_required'] == true,
      factorIds: (data['factor_ids'] as List? ?? []).cast<String>(),
    );
  }
}

class AccountRepository {
  static const storageKey = 'car_account_session';
  static const incidentOwnerKey = 'car_incident_owner';
  final ApiClient api;
  final FlutterSecureStorage storage;
  final SupabaseClient? client;
  String? _userId;
  String? _authUserId;
  String? incidentOwnerId;
  bool get hasSession => client?.auth.currentSession != null;
  String? get token => client?.auth.currentSession?.accessToken;
  String? get userId =>
      _authUserId != null && client?.auth.currentSession?.user.id == _authUserId
      ? _userId
      : null;
  AccountRepository(this.api, {FlutterSecureStorage? storage, this.client})
    : storage = storage ?? const FlutterSecureStorage();

  GoTrueClient get auth {
    if (client == null) {
      throw const ApiException(
        'Account access is not configured or could not start. Check the Supabase build settings and secure device storage, then restart. Emergency help is still available.',
      );
    }
    return client!.auth;
  }

  static String? validatePassword(String password) {
    final length = password.runes.length;
    return length < 8 || length > 20 ? 'Use 8 to 20 characters.' : null;
  }

  void _checkTransport() {
    if (kReleaseMode && api.endpoint('/accounts').scheme != 'https') {
      throw const ApiException('Account access requires an HTTPS backend.');
    }
  }

  Future<void> register(String name, String email, String password) async {
    _checkTransport();
    final error = validatePassword(password);
    if (error != null) throw ApiException(error);
    await auth.signUp(
      email: email.trim(),
      password: password,
      data: {'display_name': name.trim()},
      emailRedirectTo: authRedirectUrl,
    );
  }

  Future<AccountSession> login(String email, String password) async {
    _checkTransport();
    await auth.signInWithPassword(email: email.trim(), password: password);
    final session = await restore();
    if (session == null) {
      throw const ApiException('Sign-in ended. Please sign in again.');
    }
    return session;
  }

  Future<AccountSession?> restore() async {
    incidentOwnerId = await storage.read(key: incidentOwnerKey);
    await storage.delete(key: storageKey);
    if (!hasSession) {
      _userId = null;
      _authUserId = null;
      return null;
    }
    // Supabase auth.users.id and the backend app_users.id are distinct IDs.
    // Bind the verified app profile to the provider identity used for this call.
    final authUserId = auth.currentSession!.user.id;
    try {
      _checkTransport();
      if (auth.currentSession!.isExpired) await auth.refreshSession();
      if (auth.currentSession?.user.id != authUserId) {
        throw const ApiException('Your account changed. Sign in again.');
      }
      final session = AccountSession.fromJson(
        await api.get('/accounts/me', token: token),
      );
      if (auth.currentSession?.user.id != authUserId) {
        throw const ApiException('Your account changed. Sign in again.');
      }
      if (session.accessAllowed) {
        await storage.write(key: incidentOwnerKey, value: session.id);
        if (auth.currentSession?.user.id != authUserId) {
          throw const ApiException('Your account changed. Sign in again.');
        }
        incidentOwnerId = session.id;
        _userId = session.id;
        _authUserId = authUserId;
      } else {
        _userId = null;
        _authUserId = null;
      }
      return session;
    } catch (_) {
      _userId = null;
      _authUserId = null;
      rethrow;
    }
  }

  Future<void> requestRecovery(String email) =>
      auth.resetPasswordForEmail(email.trim(), redirectTo: authRedirectUrl);
  Future<void> resendConfirmation(String email) async {
    await auth.resend(
      type: OtpType.signup,
      email: email.trim(),
      emailRedirectTo: authRedirectUrl,
    );
  }

  Future<void> resetPassword(String password) async {
    final error = validatePassword(password);
    if (error != null) throw ApiException(error);
    await auth.updateUser(UserAttributes(password: password));
  }

  Future<void> logout() async {
    await auth.signOut(scope: SignOutScope.local);
    _userId = null;
    _authUserId = null;
    await storage.delete(key: incidentOwnerKey);
    incidentOwnerId = null;
  }
}

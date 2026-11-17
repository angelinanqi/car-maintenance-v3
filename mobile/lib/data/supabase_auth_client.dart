import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'live_logging.dart';

const authRedirectUrl = 'myroadie://auth/callback';

class SecureAuthStorage extends LocalStorage {
  final FlutterSecureStorage storage;
  final String key;
  SecureAuthStorage({
    FlutterSecureStorage? storage,
    this.key = 'supabase_session',
  }) : storage = storage ?? const FlutterSecureStorage();
  @override
  Future<void> initialize() async {}
  @override
  Future<String?> accessToken() => storage.read(key: key);
  @override
  Future<bool> hasAccessToken() async => await accessToken() != null;
  @override
  Future<void> persistSession(String persistSessionString) =>
      storage.write(key: key, value: persistSessionString);
  @override
  Future<void> removePersistedSession() => storage.delete(key: key);
}

class SecurePkceStorage extends GotrueAsyncStorage {
  final storage = const FlutterSecureStorage();
  final String prefix;
  SecurePkceStorage({this.prefix = 'auth_'});
  @override
  Future<String?> getItem({required String key}) =>
      storage.read(key: '$prefix$key');
  @override
  Future<void> setItem({required String key, required String value}) =>
      storage.write(key: '$prefix$key', value: value);
  @override
  Future<void> removeItem({required String key}) =>
      storage.delete(key: '$prefix$key');
}

Future<SupabaseClient?> initializeMobileAuth() async {
  LiveLogging.enabled =
      kDebugMode &&
      const bool.fromEnvironment('DEV_LOGGING', defaultValue: true);
  LiveLogging.output = (line) => debugPrint(line);
  const url = String.fromEnvironment('SUPABASE_URL');
  const key = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');
  if (url.isEmpty || key.isEmpty) return null;
  if (kReleaseMode && Uri.tryParse(url)?.scheme != 'https') return null;
  try {
    await Supabase.initialize(
      url: url,
      publishableKey: key,
      debug: false,
      httpClient: kDebugMode ? LoggedHttpClient() : null,
      authOptions: FlutterAuthClientOptions(
        authFlowType: AuthFlowType.pkce,
        localStorage: SecureAuthStorage(),
        pkceAsyncStorage: SecurePkceStorage(),
      ),
    );
    final client = Supabase.instance.client;
    try {
      LiveLogging.sessionChanged(client.auth.currentSession != null);
      client.auth.onAuthStateChange.listen(
        (event) {
          if (event.event == AuthChangeEvent.signedIn ||
              event.event == AuthChangeEvent.passwordRecovery) {
            LiveLogging.sessionChanged(true, newLogin: true);
          } else if (event.event == AuthChangeEvent.signedOut) {
            LiveLogging.sessionChanged(false, newLogin: true);
          } else if (event.event == AuthChangeEvent.initialSession) {
            LiveLogging.sessionChanged(event.session != null);
          }
        },
        onError: (Object _) {
          /* AccountState handles provider errors. */
        },
      );
    } catch (_) {
      /* Debug session labels never affect authentication. */
    }
    return client;
  } catch (_) {
    // Public emergency access remains available if account startup fails.
    return null;
  }
}

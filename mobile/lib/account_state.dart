import 'dart:async';
import 'package:flutter/material.dart';
import 'data/account_repository.dart';
import 'data/api_client.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AccountState extends ChangeNotifier {
  final AccountRepository repository;
  AccountSession? user;
  AccountSession? pendingSession;
  bool recoveringPassword = false;
  bool get recoveryNeedsMfa =>
      recoveringPassword &&
      recoveryFactorIds.isNotEmpty &&
      repository.auth.mfa.getAuthenticatorAssuranceLevel().currentLevel !=
          AuthenticatorAssuranceLevels.aal2;
  List<String> get recoveryFactorIds =>
      repository.auth.currentUser?.factors
          ?.where(
            (f) =>
                f.factorType == FactorType.totp &&
                f.status == FactorStatus.verified,
          )
          .map((f) => f.id)
          .toList() ??
      [];
  String? message;
  StreamSubscription<AuthState>? _authSubscription;
  bool _restorePending = false;
  bool busy = false;
  bool rateLimited = false;
  DateTime? emailRetryAt;
  int get emailRetrySeconds {
    final remaining = emailRetryAt?.difference(DateTime.now()).inSeconds ?? -1;
    return remaining < 0 ? 0 : remaining + 1;
  }

  String? error;
  Timer? _expiry;
  bool _disposed = false;
  bool get hasSavedSession => repository.hasSession;
  AccountState(this.repository) {
    final auth = repository.client?.auth;
    if (auth?.currentSession != null) {
      recoveringPassword = auth!.mfa
          .getAuthenticatorAssuranceLevel()
          .currentAuthenticationMethods
          .any((entry) => entry.method == AMRMethod.recovery);
    }
    _authSubscription = repository.client?.auth.onAuthStateChange.listen(
      (event) {
        if (event.event == AuthChangeEvent.passwordRecovery) {
          recoveringPassword = true;
          pendingSession = null;
          _accept(null);
          _notify();
        } else if (event.event == AuthChangeEvent.signedOut) {
          recoveringPassword = false;
          pendingSession = null;
          _accept(null);
          _notify();
        } else if (!recoveringPassword) {
          if (busy) {
            _restorePending = true;
          } else {
            restore();
          }
        }
      },
      onError: (Object _) {
        error =
            'The account link or session could not be verified. Reopen the latest email link or sign in again.';
        _accept(null);
        _notify();
      },
    );
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _accept(AccountSession? session) {
    _expiry?.cancel();
    user = session;
    if (session != null && !_disposed) {
      final remaining = session.expiresAt.difference(DateTime.now());
      _expiry = Timer(
        remaining.isNegative ? Duration.zero : remaining,
        restore,
      );
    }
  }

  Future<bool> _run(Future<void> Function() operation) async {
    if (busy || _disposed) return false;
    busy = true;
    rateLimited = false;
    error = null;
    _notify();
    try {
      await operation();
      return true;
    } on ApiException catch (failure) {
      error = failure.message;
      return false;
    } on AuthException catch (failure) {
      rateLimited =
          failure.statusCode == '429' ||
          [
            'over_email_send_rate_limit',
            'over_request_rate_limit',
          ].contains(failure.code);
      error = _authMessage(failure);
      return false;
    } catch (_) {
      error =
          'Account access failed. Check your connection and secure device storage, then retry.';
      return false;
    } finally {
      busy = false;
      _notify();
      if (_restorePending && !recoveringPassword) {
        _restorePending = false;
        scheduleMicrotask(restore);
      }
    }
  }

  Future<bool> restore() => _run(() async {
    if (recoveringPassword) return;
    try {
      _apply(await repository.restore());
    } catch (_) {
      pendingSession = null;
      _accept(null);
      rethrow;
    }
  });

  Future<bool> login(String email, String password) => _run(() async {
    pendingSession = null;
    _accept(null);
    _notify();
    _apply(await repository.login(email, password));
  });

  Future<bool> register(
    String name,
    String email,
    String password,
  ) => _run(() async {
    await repository.register(name, email, password);
    message =
        'If registration can proceed, check your email to confirm your account, then sign in.';
    if (repository.hasSession) _apply(await repository.restore());
  });

  Future<bool> logout() => _run(() async {
    try {
      await repository.logout();
    } finally {
      if (!repository.hasSession) {
        pendingSession = null;
        recoveringPassword = false;
        _accept(null);
      }
    }
  });

  void _apply(AccountSession? session) {
    if (recoveringPassword) return;
    if (session != null && !repository.hasSession) {
      throw const ApiException(
        'Your session ended. Sign in again to continue.',
      );
    }
    pendingSession = session?.accessAllowed == false ? session : null;
    _accept(session?.accessAllowed == true ? session : null);
  }

  Future<bool> recoveryEmail(String email) => _run(() async {
    if (emailRetrySeconds > 0)
      throw const ApiException('Wait before requesting another email.');
    await repository.requestRecovery(email);
    emailRetryAt = DateTime.now().add(const Duration(seconds: 60));
    message =
        'If this email can receive a recovery link, check its inbox. Open the latest link on this device.';
  });

  Future<bool> resend(String email) => _run(() async {
    if (emailRetrySeconds > 0)
      throw const ApiException('Wait before requesting another email.');
    await repository.resendConfirmation(email);
    emailRetryAt = DateTime.now().add(const Duration(seconds: 60));
    message =
        'If confirmation is needed, a new email will be sent. Open the latest link on this device.';
  });

  Future<bool> resetPassword(String password) => _run(() async {
    if (!recoveringPassword || !repository.hasSession) {
      throw const ApiException(
        'Open a valid password recovery email on this device first.',
      );
    }
    if (recoveryNeedsMfa) {
      throw const ApiException(
        'Verify your authenticator before changing your password.',
      );
    }
    await repository.resetPassword(password);
    message = 'Password updated. Finishing sign-out on this device.';
    try {
      await repository.logout();
    } catch (_) {
      throw const ApiException(
        'Your password was updated, but sign-out could not be confirmed. Retry signing out before continuing.',
      );
    }
    recoveringPassword = false;
    pendingSession = null;
    _accept(null);
    message = 'Password updated. Sign in with your new password.';
  });

  Future<bool> verifyFactor(String factorId, String code) => _run(() async {
    await repository.auth.mfa.challengeAndVerify(
      factorId: factorId,
      code: code,
    );
    _apply(await repository.restore());
  });

  String _authMessage(AuthException failure) {
    switch (failure.code) {
      case 'invalid_credentials':
        return 'The email or password is incorrect.';
      case 'email_not_confirmed':
        return 'Confirm your email before signing in. You can request a new confirmation email.';
      case 'weak_password':
        return 'Choose a stronger password with 8 to 20 characters. Follow the password requirements for this project.';
      case 'over_email_send_rate_limit':
      case 'over_request_rate_limit':
        return 'Too many attempts. Wait a minute before retrying.';
      case 'mfa_verification_failed':
        return 'The authenticator code is invalid or expired. Try the current code.';
      case 'otp_expired':
        return 'This email link has expired or was already used. Request a new link.';
      default:
        return 'Account access could not be completed. Check your connection and retry, or request a new email link.';
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _expiry?.cancel();
    _authSubscription?.cancel();
    super.dispose();
  }
}

class AccountScope extends InheritedNotifier<AccountState> {
  const AccountScope({
    super.key,
    required AccountState state,
    required super.child,
  }) : super(notifier: state);
  static AccountState? of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AccountScope>()?.notifier;
}

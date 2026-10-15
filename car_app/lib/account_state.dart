import 'dart:async';
import 'package:flutter/material.dart';
import 'data/account_repository.dart';
import 'data/api_client.dart';

class AccountState extends ChangeNotifier {
  final AccountRepository repository;
  AccountSession? user;
  bool busy = false;
  String? error;
  Timer? _expiry;
  bool _disposed = false;
  bool get hasSavedSession => repository.hasSession;
  AccountState(this.repository);

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
    if (busy) return false;
    busy = true;
    error = null;
    _notify();
    try {
      await operation();
      return true;
    } on ApiException catch (failure) {
      error = failure.message;
      return false;
    } catch (_) {
      error =
          'Account access failed. Check your connection and secure device storage, then retry.';
      return false;
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<bool> restore() => _run(() async {
    try {
      _accept(await repository.restore());
    } catch (_) {
      _accept(null);
      rethrow;
    }
  });

  Future<bool> login(String email, String password) => _run(() async {
    _accept(await repository.login(email, password));
  });

  Future<bool> register(String name, String email, String password) =>
      _run(() async {
        await repository.register(name, email, password);
        _accept(await repository.login(email, password));
      });

  Future<bool> logout() => _run(() async {
    try {
      await repository.logout();
    } finally {
      if (!repository.hasSession) _accept(null);
    }
  });

  @override
  void dispose() {
    _disposed = true;
    _expiry?.cancel();
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

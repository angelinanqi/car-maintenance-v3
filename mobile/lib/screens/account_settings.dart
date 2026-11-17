import 'package:flutter/material.dart';

import '../account_state.dart';
import '../app_spacing.dart';
import '../data/account_repository.dart';
import '../data/api_client.dart';
import '../widgets/design_widgets.dart';

enum AccountSetting {
  name('Edit display name', 'Save name'),
  email('Change email', 'Send confirmation'),
  password('Change password', 'Update password'),
  delete('Delete account', 'Delete account');

  const AccountSetting(this.title, this.action);
  final String title, action;
}

class AccountSettingForm extends StatefulWidget {
  final AccountSetting setting;
  const AccountSettingForm(this.setting, {super.key});

  @override
  State<AccountSettingForm> createState() => _AccountSettingFormState();
}

class _AccountSettingFormState extends State<AccountSettingForm> {
  final _form = GlobalKey<FormState>();
  final _value = TextEditingController();
  final _currentPassword = TextEditingController();
  final _confirmation = TextEditingController();
  final _code = TextEditingController();
  String? _owner, _factor, _error, _message;
  bool _needsCode = false;
  bool _hidePasswords = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final user = AccountScope.of(context)?.user;
    if (_owner == null && user != null) {
      _owner = user.id;
      if (widget.setting == AccountSetting.name) _value.text = user.name;
    }
  }

  @override
  void dispose() {
    _value.dispose();
    _currentPassword.dispose();
    _confirmation.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit(AccountState account, String? factorId) async {
    if (account.busy || !_form.currentState!.validate()) return;
    setState(() {
      _error = null;
      _message = null;
    });
    final setting = widget.setting;
    final success = await switch (setting) {
      AccountSetting.name => account.updateDisplayName(_value.text),
      AccountSetting.email => account.changeEmail(_value.text),
      AccountSetting.password => account.changePassword(
        _currentPassword.text,
        _value.text,
        nonce: _needsCode ? _code.text.trim() : null,
      ),
      AccountSetting.delete => account.deleteAccount(
        factorId!,
        _code.text.trim(),
      ),
    };
    if (!mounted) return;
    if (success) {
      Navigator.pop(context, switch (setting) {
        AccountSetting.name => 'Name updated.',
        AccountSetting.email =>
          'Check your current and new inboxes. Open any confirmation links you receive on this device.',
        AccountSetting.password => 'Password updated.',
        AccountSetting.delete => 'Your account was deleted.',
      });
    } else {
      setState(() {
        _error = account.error;
        if (account.authErrorCode == 'reauthentication_needed') {
          _needsCode = true;
        }
      });
    }
  }

  Future<void> _sendCode(AccountState account) async {
    final sent = await account.sendPasswordCode();
    if (!mounted) return;
    setState(() {
      _error = sent ? null : account.error;
      _message = sent ? 'Check your email for a verification code.' : null;
    });
  }

  Widget _passwordField(
    String label,
    TextEditingController controller,
    String autofill,
    bool busy,
    String? Function(String) validate,
  ) => TextFormField(
    controller: controller,
    obscureText: _hidePasswords,
    enabled: !busy,
    autofillHints: [autofill],
    enableSuggestions: false,
    autocorrect: false,
    decoration: InputDecoration(labelText: label),
    validator: (value) => validate(value ?? ''),
  );

  Widget _codeField(String label, bool busy) => TextFormField(
    controller: _code,
    enabled: !busy,
    keyboardType: TextInputType.number,
    autofillHints: const [AutofillHints.oneTimeCode],
    maxLength: 6,
    decoration: InputDecoration(labelText: label),
    validator: (value) => RegExp(r'^\d{6}$').hasMatch(value?.trim() ?? '')
        ? null
        : 'Enter the 6-digit code.',
  );

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context)!;
    final user = account.user;
    final setting = widget.setting;
    final busy = account.busy;
    final factors = user?.factorIds ?? const <String>[];
    final factorId = factors.contains(_factor) ? _factor : factors.firstOrNull;
    final errorColor = Theme.of(context).colorScheme.error;
    return PopScope(
      canPop: !busy,
      child: Scaffold(
        appBar: AppBar(title: Text(setting.title)),
        body: user == null || user.id != _owner
            ? const Center(child: Text('Sign in to manage your account.'))
            : AutofillGroup(
                child: Form(
                  key: _form,
                  child: FormList(
                    children: [
                      if (setting == AccountSetting.name)
                        TextFormField(
                          controller: _value,
                          enabled: !busy,
                          autofillHints: const [AutofillHints.name],
                          maxLength: 100,
                          decoration: const InputDecoration(
                            labelText: 'Display name',
                          ),
                          validator: (value) => (value ?? '').trim().isEmpty
                              ? 'Enter your display name.'
                              : null,
                        ),
                      if (setting == AccountSetting.email) ...[
                        Text('Current email: ${user.email}'),
                        const SizedBox(height: AppSpacing.standard),
                        TextFormField(
                          controller: _value,
                          enabled: !busy,
                          keyboardType: TextInputType.emailAddress,
                          autocorrect: false,
                          autofillHints: const [AutofillHints.email],
                          decoration: const InputDecoration(
                            labelText: 'New email address',
                          ),
                          validator: (value) {
                            final email = (value ?? '').trim();
                            if (!RegExp(
                              r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                            ).hasMatch(email)) {
                              return 'Enter a valid email address.';
                            }
                            if (email.toLowerCase() ==
                                user.email.toLowerCase()) {
                              return 'Enter a different email address.';
                            }
                            return null;
                          },
                        ),
                      ],
                      if (setting == AccountSetting.password) ...[
                        _passwordField(
                          'Current password',
                          _currentPassword,
                          AutofillHints.password,
                          busy,
                          (value) => value.isEmpty
                              ? 'Enter your current password.'
                              : null,
                        ),
                        const SizedBox(height: AppSpacing.standard),
                        _passwordField(
                          'New password',
                          _value,
                          AutofillHints.newPassword,
                          busy,
                          AccountRepository.validatePassword,
                        ),
                        const SizedBox(height: AppSpacing.standard),
                        _passwordField(
                          'Confirm new password',
                          _confirmation,
                          AutofillHints.newPassword,
                          busy,
                          (value) => value == _value.text
                              ? null
                              : 'Passwords do not match.',
                        ),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Show passwords'),
                          value: !_hidePasswords,
                          onChanged: busy
                              ? null
                              : (show) =>
                                    setState(() => _hidePasswords = !show),
                        ),
                        if (_needsCode) ...[
                          OutlinedButton(
                            onPressed: busy ? null : () => _sendCode(account),
                            child: const Text('Send verification code'),
                          ),
                          _codeField('Email verification code', busy),
                        ],
                      ],
                      if (setting == AccountSetting.delete) ...[
                        const Text(
                          'Your account, vehicles, service records, chats, and saved items will be removed. This cannot be undone.',
                        ),
                        const SizedBox(height: AppSpacing.standard),
                        if (user.factorIds.length > 1) ...[
                          DropdownButtonFormField<String>(
                            key: ValueKey(user.factorIds.join(',')),
                            initialValue: factorId,
                            decoration: const InputDecoration(
                              labelText: 'Authenticator',
                            ),
                            items: [
                              for (final (index, id) in user.factorIds.indexed)
                                DropdownMenuItem(
                                  value: id,
                                  child: Text('Authenticator ${index + 1}'),
                                ),
                            ],
                            onChanged: busy
                                ? null
                                : (value) => setState(() => _factor = value),
                          ),
                          const SizedBox(height: AppSpacing.standard),
                        ],
                        _codeField('6-digit authenticator code', busy),
                      ],
                      const SizedBox(height: AppSpacing.standard),
                      if (_message != null)
                        Semantics(liveRegion: true, child: Text(_message!)),
                      if (_error != null)
                        Semantics(
                          liveRegion: true,
                          child: Text(
                            _error!,
                            style: TextStyle(color: errorColor),
                          ),
                        ),
                      FilledButton(
                        style: setting == AccountSetting.delete
                            ? FilledButton.styleFrom(
                                backgroundColor: errorColor,
                                foregroundColor: Theme.of(
                                  context,
                                ).colorScheme.onError,
                              )
                            : null,
                        onPressed:
                            busy ||
                                (setting == AccountSetting.delete &&
                                    factorId == null)
                            ? null
                            : () => _submit(account, factorId),
                        child: Text(setting.action),
                      ),
                      if (busy) const LinearProgressIndicator(),
                    ],
                  ),
                ),
              ),
      ),
    );
  }
}

class SignedInSessions extends StatefulWidget {
  const SignedInSessions({super.key});

  @override
  State<SignedInSessions> createState() => _SignedInSessionsState();
}

class _SignedInSessionsState extends State<SignedInSessions> {
  Future<List<SignedInSession>>? _sessions;
  String? _owner;
  bool _busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final account = AccountScope.of(context)!;
    if (_owner == null && account.user != null) {
      _owner = account.user!.id;
      _sessions = account.repository.signedInSessions();
    }
  }

  Future<void> _signOut(AccountState account, SignedInSession session) async {
    if (_busy) return;
    setState(() => _busy = true);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out of this session?'),
        content: Text('Sign out of the ${session.device} session.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    if (confirmed != true || account.repository.userId != _owner) {
      setState(() => _busy = false);
      return;
    }
    var message = 'Session signed out.';
    try {
      await account.repository.revokeSession(session.id);
    } on ApiException catch (error) {
      message = error.message;
    } catch (_) {
      message =
          'Could not confirm sign-out. Check your connection and try again.';
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _sessions = account.repository.signedInSessions();
    });
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context)!;
    final user = account.user;
    final localizations = MaterialLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Signed-in sessions'),
        actions: [
          IconButton(
            tooltip: 'Refresh sessions',
            icon: const Icon(Icons.refresh),
            onPressed: _busy || user == null || user.id != _owner
                ? null
                : () => setState(
                    () => _sessions = account.repository.signedInSessions(),
                  ),
          ),
        ],
      ),
      body: user == null || user.id != _owner
          ? const Center(child: Text('Sign in to view your sessions.'))
          : FutureBuilder<List<SignedInSession>>(
              future: _sessions,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final sessions = snapshot.data;
                if (sessions == null) {
                  return FormList(
                    children: [
                      Text(
                        snapshot.error is ApiException
                            ? (snapshot.error! as ApiException).message
                            : 'Could not load sessions. Try again.',
                      ),
                      TextButton(
                        onPressed: () => setState(
                          () =>
                              _sessions = account.repository.signedInSessions(),
                        ),
                        child: const Text('Retry'),
                      ),
                    ],
                  );
                }
                return FormList(
                  children: [
                    if (sessions.isEmpty) const Text('No sessions to display.'),
                    for (final session in sessions)
                      SurfaceCard(
                        child: ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.devices_outlined),
                          title: Text(
                            session.current
                                ? '${session.device} (this session)'
                                : session.device,
                          ),
                          subtitle: Text(
                            'Last active ${localizations.formatShortDate(session.lastActive.toLocal())} '
                            '${localizations.formatTimeOfDay(TimeOfDay.fromDateTime(session.lastActive.toLocal()))}',
                          ),
                          trailing: session.current
                              ? null
                              : TextButton(
                                  onPressed: _busy
                                      ? null
                                      : () => _signOut(account, session),
                                  child: const Text('Sign out'),
                                ),
                        ),
                      ),
                  ],
                );
              },
            ),
    );
  }
}

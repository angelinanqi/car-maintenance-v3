import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../account_state.dart';
import '../data/account_repository.dart';
import '../widgets/design_widgets.dart';

class RecoveryEmailPage extends StatefulWidget {
  final bool confirmation;
  const RecoveryEmailPage({super.key, this.confirmation = false});
  @override
  State<RecoveryEmailPage> createState() => _RecoveryEmailPageState();
}

class _RecoveryEmailPageState extends State<RecoveryEmailPage> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  Timer? _timer;
  int _cooldown = 0;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final remaining = AccountScope.of(context)!.emailRetrySeconds;
    if (remaining > 0 && _timer == null) _startCooldown(remaining);
  }

  void _startCooldown(int seconds) {
    _cooldown = seconds;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return timer.cancel();
      setState(() => _cooldown--);
      if (_cooldown == 0) {
        timer.cancel();
        _timer = null;
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _email.dispose();
    super.dispose();
  }

  Future<void> _send(AccountState account) async {
    if (!_form.currentState!.validate()) return;
    final success = widget.confirmation
        ? await account.resend(_email.text)
        : await account.recoveryEmail(_email.text);
    if (!mounted) return;
    if (success || account.rateLimited) {
      account.emailRetryAt = DateTime.now().add(const Duration(seconds: 60));
      setState(() => _startCooldown(60));
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.confirmation ? 'Confirm email' : 'Reset password'),
      ),
      body: Form(
        key: _form,
        child: FormList(
          children: [
            const Text(
              'Enter your account email. Open the latest email link on this device.',
            ),
            TextFormField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              enabled: !account.busy,
              decoration: const InputDecoration(labelText: 'Email'),
              validator: (value) =>
                  RegExp(
                    r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                  ).hasMatch(value?.trim() ?? '')
                  ? null
                  : 'Enter a valid email',
            ),
            if (account.error != null) Text(account.error!),
            if (account.message != null) Text(account.message!),
            FilledButton(
              onPressed: account.busy || _cooldown > 0
                  ? null
                  : () => _send(account),
              child: Text(
                _cooldown > 0 ? 'Try again in ${_cooldown}s' : 'Send email',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AccountSecurity extends StatefulWidget {
  final bool requiredFlow;
  final VoidCallback? onEmergency;
  const AccountSecurity({
    super.key,
    this.requiredFlow = false,
    this.onEmergency,
  });
  @override
  State<AccountSecurity> createState() => _AccountSecurityState();
}

class _AccountSecurityState extends State<AccountSecurity> {
  final _form = GlobalKey<FormState>();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _code = TextEditingController();
  AuthMFAEnrollResponse? _enrollment;
  String? _selectedFactor;
  bool _loading = false;
  String? _verifiedFactor;
  String? _feedback;

  Future<void> _enroll(AccountState account) async {
    setState(() {
      _loading = true;
      _feedback = null;
    });
    try {
      // Remove only abandoned, unverified attempts owned by this user.
      final factors = await account.repository.auth.mfa.listFactors();
      for (final factor in factors.all.where(
        (f) => f.status == FactorStatus.unverified,
      )) {
        await account.repository.auth.mfa.unenroll(factor.id);
      }
      final enrollment = await account.repository.auth.mfa.enroll(
        factorType: FactorType.totp,
        issuer: 'MyRoadie',
        friendlyName: 'Authenticator ${DateTime.now().millisecondsSinceEpoch}',
      );
      if (mounted) setState(() => _enrollment = enrollment);
    } on AuthException catch (failure) {
      debugPrint(
        'ERROR [mobile-auth] Authenticator enrollment failed (${failure.code ?? 'unknown'}).',
      );
      if (mounted)
        setState(
          () => _feedback =
              'Authenticator setup could not start. Check your connection and retry.',
        );
    } catch (failure) {
      debugPrint(
        'ERROR [mobile-auth] Authenticator enrollment failed (${failure.runtimeType}).',
      );
      if (mounted)
        setState(
          () => _feedback =
              'Authenticator setup could not start. Check your connection and retry.',
        );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit(AccountState account) async {
    if (!_form.currentState!.validate()) return;
    if (account.recoveringPassword && !account.recoveryNeedsMfa) {
      await account.resetPassword(_password.text);
      return;
    }
    final factors =
        (account.recoveringPassword ? account.recoveryFactorIds : null) ??
        account.pendingSession?.factorIds ??
        account.user?.factorIds ??
        <String>[];
    final factorId =
        _enrollment?.id ??
        (factors.contains(_selectedFactor)
            ? _selectedFactor
            : factors.firstOrNull);
    if (factorId == null) return;
    final success = await account.verifyFactor(factorId, _code.text.trim());
    if (!mounted || !success) return;
    _code.clear();
    setState(() {
      _enrollment = null;
      _verifiedFactor = factorId;
      _feedback =
          'Authenticator verified. Keep a backup authenticator before replacing a device.';
    });
  }

  Future<void> _remove(AccountState account, String factorId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove this authenticator?'),
        content: const Text(
          'Keep access to the authenticator you just verified. It will still be required when you sign in.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    setState(() => _loading = true);
    try {
      await account.repository.auth.mfa.unenroll(factorId);
      await account.repository.auth.refreshSession();
      await account.restore();
      if (mounted)
        setState(() {
          _selectedFactor = null;
          _feedback = 'Authenticator removed.';
        });
    } catch (_) {
      if (mounted)
        setState(
          () => _feedback =
              'Removal could not be confirmed. Refresh account security before retrying.',
        );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    _code.dispose();
    // No QR codes or shared secrets are persisted by this screen.
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context)!;
    final recovery = account.recoveringPassword && !account.recoveryNeedsMfa;
    final session = account.pendingSession ?? account.user;
    final factors = account.recoveringPassword
        ? account.recoveryFactorIds
        : session?.factorIds ?? [];
    final selectedFactor = factors.contains(_selectedFactor)
        ? _selectedFactor
        : factors.firstOrNull;
    final busy = _loading || account.busy;
    final enrollment = _enrollment;
    return PopScope(
      canPop: !widget.requiredFlow,
      child: Scaffold(
        appBar: AppBar(
          title: Text(recovery ? 'Choose a new password' : 'Account security'),
          automaticallyImplyLeading: !widget.requiredFlow,
        ),
        body: Form(
          key: _form,
          child: FormList(
            children: [
              if (recovery) ...[
                const Text('Choose a password with 8 to 20 characters.'),
                TextFormField(
                  controller: _password,
                  obscureText: true,
                  maxLength: 20,
                  enabled: !busy,
                  decoration: const InputDecoration(labelText: 'New password'),
                  autofillHints: const [AutofillHints.newPassword],
                  validator: (value) =>
                      AccountRepository.validatePassword(value ?? ''),
                ),
                TextFormField(
                  controller: _confirm,
                  obscureText: true,
                  maxLength: 20,
                  enabled: !busy,
                  decoration: const InputDecoration(
                    labelText: 'Confirm new password',
                  ),
                  validator: (value) =>
                      value != _password.text ? 'Passwords do not match' : null,
                ),
                FilledButton(
                  onPressed: busy ? null : () => _submit(account),
                  child: const Text('Update password'),
                ),
              ] else ...[
                Text(
                  account.recoveryNeedsMfa
                      ? 'Verify your authenticator before choosing a new password.'
                      : session?.mfaRequired == true
                      ? 'Authenticator verification is required for this account.'
                      : 'Add an authenticator app for an extra sign-in check.',
                ),
                const Text(
                  'Keep a second authenticator as a backup. If you lose every authenticator, contact the administrator for identity-verified recovery.',
                ),
                if (enrollment == null &&
                    (!widget.requiredFlow || factors.isEmpty))
                  FilledButton(
                    onPressed: busy ? null : () => _enroll(account),
                    child: Text(
                      factors.isEmpty
                          ? 'Set up authenticator'
                          : 'Add backup authenticator',
                    ),
                  ),
                if (enrollment != null) ...[
                  const Text(
                    'Scan this code with your authenticator app, or enter the setup key. Keep this key private.',
                  ),
                  Center(
                    child: SvgPicture.string(
                      enrollment.totp!.qrCode.replaceFirst(
                        'data:image/svg+xml;utf-8,',
                        '',
                      ),
                      width: 220,
                      height: 220,
                    ),
                  ),
                  SelectableText(enrollment.totp!.secret),
                ],
                if (factors.isNotEmpty && enrollment == null)
                  DropdownButtonFormField<String>(
                    key: ValueKey(factors.join(',')),
                    initialValue: selectedFactor,
                    decoration: const InputDecoration(
                      labelText: 'Authenticator',
                    ),
                    items: [
                      for (var i = 0; i < factors.length; i++)
                        DropdownMenuItem(
                          value: factors[i],
                          child: Text('Authenticator ${i + 1}'),
                        ),
                    ],
                    onChanged: busy
                        ? null
                        : (value) => setState(() => _selectedFactor = value),
                  ),
                if (enrollment != null || factors.isNotEmpty) ...[
                  TextFormField(
                    controller: _code,
                    keyboardType: TextInputType.number,
                    maxLength: 6,
                    enabled: !busy,
                    decoration: const InputDecoration(
                      labelText: '6-digit authenticator code',
                    ),
                    validator: (value) =>
                        RegExp(r'^\d{6}$').hasMatch(value?.trim() ?? '')
                        ? null
                        : 'Enter the 6-digit code',
                  ),
                  FilledButton(
                    onPressed: busy ? null : () => _submit(account),
                    child: const Text('Verify authenticator'),
                  ),
                ],
                if (!widget.requiredFlow &&
                    factors.length > 1 &&
                    _verifiedFactor != null &&
                    selectedFactor != _verifiedFactor)
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => _remove(account, selectedFactor!),
                    child: const Text('Remove selected authenticator'),
                  ),
              ],
              if (busy) const LinearProgressIndicator(),
              if (account.error != null) Text(account.error!),
              if (_feedback != null) Text(_feedback!),
              if (widget.requiredFlow)
                TextButton(
                  onPressed: busy ? null : account.logout,
                  child: const Text('Cancel and sign out'),
                ),
              if (widget.onEmergency != null)
                TextButton.icon(
                  onPressed: widget.onEmergency,
                  icon: const Icon(Icons.emergency),
                  label: const Text('Emergency help · no sign-in'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

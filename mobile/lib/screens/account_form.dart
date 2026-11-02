import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../account_state.dart';
import '../data/account_repository.dart';
import 'account_security.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';

class AccountForm extends StatefulWidget {
  final bool register;
  final VoidCallback? onGuest, onEmergency;
  const AccountForm({
    super.key,
    required this.register,
    this.onGuest,
    this.onEmergency,
  });
  @override
  State<AccountForm> createState() => _AccountFormState();
}

class _AccountFormState extends State<AccountForm> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _hidePassword = true;
  late bool _register;

  @override
  void initState() {
    super.initState();
    _register = widget.register;
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit(AccountState account) async {
    if (!_form.currentState!.validate()) return;
    final success = _register
        ? await account.register(_name.text, _email.text, _password.text)
        : await account.login(_email.text, _password.text);
    if (!mounted) return;
    if (!success) return;
    _password.clear();
    if (_register && account.user == null) {
      setState(() => _register = false);
    } else if (Navigator.canPop(context)) {
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context);
    if (account != null &&
        (account.recoveringPassword || account.pendingSession != null)) {
      return const AccountSecurity(requiredFlow: true);
    }
    final busy = account?.busy ?? true;
    return Scaffold(
      appBar: widget.onGuest == null
          ? AppBar(title: Text(_register ? 'Create account' : 'Log in'))
          : null,
      body: SafeArea(
        child: Form(
          key: _form,
          child: FormList(
            padding: const EdgeInsets.all(AppSpacing.screen),
            children: [
              const SizedBox(height: 10),
              Align(
                alignment: Alignment.centerLeft,
                child: Image.asset(
                  'assets/images/branding/roadie_full_logo.png',
                  width: 240,
                  height: 80,
                  fit: BoxFit.contain,
                  semanticLabel: 'MyRoadie, your car companion',
                ),
              ),
              const SizedBox(height: 20),
              Text(
                _register ? 'Start your garage' : 'Welcome back',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 8),
              const Text('Log in to manage your car records.'),
              const SizedBox(height: 16),
              if (account?.message != null) Text(account!.message!),
              if (account?.error != null)
                Text(
                  account!.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              if (_register) ...[
                TextFormField(
                  controller: _name,
                  enabled: !busy,
                  maxLength: 100,
                  textCapitalization: TextCapitalization.words,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.name],
                  decoration: const InputDecoration(labelText: 'Name'),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'Enter your name'
                      : null,
                ),
                const SizedBox(height: 16),
              ],
              TextFormField(
                controller: _email,
                enabled: !busy,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.email],
                decoration: const InputDecoration(hintText: 'name@email.com'),
                validator: (value) =>
                    value != null &&
                        RegExp(
                          r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                        ).hasMatch(value.trim())
                    ? null
                    : 'Enter a valid email',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _password,
                enabled: !busy,
                obscureText: _hidePassword,
                enableSuggestions: false,
                autocorrect: false,
                maxLength: _register ? 20 : 1024,
                textInputAction: TextInputAction.done,
                autofillHints: [
                  _register
                      ? AutofillHints.newPassword
                      : AutofillHints.password,
                ],
                onFieldSubmitted: busy ? null : (_) => _submit(account!),
                decoration: InputDecoration(
                  labelText: 'Password',
                  helperText: _register ? 'Use 8 to 20 characters.' : null,
                  counterText: '',
                  suffixIcon: IconButton(
                    style: IconButton.styleFrom(
                      backgroundColor: Colors.transparent,
                    ),
                    tooltip: _hidePassword ? 'Show password' : 'Hide password',
                    icon: Icon(
                      _hidePassword ? Icons.visibility : Icons.visibility_off,
                    ),
                    onPressed: () =>
                        setState(() => _hidePassword = !_hidePassword),
                  ),
                ),
                validator: (value) => _register
                    ? AccountRepository.validatePassword(value ?? '')
                    : (value == null || value.isEmpty
                          ? 'Enter your password'
                          : null),
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: busy ? null : () => _submit(account!),
                child: Text(
                  busy
                      ? 'Please wait...'
                      : _register
                      ? 'Create account'
                      : 'Log in',
                ),
              ),
              const SizedBox(height: 8),
              if (!_register)
                TextButton(
                  onPressed: busy
                      ? null
                      : () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const RecoveryEmailPage(),
                          ),
                        ),
                  child: const Text('Forgot password?'),
                ),
              TextButton(
                onPressed: busy
                    ? null
                    : () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              const RecoveryEmailPage(confirmation: true),
                        ),
                      ),
                child: const Text('Resend confirmation email'),
              ),
              OutlinedButton(
                onPressed: busy
                    ? null
                    : () => setState(() {
                        _register = !_register;
                        _form.currentState?.reset();
                      }),
                child: Text(
                  _register
                      ? 'Already have an account? Sign in'
                      : 'Create account',
                ),
              ),
              const SizedBox(height: 55),
              ActionRow(
                icon: Icons.person_outline,
                title: 'Continue as guest',
                subtitle: 'Browse guides and roadside help',
                onTap: widget.onGuest ?? () => Navigator.pop(context),
              ),
              if (widget.onEmergency != null)
                TextButton.icon(
                  onPressed: widget.onEmergency,
                  icon: const Icon(
                    Icons.warning_amber,
                    color: AppColors.danger,
                  ),
                  label: const Text(
                    'Emergency help · no sign-in',
                    style: TextStyle(color: AppColors.danger),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

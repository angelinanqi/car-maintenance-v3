import 'package:flutter/material.dart';
import '../account_state.dart';

class AccountForm extends StatefulWidget {
  final bool register;
  const AccountForm({super.key, required this.register});
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
  String? _message;

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
    setState(() => _message = null);
    final success = _register
        ? await account.register(_name.text, _email.text, _password.text)
        : await account.login(_email.text, _password.text);
    if (!mounted) return;
    _password.clear();
    if (!success) return;
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context);
    final busy = account?.busy ?? true;
    return Scaffold(
      appBar: AppBar(title: Text(_register ? 'Create account' : 'Sign in')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              _register ? 'Start your garage' : 'Welcome back',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text(
              'Continue as a guest for learning and offline emergency assistance. Sign in for your vehicles, maintenance and learning progress.',
            ),
            const SizedBox(height: 16),
            if (_message != null) Text(_message!),
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
              decoration: const InputDecoration(labelText: 'Email'),
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
              maxLength: 1024,
              textInputAction: TextInputAction.done,
              autofillHints: [
                _register ? AutofillHints.newPassword : AutofillHints.password,
              ],
              onFieldSubmitted: busy ? null : (_) => _submit(account!),
              decoration: InputDecoration(
                labelText: 'Password',
                helperText: _register ? 'Use at least 8 characters.' : null,
                counterText: '',
                suffixIcon: IconButton(
                  tooltip: _hidePassword ? 'Show password' : 'Hide password',
                  icon: Icon(
                    _hidePassword ? Icons.visibility : Icons.visibility_off,
                  ),
                  onPressed: () =>
                      setState(() => _hidePassword = !_hidePassword),
                ),
              ),
              validator: (value) => (value?.length ?? 0) < (_register ? 8 : 1)
                  ? (_register
                        ? 'Use at least 8 characters'
                        : 'Enter your password')
                  : null,
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: busy ? null : () => _submit(account!),
              child: Text(
                busy
                    ? 'Please wait...'
                    : _register
                    ? 'Create account'
                    : 'Sign in',
              ),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: busy
                  ? null
                  : () => setState(() {
                      _register = !_register;
                      _form.currentState?.reset();
                    }),
              child: Text(
                _register
                    ? 'Already have an account? Sign in'
                    : 'New here? Create account',
              ),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Continue as guest'),
            ),
          ],
        ),
      ),
    );
  }
}

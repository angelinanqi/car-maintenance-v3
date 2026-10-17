import 'package:flutter/material.dart';
import '../app_state.dart';
import '../account_state.dart';
import 'account_form.dart';

class Profile extends StatefulWidget {
  final AppState state;
  const Profile({super.key, required this.state});
  @override
  State<Profile> createState() => _ProfileState();
}

class _ProfileState extends State<Profile> {
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _form = GlobalKey<FormState>();
  bool _busy = false;
  String? _feedback;
  @override
  void initState() {
    super.initState();
    _name.text = widget.state.contactName;
    _phone.text = widget.state.contactPhone;
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await widget.state.saveContact(_name.text, _phone.text);
      if (mounted) {
        setState(() => _feedback = 'Roadside contact saved on this device.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _feedback = 'Could not save preferences. Please retry.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Account and preferences')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            account?.user != null
                ? 'Signed in as ${account!.user!.name}'
                : account?.hasSavedSession == true
                ? 'Saved session needs verification'
                : 'Using the app as a guest',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          const Text(
            'Vehicles, maintenance and learning progress belong to your account. Roadside contacts and local incident records remain available offline.',
          ),
          if (account?.user != null) Text(account!.user!.email),
          if (account?.repository.offlineSession == true)
            const Text(
              'Using the previously signed-in device session offline. Cloud-backed actions require connectivity.',
            ),
          if (account?.busy == true) const LinearProgressIndicator(),
          if (account?.error != null) Text(account!.error!),
          if (account != null &&
              (account.hasSavedSession || account.error != null))
            TextButton(
              onPressed: account.busy ? null : account.restore,
              child: const Text('Verify session'),
            ),
          if (account?.hasSavedSession == true)
            OutlinedButton(
              onPressed: account!.busy ? null : account.logout,
              child: const Text('Sign out'),
            ),
          const SizedBox(height: 16),
          if (account?.hasSavedSession != true)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton(
                  onPressed: account == null || account.busy
                      ? null
                      : () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const AccountForm(register: false),
                          ),
                        ),
                  child: const Text('Sign in'),
                ),
                OutlinedButton(
                  onPressed: account == null || account.busy
                      ? null
                      : () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const AccountForm(register: true),
                          ),
                        ),
                  child: const Text('Create account'),
                ),
              ],
            ),
          const Divider(height: 32),
          Text(
            'Your roadside contact',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const Text(
            'Enter a number from your own insurer or assistance provider. This is a personal contact, not a verified public directory.',
          ),
          const SizedBox(height: 16),
          Form(
            key: _form,
            child: Column(
              children: [
                TextFormField(
                  controller: _name,
                  decoration: const InputDecoration(
                    labelText: 'Provider or contact name',
                  ),
                  validator: (value) =>
                      _phone.text.trim().isNotEmpty &&
                          (value == null || value.trim().isEmpty)
                      ? 'Enter a contact name'
                      : null,
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Phone number'),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return _name.text.trim().isEmpty
                          ? null
                          : 'Enter a number';
                    }
                    final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
                    return digits.length >= 3 &&
                            RegExp(
                              r'^\+?[0-9 ()-]{3,25}$',
                            ).hasMatch(value.trim())
                        ? null
                        : 'Enter a valid phone number';
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _save,
            child: Text(_busy ? 'Saving...' : 'Save roadside contact'),
          ),
          if (_feedback != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_feedback!),
            ),
        ],
      ),
    );
  }
}

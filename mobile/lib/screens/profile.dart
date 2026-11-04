import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../account_state.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';
import 'account_form.dart';
import 'account_security.dart';

class Profile extends StatefulWidget {
  final AppState state;
  const Profile({super.key, required this.state});
  @override
  State<Profile> createState() => _ProfileState();
}

class _ProfileState extends State<Profile> {
  String _familyName = '', _familyPhone = '';
  bool _busy = false;
  String? _feedback;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await widget.state.store.read('ui_preferences.json');
      if (mounted && data != null)
        setState(() {
          _familyName = data['familyName'] as String? ?? '';
          _familyPhone = data['familyPhone'] as String? ?? '';
        });
    } catch (_) {
      if (mounted)
        setState(
          () => _feedback = 'Preferences could not be opened. Try again.',
        );
    }
  }

  Future<void> _preferences({String? name, String? phone}) async {
    final data = {
      'familyName': name ?? _familyName,
      'familyPhone': phone ?? _familyPhone,
    };
    setState(() => _busy = true);
    try {
      await widget.state.store.write('ui_preferences.json', data);
      if (mounted)
        setState(() {
          _familyName = data['familyName'] as String;
          _familyPhone = data['familyPhone'] as String;
          _feedback = 'Preference saved on this device.';
        });
    } catch (_) {
      if (mounted)
        setState(() => _feedback = 'Preference could not be saved. Try again.');
      rethrow;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _contact(bool family) async {
    final value = await showDialog<(String, String)>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _ContactEditor(
        name: family ? _familyName : widget.state.contactName,
        phone: family ? _familyPhone : widget.state.contactPhone,
        onSave: family
            ? (name, phone) => _preferences(name: name, phone: phone)
            : widget.state.saveContact,
      ),
    );
    if (value == null || !mounted) return;
    setState(
      () => _feedback = family
          ? 'Family contact saved on this device.'
          : 'Roadside contact saved on this device.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final account = AccountScope.of(context);
    final user = account?.user;
    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.screen,
          0,
          AppSpacing.screen,
          24,
        ),
        children: [
          ActionRow(
            icon: Icons.person_outline,
            title: user?.name ?? 'Guest',
            subtitle: user?.email ?? 'Guides and roadside help are available',
            trailing: const SizedBox.shrink(),
          ),
          if (account?.hasSavedSession != true)
            FilledButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const AccountForm(register: false),
                ),
              ),
              child: const Text('Log in or create account'),
            ),
          if (account?.error != null)
            Text(
              account!.error!,
              style: const TextStyle(color: AppColors.danger),
            ),
          if (account?.hasSavedSession == true || account?.error != null)
            TextButton(
              onPressed: account?.busy == true ? null : account?.restore,
              child: const Text('Verify session'),
            ),
          const SizedBox(height: 24),
          if (user != null)
            ActionRow(
              icon: Icons.security,
              title: 'Account security',
              subtitle: 'Manage authenticator verification',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AccountSecurity()),
              ),
            ),
          Text(
            'Emergency contacts',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.standard),
          ActionRow(
            icon: Icons.phone_outlined,
            title: 'Roadside assistance',
            subtitle: widget.state.contactPhone.isEmpty
                ? 'Not set'
                : widget.state.contactPhone,
            onTap: _busy ? null : () => _contact(false),
            trailing: StatusPill(
              widget.state.contactPhone.isEmpty ? 'Add' : 'Edit',
            ),
          ),
          ActionRow(
            icon: Icons.phone_outlined,
            title: _familyName.isEmpty ? 'Family contact' : _familyName,
            subtitle: _familyPhone.isEmpty ? 'Not set' : _familyPhone,
            onTap: _busy ? null : () => _contact(true),
            trailing: StatusPill(_familyPhone.isEmpty ? 'Add' : 'Edit'),
          ),
          const SizedBox(height: 8),
          Text(
            'Maintenance tracking',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.standard),
          SurfaceCard(
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Distance units',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                  ),
                ),
                const Text('km', style: TextStyle(color: AppColors.muted)),
              ],
            ),
          ),
          SurfaceCard(
            child: const ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Service reminders'),
              subtitle: Text(
                'Check Home and My Car for upcoming and overdue work. Update your odometer and service history to keep reminders current.',
                style: TextStyle(fontSize: 12),
              ),
            ),
          ),
          if (_busy || account?.busy == true) const LinearProgressIndicator(),
          if (_feedback != null)
            Text(_feedback!, style: const TextStyle(color: AppColors.muted)),
          const SizedBox(height: AppSpacing.large),
          if (account?.hasSavedSession == true)
            OutlinedButton(
              onPressed: account!.busy ? null : account.logout,
              child: const Text(
                'Log out',
                style: TextStyle(color: AppColors.danger),
              ),
            ),
        ],
      ),
    );
  }
}

class _ContactEditor extends StatefulWidget {
  final String name, phone;
  final Future<void> Function(String, String)? onSave;
  const _ContactEditor({required this.name, required this.phone, this.onSave});
  @override
  State<_ContactEditor> createState() => _ContactEditorState();
}

class _ContactEditorState extends State<_ContactEditor> {
  bool _saving = false;
  String? _error;
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name, _phone;
  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.name);
    _phone = TextEditingController(text: widget.phone);
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_saving,
    child: AlertDialog(
      title: const Text('Emergency contact'),
      content: Form(
        key: _form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: _name,
              maxLength: 200,
              enabled: !_saving,
              decoration: const InputDecoration(labelText: 'Name / provider'),
              validator: (value) =>
                  _phone.text.trim().isNotEmpty &&
                      (value?.trim().isEmpty ?? true)
                  ? 'Enter a name'
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phone,
              maxLength: 25,
              enabled: !_saving,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone number'),
              validator: (value) {
                if (_name.text.trim().isEmpty &&
                    (value?.trim().isEmpty ?? true))
                  return null;
                return RegExp(
                          r'^\+?[0-9 ()-]{3,25}$',
                        ).hasMatch(value?.trim() ?? '') &&
                        (value ?? '')
                                .replaceAll(RegExp(r'[^0-9]'), '')
                                .length >=
                            3
                    ? null
                    : 'Enter a valid phone number';
              },
            ),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving
              ? null
              : () async {
                  if (!_form.currentState!.validate()) return;
                  setState(() {
                    _saving = true;
                    _error = null;
                  });
                  try {
                    await widget.onSave?.call(
                      _name.text.trim(),
                      _phone.text.trim(),
                    );
                    if (context.mounted)
                      Navigator.pop(context, (
                        _name.text.trim(),
                        _phone.text.trim(),
                      ));
                  } catch (_) {
                    if (mounted)
                      setState(
                        () => _error =
                            'Could not save roadside contact. Your entries are kept. Retry saving.',
                      );
                  } finally {
                    if (mounted) setState(() => _saving = false);
                  }
                },
          child: const Text('Save'),
        ),
      ],
    ),
  );
}

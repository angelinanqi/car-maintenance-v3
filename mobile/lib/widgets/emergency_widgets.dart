import '../app_spacing.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../app_state.dart';
import '../screens/profile.dart';
import 'preview_mode.dart';

Future<void> dialAssistance(BuildContext context, String phone) async {
  if (previewExternalActions) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Preview only. No phone call is placed.')),
    );
    return;
  }
  try {
    if (!await launchUrl(
      Uri(scheme: 'tel', path: phone.replaceAll(RegExp(r'[^+0-9]'), '')),
    )) {
      throw StateError('No dialer');
    }
  } catch (_) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not open the phone app. Dial $phone manually.'),
        ),
      );
    }
  }
}

class EmergencyNotice extends StatelessWidget {
  final String title, message;
  final bool danger;
  final Widget? action;
  const EmergencyNotice({
    super.key,
    required this.title,
    required this.message,
    this.danger = false,
    this.action,
  });
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: danger ? colors.errorContainer : colors.primaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: danger
                  ? colors.onErrorContainer
                  : colors.onPrimaryContainer,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            style: TextStyle(
              color: danger
                  ? colors.onErrorContainer
                  : colors.onPrimaryContainer,
            ),
          ),
          if (action != null) ...[const SizedBox(height: 8), action!],
        ],
      ),
    );
  }
}

class EmergencyAction extends StatelessWidget {
  final IconData icon;
  final String title, subtitle;
  final VoidCallback onTap;
  const EmergencyAction({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Material(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.standard),
          child: Row(
            children: [
              ExcludeSemantics(
                child: Icon(
                  icon,
                  size: 28,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text(subtitle),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const ExcludeSemantics(child: Icon(Icons.chevron_right)),
            ],
          ),
        ),
      ),
    ),
  );
}

class EmergencyHelpBar extends StatelessWidget {
  final VoidCallback onHelp;
  final bool showEmergencyCall;
  const EmergencyHelpBar({
    super.key,
    required this.onHelp,
    this.showEmergencyCall = false,
  });
  @override
  Widget build(BuildContext context) => Material(
    color: Theme.of(context).colorScheme.surface,
    child: SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.screen,
          8,
          AppSpacing.screen,
          8,
        ),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final stacked = MediaQuery.textScalerOf(context).scale(15) > 20;
            final width = showEmergencyCall && !stacked
                ? (constraints.maxWidth - 12) / 2
                : constraints.maxWidth;
            return Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                if (showEmergencyCall)
                  SizedBox(
                    width: width,
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: Theme.of(context).colorScheme.error,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: () => dialAssistance(context, '999'),
                      icon: const Icon(Icons.call_outlined),
                      label: const Text('Call 999'),
                    ),
                  ),
                SizedBox(
                  width: width,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: showEmergencyCall
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.error,
                      foregroundColor: showEmergencyCall
                          ? Theme.of(context).colorScheme.onPrimary
                          : Theme.of(context).colorScheme.onError,
                    ),
                    onPressed: onHelp,
                    icon: const Icon(Icons.call_outlined),
                    label: Text(
                      showEmergencyCall ? 'Roadside' : 'Call for help',
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    ),
  );
}

class RoadsideContact extends StatelessWidget {
  final AppState state;
  const RoadsideContact({super.key, required this.state});
  Future<void> _dial(BuildContext context) =>
      dialAssistance(context, state.contactPhone);

  @override
  Widget build(BuildContext context) => Card.outlined(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Your roadside contact',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (state.contactPhone.isEmpty)
            const Text('No personal assistance number saved yet.')
          else ...[
            Text(state.contactName),
            SelectableText(state.contactPhone),
            FilledButton.icon(
              onPressed: () => _dial(context),
              icon: const Icon(Icons.call),
              label: const Text('Call roadside contact'),
            ),
          ],
          TextButton(
            onPressed: state.loading
                ? null
                : () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => Profile(state: state)),
                  ),
            child: Text(
              state.contactPhone.isEmpty
                  ? 'Add roadside contact'
                  : 'Edit contact',
            ),
          ),
        ],
      ),
    ),
  );
}

class FamilyContact extends StatefulWidget {
  final AppState state;
  const FamilyContact({super.key, required this.state});
  @override
  State<FamilyContact> createState() => _FamilyContactState();
}

class _FamilyContactState extends State<FamilyContact> {
  late Future<Map<String, dynamic>?> _contact;
  @override
  void initState() {
    super.initState();
    _contact = _read();
  }

  Future<Map<String, dynamic>?> _read() async {
    final data = await widget.state.store.read('ui_preferences.json');
    if (data != null &&
        ((data['familyName'] != null && data['familyName'] is! String) ||
            (data['familyPhone'] != null && data['familyPhone'] is! String))) {
      throw const FormatException('Invalid family contact');
    }
    return data;
  }

  Future<void> _edit() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => Profile(state: widget.state)),
    );
    if (mounted) setState(() => _contact = _read());
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>?>(
    future: _contact,
    builder: (context, snapshot) {
      final name = snapshot.data?['familyName'] as String? ?? '';
      final phone = snapshot.data?['familyPhone'] as String? ?? '';
      return Card.outlined(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Your family contact',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (snapshot.hasError)
                const Text(
                  'Saved contact could not be opened. Your file has been kept.',
                )
              else if (phone.isEmpty)
                const Text('No family contact saved yet.')
              else ...[
                if (name.isNotEmpty) Text(name),
                SelectableText(phone),
                FilledButton.icon(
                  onPressed: () => dialAssistance(context, phone),
                  icon: const Icon(Icons.call),
                  label: const Text('Call family contact'),
                ),
              ],
              TextButton(
                onPressed: _edit,
                child: Text(
                  phone.isEmpty ? 'Add family contact' : 'Edit family contact',
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

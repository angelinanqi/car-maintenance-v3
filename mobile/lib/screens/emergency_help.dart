import 'package:flutter/material.dart';
import '../app_spacing.dart';
import '../app_state.dart';
import '../data/api_client.dart';
import '../data/content_repository.dart';
import '../data/nearby_repository.dart';
import '../widgets/emergency_widgets.dart';
import '../widgets/emergency_location_share.dart';
import 'nearby_assistance.dart';

Future<void> openEmergencyHelp(
  BuildContext context,
  AppState state,
  ContentRepository content,
) => Navigator.of(context).push(
  MaterialPageRoute(
    builder: (_) => EmergencyHelp(state: state, content: content),
  ),
);

class EmergencyHelp extends StatefulWidget {
  final AppState state;
  final ContentRepository content;
  const EmergencyHelp({super.key, required this.state, required this.content});
  @override
  State<EmergencyHelp> createState() => _EmergencyHelpState();
}

class _EmergencyHelpState extends State<EmergencyHelp> {
  List<Map<String, dynamic>> _contacts = [];
  bool _refreshing = false;
  String? _error;
  ApiClient? _nearbyApi;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool refresh = false}) async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      final contacts = await widget.content.emergencyContacts(refresh: refresh);
      if (mounted) {
        setState(() {
          _contacts = contacts.where((contact) {
            final phone = contact['phone'] as String;
            return phone.replaceAll(RegExp(r'[^0-9]'), '') != '999';
          }).toList();
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Could not load shared contacts. Try refreshing when connected.',
        );
      }
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
    if (!refresh && mounted && widget.content.api != null) {
      _load(refresh: true);
    }
  }

  @override
  void dispose() {
    _nearbyApi?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Call for help')),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.screen),
          children: [
            EmergencyNotice(
              title: 'Emergency services',
              message: 'For injuries, fire or immediate danger in Malaysia.',
              danger: true,
              action: FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: theme.colorScheme.error,
                  foregroundColor: theme.colorScheme.onError,
                ),
                onPressed: () => dialAssistance(context, '999'),
                icon: const Icon(Icons.call),
                label: const Text('Call 999'),
              ),
            ),
            const SizedBox(height: AppSpacing.standard),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Roadside assistance',
                    style: theme.textTheme.titleLarge,
                  ),
                ),
                IconButton(
                  tooltip: 'Refresh shared contacts',
                  onPressed: _refreshing ? null : () => _load(refresh: true),
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            if (_refreshing) ...[
              const LinearProgressIndicator(
                semanticsLabel: 'Loading assistance contacts',
              ),
              const SizedBox(height: AppSpacing.small),
            ],
            if (_error case final String error)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.small),
                child: Semantics(liveRegion: true, child: Text(error)),
              ),
            if (_contacts.isEmpty && !_refreshing && _error == null)
              const Text('No shared contacts available on this device.'),
            for (final contact in _contacts)
              _HotlineCard(
                name: contact['name'] as String,
                phone: contact['phone'] as String,
                description: contact['description'] as String? ?? '',
              ),
            const SizedBox(height: AppSpacing.section),
            Text('Saved contacts', style: theme.textTheme.titleLarge),
            const SizedBox(height: AppSpacing.compact),
            ListenableBuilder(
              listenable: widget.state,
              builder: (context, _) => RoadsideContact(state: widget.state),
            ),
            FamilyContact(state: widget.state),
            const SizedBox(height: AppSpacing.small),
            const EmergencyLocationShare(),
            const SizedBox(height: AppSpacing.section),
            EmergencyAction(
              icon: Icons.location_on_outlined,
              title: 'Find nearby assistance',
              subtitle:
                  'Workshops, tyre shops and towing searches. Internet required.',
              onTap: () {
                final api = widget.content.api ?? (_nearbyApi ??= ApiClient());
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        NearbyAssistance(repository: NearbyRepository(api)),
                  ),
                );
              },
            ),
            const Text(
              'Call providers to confirm availability, roadside service and charges. The app does not book or dispatch assistance.',
            ),
          ],
        ),
      ),
    );
  }
}

class _HotlineCard extends StatelessWidget {
  // Directory descriptions can end with an inline or standalone source note.
  static final _sourceNote = RegExp(
    r'(^[ \t]*|[.!?][ \t]+)sources?[ \t]*:[^\r\n]*',
    caseSensitive: false,
    multiLine: true,
  );

  final String name, phone, description;

  const _HotlineCard({
    required this.name,
    required this.phone,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final coverage = description
        .replaceAllMapped(_sourceNote, (match) => match.group(1)!.trimRight())
        .trim();
    return Card.outlined(
      margin: const EdgeInsets.only(bottom: AppSpacing.small),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.standard),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(name, style: text.titleMedium),
            if (coverage.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.minimal),
              Text(coverage, style: text.bodyMedium),
            ],
            const SizedBox(height: AppSpacing.small),
            OverflowBar(
              alignment: MainAxisAlignment.spaceBetween,
              spacing: AppSpacing.small,
              overflowSpacing: AppSpacing.minimal,
              overflowAlignment: OverflowBarAlignment.start,
              children: [
                SelectableText(phone, style: text.titleMedium),
                OutlinedButton.icon(
                  onPressed: () => dialAssistance(context, phone),
                  icon: const Icon(Icons.call_outlined),
                  label: Text('Call', semanticsLabel: 'Call $name'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

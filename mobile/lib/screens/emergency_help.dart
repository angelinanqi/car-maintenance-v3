import '../app_spacing.dart';
import 'package:flutter/material.dart';
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
          _contacts = contacts;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Could not open or refresh the shared directory. You can still call 999 or use your saved personal contact. Retry when connected.',
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
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Call for help')),
    body: ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: [
          EmergencyNotice(
            title: 'Injuries, fire or immediate danger?',
            message:
                'Contact Malaysia emergency services. Recording an incident can wait.',
            danger: true,
            action: OutlinedButton.icon(
              onPressed: () => dialAssistance(context, '999'),
              icon: const Icon(Icons.call),
              label: const Text('Call 999'),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Calls open your phone app and require phone service. Numbers remain visible for manual dialing.',
          ),
          const SizedBox(height: 24),
          const EmergencyLocationShare(),
          const SizedBox(height: 24),
          Text(
            'Roadside assistance',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          RoadsideContact(state: widget.state),
          for (final contact in _contacts.where(
            (c) =>
                (c['phone'] as String).replaceAll(RegExp(r'[^0-9]'), '') !=
                '999',
          ))
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    contact['name'] as String,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if ((contact['description'] as String? ?? '').isNotEmpty)
                    Text(contact['description'] as String),
                  SelectableText(contact['phone'] as String),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () =>
                        dialAssistance(context, contact['phone'] as String),
                    icon: const Icon(Icons.call_outlined),
                    label: Text('Call ${contact['name']}'),
                  ),
                ],
              ),
            ),
          if (_error != null) Text(_error!),
          if (_refreshing)
            const LinearProgressIndicator(
              semanticsLabel: 'Loading assistance contacts',
            ),
          TextButton.icon(
            onPressed: _refreshing ? null : () => _load(refresh: true),
            icon: const Icon(Icons.refresh),
            label: const Text('Refresh shared contacts'),
          ),
          const SizedBox(height: 24),
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

import 'package:flutter/material.dart';
import 'dart:io';
import 'package:url_launcher/url_launcher.dart';
import '../app_state.dart';
import '../data/content_repository.dart';
import '../data/accident_repository.dart';
import '../models/content.dart';
import 'accident_form.dart';
import 'profile.dart';
import 'incident_history.dart';
import 'nearby_assistance.dart';
import '../data/nearby_repository.dart';
import '../data/api_client.dart';
import 'dart:async';

class Emergency extends StatefulWidget {
  final AppState state;
  final ContentRepository? repository;
  const Emergency({super.key, required this.state, this.repository});
  @override
  State<Emergency> createState() => _EmergencyState();
}

class _EmergencyState extends State<Emergency> {
  late final ContentRepository _content;
  late AccidentRepository _accidents;
  String? _owner;
  Timer? _syncTimer;
  bool _syncing = false;
  bool _wasSignedIn = false;
  List<EmergencyGuide> _guides = [];
  bool _loading = true;
  String? _error;
  String? _photoWarning;
  List<Map<String, dynamic>> _contacts = [];
  String? _contactError;
  bool _refreshing = false;
  String? _savingId;
  ApiClient? _nearbyApi;
  @override
  void initState() {
    super.initState();
    _content = widget.repository ?? ContentRepository(widget.state.store);
    _owner = widget.state.emergencyOwnerId ?? widget.state.accountId;
    _accidents = AccidentRepository(
      widget.state.store,
      owner: _owner,
      remote: widget.state.repository,
    );
    _syncTimer = Timer.periodic(const Duration(seconds: 30), (_) => _sync());
    _sync();
    _wasSignedIn = widget.state.signedIn;
    if (_wasSignedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _offerGuestImport());
    }
    _load();
    _loadContacts();
    _recoverPhotos();
  }

  @override
  void didUpdateWidget(Emergency oldWidget) {
    super.didUpdateWidget(oldWidget);
    final owner = widget.state.emergencyOwnerId ?? widget.state.accountId;
    if (_owner != owner) {
      _owner = owner;
      _accidents = AccidentRepository(
        widget.state.store,
        owner: _owner,
        remote: widget.state.repository,
      );
      _sync();
    }
    if (!_wasSignedIn && widget.state.signedIn) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _offerGuestImport());
    }
    _wasSignedIn = widget.state.signedIn;
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    _nearbyApi?.close();
    super.dispose();
  }

  Future<void> _sync() async {
    if (_syncing || _owner == null) return;
    _syncing = true;
    try {
      await _accidents.sync();
    } catch (_) {
      /* Local records stay pending; retry while the app is running. */
    } finally {
      _syncing = false;
    }
  }

  Future<void> _offerGuestImport() async {
    if (!widget.state.signedIn) return;
    final owner = _owner;
    try {
      final guest = await AccidentRepository(widget.state.store).records();
      if (guest.isEmpty || !mounted || owner != _owner) return;
      final associate = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Keep your guest incident records?'),
          content: const Text(
            'Associate existing guest incident records with this account? Local copies are kept. If you have already enabled cloud backup for this account, their text will also be uploaded. Otherwise they stay on this device.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep as guest records'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Associate with my account'),
            ),
          ],
        ),
      );
      if (associate == true && mounted && owner == _owner) {
        await _accidents.importGuestRecords();
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _photoWarning =
              'Guest incidents could not be associated. Local files have been kept. $error',
        );
      }
    }
  }

  Future<void> _recoverPhotos() async {
    try {
      await _accidents.recoverLostPhotos();
    } catch (_) {
      if (mounted) {
        setState(
          () => _photoWarning =
              'Interrupted photo selection could not be recovered. Check your accident draft.',
        );
      }
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final guides = await _content.emergencyGuides();
      if (mounted) setState(() => _guides = guides);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Bundled emergency catalogue could not be opened. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
    if (mounted && _content.api != null) _refresh();
  }

  Future<void> _loadContacts({bool refresh = false}) async {
    try {
      final contacts = await _content.emergencyContacts(refresh: refresh);
      if (mounted) {
        setState(() {
          _contacts = contacts;
          _contactError = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _contactError =
              'Shared contacts could not be refreshed. Any saved directory is shown.',
        );
      }
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    _loadContacts(refresh: true);
    try {
      final guides = await _content.refreshEmergency();
      if (mounted) setState(() => _guides = guides);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _save(EmergencyGuide guide, {bool remove = false}) async {
    setState(() => _savingId = guide.id);
    try {
      List<EmergencyGuide> guides;
      if (remove) {
        await _content.removeOfflineGuide(guide.id);
        guides = await _content.refreshEmergency();
      } else {
        guides = await _content.saveOfflineGuide(guide.id);
      }
      if (mounted) {
        setState(() {
          _guides = guides;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not change the offline copy. $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _savingId = null);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Emergency'),
      backgroundColor: Colors.red[50],
      foregroundColor: Colors.red[900],
      actions: [
        IconButton(
          tooltip: 'Refresh emergency content',
          onPressed: _refreshing || _savingId != null ? null : _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card.outlined(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Nearby assistance',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const Text(
                  'Find workshop phone numbers or search for towing. Requires internet; no account needed.',
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () {
                    final api = _content.api ?? (_nearbyApi ??= ApiClient());
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) =>
                            NearbyAssistance(repository: NearbyRepository(api)),
                      ),
                    );
                  },
                  icon: const Icon(Icons.location_on_outlined),
                  label: const Text('Find nearby help · Online'),
                ),
              ],
            ),
          ),
        ),
        Card.outlined(
          color: Colors.red[50],
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              _guides.any((guide) => guide.available)
                  ? 'Essential safety guides are bundled and work offline immediately. Download published updates when connected. Calling requires phone service.'
                  : 'Reviewed emergency instructions have not been supplied yet. The offline catalogue below identifies the missing guides; it does not provide repair or safety instructions.',
            ),
          ),
        ),
        if (_photoWarning != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(_photoWarning!),
          ),
        if (_content.warning != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(_content.warning!),
          ),
        const SizedBox(height: 12),
        if (_refreshing) const LinearProgressIndicator(),
        Text(
          'Offline catalogue',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        if (_loading)
          const Center(child: CircularProgressIndicator())
        else if (_error != null)
          Column(
            children: [
              Text(_error!),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          )
        else
          ..._guides.map(
            (guide) => Card.outlined(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.warning_amber),
                    title: Text(guide.title),
                    subtitle: Text(
                      guide.available
                          ? '${guide.savedOffline ? 'Available offline' : 'Online guide'} • ${guide.bundled ? 'bundled safety guidance' : 'reviewed ${guide.reviewedAt}'}'
                          : 'Instructions unavailable • review required',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => EmergencyGuidePage(
                          guide: guide,
                          state: widget.state,
                          accidents: _accidents,
                        ),
                      ),
                    ),
                  ),
                  if (guide.available && !guide.legacy)
                    Padding(
                      padding: const EdgeInsets.only(
                        left: 16,
                        right: 16,
                        bottom: 8,
                      ),
                      child: Wrap(
                        spacing: 8,
                        children: [
                          TextButton.icon(
                            onPressed: _savingId == null
                                ? () => _save(guide)
                                : null,
                            icon: const Icon(Icons.download),
                            label: Text(
                              _savingId == guide.id
                                  ? 'Saving...'
                                  : guide.savedOffline
                                  ? (_content.hasUpdate(guide)
                                        ? 'Download updated guide'
                                        : 'Update offline copy')
                                  : 'Save offline',
                            ),
                          ),
                          if (guide.savedOffline)
                            TextButton(
                              onPressed: _savingId == null
                                  ? () => _save(guide, remove: true)
                                  : null,
                              child: const Text('Remove offline copy'),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 16),
        Text(
          'Shared emergency contacts',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (_contactError != null) Text(_contactError!),
        if (_contacts.isEmpty)
          const Text('No shared contacts are available yet.'),
        for (final contact in _contacts)
          Card.outlined(
            child: ListTile(
              title: Text(contact['name'] as String),
              subtitle: SelectableText(contact['phone'] as String),
              trailing: IconButton(
                tooltip: 'Open dialer',
                icon: const Icon(Icons.call),
                onPressed: () async {
                  final phone = contact['phone'] as String;
                  try {
                    if (!await launchUrl(
                      Uri(
                        scheme: 'tel',
                        path: phone.replaceAll(RegExp(r'[^+0-9]'), ''),
                      ),
                    )) {
                      throw StateError('No dialer');
                    }
                  } catch (_) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            'Could not open the phone app. Dial $phone manually.',
                          ),
                        ),
                      );
                    }
                  }
                },
              ),
            ),
          ),
        RoadsideContact(state: widget.state),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          icon: const Icon(Icons.assignment_outlined),
          label: const Text('Continue incident draft'),
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => AccidentForm(repository: _accidents),
            ),
          ),
        ),
        OutlinedButton.icon(
          icon: const Icon(Icons.add),
          label: const Text('Start new incident'),
          onPressed: () async {
            final confirmed = await showDialog<bool>(
              context: context,
              builder: (_) => AlertDialog(
                title: const Text('Start a new incident?'),
                content: const Text(
                  'The current draft will be kept in incident history before a new draft starts.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Cancel'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Continue'),
                  ),
                ],
              ),
            );
            if (confirmed != true) return;
            try {
              final old = await _accidents.load();
              if ((old['details'] as String).isNotEmpty ||
                  (old['photos'] as List).isNotEmpty ||
                  (old['name'] as String).isNotEmpty) {
                await _accidents.saveRecord({
                  ...old,
                  'id':
                      old['id'] ??
                      DateTime.now().microsecondsSinceEpoch.toString(),
                });
              }
              await _accidents.save({
                'version': 1,
                'id': DateTime.now().microsecondsSinceEpoch.toString(),
                'name': '',
                'plate': '',
                'phone': '',
                'insurer': '',
                'details': '',
                'photos': <String>[],
                'type': 'Road accident',
                'location': '',
                'occurredAt': DateTime.now().toIso8601String(),
              });
              if (context.mounted) {
                await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AccidentForm(repository: _accidents),
                  ),
                );
              }
            } catch (error) {
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Could not start a new incident. $error'),
                  ),
                );
              }
            }
          },
        ),
        OutlinedButton.icon(
          icon: const Icon(Icons.history),
          label: const Text('Incident records and backup'),
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => IncidentHistory(repository: _accidents),
            ),
          ),
        ),
      ],
    ),
  );
}

class EmergencyGuidePage extends StatefulWidget {
  final EmergencyGuide guide;
  final AppState state;
  final AccidentRepository accidents;
  const EmergencyGuidePage({
    super.key,
    required this.guide,
    required this.state,
    required this.accidents,
  });
  @override
  State<EmergencyGuidePage> createState() => _EmergencyGuidePageState();
}

class _EmergencyGuidePageState extends State<EmergencyGuidePage> {
  late final List<bool> _checked;
  @override
  void initState() {
    super.initState();
    _checked = List.filled(widget.guide.steps.length, false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.guide.title),
      backgroundColor: Colors.red[50],
    ),
    body: ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!widget.guide.available)
            const Card.outlined(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text(
                  'No reviewed instructions are available for this scenario. This notice is accessible offline.',
                ),
              ),
            )
          else ...[
            Text(
              '${widget.guide.savedOffline ? 'Available offline' : 'Online guide'} • ${widget.guide.bundled ? 'Sources checked ${widget.guide.reviewedAt}' : 'reviewed ${widget.guide.reviewedAt}'}',
            ),
            if (widget.guide.legacy && !widget.guide.bundled)
              const Text(
                'Legacy local copy; backend publication has not been confirmed.',
              ),
            Text('Source: ${widget.guide.source}'),
            if (widget.guide.bundled)
              const Text(
                'General safety guidance compiled from the linked sources. This is not a vehicle-specific repair procedure.',
              ),
            const SizedBox(height: 16),
            for (var i = 0; i < widget.guide.steps.length; i++)
              Card.outlined(
                child: Column(
                  children: [
                    CheckboxListTile(
                      title: Text('${i + 1}. ${widget.guide.steps[i].title}'),
                      subtitle: Text(widget.guide.steps[i].description),
                      value: _checked[i],
                      onChanged: (value) =>
                          setState(() => _checked[i] = value!),
                      controlAffinity: ListTileControlAffinity.leading,
                    ),
                    if (widget.guide.steps[i].localImagePath != null)
                      Image.file(
                        File(widget.guide.steps[i].localImagePath!),
                        errorBuilder: (_, _, _) => const Text(
                          'Saved image is unavailable. Download the guide again.',
                        ),
                      )
                    else if (widget.guide.steps[i].imageUrl.isNotEmpty)
                      Image.network(
                        widget.guide.steps[i].imageUrl,
                        errorBuilder: (_, _, _) =>
                            const Text('Image could not be loaded.'),
                      ),
                  ],
                ),
              ),
          ],
          const SizedBox(height: 16),
          RoadsideContact(state: widget.state),
          if (widget.guide.scenarioKey == 'minor-accident')
            OutlinedButton.icon(
              icon: const Icon(Icons.assignment),
              label: const Text('Collect accident information'),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => AccidentForm(repository: widget.accidents),
                ),
              ),
            ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Back to scenarios'),
          ),
        ],
      ),
    ),
  );
}

class RoadsideContact extends StatelessWidget {
  final AppState state;
  const RoadsideContact({super.key, required this.state});
  Future<void> _dial(BuildContext context) async {
    final number = state.contactPhone.replaceAll(RegExp(r'[^+0-9]'), '');
    try {
      if (!await launchUrl(Uri(scheme: 'tel', path: number))) {
        throw StateError('Phone handler unavailable');
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Could not open the phone app. Dial ${state.contactPhone} manually.',
            ),
          ),
        );
      }
    }
  }

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
              label: const Text('Open dialer'),
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

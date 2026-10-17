import 'dart:async';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/content_repository.dart';
import '../data/accident_repository.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';
import 'accident_form.dart';
import 'incident_history.dart';
import 'emergency_guide.dart';
import 'emergency_help.dart';
import 'emergency_downloads.dart';
export 'emergency_guide.dart' show EmergencyGuidePage;

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
  bool _hasGuestRecords = false;
  List<EmergencyGuide> _guides = [];
  bool _loading = true;
  String? _error;
  String? _photoWarning;
  bool _refreshing = false;
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
      _checkGuestRecords();
    }
    _load();
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
      _checkGuestRecords();
    }
    _wasSignedIn = widget.state.signedIn;
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
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

  Future<void> _checkGuestRecords() async {
    try {
      final guest = await AccidentRepository(widget.state.store).records();
      if (mounted) setState(() => _hasGuestRecords = guest.isNotEmpty);
    } catch (_) {
      // History provides an explicit retry without interrupting emergency help.
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
        if (mounted) setState(() => _hasGuestRecords = false);
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _photoWarning =
              'Guest incidents could not be associated. Local files have been kept. Please retry from Incident records.',
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
    try {
      final guides = await _content.emergencyGuides();
      if (mounted) {
        setState(() {
          _guides = guides;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Safety guides could not be opened. You can still call for help. Retry loading below.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
    if (mounted && _content.api != null) _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    _refreshing = true;
    try {
      final guides = await _content.refreshEmergency();
      if (mounted) setState(() => _guides = guides);
    } catch (_) {
      // Keep the local catalogue visible; downloads has an explicit retry action.
    } finally {
      _refreshing = false;
    }
  }

  void _help() => openEmergencyHelp(context, widget.state, _content);

  void _openGuide(EmergencyGuide guide) => Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => EmergencyGuidePage(
        guide: guide,
        state: widget.state,
        accidents: _accidents,
        content: _content,
      ),
    ),
  );

  Future<void> _downloads() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => EmergencyDownloads(content: _content, guides: _guides),
      ),
    );
    if (!mounted) return;
    // Reuse the catalogue already resolved by the downloads screen, including
    // online-only entries. This does not issue another network request.
    final guides = await _content.currentEmergencyCatalogue();
    if (mounted) setState(() => _guides = guides);
  }

  Future<void> _startIncident() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Start a new incident?'),
        content: const Text(
          'Your current draft will be kept in incident history before a new draft starts.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Start new incident'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      final old = await _accidents.load();
      if ([
            'details',
            'name',
            'plate',
            'phone',
            'insurer',
            'location',
          ].any((key) => (old[key] as String? ?? '').isNotEmpty) ||
          (old['photos'] as List).isNotEmpty) {
        await _accidents.saveRecord(old);
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
      if (mounted) {
        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => AccidentForm(repository: _accidents, onHelp: _help),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not start a new incident. Your saved files have been kept. Please retry.',
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final general = _guides
        .where((g) => g.scenarioKey == 'breakdown' && g.available)
        .firstOrNull;
    final accidents = _guides
        .where((g) => g.scenarioKey == 'minor-accident')
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Emergency')),
      bottomNavigationBar: EmergencyHelpBar(onHelp: _help),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const EmergencyNotice(
            title: 'First, protect yourself',
            message:
                'If you are driving, put the phone down. Use the app only once stopped in a safe place.',
          ),
          const SizedBox(height: 12),
          if (general != null) ...[
            // Reuse the resolved, reviewed general-breakdown content verbatim.
            // There is no universal safety content role in the current contract.
            if (general.safetyWarnings.isNotEmpty) ...[
              Text(general.safetyWarnings),
              const SizedBox(height: 12),
            ],
            for (final step in general.steps.take(2))
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      step.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(step.description),
                  ],
                ),
              ),
          ],
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            children: [
              const Text('Injuries, fire or immediate danger?'),
              TextButton.icon(
                onPressed: () => dialAssistance(context, '999'),
                icon: const Icon(Icons.call_outlined),
                label: const Text('Call 999'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            'Help for your situation',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          EmergencyAction(
            icon: Icons.car_repair_outlined,
            title: 'Car stopped or something wrong',
            subtitle: 'Get help without knowing the cause.',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => EmergencySituations(
                  guides: _guides
                      .where((g) => g.scenarioKey != 'minor-accident')
                      .toList(),
                  onOpen: _openGuide,
                  onHelp: _help,
                ),
              ),
            ),
          ),
          EmergencyAction(
            icon: Icons.car_crash_outlined,
            title: 'Minor road accident',
            subtitle:
                'Property damage with no injuries. Safety first, details later.',
            onTap: () {
              if (accidents.length == 1) {
                _openGuide(accidents.first);
              } else {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => EmergencySituations(
                      guides: accidents,
                      onOpen: _openGuide,
                      onHelp: _help,
                      accident: true,
                    ),
                  ),
                );
              }
            },
          ),
          if (_loading)
            const Text(
              'Opening saved safety guides. Calling help is available now.',
            ),
          if (_error != null) ...[
            Text(_error!),
            TextButton(
              onPressed: _load,
              child: const Text('Retry loading guides'),
            ),
          ],
          if (_content.warning != null)
            const Text(
              'Some content could not be updated. Available local guidance is kept. Open Offline guides to retry.',
            ),
          const SizedBox(height: 24),
          Text(
            'When you can record details',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          const Text(
            'Save what you know on this device. You can finish later.',
          ),
          const SizedBox(height: 12),
          if (_photoWarning != null) Text(_photoWarning!),
          if (_hasGuestRecords && widget.state.signedIn)
            TextButton(
              onPressed: _offerGuestImport,
              child: const Text('Associate guest incident records'),
            ),
          OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    AccidentForm(repository: _accidents, onHelp: _help),
              ),
            ),
            icon: const Icon(Icons.edit_note),
            label: const Text('Continue incident draft'),
          ),
          TextButton.icon(
            onPressed: _startIncident,
            icon: const Icon(Icons.add),
            label: const Text('Start new incident'),
          ),
          EmergencyAction(
            icon: Icons.history,
            title: 'Incident records and backup',
            subtitle:
                'Review saved records. Optional account backup covers text only.',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    IncidentHistory(repository: _accidents, onHelp: _help),
              ),
            ),
          ),
          TextButton.icon(
            onPressed: _downloads,
            icon: const Icon(Icons.download_outlined),
            label: const Text('Offline guides'),
          ),
        ],
      ),
    );
  }
}

class EmergencySituations extends StatelessWidget {
  final List<EmergencyGuide> guides;
  final ValueChanged<EmergencyGuide> onOpen;
  final VoidCallback onHelp;
  final bool accident;
  const EmergencySituations({
    super.key,
    required this.guides,
    required this.onOpen,
    required this.onHelp,
    this.accident = false,
  });
  @override
  Widget build(BuildContext context) {
    final unknown = guides.where((g) => g.scenarioKey == 'breakdown').toList();
    final specific = guides.where((g) => g.scenarioKey != 'breakdown').toList();
    return Scaffold(
      appBar: AppBar(
        title: Text(accident ? 'Minor road accident' : 'Car trouble'),
      ),
      bottomNavigationBar: EmergencyHelpBar(onHelp: onHelp),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            accident ? 'Safety comes first' : 'You do not need to diagnose it',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            accident
                ? 'For injuries, fire or immediate danger, contact emergency services. The incident form is for minor property damage.'
                : 'Choose what you notice, or use general breakdown guidance. You can call for help at any time.',
          ),
          const SizedBox(height: 24),
          if (!accident) ...[
            if (unknown.isEmpty)
              EmergencyAction(
                icon: Icons.call_outlined,
                title: "I'm not sure what's wrong",
                subtitle: 'Contact assistance without choosing a guide.',
                onTap: onHelp,
              ),
            for (final guide in unknown)
              EmergencyAction(
                icon: Icons.help_outline,
                title: "I'm not sure what's wrong",
                subtitle: guide.title,
                onTap: () => onOpen(guide),
              ),
          ],
          if (specific.isNotEmpty)
            Text(
              accident ? 'Available guidance' : 'Or choose a situation',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          const SizedBox(height: 12),
          for (final guide in specific)
            EmergencyAction(
              icon: Icons.format_list_numbered,
              title: guide.title,
              subtitle: !guide.available
                  ? 'Reviewed instructions unavailable. Call for help.'
                  : [
                      if (guide.category.isNotEmpty) guide.category,
                      guide.savedOffline
                          ? 'Guidance available offline'
                          : 'Online guide',
                    ].join(' · '),
              onTap: () => onOpen(guide),
            ),
          if (guides.isEmpty)
            const Text(
              'No reviewed guides are available here yet. Call for help below; you do not need to choose a situation.',
            ),
        ],
      ),
    );
  }
}

import '../app_spacing.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';
import '../data/api_client.dart';
import '../data/nearby_repository.dart';
import 'nearby_assistance.dart';
import '../data/content_repository.dart';
import '../data/accident_repository.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';
import 'accident_reports.dart';
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

class _EmergencyState extends State<Emergency> with WidgetsBindingObserver {
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
  ApiClient? _nearbyApi;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    WidgetsBinding.instance.removeObserver(this);
    _syncTimer?.cancel();
    _nearbyApi?.close();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh();
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
      await _accidents.store.cleanupPhotos();
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

  void _nearby() => Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => NearbyAssistance(
        repository: NearbyRepository(
          _content.api ?? (_nearbyApi ??= ApiClient()),
        ),
      ),
    ),
  );

  void _openAccidentForm() => Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => AccidentReports(repository: _accidents, onHelp: _help),
    ),
  );

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

  @override
  Widget build(BuildContext context) {
    final general = _guides
        .where((g) => g.isGeneralBreakdown && g.available)
        .firstOrNull;
    final offline =
        _guides.isNotEmpty &&
        _guides.where((g) => g.available).isNotEmpty &&
        _guides.where((g) => g.available).every((g) => g.savedOffline);
    void situations(bool accident) => Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => EmergencySituations(
          guides: _guides
              .where((g) => accident ? g.isAccident : !g.isAccident)
              .toList(),
          onOpen: _openGuide,
          onHelp: _help,
          accident: accident,
          onRecordAccident: _openAccidentForm,
          loadFailed: _content.warning != null,
        ),
      ),
    );
    return Scaffold(
      appBar: AppBar(
        title: const Text('Roadside help'),
        actions: [
          Center(
            child: StatusPill(
              offline ? 'Works offline' : 'Offline guides',
              color: AppColors.success,
              foreground: AppColors.successInk,
            ),
          ),
          PopupMenuButton<String>(
            tooltip: 'Roadside options',
            onSelected: (value) {
              if (value == 'downloads') _downloads();
              if (value == 'drafts') _openAccidentForm();
              if (value == 'import') _offerGuestImport();
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'downloads',
                child: Text('Manage offline guides'),
              ),
              const PopupMenuItem(
                value: 'drafts',
                child: Text('Accident forms & drafts'),
              ),
              if (_hasGuestRecords && widget.state.signedIn)
                const PopupMenuItem(
                  value: 'import',
                  child: Text('Associate guest records'),
                ),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.screen,
          0,
          AppSpacing.screen,
          24,
        ),
        children: [
          SurfaceCard(
            borderColor: const Color(0xFFF1B3AD),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppColors.dangerSurface,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.health_and_safety_outlined,
                        color: AppColors.danger,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Do this first',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            'Stay calm. Take it one step at a time.',
                            style: TextStyle(color: AppColors.muted),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                for (final step in [
                  (1, 'Turn on hazard lights'),
                  (2, 'Move to a safe place if you can'),
                  (3, 'Everyone out, away from traffic'),
                ])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 26,
                          height: 26,
                          alignment: Alignment.center,
                          decoration: const BoxDecoration(
                            color: AppColors.dangerSurface,
                            shape: BoxShape.circle,
                          ),
                          child: Text(
                            '${step.$1}',
                            style: const TextStyle(
                              color: AppColors.danger,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(step.$2),
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 4),
                const Text(
                  'Immediate danger?',
                  style: TextStyle(
                    color: AppColors.danger,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () => dialAssistance(context, '999'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.danger,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 54),
                    textStyle: const TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  icon: const Icon(Icons.call_outlined, size: 24),
                  label: const Text('Call 999'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            'What’s happening?',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.standard),
          Row(
            children: [
              for (final accident in [false, true])
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(right: accident ? 0 : 8),
                    child: SurfaceCard(
                      onTap: () => situations(accident),
                      child: Column(
                        children: [
                          Icon(
                            accident
                                ? Icons.warning_amber_outlined
                                : Icons.directions_car_outlined,
                            color: AppColors.danger,
                            size: 30,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            accident ? 'Minor incident' : 'Breakdown',
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.accent,
              foregroundColor: AppColors.ink,
            ),
            onPressed: () {
              if (general != null) {
                _openGuide(general);
              } else {
                _help();
              }
            },
            child: const Text('I don’t know what to do'),
          ),
          const SizedBox(height: AppSpacing.standard),
          ActionRow(
            icon: Icons.location_on_outlined,
            title: 'Nearby help',
            subtitle: 'Workshops, tyre shops and towing in Maps',
            onTap: _nearby,
          ),
          ActionRow(
            icon: Icons.chat_bubble_outline,
            title: 'Saved incidents',
            subtitle: 'Your records and photos',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    IncidentHistory(repository: _accidents, onHelp: _help),
              ),
            ),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.danger,
              foregroundColor: Colors.white,
            ),
            onPressed: _help,
            child: const Text('Call emergency contact'),
          ),
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(12),
              child: LinearProgressIndicator(),
            ),
          if (_error != null)
            SurfaceCard(
              child: Column(
                children: [
                  Text(_error!),
                  TextButton(
                    onPressed: _load,
                    child: const Text('Retry loading guides'),
                  ),
                ],
              ),
            ),
          if (_photoWarning != null) Text(_photoWarning!),
          if (_content.warning != null)
            TextButton(
              onPressed: _downloads,
              child: const Text(
                'Some guides could not update. Open offline guides.',
              ),
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
  final VoidCallback? onRecordAccident;
  final bool loadFailed;
  const EmergencySituations({
    super.key,
    required this.guides,
    required this.onOpen,
    required this.onHelp,
    this.accident = false,
    this.onRecordAccident,
    this.loadFailed = false,
  });
  @override
  Widget build(BuildContext context) {
    final unknown = guides.where((g) => g.isGeneralBreakdown).toList();
    final specific = guides.where((g) => !g.isGeneralBreakdown).toList();
    return Scaffold(
      appBar: AppBar(
        title: Text(accident ? 'Minor road accident' : 'Car trouble'),
      ),
      bottomNavigationBar: EmergencyHelpBar(onHelp: onHelp),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
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
          if (accident && onRecordAccident != null) ...[
            FilledButton.icon(
              onPressed: onRecordAccident,
              icon: const Icon(Icons.assignment_outlined),
              label: const Text('Accident forms and saved drafts'),
            ),
            const SizedBox(height: 8),
            const Text(
              'Start a new accident form, continue a saved draft, or review past forms. Available offline.',
            ),
            const SizedBox(height: 24),
          ],
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
            Text(
              loadFailed
                  ? 'Guides could not be loaded. Go back and retry, or call for help below.'
                  : accident
                  ? 'No reviewed accident guides are available yet. You can still record an accident or call for help.'
                  : 'No reviewed guides are available here yet. Call for help below; you do not need to choose a situation.',
            ),
        ],
      ),
    );
  }
}

import '../app_spacing.dart';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/accident_repository.dart';
import '../data/content_repository.dart';
import '../data/local_store.dart';
import '../data/api_client.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';
import '../widgets/content_media.dart';
import '../widgets/emergency_offline_status.dart';
import '../data/emergency_progress.dart';
import 'emergency_safety.dart';
import 'emergency_help.dart';
import 'accident_form.dart';
import 'accident_reports.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';

class EmergencyGuidePage extends StatefulWidget {
  final EmergencyGuide guide;
  final AppState state;
  final AccidentRepository accidents;
  final ContentRepository? content;
  const EmergencyGuidePage({
    super.key,
    required this.guide,
    required this.state,
    required this.accidents,
    this.content,
  });
  @override
  State<EmergencyGuidePage> createState() => _EmergencyGuidePageState();
}

class _EmergencyGuidePageState extends State<EmergencyGuidePage> {
  final _images = <String, Future<Uint8List>>{};
  late final EmergencyProgressStore _progress;
  final _scroll = ScrollController();
  Set<String> _completed = {};
  int _current = 0;
  bool _safe = false, _loading = true, _overview = false, _largeText = false;
  bool _saved = false, _finishing = false;
  bool _saveFailed = false;
  String? _notice;
  int _saveRevision = 0;

  @override
  void initState() {
    super.initState();
    _progress = EmergencyProgressStore(widget.state.store);
    _restore();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _restore() async {
    try {
      final saved = await _progress.forGuide(widget.guide.id);
      if (!mounted) return;
      if (saved != null && saved.matches(widget.guide)) {
        _current = widget.guide.steps.indexWhere((s) => s.id == saved.stepId);
        _completed = saved.completed.intersection(
          widget.guide.steps.map((s) => s.id).toSet(),
        );
        _overview = true;
        _saved = true;
      } else if (saved != null) {
        _notice =
            'This guide has changed. Start from the beginning and review the current instructions.';
      }
    } catch (_) {
      _notice =
          'Saved progress could not be opened. You can still use this guide.';
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        if (_safe) _save();
      }
    }
  }

  Future<bool> _save() async {
    if (!widget.guide.available || _loading || _finishing) return false;
    final revision = ++_saveRevision;
    final snapshot = EmergencyProgress(
      guideId: widget.guide.id,
      revision: EmergencyProgress.fingerprint(widget.guide),
      stepId: widget.guide.steps[_current].id,
      completed: {..._completed},
    );
    if (mounted) setState(() => _saved = false);
    try {
      await _progress.save(snapshot);
      if (mounted && revision == _saveRevision)
        setState(() {
          _saved = true;
          if (_saveFailed) _notice = null;
          _saveFailed = false;
        });
      return true;
    } catch (_) {
      if (mounted && revision == _saveRevision)
        setState(() {
          _saved = false;
          _saveFailed = true;
          _notice =
              'Progress could not be saved. Keep this guide open or retry saving.';
        });
      return false;
    }
  }

  void _go(int step) {
    if (_finishing) return;
    setState(() {
      _current = step;
      _overview = false;
    });
    if (_scroll.hasClients) _scroll.jumpTo(0);
    _save();
  }

  void _help() => openEmergencyHelp(
    context,
    widget.state,
    widget.content ?? ContentRepository(widget.state.store),
  );

  void _record() => Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => AccidentForm(
        repository: widget.accidents,
        incidentType: widget.guide.title,
        onHelp: _help,
      ),
    ),
  );

  Future<void> _finish() async {
    if (_finishing) return;
    setState(() => _finishing = true);
    ++_saveRevision;
    // Wait for pending checkpoints before removing this completed session.
    try {
      await _progress.clear(widget.guide.id);
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted)
        setState(() {
          _finishing = false;
          _notice =
              'Could not close saved progress. You can exit and retry later.';
        });
    }
  }

  Future<Uint8List> _readImage(EmergencyStep step) async {
    Uint8List bytes;
    if (step.localImagePath != null) {
      final file = File(step.localImagePath!);
      if (await file.length() > LocalStore.maxPhotoBytes)
        throw const FormatException('Image too large');
      bytes = await file.readAsBytes();
    } else {
      final api = widget.content?.api;
      if (api == null) throw const ApiException('Image unavailable');
      bytes = await api.imageBytes(step.imageUrl);
    }
    await LocalStore.validateImage(bytes);
    return bytes;
  }

  Widget _image(EmergencyStep step) {
    const unavailable = Padding(
      padding: EdgeInsets.all(16),
      child: Text(
        'Illustration unavailable. Use the written instructions above. Download the guide again when connected.',
      ),
    );
    // The current image contract has no alt text. Do not fabricate a description.
    final image = FutureBuilder<Uint8List>(
      future: _images.putIfAbsent(
        step.localImagePath ?? step.imageUrl,
        () => _readImage(step),
      ),
      builder: (_, snapshot) {
        if (snapshot.hasError) return unavailable;
        if (!snapshot.hasData)
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Loading illustration. You can continue with the written instructions.',
            ),
          );
        return Image.memory(
          snapshot.data!,
          fit: BoxFit.contain,
          errorBuilder: (_, _, _) => unavailable,
        );
      },
    );
    return Semantics(
      label: 'Supporting illustration for ${step.title}',
      image: true,
      child: ExcludeSemantics(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 360),
          child: image,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!_safe)
      return EmergencySafetyCheck(
        onHelp: _help,
        onContinue: () {
          setState(() => _safe = true);
          if (!_loading) _save();
        },
      );
    final guide = widget.guide;
    final step = guide.steps.isEmpty ? null : guide.steps[_current];
    final scaler = MediaQuery.textScalerOf(context);
    return Scaffold(
      appBar: AppBar(title: Text(guide.title)),
      bottomNavigationBar: EmergencyHelpBar(
        onHelp: _help,
        showEmergencyCall: true,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : MediaQuery(
              data: MediaQuery.of(context).copyWith(
                textScaler: _largeText
                    ? TextScaler.linear(scaler.scale(16) / 16 * 1.25)
                    : scaler,
              ),
              child: ListView(
                controller: _scroll,
                padding: const EdgeInsets.all(AppSpacing.screen),
                children: [
                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      StatusPill(
                        guide.savedOffline
                            ? 'Available offline'
                            : 'Online guide',
                        color: AppColors.success,
                        foreground: AppColors.successInk,
                      ),
                      OutlinedButton(
                        onPressed: () =>
                            setState(() => _largeText = !_largeText),
                        child: Text(
                          _largeText ? 'Text size A−' : 'Text size A+',
                        ),
                      ),
                    ],
                  ),
                  if (_notice != null) ...[
                    const SizedBox(height: 12),
                    Text(_notice!),
                    if (!_saved && guide.available)
                      TextButton(
                        onPressed: _save,
                        child: const Text('Retry saving progress'),
                      ),
                  ],
                  if (guide.description.isNotEmpty &&
                      !_overview &&
                      _current == 0) ...[
                    const SizedBox(height: 12),
                    Text(guide.description),
                  ],
                  if (!guide.available || step == null) ...[
                    const SizedBox(height: 16),
                    const EmergencyNotice(
                      title: 'Instructions unavailable',
                      message:
                          'No reviewed instructions are available for this situation. You can still call for help below.',
                    ),
                  ] else ...[
                    if (guide.isAccident) ...[
                      const SizedBox(height: 16),
                      const EmergencyNotice(
                        title: 'Safety before recording details',
                        danger: true,
                        message:
                            'This incident flow is for minor property damage with no injuries. For injuries, fire or immediate danger, call emergency services.',
                      ),
                    ],
                    if (guide.safetyWarnings.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      EmergencyNotice(
                        title: 'Safety warnings',
                        message: guide.safetyWarnings,
                        danger: true,
                      ),
                    ],
                    const SizedBox(height: 16),
                    if (_overview) ...[
                      SurfaceCard(
                        color: AppColors.accent,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              'You stopped at step ${_current + 1}',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            Text(
                              _saved
                                  ? 'Saved on this phone'
                                  : 'Progress not yet saved',
                            ),
                            const SizedBox(height: 12),
                            FilledButton(
                              onPressed: () => _go(_current),
                              child: Text('Resume step ${_current + 1}'),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '${_completed.length} of ${guide.steps.length} steps marked',
                      ),
                      const SizedBox(height: 12),
                      for (var i = 0; i < guide.steps.length; i++)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Material(
                            color: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: BorderSide(
                                color: i == _current
                                    ? AppColors.ink
                                    : AppColors.border,
                                width: i == _current ? 2 : 1,
                              ),
                            ),
                            child: ListTile(
                              leading: Checkbox(
                                value: _completed.contains(guide.steps[i].id),
                                onChanged: (value) {
                                  setState(() {
                                    if (value == true) {
                                      _completed.add(guide.steps[i].id);
                                    } else {
                                      _completed.remove(guide.steps[i].id);
                                    }
                                  });
                                  _save();
                                },
                              ),
                              title: Text('${i + 1}. ${guide.steps[i].title}'),
                              subtitle: i == _current
                                  ? Text(guide.steps[i].description)
                                  : null,
                              onTap: () => _go(i),
                            ),
                          ),
                        ),
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _completed.clear();
                            _current = 0;
                            _overview = false;
                            _safe = false;
                          });
                          _save();
                        },
                        child: const Text('Start again'),
                      ),
                    ] else ...[
                      Semantics(
                        label: 'Step ${_current + 1} of ${guide.steps.length}',
                        child: ExcludeSemantics(
                          child: Row(
                            children: [
                              for (var i = 0; i < guide.steps.length; i++)
                                Expanded(
                                  child: Padding(
                                    padding: EdgeInsets.only(
                                      right: i == guide.steps.length - 1
                                          ? 0
                                          : 4,
                                    ),
                                    child: Container(
                                      height: 7,
                                      decoration: BoxDecoration(
                                        color: i <= _current
                                            ? AppColors.accent
                                            : AppColors.border,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Step ${_current + 1} of ${guide.steps.length}',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        step.title,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        step.description,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      ContentMediaList(
                        key: ValueKey(step.id),
                        items: step.media,
                        imageBuilder: (item) => _image(
                          EmergencyStep(
                            id: item['id'] as String,
                            title: item['title'] as String,
                            description: item['description'] as String,
                            imageUrl: item['url'] as String,
                            localImagePath: item['localImagePath'] as String?,
                          ),
                        ),
                      ),
                      if (step.localImagePath != null ||
                          step.imageUrl.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        _image(step),
                      ],
                      const SizedBox(height: 16),
                      const OutlinedButton(
                        onPressed: null,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.volume_up_outlined),
                            SizedBox(width: 8),
                            Flexible(child: Text('Read aloud · Coming soon')),
                          ],
                        ),
                      ),
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        controlAffinity: ListTileControlAffinity.leading,
                        title: const Text('Mark this step'),
                        value: _completed.contains(step.id),
                        onChanged: (value) {
                          setState(() {
                            if (value == true) {
                              _completed.add(step.id);
                            } else {
                              _completed.remove(step.id);
                            }
                          });
                          _save();
                        },
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: _current > 0
                                  ? () => _go(_current - 1)
                                  : () => setState(() => _safe = false),
                              child: const Text('Back'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            flex: 2,
                            child: FilledButton(
                              style: FilledButton.styleFrom(
                                backgroundColor: AppColors.accent,
                                foregroundColor: AppColors.ink,
                              ),
                              onPressed: _finishing
                                  ? null
                                  : (_current < guide.steps.length - 1
                                        ? () => _go(_current + 1)
                                        : _finish),
                              child: Text(
                                _current < guide.steps.length - 1
                                    ? 'Next step'
                                    : 'Finish guide',
                              ),
                            ),
                          ),
                        ],
                      ),
                      TextButton(
                        onPressed: () => setState(() => _overview = true),
                        child: const Text('All steps / jump to a step'),
                      ),
                      Text(
                        _saved
                            ? 'Progress saved on this phone.'
                            : 'Progress not yet saved.',
                      ),
                    ],
                    const SizedBox(height: 8),
                    const Text(
                      'Marked steps do not confirm it is safe to drive.',
                    ),
                    const SizedBox(height: 16),
                    if (guide.isAccident)
                      TextButton(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => AccidentReports(
                              repository: widget.accidents,
                              onHelp: _help,
                            ),
                          ),
                        ),
                        child: const Text('Accident forms and saved drafts'),
                      ),
                    EmergencyOfflineStatus(
                      guide: guide,
                      store: widget.state.store,
                    ),
                    ExpansionTile(
                      title: const Text('About this guide and sources'),
                      childrenPadding: const EdgeInsets.all(16),
                      expandedCrossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (guide.description.isNotEmpty)
                          Text(guide.description),
                        Text(
                          guide.savedOffline
                              ? 'Written guide saved on this device.'
                              : 'Save this guide from Offline guides before you need it.',
                        ),
                        Text('Reviewed ${guide.reviewedAt}'),
                        if (guide.bundled)
                          const Text(
                            'General safety guidance. This is not a vehicle-specific repair procedure.',
                          ),
                        if (guide.legacy && !guide.bundled)
                          const Text(
                            'Legacy local copy; backend publication has not been confirmed.',
                          ),
                        SelectableText('Source: ${guide.source}'),
                      ],
                    ),
                  ],
                  OutlinedButton.icon(
                    onPressed: _record,
                    icon: const Icon(Icons.assignment_outlined),
                    label: const Text('Save incident'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Back to scenarios'),
                  ),
                ],
              ),
            ),
    );
  }
}

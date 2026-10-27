import 'package:flutter/material.dart';
import 'package:html/parser.dart' as html;
import 'package:url_launcher/url_launcher.dart';
import '../app_state.dart';
import '../data/content_repository.dart';
import '../models/content.dart';
import '../widgets/guide_content.dart';
import '../widgets/module_widgets.dart';
import '../widgets/vehicle_selector.dart';

class Learn extends StatefulWidget {
  final AppState state;
  final void Function(String) onAsk;
  final ContentRepository? repository;
  final void Function(Map<String, dynamic>)? onAskContext;
  final void Function(String)? onMaintenanceItem;
  final String? requestedLessonId;
  final int lessonRequestNumber;
  const Learn({
    super.key,
    required this.state,
    required this.onAsk,
    this.repository,
    this.onAskContext,
    this.onMaintenanceItem,
    this.requestedLessonId,
    this.lessonRequestNumber = 0,
  });
  @override
  State<Learn> createState() => _LearnState();
}

class _LearnState extends State<Learn> {
  late final ContentRepository _repository;
  List<LearningTrack> _tracks = [];
  List<OwnerManual> _manuals = [];
  String _scope = 'general';
  bool _loading = true, _manualLoading = true, _showManuals = false;
  String? _error, _manualError, _openingManual;
  int _manualRequest = 0;
  String? _openingLesson;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? ContentRepository(widget.state.store);
    _scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    widget.state.addListener(_stateChanged);
    _load();
    _loadManuals();
    if (widget.requestedLessonId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _related(widget.requestedLessonId!);
      });
    }
  }

  void _stateChanged() {
    if (!mounted) return;
    final scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    if (scope != _scope) {
      _scope = scope;
      _manuals = [];
      _loadManuals();
    }
    setState(() {});
  }

  @override
  void didUpdateWidget(covariant Learn oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state != oldWidget.state) {
      oldWidget.state.removeListener(_stateChanged);
      widget.state.addListener(_stateChanged);
      _stateChanged();
    }
    if (widget.lessonRequestNumber != oldWidget.lessonRequestNumber &&
        widget.requestedLessonId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _related(widget.requestedLessonId!);
      });
    }
  }

  @override
  void dispose() {
    widget.state.removeListener(_stateChanged);
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final tracks = await _repository.learningTracks();
      if (mounted) setState(() => _tracks = tracks);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Check your connection and try again.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadManuals() async {
    final request = ++_manualRequest;
    setState(() {
      _manualLoading = true;
      _manualError = null;
    });
    try {
      final manuals = await _repository.manuals(_scope);
      if (mounted && request == _manualRequest) {
        setState(() => _manuals = manuals);
      }
    } catch (_) {
      if (mounted && request == _manualRequest) {
        setState(() => _manualError = 'Check your connection and try again.');
      }
    } finally {
      if (mounted && request == _manualRequest) {
        setState(() => _manualLoading = false);
      }
    }
  }

  Future<void> _openManual(OwnerManual manual) async {
    setState(() => _openingManual = manual.id);
    final request = _manualRequest;
    try {
      if (manual.sourceType == 'pdf') {
        if (!await launchUrl(
          _repository.manualUrl(manual),
          mode: LaunchMode.externalApplication,
        )) {
          throw StateError('No PDF handler');
        }
      } else {
        final text = await _repository.manualText(manual);
        if (!mounted || request != _manualRequest) return;
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => Scaffold(
              appBar: AppBar(title: const Text('Owner manual')),
              body: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: SelectionArea(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        manual.name,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 24),
                      Text(text, style: Theme.of(context).textTheme.bodyLarge),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not open this manual. Check your connection. PDFs also need a PDF viewer.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _openingManual = null);
    }
  }

  void _read(Lesson lesson) {
    Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => _LessonReader(
          state: widget.state,
          lesson: lesson,
          repository: _repository,
          tracks: _tracks,
          onAsk: widget.onAsk,
          onAskContext: widget.onAskContext,
          onMaintenanceItem: widget.onMaintenanceItem,
        ),
      ),
    );
  }

  Future<void> _related(String id) async {
    if (_openingLesson != null) return;
    setState(() => _openingLesson = id);
    try {
      final lesson = await _repository.lesson(id);
      if (mounted) _read(lesson);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
              'This guide could not be opened. It may no longer be published.',
            ),
            action: SnackBarAction(
              label: 'Retry',
              onPressed: () => _related(id),
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _openingLesson = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final lessons = _tracks.expand((t) => t.lessons).toList();
    final completed = lessons
        .where((l) => widget.state.completedLessons.contains(l.id))
        .length;
    final rows = <Widget>[
      Text(
        'Know your car better.',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 8),
      const Text('Practical guides, at your own pace.'),
      const SizedBox(height: 20),
      SegmentedButton<bool>(
        segments: const [
          ButtonSegment(
            value: false,
            label: Text('Guides'),
            icon: Icon(Icons.menu_book_outlined),
          ),
          ButtonSegment(
            value: true,
            label: Text('Manuals'),
            icon: Icon(Icons.description_outlined),
          ),
        ],
        selected: {_showManuals},
        onSelectionChanged: (v) => setState(() => _showManuals = v.first),
      ),
      const SizedBox(height: 20),
    ];
    if (_showManuals) {
      rows.addAll([
        Text('Owner manuals', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          widget.state.selectedVehicle == null
              ? 'General reference documents. Select a registered vehicle to see its manuals too.'
              : 'Manuals for ${widget.state.selectedVehicle!.name}, plus general reference documents.',
        ),
        if (widget.state.vehicles.isNotEmpty)
          VehicleSelector(state: widget.state),
        const SizedBox(height: 8),
        if (_manualLoading)
          const LinearProgressIndicator(semanticsLabel: 'Loading manuals'),
        if (_manualError != null)
          ModuleMessage(
            title: 'Manuals unavailable',
            message: _manualError!,
            action: OutlinedButton.icon(
              onPressed: _loadManuals,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ),
        if (!_manualLoading && _manualError == null && _manuals.isEmpty)
          const ModuleMessage(
            icon: Icons.description_outlined,
            title: 'No manuals available yet',
            message:
                'Published manuals for this selection will appear here. Learning guides are available in Guides.',
          ),
        for (final manual in _manuals)
          ListTile(
            contentPadding: const EdgeInsets.symmetric(vertical: 8),
            leading: const Icon(Icons.description_outlined),
            title: Text(manual.name),
            subtitle: Text(
              '${manual.sourceType.toUpperCase()} · ${(manual.sizeBytes / 1024).ceil()} KB${manual.vehicleIndependent ? ' · General' : ''}\n${manual.sourceType == 'pdf' ? 'Opens in your PDF viewer' : 'Read in the app'}',
            ),
            trailing: _openingManual == manual.id
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(),
                  )
                : const Icon(Icons.chevron_right),
            onTap: _openingManual == null ? () => _openManual(manual) : null,
          ),
      ]);
    } else {
      rows.addAll([
        if (widget.state.signedIn && lessons.isNotEmpty) ...[
          Text(
            '$completed of ${lessons.length} guides completed',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: completed / lessons.length,
            semanticsLabel:
                'Learning progress: $completed of ${lessons.length} guides completed',
          ),
          const SizedBox(height: 8),
        ],
        if (!widget.state.signedIn)
          const Text('Read any guide. Sign in to save your progress.'),
        if (_loading || _openingLesson != null)
          const LinearProgressIndicator(
            semanticsLabel: 'Loading learning guides',
          ),
        if (_error != null)
          ModuleMessage(
            title: 'Learning guides unavailable',
            message: _error!,
            action: OutlinedButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ),
        if (!_loading && _error == null && lessons.isEmpty)
          const ModuleMessage(
            icon: Icons.menu_book_outlined,
            title: 'No learning guides yet',
            message: 'New guides will appear here when available.',
          ),
        for (final track in _tracks.where((t) => t.lessons.isNotEmpty))
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Material(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(16),
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                key: PageStorageKey('learn-${track.title}'),
                initiallyExpanded: track == _tracks.first,
                tilePadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 6,
                ),
                childrenPadding: const EdgeInsets.symmetric(horizontal: 16),
                title: Text(
                  track.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                subtitle: Text(
                  '${track.lessons.length} ${track.lessons.length == 1 ? 'guide' : 'guides'}',
                ),
                children: [
                  if (track.subtitle.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text(track.subtitle),
                      ),
                    ),
                  for (final lesson in track.lessons) ...[
                    ListTile(
                      contentPadding: const EdgeInsets.symmetric(vertical: 8),
                      title: Text(
                        lesson.title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (lesson.introduction.isNotEmpty)
                              Text(
                                lesson.introduction,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            if (lesson.readingMinutes != null ||
                                widget.state.completedLessons.contains(
                                  lesson.id,
                                )) ...[
                              const SizedBox(height: 6),
                              Text(
                                [
                                  if (lesson.readingMinutes != null)
                                    '${lesson.readingMinutes} min read',
                                  if (widget.state.completedLessons.contains(
                                    lesson.id,
                                  ))
                                    'Completed',
                                ].join(' · '),
                                style: Theme.of(context).textTheme.labelMedium,
                              ),
                            ],
                          ],
                        ),
                      ),
                      trailing: Icon(
                        widget.state.completedLessons.contains(lesson.id)
                            ? Icons.check_circle_outline
                            : Icons.chevron_right,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      onTap: () => _read(lesson),
                    ),
                    const SizedBox(height: 4),
                  ],
                ],
              ),
            ),
          ),
      ]);
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Learn'),
        actions: [
          IconButton(
            tooltip: _showManuals
                ? 'Refresh manuals'
                : 'Refresh learning guides',
            onPressed: (_showManuals ? _manualLoading : _loading)
                ? null
                : (_showManuals ? _loadManuals : _load),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _showManuals ? _loadManuals : _load,
        child: ListView.builder(
          key: ValueKey(_showManuals),
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
          itemCount: rows.length,
          itemBuilder: (_, index) => rows[index],
        ),
      ),
    );
  }
}

class _LessonReader extends StatefulWidget {
  final AppState state;
  final Lesson lesson;
  final ContentRepository repository;
  final List<LearningTrack> tracks;
  final void Function(String) onAsk;
  final void Function(Map<String, dynamic>)? onAskContext;
  final void Function(String)? onMaintenanceItem;
  const _LessonReader({
    required this.state,
    required this.lesson,
    required this.repository,
    required this.tracks,
    required this.onAsk,
    this.onAskContext,
    this.onMaintenanceItem,
  });
  @override
  State<_LessonReader> createState() => _LessonReaderState();
}

class _LessonReaderState extends State<_LessonReader> {
  bool _busy = false;
  String? _error;
  String? _opening;

  Future<void> _related(String id) async {
    setState(() {
      _opening = id;
      _error = null;
    });
    try {
      final lesson = await widget.repository.lesson(id);
      if (!mounted) return;
      await Navigator.pushReplacement<void, void>(
        context,
        MaterialPageRoute(
          builder: (_) => _LessonReader(
            state: widget.state,
            lesson: lesson,
            repository: widget.repository,
            tracks: widget.tracks,
            onAsk: widget.onAsk,
            onAskContext: widget.onAskContext,
            onMaintenanceItem: widget.onMaintenanceItem,
          ),
        ),
      );
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'This related guide is unavailable. You can try opening it again.',
        );
      }
    } finally {
      if (mounted) setState(() => _opening = null);
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) {
      final lesson = widget.lesson;
      final completed = widget.state.completedLessons.contains(lesson.id);
      final known = {
        for (final l in widget.tracks.expand((t) => t.lessons)) l.id: l.title,
      };
      return Scaffold(
        appBar: AppBar(title: const Text('Learning guide')),
        body: SelectionArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
            children: [
              Text(
                lesson.title,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              if (lesson.readingMinutes != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text('${lesson.readingMinutes} minute read'),
                ),
              if (lesson.introduction.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(
                    lesson.introduction,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ),
              const Divider(height: 40),
              GuideContent(content: lesson.content),
              const Divider(height: 40),
              if (_error != null)
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (widget.state.signedIn) ...[
                if (completed)
                  const ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(Icons.check_circle_outline),
                    title: Text('Guide completed'),
                  ),
                FilledButton.icon(
                  icon: Icon(completed ? Icons.undo : Icons.check),
                  label: Text(
                    _busy
                        ? 'Saving…'
                        : completed
                        ? 'Mark as unread'
                        : 'Mark lesson completed',
                  ),
                  onPressed: _busy || widget.state.saving
                      ? null
                      : () async {
                          setState(() {
                            _busy = true;
                            _error = null;
                          });
                          try {
                            if (completed) {
                              await widget.state.markLessonUnread(lesson.id);
                            } else {
                              await widget.state.completeLesson(lesson.id);
                            }
                          } catch (_) {
                            if (mounted) {
                              setState(
                                () => _error =
                                    'Progress could not be saved. Please try again.',
                              );
                            }
                          } finally {
                            if (mounted) setState(() => _busy = false);
                          }
                        },
                ),
              ] else
                const Text(
                  'Sign in from your profile to save learning progress.',
                ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.chat_bubble_outline),
                label: const Text('Ask AI about this topic'),
                onPressed: () {
                  final details = html.parse(lesson.content).body?.text ?? '';
                  Navigator.pop(context);
                  if (widget.onAskContext != null) {
                    widget.onAskContext!({
                      'kind': 'Learning card',
                      'id': lesson.id,
                      'categoryId': lesson.categoryId,
                      'title': lesson.title,
                      'details': details.length > 1800
                          ? '${details.substring(0, 1800)} (excerpt)'
                          : details,
                    });
                  } else {
                    widget.onAsk(lesson.title);
                  }
                },
              ),
              if (lesson.relatedLessonIds.isNotEmpty)
                const ModuleSection(title: 'Related guides'),
              for (var i = 0; i < lesson.relatedLessonIds.length; i++)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.menu_book_outlined),
                  title: Text(
                    known[lesson.relatedLessonIds[i]] ??
                        'Related guide ${i + 1}',
                  ),
                  trailing: _opening == lesson.relatedLessonIds[i]
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(),
                        )
                      : const Icon(Icons.chevron_right),
                  onTap: _opening == null
                      ? () => _related(lesson.relatedLessonIds[i])
                      : null,
                ),
              if (lesson.maintenanceItemIds.isNotEmpty &&
                  widget.onMaintenanceItem != null) ...[
                const ModuleSection(
                  title: 'Related maintenance',
                  description:
                      'See this item for your selected vehicle. An item can be added if it is not in your schedule.',
                ),
                for (var i = 0; i < lesson.maintenanceItemIds.length; i++)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.build_outlined),
                    title: Text(
                      lesson.maintenanceItemIds.length == 1
                          ? 'Open related maintenance'
                          : 'Open maintenance item ${i + 1}',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      Navigator.pop(context);
                      widget.onMaintenanceItem!(lesson.maintenanceItemIds[i]);
                    },
                  ),
              ],
            ],
          ),
        ),
      );
    },
  );
}

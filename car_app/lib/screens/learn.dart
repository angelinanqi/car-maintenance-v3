import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../app_state.dart';
import '../data/content_repository.dart';
import '../models/content.dart';
import '../widgets/guide_content.dart';
import 'package:html/parser.dart' as html;

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
  List<OwnerManual> _manuals = [];
  String _scope = 'general';
  bool _manualLoading = true;
  String? _manualError;
  String? _openingManual;
  int _manualRequest = 0;
  List<LearningTrack> _tracks = [];
  bool _loading = true;
  String? _error;
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? ContentRepository(widget.state.store);
    _scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    _load();
    _loadManuals();
  }

  @override
  void didUpdateWidget(covariant Learn oldWidget) {
    super.didUpdateWidget(oldWidget);
    final scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    if (scope != _scope) {
      _scope = scope;
      _manuals = [];
      _loadManuals();
    }
    if (widget.lessonRequestNumber != oldWidget.lessonRequestNumber &&
        widget.requestedLessonId != null) {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => _related(widget.requestedLessonId!),
      );
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
        setState(
          () => _manualError =
              'Manuals could not be loaded. Check your connection and retry.',
        );
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
        await showModalBottomSheet<void>(
          context: context,
          isScrollControlled: true,
          useSafeArea: true,
          builder: (_) => DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.85,
            builder: (_, controller) => ListView(
              controller: controller,
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  manual.name,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 16),
                SelectableText(text),
              ],
            ),
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not open the manual. It may be unavailable or your device may need a PDF viewer.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _openingManual = null);
    }
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
        setState(
          () => _error = 'Learning content could not be loaded. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _read(Lesson lesson) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) => DraggableScrollableSheet(
        initialChildSize: 0.85,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (_, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              lesson.title,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            const Text('Published learning guide'),
            if (lesson.readingMinutes != null)
              Text('${lesson.readingMinutes} minute read'),
            if (lesson.introduction.isNotEmpty) Text(lesson.introduction),
            const Divider(height: 32),
            GuideContent(content: lesson.content),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Ask AI about this topic'),
              onPressed: () {
                Navigator.pop(sheetContext);
                final details = html.parse(lesson.content).body?.text ?? '';
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
            const SizedBox(height: 16),
            for (final id in lesson.relatedLessonIds)
              TextButton(
                onPressed: () {
                  Navigator.pop(sheetContext);
                  _related(id);
                },
                child: const Text('Read related lesson'),
              ),
            for (final id in lesson.maintenanceItemIds)
              TextButton(
                onPressed: () {
                  Navigator.pop(sheetContext);
                  widget.onMaintenanceItem?.call(id);
                },
                child: const Text('Open related maintenance'),
              ),
            _CompleteLesson(state: widget.state, lesson: lesson),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Future<void> _related(String id) async {
    try {
      final lesson = await _repository.lesson(id);
      if (mounted) _read(lesson);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lesson could not be opened. $error')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Learn'),
      backgroundColor: Theme.of(context).colorScheme.primaryContainer,
      actions: [
        IconButton(
          tooltip: 'Refresh learning guides',
          onPressed: _loading ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Your learning tracks',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Read published learning cards. Sign in to save completion progress to your account.',
        ),
        const SizedBox(height: 16),
        if (widget.state.signedIn)
          Text(
            'Overall progress: ${_tracks.expand((t) => t.lessons).where((l) => widget.state.completedLessons.contains(l.id)).length} of ${_tracks.expand((t) => t.lessons).length} lessons completed',
          ),
        if (_loading) const Center(child: CircularProgressIndicator()),
        if (!_loading && _error == null && _tracks.isEmpty)
          const Text('No learning content is available yet.'),
        if (_error != null)
          Column(
            children: [
              Text(_error!),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ..._tracks.asMap().entries.map((entry) {
          final track = entry.value;
          final read = track.lessons
              .where((l) => widget.state.completedLessons.contains(l.id))
              .length;
          final progress = track.lessons.isEmpty
              ? 0.0
              : read / track.lessons.length;
          return Card.outlined(
            child: ExpansionTile(
              key: PageStorageKey(track.title),
              initiallyExpanded: entry.key == 0,
              title: Text('${track.title} ($read/${track.lessons.length})'),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(track.subtitle),
                  const SizedBox(height: 8),
                  LinearProgressIndicator(
                    value: progress,
                    semanticsLabel: '${track.title} completion',
                    semanticsValue: '${(progress * 100).round()}',
                  ),
                ],
              ),
              children: track.lessons
                  .map(
                    (lesson) => ListTile(
                      leading: Icon(
                        widget.state.completedLessons.contains(lesson.id)
                            ? Icons.check_circle_outline
                            : Icons.menu_book,
                      ),
                      title: Text(lesson.title),
                      subtitle:
                          widget.state.completedLessons.contains(lesson.id)
                          ? const Text('Completed • tap to read again')
                          : const Text('Tap to read'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _read(lesson),
                    ),
                  )
                  .toList(),
            ),
          );
        }),
        const SizedBox(height: 16),
        Text('Owner manuals', style: Theme.of(context).textTheme.titleLarge),
        Text('${widget.state.vehicleScopes[_scope] ?? _scope} · Online access'),
        if (_manualLoading) const LinearProgressIndicator(),
        if (_manualError != null) Text(_manualError!),
        if (!_manualLoading && _manualError == null && _manuals.isEmpty)
          const Text('No manuals are available for this vehicle scope yet.'),
        TextButton(
          onPressed: _manualLoading ? null : _loadManuals,
          child: const Text('Refresh manuals'),
        ),
        ..._manuals.map(
          (manual) => Card.outlined(
            child: ListTile(
              leading: const Icon(Icons.description_outlined),
              title: Text(manual.name),
              subtitle: Text(
                '${manual.sourceType.toUpperCase()} · ${(manual.sizeBytes / 1024).ceil()} KB${manual.scope == 'general' ? ' · General' : ''}',
              ),
              trailing: _openingManual == manual.id
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(),
                    )
                  : const Icon(Icons.open_in_new),
              onTap: _openingManual == null ? () => _openManual(manual) : null,
            ),
          ),
        ),
      ],
    ),
  );
}

class _CompleteLesson extends StatefulWidget {
  final AppState state;
  final Lesson lesson;
  const _CompleteLesson({required this.state, required this.lesson});
  @override
  State<_CompleteLesson> createState() => _CompleteLessonState();
}

class _CompleteLessonState extends State<_CompleteLesson> {
  bool _busy = false;
  String? _error;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (_error != null) Text(_error!),
      if (!widget.state.signedIn)
        const Text('Sign in to track learning progress.'),
      if (widget.state.signedIn)
        FilledButton(
          onPressed: _busy
              ? null
              : () async {
                  setState(() {
                    _busy = true;
                    _error = null;
                  });
                  try {
                    await widget.state.completeLesson(widget.lesson.id);
                    if (context.mounted) Navigator.pop(context);
                  } catch (_) {
                    if (mounted) {
                      setState(
                        () => _error =
                            'Progress could not be saved. Please retry.',
                      );
                    }
                  } finally {
                    if (mounted) setState(() => _busy = false);
                  }
                },
          child: Text(_busy ? 'Saving...' : 'Mark lesson completed'),
        ),
    ],
  );
}

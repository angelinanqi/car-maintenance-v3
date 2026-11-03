import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../app_theme.dart';
import '../models/content.dart';
import '../widgets/design_widgets.dart';
import '../widgets/guide_content.dart';
import '../widgets/content_media.dart';
import '../data/learning_errors.dart';

class GuideStepPage extends StatefulWidget {
  final AppState state;
  final Lesson lesson;
  final VoidCallback onRead;
  final ValueChanged<int> onAsk;
  final VoidCallback onCompleted;
  const GuideStepPage({
    super.key,
    required this.state,
    required this.lesson,
    required this.onRead,
    required this.onAsk,
    required this.onCompleted,
  });
  @override
  State<GuideStepPage> createState() => _GuideStepPageState();
}

class _GuideStepPageState extends State<GuideStepPage> {
  int _index = 0;
  String? _answer, _error;
  bool _busy = false;
  late final String? _owner;
  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    final progress = widget.state.learningProgress[widget.lesson.id];
    if (widget.state.learningError == null &&
        progress != null &&
        progress['completed'] != true) {
      final found = widget.lesson.sections.indexWhere(
        (s) => s.id == progress['current_step_id'],
      );
      final savedRevision = DateTime.tryParse(
        progress['guide_revision'] as String? ?? '',
      );
      final revision = DateTime.tryParse(widget.lesson.revision);
      if (found >= 0 && savedRevision != null && savedRevision == revision) {
        _index = found;
      } else if (progress['current_step_id'] != null) {
        _error =
            'This guide has changed. Start again with the current version.';
      }
    }
  }

  Future<void> _navigate(int index) async {
    if (_busy) return;
    if (widget.state.accountId != _owner) {
      setState(() {
        _index = index;
        _answer = null;
        _error = 'Your account changed. Reopen this guide to save progress.';
      });
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (widget.state.signedIn) {
        if (widget.state.accountId != _owner)
          throw StateError('Account changed');
        await widget.state.saveLessonStep(
          widget.lesson.id,
          widget.lesson.sections[index].id,
          widget.lesson.revision,
        );
      }
    } catch (error) {
      if (mounted)
        setState(
          () => _error = learningFailureMessage(
            error,
            fallback:
                'Progress could not be confirmed. You can keep reading. Refresh progress before retrying the save.',
          ),
        );
    } finally {
      if (mounted)
        setState(() {
          _busy = false;
          _index = index;
          _answer = null;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final lesson = widget.lesson;
    final section = lesson.sections.isEmpty ? null : lesson.sections[_index];
    final count = lesson.sections.isEmpty ? 1 : lesson.sections.length;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          key: ValueKey(_index),
          padding: const EdgeInsets.all(AppSpacing.screen),
          children: [
            Row(
              children: [
                IconButton(
                  tooltip: 'Close guide',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: LinearProgressIndicator(
                    value: (_index + 1) / count,
                    minHeight: 12,
                    borderRadius: BorderRadius.circular(12),
                    color: AppColors.accent,
                  ),
                ),
                const SizedBox(width: 12),
                StatusPill('${_index + 1} / $count'),
              ],
            ),
            const SizedBox(height: 16),
            if (widget.state.learningError != null)
              Text(
                widget.state.learningError!,
                style: const TextStyle(color: AppColors.danger),
              ),
            Row(
              children: [
                const Mascot(size: 52),
                const SizedBox(width: 12),
                Expanded(
                  child: SurfaceCard(
                    child: Text(
                      lesson.introduction.isEmpty
                          ? 'Take it one step at a time.'
                          : lesson.introduction,
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.standard),
            Text(
              'STEP ${_index + 1}',
              style: const TextStyle(
                color: AppColors.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              section?.title ?? lesson.title,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            GuideContent(content: section?.content ?? lesson.content),
            ContentMediaList(items: lesson.media.where((item) => section == null || item['section_id'] == null || item['section_id'] == section.sectionId).toList()),
            const SizedBox(height: 16),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.tonal(
                onPressed: () => widget.onAsk(_index),
                child: const Text('Ask AI about this step'),
              ),
            ),
            if (section != null && section.example.isNotEmpty)
              ExpansionTile(
                title: const Text('Show an example'),
                children: [GuideContent(content: section.example)],
              ),
            if (section?.question != null)
              ExpansionTile(
                title: const Text('Try a situation'),
                children: [
                  Text(section!.question!),
                  RadioGroup<String>(
                    groupValue: _answer,
                    onChanged: (value) => setState(() => _answer = value),
                    child: Column(
                      children: [
                        for (final option in section.options)
                          RadioListTile<String>(
                            value: option.id,
                            title: Text(option.text),
                          ),
                      ],
                    ),
                  ),
                  if (_answer != null)
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        section.options
                            .firstWhere((o) => o.id == _answer)
                            .feedback,
                      ),
                    ),
                ],
              ),
            TextButton(
              onPressed: widget.onRead,
              child: const Text('Original guide, related items & progress'),
            ),
            if (_error != null)
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            const SizedBox(height: AppSpacing.large),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.accent,
                foregroundColor: AppColors.ink,
              ),
              onPressed: _busy
                  ? null
                  : () async {
                      if (_index < count - 1) {
                        await _navigate(_index + 1);
                        return;
                      }
                      if (!widget.state.signedIn ||
                          widget.state.accountId != _owner) {
                        setState(
                          () => _error =
                              'Sign in to save your learning progress. You can still read every guide.',
                        );
                        return;
                      }
                      setState(() {
                        _busy = true;
                        _error = null;
                      });
                      try {
                        await widget.state.completeLesson(
                          lesson.id,
                          revision: lesson.revision,
                        );
                        if (!mounted || widget.state.accountId != _owner)
                          return;
                        widget.onCompleted();
                        Navigator.pop(context);
                      } catch (error) {
                        if (mounted)
                          setState(
                            () => _error = learningFailureMessage(
                              error,
                              fallback:
                                  'Progress could not be confirmed. Refresh progress before retrying.',
                            ),
                          );
                      } finally {
                        if (mounted) setState(() => _busy = false);
                      }
                    },
              child: Text(
                _busy
                    ? 'Saving…'
                    : _index < count - 1
                    ? 'Continue'
                    : 'Complete guide',
              ),
            ),
            if (_index > 0)
              TextButton(
                onPressed: _busy ? null : () => _navigate(_index - 1),
                child: const Text('Previous step'),
              ),
          ],
        ),
      ),
    );
  }
}

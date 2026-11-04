import 'package:flutter/material.dart';
import '../models/content.dart';
import 'guide_content.dart';

class LearningActivity extends StatefulWidget {
  final Lesson lesson;
  final int index;
  final bool busy;
  final ValueChanged<int> onStep;
  final VoidCallback onAsk, onSimplify, onPlan, onSave, onRead, onComplete;
  final ValueChanged<String> onRelated;
  const LearningActivity({
    super.key,
    required this.lesson,
    required this.index,
    required this.onStep,
    required this.onAsk,
    required this.onSimplify,
    required this.onPlan,
    required this.onSave,
    required this.onRead,
    required this.onComplete,
    required this.onRelated,
    this.busy = false,
  });
  @override
  State<LearningActivity> createState() => _LearningActivityState();
}

class _LearningActivityState extends State<LearningActivity> {
  bool _example = false, _activity = false;
  String? _answer;
  @override
  void didUpdateWidget(covariant LearningActivity oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.index != widget.index ||
        oldWidget.lesson.id != widget.lesson.id) {
      _example = false;
      _activity = false;
      _answer = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final lesson = widget.lesson;
    final section = lesson.sections.isEmpty
        ? null
        : lesson.sections[widget.index];
    final colors = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(lesson.title, style: Theme.of(context).textTheme.titleLarge),
        if (section != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              '${widget.index + 1} of ${lesson.sections.length} sections',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        if (widget.index == 0 && lesson.outcomes.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'What you can take away',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final outcome in lesson.outcomes)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(outcome),
                  ),
              ],
            ),
          ),
        GuideContent(content: section?.content ?? lesson.content),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: widget.onRead,
            icon: const Icon(Icons.menu_book_outlined, size: 18),
            label: const Text('Read published guide'),
          ),
        ),
        if (_example && section != null)
          Container(
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: colors.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'An example',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                GuideContent(content: section.example),
              ],
            ),
          ),
        if (_activity && section?.question != null)
          Container(
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: colors.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  section!.question!,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final option in section.options)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: OutlinedButton(
                      style: _answer == option.id
                          ? OutlinedButton.styleFrom(
                              backgroundColor: colors.primaryContainer,
                            )
                          : null,
                      onPressed: () => setState(() => _answer = option.id),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Text(option.text),
                      ),
                    ),
                  ),
                if (_answer != null)
                  Semantics(
                    liveRegion: true,
                    child: Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: Text(
                        section.options
                            .firstWhere((option) => option.id == _answer)
                            .feedback,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton(
              onPressed: widget.busy ? null : widget.onAsk,
              child: const Text('Ask about this'),
            ),
            if (section != null &&
                section.example.trim().isNotEmpty &&
                section.example != '<p></p>')
              TextButton(
                onPressed: () => setState(() => _example = !_example),
                child: Text(_example ? 'Hide example' : 'Show an example'),
              ),
            if (section?.question != null)
              TextButton(
                onPressed: () => setState(() => _activity = !_activity),
                child: Text(_activity ? 'Hide situation' : 'Try a situation'),
              ),
          ],
        ),
        if (lesson.maintenanceItemIds.isNotEmpty)
          TextButton(
            onPressed: widget.busy ? null : widget.onPlan,
            child: const Text('Look at my service plan'),
          ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('More ways to explore'),
          children: [
            ListTile(
              title: const Text('Explain this more simply'),
              onTap: widget.busy ? null : widget.onSimplify,
            ),
            ListTile(
              title: const Text('Read the original guide'),
              onTap: widget.onRead,
            ),
            ListTile(
              title: const Text('Save this guide'),
              onTap: widget.busy ? null : widget.onSave,
            ),
          ],
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            if (widget.index > 0)
              OutlinedButton(
                onPressed: widget.busy
                    ? null
                    : () => widget.onStep(widget.index - 1),
                child: const Text('Previous section'),
              ),
            if (section != null && widget.index < lesson.sections.length - 1)
              FilledButton(
                onPressed: widget.busy
                    ? null
                    : () => widget.onStep(widget.index + 1),
                child: const Text('Continue'),
              )
            else
              OutlinedButton(
                onPressed: widget.busy ? null : widget.onComplete,
                child: const Text('Mark as completed'),
              ),
          ],
        ),
        if ((section == null || widget.index == lesson.sections.length - 1) &&
            lesson.relatedLessonIds.isNotEmpty)
          TextButton(
            onPressed: widget.busy
                ? null
                : () => widget.onRelated(lesson.relatedLessonIds.first),
            child: const Text('Explore a related guide'),
          ),
      ],
    );
  }
}

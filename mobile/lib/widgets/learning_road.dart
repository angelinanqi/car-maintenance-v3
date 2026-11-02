import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../app_theme.dart';
import '../models/content.dart';
import 'design_widgets.dart';

class LearningRoad extends StatelessWidget {
  final AppState state;
  final List<LearningTrack> tracks;
  final int weeklyCount;
  final Set<String> completedRecaps;
  final VoidCallback onSearch, onAsk;
  final ValueChanged<Lesson> onOpen;
  final ValueChanged<LearningTrack> onRecap;
  const LearningRoad({
    super.key,
    required this.state,
    required this.tracks,
    required this.weeklyCount,
    this.completedRecaps = const {},
    required this.onSearch,
    required this.onAsk,
    required this.onOpen,
    required this.onRecap,
  });
  @override
  Widget build(BuildContext context) {
    final lessons = tracks.expand((t) => t.lessons).toList();
    final recommended =
        lessons
            .where((l) => !state.completedLessons.contains(l.id))
            .firstOrNull ??
        lessons.firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text('Learn', style: Theme.of(context).textTheme.headlineMedium),
            if (state.signedIn)
              StatusPill('Weekly goal ${weeklyCount.clamp(0, 2)}/2'),
            IconButton.filledTonal(
              tooltip: 'Search guides and manuals',
              style: IconButton.styleFrom(backgroundColor: AppColors.pale),
              onPressed: onSearch,
              icon: const Icon(Icons.search),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.standard),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Mascot(size: 58),
            const SizedBox(width: 14),
            Expanded(
              child: SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pick any guide you like',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      recommended == null
                          ? 'Practical guides, at your pace.'
                          : 'I’d start with ${recommended.title.toLowerCase().replaceFirst('reading ', '')}. ${recommended.readingMinutes == null ? '' : '${recommended.readingMinutes} minutes.'}',
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        for (var unit = 0; unit < tracks.length; unit++) ...[
          SurfaceCard(
            color: AppColors.accent,
            borderColor: AppColors.accent,
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'UNIT ${unit + 1}',
                        style: const TextStyle(fontSize: 13),
                      ),
                      Text(
                        tracks[unit].title,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ],
                  ),
                ),
                StatusPill(
                  '${tracks[unit].lessons.where((l) => state.completedLessons.contains(l.id)).length + (completedRecaps.contains(tracks[unit].id) ? 1 : 0)} of ${tracks[unit].lessons.length + (tracks[unit].id == null ? 0 : 1)} stops',
                  color: AppColors.ink,
                  foreground: const Color(0xFFFFE08A),
                ),
              ],
            ),
          ),
          _RoadStops(
            track: tracks[unit],
            completed: state.completedLessons,
            recapCompleted: completedRecaps.contains(tracks[unit].id),
            recommendedId: recommended?.id,
            onOpen: onOpen,
            onRecap: () => onRecap(tracks[unit]),
          ),
        ],
        const SizedBox(height: 20),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.tonalIcon(
            onPressed: onAsk,
            icon: const Icon(Icons.chat_bubble_outline),
            label: const Text('Ask AI about this'),
          ),
        ),
      ],
    );
  }
}

class _RoadStops extends StatelessWidget {
  final LearningTrack track;
  final Set<String> completed;
  final bool recapCompleted;
  final String? recommendedId;
  final ValueChanged<Lesson> onOpen;
  final VoidCallback onRecap;
  const _RoadStops({
    required this.track,
    required this.completed,
    required this.recapCompleted,
    required this.recommendedId,
    required this.onOpen,
    required this.onRecap,
  });
  @override
  Widget build(BuildContext context) {
    final stops = <Lesson?>[
      ...track.lessons.take(4),
      if (track.id != null) null,
      ...track.lessons.skip(4),
    ];
    final count = stops.length;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final textScale = MediaQuery.textScalerOf(context).scale(12) / 12;
        final stopSpacing = 112.0 + 40.0 * (textScale - 1).clamp(0.0, 2.0);
        final height = count * stopSpacing + 25;
        return SizedBox(
          height: height,
          child: Stack(
            children: [
              Positioned.fill(
                child: CustomPaint(painter: _RoadPainter(count, stopSpacing)),
              ),
              for (var i = 0; i < count; i++)
                Positioned(
                  top: i * stopSpacing,
                  left: (width * _roadX(i) - 70).clamp(0.0, width - 140),
                  width: 140,
                  child: Column(
                    children: [
                      if (stops[i] != null && stops[i]!.id == recommendedId)
                        const StatusPill(
                          'RECOMMENDED',
                          color: AppColors.ink,
                          foreground: Color(0xFFFFE08A),
                        ),
                      SizedBox.square(
                        dimension: 54,
                        child: FilledButton(
                          style: FilledButton.styleFrom(
                            padding: EdgeInsets.zero,
                            shape: const CircleBorder(
                              side: BorderSide(
                                color: AppColors.accent,
                                width: 4,
                              ),
                            ),
                            backgroundColor: stops[i] == null
                                ? recapCompleted
                                      ? AppColors.accent
                                      : AppColors.pale
                                : completed.contains(stops[i]!.id)
                                ? AppColors.accent
                                : Colors.white,
                            foregroundColor: AppColors.ink,
                          ),
                          onPressed: stops[i] == null
                              ? onRecap
                              : () => onOpen(stops[i]!),
                          child: Icon(
                            stops[i] == null
                                ? recapCompleted
                                      ? Icons.check
                                      : Icons.flag_outlined
                                : completed.contains(stops[i]!.id)
                                ? Icons.check
                                : stops[i]!.id == recommendedId
                                ? Icons.directions_car_outlined
                                : Icons.menu_book_outlined,
                          ),
                        ),
                      ),
                      InkWell(
                        onTap: stops[i] == null
                            ? onRecap
                            : () => onOpen(stops[i]!),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            border: Border.all(color: AppColors.border),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            stops[i] == null
                                ? 'Optional recap'
                                : stops[i]!.title,
                            textAlign: TextAlign.center,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

double _roadX(int index) => const [.5, .27, .5, .73, .5, .27][index % 6];

class _RoadPainter extends CustomPainter {
  final int count;
  final double stopSpacing;
  _RoadPainter(this.count, this.stopSpacing);
  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()..moveTo(size.width * _roadX(0), 28);
    for (var i = 1; i < count; i++) {
      final previous = Offset(
        size.width * _roadX(i - 1),
        (i - 1) * stopSpacing + 28,
      );
      final next = Offset(size.width * _roadX(i), i * stopSpacing + 28);
      path.cubicTo(
        previous.dx,
        previous.dy + 48,
        next.dx,
        next.dy - 48,
        next.dx,
        next.dy,
      );
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = AppColors.ink
        ..style = PaintingStyle.stroke
        ..strokeWidth = 58
        ..strokeCap = StrokeCap.round,
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xFF4A4128)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 49
        ..strokeCap = StrokeCap.round,
    );
    final paint = Paint()
      ..color = const Color(0xFFFFE08A)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    for (final metric in path.computeMetrics()) {
      for (double distance = 0; distance < metric.length; distance += 22)
        canvas.drawPath(metric.extractPath(distance, distance + 10), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _RoadPainter oldDelegate) =>
      oldDelegate.count != count || oldDelegate.stopSpacing != stopSpacing;
}

class RecapComplete extends StatelessWidget {
  final String title;
  final bool progressSaved;
  final int recaps, weeklyCount, completed, total;
  const RecapComplete({
    super.key,
    required this.title,
    this.progressSaved = true,
    required this.recaps,
    required this.weeklyCount,
    required this.completed,
    required this.total,
  });
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        child: Column(
          children: [
            const SizedBox(height: AppSpacing.large),
            const Mascot(size: 180, artwork: MascotArtwork.companion),
            const SizedBox(height: AppSpacing.section),
            Text(
              'Recap complete!',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineLarge,
            ),
            const SizedBox(height: 16),
            Text(
              'Nice work on $title.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.muted, fontSize: 16),
            ),
            const SizedBox(height: 20),
            if (!progressSaved)
              const Text('Sign in to save your recap and learning progress.'),
            Row(
              children: [
                for (final stat in [
                  (recaps.toString(), 'Recap done'),
                  ('${weeklyCount.clamp(0, 2)} of 2', 'Weekly goal'),
                  ('$completed of $total', 'Stops done'),
                ])
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3),
                      child: SurfaceCard(
                        padding: const EdgeInsets.symmetric(
                          vertical: 16,
                          horizontal: 4,
                        ),
                        child: Column(
                          children: [
                            Text(
                              stat.$1,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            Text(
                              stat.$2,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.large),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.accent,
                  foregroundColor: AppColors.ink,
                ),
                onPressed: () => Navigator.pop(context),
                child: const Text('Continue'),
              ),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Back to the road'),
            ),
          ],
        ),
      ),
    ),
  );
}

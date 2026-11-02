import 'package:flutter/material.dart';
import '../models/companion.dart';

class ServicePlanView extends StatelessWidget {
  final ServicePlan plan;
  final bool busy;
  final VoidCallback onSave, onRefresh, onNotes, onAsk;
  final ValueChanged<String> onRecord, onGuide;
  const ServicePlanView({
    super.key,
    required this.plan,
    required this.onSave,
    required this.onRefresh,
    required this.onNotes,
    required this.onAsk,
    required this.onRecord,
    required this.onGuide,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    const headings = {
      'due': 'Due now',
      'discuss': 'Discuss at this visit',
      'check': 'Needs checking',
      'upcoming': 'Other tracked items',
    };
    Widget item(Map<String, dynamic> item) {
      final timing = item['status'] as Map;
      final rule = item['rule'] as Map?;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${item['title']} · ${item['action']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(timing['label'] as String),
            if (timing['nextKm'] != null)
              Text('Due mileage: ${timing['nextKm']} km'),
            if (timing['nextDate'] != null)
              Text('Due date: ${timing['nextDate']}'),
            Text(
              item['schedule_source'] == 'custom'
                  ? 'Your custom reminder'
                  : item['schedule_source'] == 'manufacturer'
                  ? 'Published manufacturer schedule'
                  : 'No timing rule',
            ),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Why is this included?'),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(switch (item['reason']) {
                    'scheduled_threshold_reached' =>
                      'A calculated date or mileage threshold has been reached.',
                    'within_discussion_window' =>
                      'This item is approaching its due point. Discuss whether it belongs in this visit; its original timing still applies.',
                    'schedule_or_history_needs_review' =>
                      'The available schedule or service history does not establish a confirmed due point.',
                    _ =>
                      'This item is tracked outside the proposed next visit.',
                  }),
                ),
                if (rule?['conditions'] != null &&
                    (rule!['conditions'] as String).isNotEmpty)
                  Text(rule['conditions'] as String),
                if (rule?['notes'] != null &&
                    (rule!['notes'] as String).isNotEmpty)
                  Text(rule['notes'] as String),
                Wrap(
                  spacing: 8,
                  children: [
                    if ((item['lesson_ids'] as List).isNotEmpty)
                      TextButton(
                        onPressed: () => onGuide(
                          (item['lesson_ids'] as List).first as String,
                        ),
                        child: const Text('Understand this maintenance'),
                      ),
                    if (!plan.stale)
                      TextButton(
                        onPressed: busy
                            ? null
                            : () => onRecord(item['task_id'] as String),
                        child: const Text('Record completed work'),
                      ),
                  ],
                ),
              ],
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Your next service',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text('${plan.mileage} km recorded · Prepared ${plan.date}'),
        Text('Covers ${plan.totalTasks} tracked items.'),
        if (plan.stale)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(
              'Your records, schedule or date have changed. Refresh this proposal before using it.',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (plan.totalTasks == 0)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Text(
              'Add maintenance items or review your service schedule to prepare a plan.',
            ),
          ),
        for (final key in ['due', 'discuss', 'check'])
          if ((plan.groups[key] ?? []).isNotEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              margin: const EdgeInsets.only(top: 20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    headings[key]!,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  ...plan.groups[key]!.map(item),
                ],
              ),
            ),
        if ((plan.groups['upcoming'] ?? []).isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(headings['upcoming']!),
            children: plan.groups['upcoming']!.map(item).toList(),
          ),
        const SizedBox(height: 20),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton(
              onPressed: busy || plan.stale ? null : onNotes,
              child: const Text('Prepare mechanic notes'),
            ),
            OutlinedButton(
              onPressed: busy ? null : onRefresh,
              child: const Text('Refresh plan'),
            ),
            TextButton(
              onPressed: busy || plan.stale ? null : onSave,
              child: Text(plan.id == null ? 'Save plan' : 'Keep in Saved'),
            ),
            TextButton(
              onPressed: busy || plan.stale ? null : onAsk,
              child: const Text('Ask about this plan'),
            ),
          ],
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';

import '../app_theme.dart';
import '../models/companion.dart';
import '../models/maintenance.dart';
import 'design_widgets.dart';

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

  static const _headings = {
    'due': 'Due now',
    'discuss': 'Due soon',
    'check': 'Confirm service details',
    'upcoming': 'Later & completed',
  };
  int _count(String group) => plan.groups[group]?.length ?? 0;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      SurfaceCard(
        color: AppColors.pale,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text(
                'Your maintenance plan',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                Text('${_number(plan.mileage)} km recorded'),
                Text('Prepared ${_date(plan.date)}'),
              ],
            ),
            if (!plan.stale && plan.totalTasks > 0 && _count('due') == 0) ...[
              const SizedBox(height: 12),
              Text(
                'No confirmed items are due now.',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ],
          ],
        ),
      ),
      if (plan.stale)
        SurfaceCard(
          color: AppColors.dangerSurface,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'This plan needs a refresh',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              const Text(
                'Your records, schedule or the date have changed. Refresh to see current timing.',
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: busy ? null : onRefresh,
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh plan'),
              ),
            ],
          ),
        ),
      if (plan.totalTasks == 0)
        const SurfaceCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.event_note_outlined, size: 32),
              SizedBox(height: 12),
              Text('No maintenance items yet'),
              SizedBox(height: 6),
              Text('Add a maintenance item in My Car to start your plan.'),
            ],
          ),
        ),
      for (final group in ['due', 'discuss', 'check'])
        if (_count(group) > 0) ...[
          Padding(
            padding: const EdgeInsets.only(top: 4, bottom: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  header: true,
                  child: Text(
                    '${_headings[group]} (${_count(group)})',
                    style: Theme.of(
                      context,
                    ).textTheme.titleLarge?.copyWith(color: _groupColor(group)),
                  ),
                ),
                if (group == 'check') ...[
                  const SizedBox(height: 4),
                  const Text('Check these before deciding what to book.'),
                ],
              ],
            ),
          ),
          _groupItems(context, group),
        ],
      if (_count('upcoming') > 0)
        ExpansionTile(
          key: PageStorageKey('later-${plan.fingerprint}'),
          tilePadding: EdgeInsets.zero,
          childrenPadding: EdgeInsets.zero,
          title: Text('${_headings['upcoming']} (${_count('upcoming')})'),
          children: [_groupItems(context, 'upcoming')],
        ),
      const SizedBox(height: 20),
      if (plan.totalTasks > 0) ...[
        FilledButton.icon(
          onPressed: busy || plan.stale ? null : onNotes,
          icon: const Icon(Icons.assignment_outlined),
          label: const Text('Prepare mechanic notes'),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: busy || plan.stale ? null : onSave,
          icon: const Icon(Icons.bookmark_border),
          label: Text(plan.id == null ? 'Save this plan' : 'Keep in Saved'),
        ),
      ],
      Wrap(
        spacing: 8,
        runSpacing: 4,
        alignment: WrapAlignment.center,
        children: [
          if (plan.totalTasks > 0)
            TextButton(
              onPressed: busy || plan.stale ? null : onAsk,
              child: const Text('Ask about this plan'),
            ),
          if (!plan.stale)
            TextButton.icon(
              onPressed: busy ? null : onRefresh,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Refresh plan'),
            ),
        ],
      ),
    ],
  );

  Widget _groupItems(BuildContext context, String group) {
    final items = plan.groups[group]!;
    return SurfaceCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var index = 0; index < items.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _item(context, items[index], group),
          ],
        ],
      ),
    );
  }

  Widget _item(BuildContext context, Map<String, dynamic> item, String group) {
    final timing = item['status'] as Map;
    final rule = item['rule'] as Map?;
    final display = item['display'] as Map?;
    final summary = display?['summary'] as String? ?? timing['label'] as String;
    final conditions =
        display?['conditions'] as String? ??
        rule?['conditions'] as String? ??
        '';
    final notes =
        display?['notes'] as String? ?? rule?['notes'] as String? ?? '';
    final sourceLabel =
        display?['source_label'] as String? ??
        switch (item['schedule_source']) {
          'manufacturer' => 'Manufacturer schedule',
          'custom' => 'Your custom reminder',
          _ => 'No schedule saved',
        };
    final reference =
        display?['source_reference'] as String? ??
        (item['source_name'] == null
            ? null
            : '${item['source_name']}${rule?['sourcePage'] == null ? '' : ', page ${rule!['sourcePage']}'}');
    final lessons = item['lesson_ids'] as List? ?? [];
    final nextKm = timing['nextKm'] as int?;
    final nextDate = timing['nextDate'] as String?;
    final check = group == 'check';
    final deadlines = [
      if (!check && nextKm != null) 'At ${_number(nextKm)} km',
      if (!check && nextDate != null) 'By ${_date(nextDate)}',
    ];
    final timingPreview = _timingPreview(item, group, summary, conditions);
    final action = maintenanceActionLabel(item['action'] as String);
    return ExpansionTile(
      key: PageStorageKey('details-${plan.fingerprint}-${item['task_id']}'),
      shape: const Border(),
      collapsedShape: const Border(),
      tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
      expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
      title: Text(
        item['title'] as String,
        style: Theme.of(context).textTheme.titleMedium,
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Text(
          check ? timingPreview : '$action · $timingPreview',
          style: Theme.of(
            context,
          ).textTheme.bodySmall?.copyWith(color: _groupColor(group)),
        ),
      ),
      children: [
        const Divider(height: 16),
        if (deadlines.isNotEmpty)
          _DetailBlock(
            label: 'Next scheduled service',
            value: deadlines.length == 2
                ? '${deadlines.join(' or ')}, whichever comes first'
                : deadlines.single,
          ),
        if (check && conditions.trim().isEmpty && summary != timingPreview)
          _DetailBlock(label: 'What to confirm', value: summary),
        if (conditions.trim().isNotEmpty)
          _DetailBlock(label: 'Schedule conditions', value: conditions),
        if (check) _DetailBlock(label: 'Listed action', value: action),
        if (display?['schedule'] != null)
          _DetailBlock(
            label: 'Service interval',
            value: (display!['schedule'] as String).replaceFirst(
              'Interval: ',
              '',
            ),
          ),
        _DetailBlock(
          label: 'Last recorded service',
          value: display?['history'] as String? ?? _history(item),
        ),
        if ((display?['calculations'] as List? ?? []).isNotEmpty)
          _DetailBlock(
            label: 'How the next service is calculated',
            value: (display!['calculations'] as List).join('\n'),
          ),
        if (display?['planning_note'] != null)
          _DetailBlock(
            label: 'Why it appears now',
            value: display!['planning_note'] as String,
          ),
        if (display?['timing_note'] != null)
          _DetailBlock(
            label: 'Still to confirm',
            value: display!['timing_note'] as String,
          ),
        _DetailBlock(
          label: 'Schedule source',
          value: [
            sourceLabel,
            if (reference?.isNotEmpty == true) reference!,
          ].join('\n'),
        ),
        if (notes.trim().isNotEmpty)
          _DetailBlock(
            label: display == null ? 'Schedule details' : 'Schedule notes',
            value: notes,
          ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (!plan.stale)
              OutlinedButton.icon(
                onPressed: busy
                    ? null
                    : () => onRecord(item['task_id'] as String),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Record service'),
              ),
            if (lessons.isNotEmpty)
              TextButton(
                onPressed: busy ? null : () => onGuide(lessons.first as String),
                child: const Text('Learn about this item'),
              ),
          ],
        ),
      ],
    );
  }

  String _timingPreview(
    Map<String, dynamic> item,
    String group,
    String summary,
    String conditions,
  ) {
    final timing = item['status'] as Map;
    final rule = item['rule'] as Map?;
    if (group == 'check') {
      if (conditions.trim().isNotEmpty) return 'Check which schedule applies';
      if (rule == null) return 'No service interval set';
      if (rule['type'] == 'informational') return 'No fixed service interval';
      if (timing['label'] == 'Untracked' ||
          (item.containsKey('latest_service') &&
              item['latest_service'] == null)) {
        return 'No previous service recorded';
      }
      if (rule['type'] == 'milestone' &&
          (rule['monthMilestones'] as List? ?? []).isNotEmpty &&
          rule['vehicleStartDate'] == null) {
        return 'Vehicle start date needed';
      }
      return 'Check schedule and service history';
    }
    final prefix = group == 'upcoming' ? 'Upcoming' : _headings[group];
    final timingDetail = summary.replaceFirst('$prefix · ', '');
    final nextKm = timing['nextKm'] as int?;
    if (nextKm != null) {
      return timingDetail.replaceFirst(
        'Due at the recorded mileage',
        'Due at ${_number(nextKm)} km',
      );
    }
    return timingDetail;
  }

  static Color _groupColor(String group) => switch (group) {
    'due' => AppColors.danger,
    'check' => AppColors.blueInk,
    _ => AppColors.muted,
  };
}

class _DetailBlock extends StatelessWidget {
  final String label, value;
  const _DetailBlock({required this.label, required this.value});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 4),
        Text(value, style: Theme.of(context).textTheme.bodyMedium),
      ],
    ),
  );
}

String _number(int value) => value.toString().replaceAllMapped(
  RegExp(r'\B(?=(\d{3})+(?!\d))'),
  (_) => ',',
);

String _date(String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return '${parsed.day} ${months[parsed.month - 1]} ${parsed.year}';
}

String _history(Map<String, dynamic> item) {
  if (!item.containsKey('latest_service'))
    return 'Refresh this plan to load its service history.';
  final last = item['latest_service'] as Map?;
  if (last == null) return 'No previous service is linked to this item.';
  return '${_date(last['date'] as String)} at ${_number(last['mileage'] as int)} km';
}

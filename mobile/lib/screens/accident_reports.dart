import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../data/accident_repository.dart';
import 'accident_form.dart';
import 'incident_history.dart';

class AccidentReports extends StatefulWidget {
  final AccidentRepository repository;
  final VoidCallback? onHelp;
  const AccidentReports({super.key, required this.repository, this.onHelp});

  @override
  State<AccidentReports> createState() => _AccidentReportsState();
}

class _AccidentReportsState extends State<AccidentReports> {
  List<Map<String, dynamic>> _drafts = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final drafts = await widget.repository.drafts();
      if (mounted) {
        setState(() {
          _drafts = drafts;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Saved drafts could not be opened. Your files have been kept. Retry before starting a form.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([Map<String, dynamic>? draft]) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => AccidentForm(
          repository: widget.repository,
          draft: draft,
          onHelp: widget.onHelp,
        ),
      ),
    );
    if (mounted) await _load();
  }

  String _time(Map<String, dynamic> draft) {
    final date = DateTime.tryParse(
      draft['occurredAt'] as String? ?? '',
    )?.toLocal();
    if (date == null) return 'Time not recorded';
    final labels = MaterialLocalizations.of(context);
    return '${labels.formatShortDate(date)} at ${labels.formatTimeOfDay(TimeOfDay.fromDateTime(date))}';
  }

  Future<void> _discard(Map<String, dynamic> draft) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Discard this accident draft?'),
        content: const Text(
          'This removes the draft. Past accident forms are kept.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep draft'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard draft'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.repository.discardDraft(draft['id'] as String);
      if (mounted) await _load();
    } catch (_) {
      if (mounted) {
        setState(
          () => _error = 'The draft could not be removed. Please retry.',
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Accident forms')),
    body: ListView(
      padding: const EdgeInsets.all(AppSpacing.screen),
      children: [
        const Text(
          'Record a road accident when you are safe. Drafts and saved forms stay on this device and work offline.',
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _loading || _error != null ? null : () => _openForm(),
          icon: const Icon(Icons.add),
          label: const Text('New accident form'),
        ),
        const SizedBox(height: 8),
        const Text(
          'Starts a separate form with the current time and location. Existing drafts are kept.',
        ),
        const SizedBox(height: 24),
        Text('Saved drafts', style: Theme.of(context).textTheme.titleLarge),
        if (_loading) const LinearProgressIndicator(),
        if (_error != null) ...[
          Text(_error!),
          TextButton(
            onPressed: _load,
            child: const Text('Retry loading drafts'),
          ),
        ],
        if (!_loading && _error == null && _drafts.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('No saved drafts. Start a new accident form above.'),
          ),
        for (final draft in _drafts)
          Card.outlined(
            child: ListTile(
              leading: const Icon(Icons.edit_note),
              title: const Text('Continue saved draft'),
              subtitle: Text(
                '${_time(draft)}\n${(draft['location'] as String? ?? '').isEmpty ? 'Location not recorded' : draft['location']}',
              ),
              isThreeLine: true,
              trailing: PopupMenuButton<String>(
                tooltip: 'Draft actions',
                itemBuilder: (_) => const [
                  PopupMenuItem(value: 'discard', child: Text('Discard draft')),
                ],
                onSelected: (_) => _discard(draft),
              ),
              onTap: () => _openForm(draft),
            ),
          ),
        const SizedBox(height: 24),
        OutlinedButton.icon(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => IncidentHistory(
                repository: widget.repository,
                onHelp: widget.onHelp,
              ),
            ),
          ),
          icon: const Icon(Icons.history),
          label: const Text('Past accident forms'),
        ),
      ],
    ),
  );
}

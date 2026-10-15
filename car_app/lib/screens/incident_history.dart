import 'package:flutter/material.dart';
import '../data/accident_repository.dart';
import 'accident_form.dart';

class IncidentHistory extends StatefulWidget {
  final AccidentRepository repository;
  const IncidentHistory({super.key, required this.repository});
  @override
  State<IncidentHistory> createState() => _IncidentHistoryState();
}

class _IncidentHistoryState extends State<IncidentHistory> {
  List<Map<String, dynamic>> _records = [];
  bool _loading = true, _busy = false, _backup = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final rows = await widget.repository.records();
      final enabled = await widget.repository.backupEnabled();
      if (mounted) {
        setState(() {
          _records = rows;
          _backup = enabled;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error =
              'Records could not be opened. Existing files have been kept. $error',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _operation(Future<void> Function() operation) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await operation();
      await _load();
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = 'Operation failed. Local records remain saved. $error',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Incident records'),
      actions: [
        IconButton(
          onPressed: _busy ? null : _load,
          tooltip: 'Refresh records',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Incident details and photos are saved on this device. Cloud text backup is optional; photos remain local.',
        ),
        if (_loading || _busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!),
        if (widget.repository.owner != null &&
            widget.repository.remote?.account.userId ==
                widget.repository.owner) ...[
          SwitchListTile(
            title: const Text('Back up incident details to my account'),
            value: _backup,
            subtitle: const Text(
              'Uploads your saved incident text when online. Local photos are retained on this device.',
            ),
            onChanged: _busy
                ? null
                : (value) => _operation(() async {
                    await widget.repository.enableBackup(value);
                    if (value) await widget.repository.sync();
                  }),
          ),
          OutlinedButton(
            onPressed: _busy || !_backup
                ? null
                : () => _operation(widget.repository.sync),
            child: const Text('Retry cloud backup'),
          ),
          TextButton(
            onPressed: _busy
                ? null
                : () async {
                    final agreed = await showDialog<bool>(
                      context: context,
                      builder: (_) => AlertDialog(
                        title: const Text('Associate guest incident records?'),
                        content: const Text(
                          'Move locally saved guest incidents into this account’s device records? If cloud backup is enabled, their text will also be uploaded. Guest incidents are never uploaded without your choice.',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(context, false),
                            child: const Text('Keep as guest records'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(context, true),
                            child: const Text('Associate records'),
                          ),
                        ],
                      ),
                    );
                    if (agreed == true && mounted) {
                      await _operation(() async {
                        await widget.repository.importGuestRecords();
                        await widget.repository.sync();
                      });
                    }
                  },
            child: const Text('Associate existing guest incident records'),
          ),
        ],
        if (!_loading && _records.isEmpty)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'No saved incidents yet. Your current draft is separate from incident history.',
            ),
          ),
        ..._records.map(
          (r) => Card.outlined(
            child: ListTile(
              title: Text(r['type'] as String? ?? 'Incident'),
              subtitle: Text(
                '${r['occurredAt']}\n${r['location'] ?? ''}\n${r['pendingSync'] == false ? 'Text backed up' : 'Saved locally'}',
              ),
              trailing: const Icon(Icons.edit_outlined),
              onTap: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        AccidentForm(repository: widget.repository, record: r),
                  ),
                );
                await _load();
              },
            ),
          ),
        ),
      ],
    ),
  );
}

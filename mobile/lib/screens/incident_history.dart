import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../data/accident_repository.dart';
import '../data/api_client.dart';
import 'accident_form.dart';
import 'accident_reports.dart';
import '../widgets/design_widgets.dart';

class IncidentHistory extends StatefulWidget {
  final AccidentRepository repository;
  final VoidCallback? onHelp;
  const IncidentHistory({super.key, required this.repository, this.onHelp});
  @override
  State<IncidentHistory> createState() => _IncidentHistoryState();
}

class _IncidentHistoryState extends State<IncidentHistory> {
  List<Map<String, dynamic>> _records = [];
  bool _loading = true, _busy = false, _backup = false;
  String? _error;
  bool _settingsOpen = false;
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
              'Records could not be opened. Existing files have been kept. Please retry.',
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
      if (mounted) await _load();
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Could not complete this action. Local records remain saved. Check your connection and retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _incidentTime(BuildContext context, Map<String, dynamic> record) {
    final date = DateTime.tryParse(record['occurredAt'] as String? ?? '');
    if (date == null) return 'Time not recorded';
    final local = date.toLocal();
    final labels = MaterialLocalizations.of(context);
    return '${labels.formatShortDate(local)} at ${labels.formatTimeOfDay(TimeOfDay.fromDateTime(local))}';
  }

  Future<void> _delete(Map<String, dynamic> record) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this incident?'),
        content: const Text(
          'This permanently removes the saved incident from this device. Drafts are kept separately.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await _operation(
        () => widget.repository.deleteGuestRecord(record['id'] as String),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_settingsOpen) return _options(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Saved incidents'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Incident options',
            onSelected: (value) {
              if (value == 'settings') setState(() => _settingsOpen = true);
              if (value == 'refresh') _load();
              if (value == 'drafts')
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AccidentReports(
                      repository: widget.repository,
                      onHelp: widget.onHelp,
                    ),
                  ),
                ).then((_) {
                  if (mounted) _load();
                });
            },
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: 'drafts',
                child: Text('New accident / saved drafts'),
              ),
              PopupMenuItem(
                value: 'settings',
                child: Text('Backup and guest record options'),
              ),
              PopupMenuItem(value: 'refresh', child: Text('Refresh')),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screen,
            0,
            AppSpacing.screen,
            24,
          ),
          children: [
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              SurfaceCard(
                child: Column(
                  children: [
                    Text(_error!),
                    TextButton(onPressed: _load, child: const Text('Retry')),
                  ],
                ),
              ),
            if (!_loading && _error == null && _records.isEmpty)
              ActionRow(
                icon: Icons.edit_note,
                title: 'No incidents saved',
                subtitle: 'Add a record when it is safe to do so',
                onTap: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AccidentForm(
                        repository: widget.repository,
                        onHelp: widget.onHelp,
                      ),
                    ),
                  );
                  if (mounted) _load();
                },
              ),
            for (final record in _records)
              ActionRow(
                icon: Icons.warning_amber_outlined,
                title: record['type'] as String? ?? 'Incident',
                subtitle:
                    '${_incidentTime(context, record)}${record['mileage'] == null ? '' : ' · ${record['mileage']} km'} · ${(record['photos'] as List? ?? []).length} photos',
                trailing: widget.repository.owner == null
                    ? PopupMenuButton<String>(
                        tooltip: 'Incident actions',
                        enabled: !_busy,
                        itemBuilder: (_) => const [
                          PopupMenuItem(
                            value: 'delete',
                            child: Text('Delete incident'),
                          ),
                        ],
                        onSelected: (_) => _delete(record),
                      )
                    : null,
                onTap: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AccidentForm(
                        repository: widget.repository,
                        record: record,
                        onHelp: widget.onHelp,
                      ),
                    ),
                  );
                  if (mounted) _load();
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _options(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Incident options'),
      leading: IconButton(
        tooltip: 'Back to saved incidents',
        onPressed: () => setState(() => _settingsOpen = false),
        icon: const Icon(Icons.arrow_back_ios_new),
      ),
      actions: [
        IconButton(
          onPressed: _busy ? null : _load,
          tooltip: 'Refresh records',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(AppSpacing.screen),
      children: [
        const Text(
          'Saved accident forms and photos are kept on this device. You can record past accidents by editing the time and location in a new form. Cloud text backup is optional; photos remain local.',
        ),
        if (_loading || _busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!),
        if (widget.repository.owner != null &&
            widget.repository.remote?.account.userId ==
                widget.repository.owner) ...[
          ExpansionTile(
            title: const Text('Account backup'),
            subtitle: Text(
              _backup
                  ? 'Text backup on. Photos stay on this device.'
                  : 'Text backup off. Records stay on this device.',
            ),
            children: [
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
                            title: const Text(
                              'Associate guest incident records?',
                            ),
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
          ),
        ],
        const SizedBox(height: 24),
        Text(
          'Saved accident forms',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Saved drafts are separate. Open a form to review or edit it.',
        ),
        const SizedBox(height: 12),
        if (!_loading && _error == null && _records.isEmpty)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'No incidents saved yet. In a draft, choose Save incident to keep it here.',
            ),
          ),
        ..._records.map(
          (r) => Card.outlined(
            child: Column(
              children: [
                ListTile(
                  title: Text(r['type'] as String? ?? 'Incident'),
                  subtitle: Text(
                    '${_incidentTime(context, r)}\n${r['location'] ?? ''}\n${r['pendingSync'] == false
                        ? 'Text backed up'
                        : _backup
                        ? 'Waiting for text backup'
                        : 'Saved locally'}',
                  ),
                  trailing: const Icon(Icons.edit_outlined),
                  onTap: () async {
                    await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => AccidentForm(
                          repository: widget.repository,
                          record: r,
                          onHelp: widget.onHelp,
                        ),
                      ),
                    );
                    if (mounted) await _load();
                  },
                ),
                if (r['cloudConflict'] == true)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      children: [
                        const Text(
                          'This incident has different local and cloud copies. Keep both to preserve each version and your local photos.',
                        ),
                        OutlinedButton(
                          onPressed: _busy
                              ? null
                              : () => _operation(() async {
                                  await widget.repository.keepBothCopies(
                                    r['id'] as String,
                                  );
                                  await widget.repository.sync();
                                }),
                          child: const Text('Keep both copies'),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

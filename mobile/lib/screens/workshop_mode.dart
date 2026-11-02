import 'package:flutter/material.dart';
import '../app_spacing.dart';
import '../app_state.dart';
import '../data/api_client.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/design_widgets.dart';
import '../widgets/sign_in_prompt.dart';
import 'service_forms.dart';

class WorkshopMode extends StatefulWidget {
  final AppState state;
  final Vehicle vehicle;
  const WorkshopMode({super.key, required this.state, required this.vehicle});
  @override
  State<WorkshopMode> createState() => _WorkshopModeState();
}

class _WorkshopModeState extends State<WorkshopMode> {
  final _form = GlobalKey<FormState>();
  final _notes = TextEditingController(), _workshop = TextEditingController();
  late final TextEditingController _mileage;
  late final String? _owner;
  final Set<String> _work = {}, _confirmed = {};
  List<ServiceRecord>? _pending;
  DateTime _date = DateTime.now();
  bool _review = false,
      _busy = false,
      _restoring = true,
      _restoreFailed = false;
  String? _error;
  String get _draftFile => 'workshop_${_owner}_${widget.vehicle.id}.json';
  bool get _sameOwner =>
      widget.state.signedIn && widget.state.accountId == _owner;

  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    _mileage = TextEditingController(text: '${widget.vehicle.mileage}');
    _restore();
  }

  Future<void> _restore() async {
    setState(() {
      _restoring = true;
      _restoreFailed = false;
      _error = null;
    });
    try {
      final data = await widget.state.store.read(_draftFile);
      final records = (data?['records'] as List? ?? [])
          .map(
            (row) =>
                ServiceRecord.fromJson(Map<String, dynamic>.from(row as Map)),
          )
          .toList();
      final ids = records.map((r) => r.id).toSet();
      final confirmed = (data?['confirmed'] as List? ?? []).cast<String>();
      if (records.any(
            (r) =>
                r.id.isEmpty ||
                r.vehicleId != widget.vehicle.id ||
                r.taskId == null ||
                r.taskId!.isEmpty ||
                r.mileage < 0,
          ) ||
          ids.length != records.length ||
          confirmed.toSet().length != confirmed.length ||
          confirmed.any((id) => !ids.contains(id))) {
        throw const FormatException('Invalid workshop draft');
      }
      if (!mounted || !_sameOwner) return;
      if (records.isNotEmpty) {
        _pending = records;
        _confirmed.addAll(confirmed);
        _review = true;
        _date = records.first.date;
        _mileage.text = '${records.first.mileage}';
        _notes.text = records.first.notes;
        _workshop.text = records.first.workshopName;
        _error =
            'An unfinished save was restored. Retry to finish saving these records.';
      }
    } catch (_) {
      if (mounted) {
        _restoreFailed = true;
        _error =
            'The unfinished workshop save could not be opened. Its file has been kept. Retry loading before continuing.';
      }
    } finally {
      if (mounted) setState(() => _restoring = false);
    }
  }

  Future<void> _keepPending() => widget.state.store.write(_draftFile, {
    'records': _pending!.map((r) => r.toJson()).toList(),
    'confirmed': _confirmed.toList(),
  });

  Future<void> _save() async {
    if (_busy || !_sameOwner) return;
    final batchId = DateTime.now().microsecondsSinceEpoch;
    final selectedTasks = widget.state
        .tasksFor(widget.vehicle.id)
        .where((t) => _work.contains(t.id))
        .toList();
    _pending ??= [
      for (final entry in selectedTasks.asMap().entries)
        ServiceRecord(
          id: 'workshop-$batchId-${entry.key}',
          vehicleId: widget.vehicle.id,
          taskId: entry.value.id,
          title: entry.value.title,
          category: entry.value.category,
          mileage: int.parse(_mileage.text),
          date: DateTime(_date.year, _date.month, _date.day),
          notes: _notes.text.trim(),
          workshopName: _workshop.text.trim(),
        ),
    ];
    if (_pending!.isEmpty) {
      setState(() {
        _pending = null;
        _review = false;
        _error = 'Select at least one current maintenance item.';
      });
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      // Journal before sending anything. A restart retries the same record IDs.
      await _keepPending();
      for (final record in _pending!) {
        if (!_sameOwner)
          throw const ApiException(
            'Your account changed. Reopen workshop mode for the original account.',
          );
        if (_confirmed.contains(record.id)) continue;
        await widget.state.addRecord(record);
        _confirmed.add(record.id);
        await _keepPending();
        if (mounted) setState(() {});
      }
      if (!_sameOwner)
        throw const ApiException(
          'Your account changed. Reopen workshop mode for the original account.',
        );
      await widget.state.refresh();
      if (!_sameOwner || widget.state.loadError != null)
        throw const ApiException(
          'Records were saved, but account data could not be refreshed. Retry to confirm.',
        );
      await widget.state.store.write(_draftFile, {
        'records': [],
        'confirmed': [],
      });
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted)
        setState(
          () => _error =
              '${_confirmed.length} of ${_pending!.length} records confirmed. '
              '${error is ApiException ? error.message : 'The save could not finish.'} '
              'Retry this save to finish without creating duplicate records.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addItem() async {
    await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          AddTaskDialog(state: widget.state, vehicle: widget.vehicle),
    );
    if (mounted) setState(() {});
  }

  Future<void> _stopSave() async {
    final stop = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Stop this unfinished save?'),
        content: const Text(
          'Records already saved remain in your account. This removes only the retry list on this device. Check service history before recording the work again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep retry list'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Stop save'),
          ),
        ],
      ),
    );
    if (stop != true || !mounted || !_sameOwner) return;
    try {
      await widget.state.store.write(_draftFile, {
        'records': [],
        'confirmed': [],
      });
      if (mounted && _sameOwner) Navigator.pop(context);
    } catch (_) {
      if (mounted)
        setState(
          () => _error =
              'The retry list could not be cleared. It has been kept. Try again.',
        );
    }
  }

  @override
  void dispose() {
    _notes.dispose();
    _workshop.dispose();
    _mileage.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) {
      if (!_sameOwner)
        return const Scaffold(
          body: SignInPrompt(
            icon: Icons.build_outlined,
            title: 'Sign in to continue',
            message:
                'Reopen workshop mode for the account that owns this vehicle.',
          ),
        );
      final tasks = widget.state.tasksFor(widget.vehicle.id);
      return PopScope(
        canPop: !_busy,
        child: Scaffold(
          appBar: AppBar(
            title: Text(_review ? 'Check what was added' : 'Workshop mode'),
          ),
          body: SafeArea(
            child: Form(
              key: _form,
              child: FormList(
                padding: const EdgeInsets.all(AppSpacing.screen),
                children: [
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.vehicle.name,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          _review
                              ? '${formatDate(_date)} · ${_mileage.text} km'
                              : 'Filling in on the owner’s phone',
                        ),
                        if (_review && _workshop.text.trim().isNotEmpty)
                          Text('Workshop: ${_workshop.text.trim()}'),
                      ],
                    ),
                  ),
                  if (_restoring || _busy) const LinearProgressIndicator(),
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
                  if (_restoreFailed)
                    TextButton(
                      onPressed: _restore,
                      child: const Text('Retry loading'),
                    ),
                  if (!_review && !_restoring && !_restoreFailed) ...[
                    TextFormField(
                      controller: _mileage,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Odometer at service (km)',
                      ),
                      validator: (value) {
                        final n = int.tryParse(value?.trim() ?? '');
                        if (n == null || n < 0 || n > 2147483647)
                          return 'Enter a valid mileage';
                        final current = widget.state.vehicles
                            .where((v) => v.id == widget.vehicle.id)
                            .firstOrNull;
                        if (current == null)
                          return 'This vehicle is no longer available';
                        if (n > current.mileage)
                          return 'Update the vehicle odometer in My Car first';
                        return null;
                      },
                    ),
                    OutlinedButton(
                      onPressed: () async {
                        final date = await showDatePicker(
                          context: context,
                          initialDate: _date,
                          firstDate: DateTime(2000),
                          lastDate: DateTime.now(),
                        );
                        if (date != null && mounted)
                          setState(() => _date = date);
                      },
                      child: Text('Service date: ${formatDate(_date)}'),
                    ),
                    Text(
                      'Work done',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    for (final task in tasks)
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(task.title),
                        subtitle: Text(maintenanceActionLabel(task.action)),
                        value: _work.contains(task.id),
                        onChanged: (value) => setState(() {
                          if (value == true) {
                            _work.add(task.id);
                          } else {
                            _work.remove(task.id);
                          }
                        }),
                      ),
                    TextButton.icon(
                      onPressed: _addItem,
                      icon: const Icon(Icons.add),
                      label: const Text('Add maintenance item'),
                    ),
                    TextFormField(
                      controller: _notes,
                      maxLines: 3,
                      maxLength: 10000,
                      decoration: const InputDecoration(
                        labelText: 'Notes (optional)',
                      ),
                    ),
                    TextFormField(
                      controller: _workshop,
                      maxLength: 200,
                      decoration: const InputDecoration(
                        labelText: 'Workshop name (optional)',
                      ),
                    ),
                    FilledButton(
                      onPressed: () {
                        if (!_form.currentState!.validate()) return;
                        if (!tasks.any((t) => _work.contains(t.id))) {
                          setState(
                            () => _error = 'Select at least one item of work.',
                          );
                          return;
                        }
                        FocusScope.of(context).unfocus();
                        setState(() {
                          _review = true;
                          _error = null;
                        });
                      },
                      child: const Text('Done — hand phone back'),
                    ),
                  ],
                  if (_review) ...[
                    if (_pending == null)
                      for (final task in tasks.where(
                        (t) => _work.contains(t.id),
                      ))
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(task.title),
                          subtitle: Text(maintenanceActionLabel(task.action)),
                        ),
                    if (_pending != null)
                      for (final record in _pending!)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(record.title),
                          subtitle: Text(record.category),
                          trailing: _confirmed.contains(record.id)
                              ? const Icon(Icons.check)
                              : null,
                        ),
                    if (_notes.text.trim().isNotEmpty) Text(_notes.text.trim()),
                    const Text(
                      'Check this matches the work performed. Each item is saved to your account and updates its maintenance history.',
                    ),
                    if (_pending != null)
                      const Text(
                        'This save can be resumed here after reopening the app. Confirmed records stay in account history.',
                      ),
                    FilledButton(
                      onPressed: _busy || widget.state.saving ? null : _save,
                      child: Text(
                        _busy
                            ? 'Saving…'
                            : _pending == null
                            ? 'Save service records'
                            : 'Retry save',
                      ),
                    ),
                    if (_pending == null)
                      OutlinedButton(
                        onPressed: () => setState(() => _review = false),
                        child: const Text('Edit'),
                      ),
                    if (_pending != null)
                      TextButton(
                        onPressed: _busy ? null : _stopSave,
                        child: const Text('Stop unfinished save'),
                      ),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    },
  );
}

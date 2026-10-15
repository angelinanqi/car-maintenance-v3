import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';

class ServiceLogDialog extends StatefulWidget {
  final AppState state;
  final Vehicle vehicle;
  final MaintenanceTask? task;
  final ServiceRecord? record;
  const ServiceLogDialog({
    super.key,
    required this.state,
    required this.vehicle,
    this.task,
    this.record,
  });
  @override
  State<ServiceLogDialog> createState() => _ServiceLogDialogState();
}

class _ServiceLogDialogState extends State<ServiceLogDialog> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _mileage = TextEditingController();
  final _cost = TextEditingController();
  final _notes = TextEditingController();
  late String _category;
  DateTime _date = DateTime.now();
  bool _busy = false;
  String? _error;
  MaintenanceTask? _task;
  @override
  void initState() {
    super.initState();
    _task = widget.task;
    final record = widget.record;
    _title.text = record?.title ?? widget.task?.title ?? '';
    _mileage.text = (record?.mileage ?? widget.vehicle.mileage).toString();
    _category =
        record?.category ??
        widget.task?.category ??
        maintenanceCategories.first;
    _date = record?.date ?? DateTime.now();
    _notes.text = record?.notes ?? '';
    _cost.text = record?.cost?.toString() ?? '';
  }

  @override
  void dispose() {
    _title.dispose();
    _mileage.dispose();
    _cost.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (_task == null && widget.record == null) {
      setState(
        () => _error =
            'Choose a maintenance item. Add an item first if none is available.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.state.addRecord(
        ServiceRecord(
          id:
              widget.record?.id ??
              DateTime.now().microsecondsSinceEpoch.toString(),
          taskId: widget.record?.taskId ?? _task?.id,
          vehicleId: widget.vehicle.id,
          title: _title.text.trim(),
          category: _category,
          mileage: int.parse(_mileage.text.trim()),
          date: DateTime(_date.year, _date.month, _date.day),
          notes: _notes.text.trim(),
          cost: double.tryParse(_cost.text.trim()),
        ),
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'Record could not be saved. Your entries have been kept.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.record == null ? 'Record maintenance' : 'Edit service record',
    ),
    content: SizedBox(
      width: 420,
      child: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('${widget.vehicle.name} • ${widget.vehicle.model}'),
              const SizedBox(height: 16),
              if (_error != null)
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              if (widget.task == null && widget.record == null)
                DropdownButtonFormField<String>(
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Maintenance item',
                  ),
                  items: widget.state
                      .tasksFor(widget.vehicle.id)
                      .map(
                        (t) => DropdownMenuItem(
                          value: t.id,
                          child: Text(
                            '${t.title} (${t.action})',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: _busy
                      ? null
                      : (id) => setState(() {
                          _task = widget.state
                              .tasksFor(widget.vehicle.id)
                              .firstWhere((t) => t.id == id);
                          _title.text = _task!.title;
                          _category = _task!.category;
                        }),
                ),
              TextFormField(
                controller: _title,
                readOnly: true,
                decoration: const InputDecoration(labelText: 'Service or task'),
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Enter the service performed'
                    : null,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: ValueKey(_category),
                initialValue: _category,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Category'),
                items: {...maintenanceCategories, _category}
                    .map(
                      (v) => DropdownMenuItem(
                        value: v,
                        child: Text(v, overflow: TextOverflow.ellipsis),
                      ),
                    )
                    .toList(),
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _category = value!),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _mileage,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Mileage (km)'),
                validator: (value) {
                  final number = int.tryParse(value?.trim() ?? '');
                  return number == null || number < 0
                      ? 'Enter zero or more kilometres'
                      : null;
                },
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.calendar_month),
                label: Text('Performed: ${formatDate(_date)}'),
                onPressed: _busy
                    ? null
                    : () async {
                        final date = await showDatePicker(
                          context: context,
                          initialDate: _date,
                          firstDate: DateTime(2000),
                          lastDate: DateTime.now(),
                        );
                        if (date != null && mounted) {
                          setState(() => _date = date);
                        }
                      },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _cost,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Cost (RM, optional)',
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) return null;
                  final cost = double.tryParse(value.trim());
                  return cost == null || !cost.isFinite || cost < 0
                      ? 'Enter a valid amount'
                      : null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _notes,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Notes (optional)',
                ),
              ),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: _busy ? null : () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _busy ? null : _save,
        child: Text(_busy ? 'Saving...' : 'Save record'),
      ),
    ],
  );
}

class AddTaskDialog extends StatefulWidget {
  final AppState state;
  final Vehicle vehicle;
  final MaintenanceTask? task;
  final String? initialItemId;
  const AddTaskDialog({
    super.key,
    required this.state,
    required this.vehicle,
    this.task,
    this.initialItemId,
  });
  @override
  State<AddTaskDialog> createState() => _AddTaskDialogState();
}

class _AddTaskDialogState extends State<AddTaskDialog> {
  final _form = GlobalKey<FormState>();
  final _title = TextEditingController();
  String _category = maintenanceCategories.first;
  bool _busy = false;
  String? _error;
  final _distance = TextEditingController(), _months = TextEditingController();
  List<Map<String, dynamic>> _items = [];
  Map<String, dynamic>? _item;
  String _source = 'none';
  String _action = 'service';
  bool _loading = true;
  @override
  void initState() {
    super.initState();
    final task = widget.task;
    _title.text = task?.title ?? '';
    _category = task?.category ?? maintenanceCategories.first;
    _source = task?.scheduleSource ?? 'none';
    _action = task?.action ?? 'service';
    _distance.text = task?.customRule?.distanceKm?.toString() ?? '';
    _months.text = task?.customRule?.months?.toString() ?? '';
    _loadItems();
  }

  Future<void> _loadItems() async {
    try {
      final rows = await widget.state.repository!.items();
      if (mounted) {
        setState(() {
          _items = rows;
          final matches = rows.where((r) => r['id'] == widget.initialItemId);
          if (widget.task == null && matches.isNotEmpty) {
            _item = matches.first;
            _title.text = _item!['title'] as String;
            _category = _item!['category'] as String;
            _action = _item!['action'] as String;
          }
        });
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error =
              'Standard items could not be loaded. You can still define a personal item. $error',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _title.dispose();
    _distance.dispose();
    _months.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.state.addTask(
        MaintenanceTask(
          id:
              widget.task?.id ??
              DateTime.now().microsecondsSinceEpoch.toString(),
          vehicleId: widget.vehicle.id,
          title: _title.text.trim(),
          category: _category,
          itemId: widget.task?.itemId ?? _item?['id'] as String?,
          action: _item?['action'] as String? ?? _action,
          isCustom: widget.task?.isCustom ?? _item == null,
          manufacturerRule: widget.task?.manufacturerRule,
          customRule: _source == 'custom'
              ? MaintenanceRule(
                  distanceKm: int.tryParse(_distance.text.trim()),
                  months: int.tryParse(_months.text.trim()),
                )
              : widget.task?.customRule,
          scheduleSource: _source,
          lessonIds:
              widget.task?.lessonIds ??
              (_item?['lessonIds'] as List? ?? []).cast<String>(),
        ),
      );
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Task could not be saved. Please retry.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.task == null
          ? 'Add item / custom schedule'
          : 'Edit maintenance item',
    ),
    content: SingleChildScrollView(
      child: Form(
        key: _form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_error != null) Text(_error!),
            if (_loading) const LinearProgressIndicator(),
            if (widget.task == null)
              DropdownButtonFormField<String>(
                key: ValueKey(_item?['id']),
                initialValue: _item?['id'] as String?,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Standard item or personal item',
                ),
                items: [
                  const DropdownMenuItem(
                    value: '',
                    child: Text('Create personal item'),
                  ),
                  ..._items.map(
                    (i) => DropdownMenuItem(
                      value: i['id'] as String,
                      child: Text(
                        '${i['title']} (${i['action']})',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                ],
                onChanged: _busy
                    ? null
                    : (id) => setState(() {
                        _item = id == ''
                            ? null
                            : _items.firstWhere((i) => i['id'] == id);
                        _title.text = _item?['title'] as String? ?? '';
                        _category =
                            _item?['category'] as String? ??
                            maintenanceCategories.first;
                      }),
              ),
            TextFormField(
              controller: _title,
              readOnly: _item != null || widget.task?.isCustom == false,
              decoration: const InputDecoration(labelText: 'Task name'),
              validator: (value) => value == null || value.trim().isEmpty
                  ? 'Enter a task name'
                  : null,
            ),
            const SizedBox(height: 16),
            if (_item == null && widget.task?.isCustom != false)
              DropdownButtonFormField<String>(
                initialValue: _action,
                decoration: const InputDecoration(labelText: 'Action'),
                items: ['service', 'inspect', 'replace']
                    .map((v) => DropdownMenuItem(value: v, child: Text(v)))
                    .toList(),
                onChanged: _busy ? null : (v) => setState(() => _action = v!),
              ),
            DropdownButtonFormField<String>(
              key: ValueKey(_category),
              initialValue: _category,
              isExpanded: true,
              items: {...maintenanceCategories, _category}
                  .map(
                    (v) => DropdownMenuItem(
                      value: v,
                      child: Text(v, overflow: TextOverflow.ellipsis),
                    ),
                  )
                  .toList(),
              onChanged: _busy
                  ? null
                  : (value) => setState(() => _category = value!),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _source,
              decoration: const InputDecoration(
                labelText: 'Active schedule source',
              ),
              items: [
                const DropdownMenuItem(
                  value: 'none',
                  child: Text('History only — no schedule'),
                ),
                const DropdownMenuItem(
                  value: 'custom',
                  child: Text('User-defined recurring schedule'),
                ),
                if (widget.task?.manufacturerRule != null)
                  const DropdownMenuItem(
                    value: 'manufacturer',
                    child: Text('Verified manufacturer schedule'),
                  ),
              ],
              onChanged: _busy ? null : (v) => setState(() => _source = v!),
            ),
            if (_source == 'custom') ...[
              const Text(
                'Your own reminder interval; this is not a manufacturer recommendation. Due when either limit is reached.',
              ),
              TextFormField(
                controller: _distance,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Every distance (km, optional)',
                ),
                validator: (v) => _intervalError(v),
              ),
              TextFormField(
                controller: _months,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Every time interval (months, optional)',
                ),
                validator: (v) => _intervalError(v),
              ),
            ],
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: _busy ? null : () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _busy ? null : _save,
        child: Text(_busy ? 'Saving...' : 'Save item'),
      ),
    ],
  );

  String? _intervalError(String? value) {
    if (value == null || value.trim().isEmpty) {
      return _distance.text.trim().isEmpty && _months.text.trim().isEmpty
          ? 'Enter at least one interval'
          : null;
    }
    return (int.tryParse(value.trim()) ?? 0) <= 0
        ? 'Enter a positive whole number'
        : null;
  }
}

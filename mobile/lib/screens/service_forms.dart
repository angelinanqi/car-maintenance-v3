import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/api_client.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/module_widgets.dart';

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
  final _title = TextEditingController(), _mileage = TextEditingController();
  final _cost = TextEditingController(), _notes = TextEditingController();
  final _workshop = TextEditingController();
  late String _category;
  String? _performedBy;
  late final String? _owner;
  late final String _recordId;
  DateTime _date = DateTime.now();
  bool _busy = false;
  String? _error;
  MaintenanceTask? _task;

  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    _recordId =
        widget.record?.id ?? DateTime.now().microsecondsSinceEpoch.toString();
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
    _workshop.text = record?.workshopName ?? '';
    _cost.text = record?.cost?.toString() ?? '';
    _performedBy = record == null ? 'self' : record.performedBy;
  }

  @override
  void dispose() {
    _title.dispose();
    _mileage.dispose();
    _cost.dispose();
    _notes.dispose();
    _workshop.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy) return;
    if (!_form.currentState!.validate()) return;
    if (_task == null && widget.record == null) {
      setState(
        () => _error = 'Choose the maintenance item this work belongs to.',
      );
      return;
    }
    if (!widget.state.signedIn || widget.state.accountId != _owner) {
      setState(
        () =>
            _error = 'Your account changed. Close this form and open it again.',
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
          id: _recordId,
          taskId: widget.record?.taskId ?? _task?.id,
          vehicleId: widget.vehicle.id,
          title: _title.text.trim(),
          category: _category,
          mileage: int.parse(_mileage.text.trim()),
          date: DateTime(_date.year, _date.month, _date.day),
          notes: _notes.text.trim(),
          workshopName: _workshop.text.trim(),
          performedBy: _performedBy,
          cost: double.tryParse(_cost.text.trim()),
        ),
      );
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Record could not be saved. Your entries have been kept. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addItem() async {
    final id = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          AddTaskDialog(state: widget.state, vehicle: widget.vehicle),
    );
    if (!mounted || id == null) return;
    final matches = widget.state
        .tasksFor(widget.vehicle.id)
        .where((t) => t.id == id);
    if (matches.isNotEmpty) {
      setState(() {
        _task = matches.first;
        _title.text = _task!.title;
        _category = _task!.category;
      });
    } else {
      setState(
        () => _error =
            'The item was saved, but the updated list could not be loaded. Close this form and refresh before recording work.',
      );
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) => MaintenanceForm(
      title: widget.record == null
          ? 'Record maintenance'
          : 'Edit service record',
      busy: _busy,
      onSave: _save,
      saveLabel: 'Save record',
      child: Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              widget.vehicle.name,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(widget.vehicle.model),
            const SizedBox(height: 12),
            const Text(
              'Record work that has already been done. This becomes part of this vehicle’s service history.',
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ),
            const ModuleSection(title: 'Work performed'),
            if (widget.task == null && widget.record == null) ...[
              DropdownButtonFormField<String>(
                key: ValueKey(_task?.id),
                initialValue: _task?.id,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Maintenance item',
                  helperText: 'Choose what was serviced, checked or replaced.',
                ),
                items: widget.state
                    .tasksFor(widget.vehicle.id)
                    .map(
                      (t) => DropdownMenuItem(
                        value: t.id,
                        child: Text(
                          '${t.title} (${maintenanceActionLabel(t.action)})',
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
                validator: (v) =>
                    v == null ? 'Select an item, or add one below' : null,
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: _busy ? null : _addItem,
                  icon: const Icon(Icons.add),
                  label: const Text('Add maintenance item'),
                ),
              ),
            ] else ...[
              Text(_title.text, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
            ],
            DropdownButtonFormField<String>(
              key: ValueKey(_category),
              initialValue: _category,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Category'),
              items:
                  {
                        ...maintenanceCategories,
                        ...widget.state
                            .tasksFor(widget.vehicle.id)
                            .map((task) => task.category),
                        _category,
                      }
                      .map(
                        (v) => DropdownMenuItem(
                          value: v,
                          child: Text(
                            v.isEmpty ? 'Uncategorised' : v,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
              onChanged: _busy ? null : (v) => setState(() => _category = v!),
            ),
            const ModuleSection(title: 'When was it done?'),
            OutlinedButton.icon(
              icon: const Icon(Icons.calendar_month_outlined),
              label: Text('Service date: ${formatDate(_date)}'),
              onPressed: _busy
                  ? null
                  : () async {
                      final today = DateTime.now();
                      final date = await showDatePicker(
                        context: context,
                        initialDate: _date.isAfter(today) ? today : _date,
                        firstDate: _date.year < 2000
                            ? DateTime(_date.year)
                            : DateTime(2000),
                        lastDate: today,
                      );
                      if (date != null && mounted) setState(() => _date = date);
                    },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _mileage,
              enabled: !_busy,
              keyboardType: TextInputType.number,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Odometer at service',
                suffixText: 'km',
                helperText:
                    'The total kilometres shown on the car when this work was done. This does not update the current odometer.',
              ),
              validator: (v) {
                final number = int.tryParse(v?.trim() ?? '');
                if (number == null || number < 0 || number > 2147483647) {
                  return 'Enter kilometres from 0 to 2,147,483,647';
                }
                if (number > widget.vehicle.mileage) {
                  return 'Exceeds the current odometer. Update it in My Car first.';
                }
                return null;
              },
            ),
            const ModuleSection(title: 'Service cost'),
            DropdownButtonFormField<String>(
              initialValue: _performedBy,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Who performed the maintenance?',
                helperText: 'Mechanic services need a cost, even if free.',
              ),
              items: const [
                DropdownMenuItem(value: 'self', child: Text('I did it myself')),
                DropdownMenuItem(value: 'mechanic', child: Text('A mechanic')),
              ],
              onChanged: _busy
                  ? null
                  : (value) => setState(() => _performedBy = value),
            ),
            if (widget.record != null && _performedBy == null)
              const Text(
                'Who performed this older service was not recorded. You can leave it unknown.',
              ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _cost,
              enabled: !_busy,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: _performedBy == 'mechanic'
                    ? 'Cost (required)'
                    : 'Cost (optional)',
                prefixText: 'RM ',
                helperText: _performedBy == 'mechanic'
                    ? 'Enter 0 only if this service was free.'
                    : 'Leave blank if the cost is unknown. Enter 0 if free.',
              ),
              validator: (v) => validateMaintenanceCost(
                v,
                required: _performedBy == 'mechanic',
              ),
            ),
            const ModuleSection(
              title: 'Additional details',
              description: 'Optional',
            ),
            TextFormField(
              controller: _notes,
              enabled: !_busy,
              maxLines: 4,
              maxLength: 10000,
              decoration: const InputDecoration(
                labelText: 'Notes',
                helperText: 'For example, details from your service receipt.',
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _workshop,
              enabled: !_busy,
              maxLength: 200,
              decoration: const InputDecoration(
                labelText: 'Workshop name (optional)',
              ),
            ),
          ],
        ),
      ),
    ),
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
  final _title = TextEditingController(),
      _distance = TextEditingController(),
      _months = TextEditingController();
  String _category = maintenanceCategories.first,
      _source = 'none',
      _action = 'service';
  late final String? _owner;
  late final String _taskId;
  bool _busy = false, _loading = true;
  String? _error, _catalogueError;
  List<Map<String, dynamic>> _items = [];
  List<String> _categories = [];
  Map<String, dynamic>? _item;

  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    _taskId =
        widget.task?.id ?? DateTime.now().microsecondsSinceEpoch.toString();
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
    setState(() {
      _loading = true;
      _catalogueError = null;
    });
    try {
      final rows = await widget.state.repository!.items();
      if (!mounted) return;
      setState(() {
        _categories = rows
            .map((row) => row['category'] as String? ?? '')
            .where((category) => category.isNotEmpty)
            .toSet()
            .toList();
        final existing = widget.state
            .tasksFor(widget.vehicle.id)
            .map((t) => t.itemId)
            .toSet();
        _items = rows.where((r) => !existing.contains(r['id'])).toList();
        final matches = rows.where(
          (r) => r['id'] == (widget.task?.itemId ?? widget.initialItemId),
        );
        if (matches.isNotEmpty) {
          if (widget.task != null) {
            _item = matches.first;
          } else if (!existing.contains(widget.initialItemId)) {
            _selectItem(matches.first);
          }
        }
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => _catalogueError =
              'Standard items could not be loaded. You can retry or create a personal item.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _selectItem(Map<String, dynamic>? item) {
    _item = item;
    _title.text = item?['title'] as String? ?? '';
    _category = item?['category'] as String? ?? maintenanceCategories.first;
    _action = item?['action'] as String? ?? 'service';
  }

  @override
  void dispose() {
    _title.dispose();
    _distance.dispose();
    _months.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy) return;
    if (!_form.currentState!.validate()) return;
    if (_source == 'manufacturer' && widget.task?.manufacturerRule == null) {
      setState(
        () => _error =
            'The manufacturer schedule is unavailable. Choose History only or your own schedule.',
      );
      return;
    }
    if (!widget.state.signedIn || widget.state.accountId != _owner) {
      setState(
        () =>
            _error = 'Your account changed. Close this form and open it again.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final id = _taskId;
      await widget.state.addTask(
        MaintenanceTask(
          id: id,
          vehicleId: widget.vehicle.id,
          title: _title.text.trim(),
          category: _category,
          itemId: widget.task?.itemId ?? _item?['id'] as String?,
          action: widget.task?.action ?? _action,
          isCustom: widget.task?.isCustom ?? _item == null,
          manufacturerRule: widget.task?.manufacturerRule,
          customRule: _source == 'custom'
              ? MaintenanceRule.fromJson({
                  ...?widget.task?.customRule?.toJson(),
                  'type': 'recurring',
                  'distanceKm': int.tryParse(_distance.text.trim()),
                  'months': int.tryParse(_months.text.trim()),
                })
              : widget.task?.customRule,
          scheduleSource: _source,
          lessonIds:
              widget.task?.lessonIds ??
              (_item?['lessonIds'] as List? ?? []).cast<String>(),
        ),
      );
      if (mounted) Navigator.pop(context, id);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Item could not be saved. Your entries have been kept. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final standard = _item != null || widget.task?.isCustom == false;
    return MaintenanceForm(
      title: widget.task == null
          ? 'Add maintenance item'
          : 'Edit maintenance item',
      busy: _busy,
      onSave: _save,
      saveLabel: 'Save item',
      child: Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              widget.vehicle.name,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'An item describes work you want to keep track of. You can record its history with or without a schedule.',
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ),
            const ModuleSection(title: 'Maintenance item'),
            if (_loading)
              const LinearProgressIndicator(
                semanticsLabel: 'Loading standard maintenance items',
              ),
            if (_catalogueError != null) ...[
              Text(_catalogueError!),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: _loadItems,
                  child: const Text('Retry standard items'),
                ),
              ),
            ],
            if (widget.task == null) ...[
              DropdownButtonFormField<String>(
                key: ValueKey(_item?['id']),
                initialValue: _item?['id'] as String? ?? '',
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Choose an item',
                  helperText: 'Use a standard item, or name your own.',
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
                        '${i['title']} (${maintenanceActionLabel(i['action'] as String)})',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                ],
                onChanged: _busy
                    ? null
                    : (id) => setState(
                        () => _selectItem(
                          id == ''
                              ? null
                              : _items.firstWhere((i) => i['id'] == id),
                        ),
                      ),
              ),
              const SizedBox(height: 16),
            ],
            TextFormField(
              controller: _title,
              enabled: !_busy,
              readOnly: standard,
              maxLength: 200,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: 'Item name'),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Enter an item name' : null,
            ),
            if ((_item?['description'] as String? ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(_item!['description'] as String),
              ),
            DropdownButtonFormField<String>(
              key: ValueKey(_action),
              initialValue: _action,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: 'Type of work',
                helperText: widget.task != null
                    ? 'The type stays with this item and its history.'
                    : null,
              ),
              items: ['service', 'inspect', 'replace']
                  .map(
                    (v) => DropdownMenuItem(
                      value: v,
                      child: Text(maintenanceActionLabel(v)),
                    ),
                  )
                  .toList(),
              onChanged: _busy || standard || widget.task != null
                  ? null
                  : (v) => setState(() => _action = v!),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              key: ValueKey(_category),
              initialValue: _category,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Category'),
              items: {...maintenanceCategories, ..._categories, _category}
                  .map(
                    (v) => DropdownMenuItem(
                      value: v,
                      child: Text(
                        v.isEmpty ? 'Uncategorised' : v,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                  .toList(),
              onChanged: _busy || standard
                  ? null
                  : (v) => setState(() => _category = v!),
            ),
            const ModuleSection(
              title: 'Schedule',
              description: 'Choose how this item’s next service is calculated.',
            ),
            DropdownButtonFormField<String>(
              key: ValueKey(_source),
              initialValue: _source,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Schedule source'),
              items: [
                const DropdownMenuItem(
                  value: 'none',
                  child: Text(
                    'History only · no schedule',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const DropdownMenuItem(
                  value: 'custom',
                  child: Text(
                    'My own recurring schedule',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (widget.task?.manufacturerRule != null)
                  const DropdownMenuItem(
                    value: 'manufacturer',
                    child: Text(
                      'Manufacturer schedule',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                if (_source == 'manufacturer' &&
                    widget.task?.manufacturerRule == null)
                  const DropdownMenuItem(
                    value: 'manufacturer',
                    enabled: false,
                    child: Text(
                      'Manufacturer schedule unavailable',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: _busy ? null : (v) => setState(() => _source = v!),
            ),
            const SizedBox(height: 12),
            if (_source == 'none')
              const Text(
                'Keep service records without calculating a next service date or distance.',
              ),
            if (_source == 'manufacturer' &&
                widget.task?.manufacturerRule != null)
              const Text(
                'Uses the published, verified schedule for this vehicle. Your personal interval is kept if you switch back.',
              ),
            if (_source == 'manufacturer' &&
                widget.task?.manufacturerRule == null)
              const Text(
                'The previously selected manufacturer schedule is no longer available. Choose History only or your own schedule.',
              ),
            if (_source == 'custom') ...[
              const Text(
                'Your interval is a personal reminder, not a manufacturer recommendation. Enter a distance, a number of months, or both. With both, work is due when either limit is reached.',
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _distance,
                enabled: !_busy,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Repeat every distance',
                  suffixText: 'km',
                  helperText: 'Optional if you enter a time interval below.',
                ),
                validator: _intervalError,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _months,
                enabled: !_busy,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.done,
                decoration: const InputDecoration(
                  labelText: 'Repeat every time interval',
                  suffixText: 'months',
                  helperText: 'Optional if you enter a distance above.',
                ),
                validator: _intervalError,
              ),
              const SizedBox(height: 12),
              const Text(
                'Record a known service to give this recurring schedule a starting point.',
              ),
            ],
          ],
        ),
      ),
    );
  }

  String? _intervalError(String? value) {
    if (value == null || value.trim().isEmpty) {
      return _distance.text.trim().isEmpty && _months.text.trim().isEmpty
          ? 'Enter a distance or a number of months'
          : null;
    }
    return (int.tryParse(value.trim()) ?? 0) <= 0
        ? 'Enter a positive whole number'
        : null;
  }
}

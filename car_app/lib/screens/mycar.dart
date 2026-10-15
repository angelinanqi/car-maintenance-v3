import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/maintenance.dart';
import '../widgets/vehicle_selector.dart';
import 'service_forms.dart';
import 'vehicle_profile.dart';

class MyCar extends StatefulWidget {
  final AppState state;
  final int logRequest;
  final String? requestedItemId;
  final int itemRequestNumber;
  final void Function(Map<String, dynamic>)? onAsk;
  final void Function(String)? onLearn;
  const MyCar({
    super.key,
    required this.state,
    this.logRequest = 0,
    this.requestedItemId,
    this.itemRequestNumber = 0,
    this.onAsk,
    this.onLearn,
  });
  @override
  State<MyCar> createState() => _MyCarState();
}

class _MyCarState extends State<MyCar> {
  bool _schedule = true;
  String _filter = 'All';
  @override
  void didUpdateWidget(MyCar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.logRequest != oldWidget.logRequest) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _log();
      });
    }
    if (widget.itemRequestNumber != oldWidget.itemRequestNumber &&
        widget.requestedItemId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        final tasks = widget.state
            .tasksFor(widget.state.selectedVehicle?.id ?? '')
            .where((t) => t.itemId == widget.requestedItemId);
        if (tasks.isNotEmpty) {
          _detail(tasks.first);
        } else {
          showDialog(
            context: context,
            builder: (_) => AlertDialog(
              title: const Text('Maintenance item not configured'),
              content: const Text(
                'Register a vehicle or add this item to your active vehicle. No manufacturer interval is assumed.',
              ),
              actions: [
                if (widget.state.signedIn &&
                    widget.state.selectedVehicle != null)
                  TextButton(
                    onPressed: () {
                      Navigator.pop(context);
                      showDialog(
                        context: context,
                        builder: (_) => AddTaskDialog(
                          state: widget.state,
                          vehicle: widget.state.selectedVehicle!,
                          initialItemId: widget.requestedItemId,
                        ),
                      );
                    },
                    child: const Text('Add this item'),
                  ),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Close'),
                ),
              ],
            ),
          );
        }
      });
    }
  }

  Future<void> _detail(MaintenanceTask task) async {
    final vehicle = widget.state.selectedVehicle!;
    final history = widget.state
        .recordsFor(vehicle.id)
        .where((r) => r.taskId == task.id)
        .toList();
    await showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(task.title),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${task.action} • ${task.scheduleSource == 'custom'
                    ? 'User-defined schedule'
                    : task.scheduleSource == 'manufacturer'
                    ? 'Verified manufacturer schedule'
                    : 'History only'}',
              ),
              Text(widget.state.statusFor(task).description),
              if (task.manufacturerRule != null &&
                  task.scheduleSource != 'manufacturer')
                const Text(
                  'Verified manufacturer information is available. Your personal schedule has been retained; choose a source under Edit schedule.',
                ),
              if (task.activeRule != null) ...[
                Text(
                  'Conditions: ${task.activeRule!.conditions.isEmpty ? 'None specified' : task.activeRule!.conditions}',
                ),
                Text(task.activeRule!.notes),
                if (task.activeRule!.sourceDocumentId != null)
                  Text(
                    'Source document ${task.activeRule!.sourceDocumentId}, page ${task.activeRule!.sourcePage ?? 'not supplied'}',
                  ),
              ],
              Text(
                history.isEmpty
                    ? 'Previous maintenance not recorded. Add known service information for reliable recurring calculations.'
                    : 'Last service: ${formatDate(history.first.date)} • ${history.first.mileage} km',
              ),
              TextButton(
                onPressed: () {
                  Navigator.pop(dialogContext);
                  _log(task);
                },
                child: const Text('Record maintenance'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.pop(dialogContext);
                  showDialog(
                    context: context,
                    builder: (_) => AddTaskDialog(
                      state: widget.state,
                      vehicle: vehicle,
                      task: task,
                    ),
                  );
                },
                child: const Text('Edit item / schedule source'),
              ),
              for (final id in task.lessonIds)
                TextButton(
                  onPressed: () {
                    Navigator.pop(dialogContext);
                    widget.onLearn?.call(id);
                  },
                  child: const Text('Learn why this matters'),
                ),
              OutlinedButton.icon(
                icon: const Icon(Icons.auto_awesome),
                label: const Text('Ask AI about this item'),
                onPressed: () {
                  Navigator.pop(dialogContext);
                  widget.onAsk?.call({
                    'kind': 'Maintenance item',
                    'id': task.id,
                    'title': task.title,
                    'details': {
                      'vehicle': '${vehicle.model} ${vehicle.year}',
                      'odometerKm': vehicle.mileage,
                      'action': task.action,
                      'scheduleSource': task.scheduleSource,
                      'schedule': task.activeRule?.toJson(),
                      'calculatedStatus': widget.state
                          .statusFor(task)
                          .description,
                      'lastService': history.isEmpty
                          ? null
                          : history.first.toJson(),
                    },
                  });
                },
              ),
              if (task.isCustom)
                TextButton(
                  onPressed: () async {
                    try {
                      await widget.state.removeTask(task);
                      if (dialogContext.mounted) Navigator.pop(dialogContext);
                    } catch (error) {
                      if (dialogContext.mounted) {
                        ScaffoldMessenger.of(
                          dialogContext,
                        ).showSnackBar(SnackBar(content: Text('$error')));
                      }
                    }
                  },
                  child: const Text('Remove personal item'),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _log([MaintenanceTask? task]) async {
    final vehicle = widget.state.selectedVehicle;
    if (vehicle == null) return;
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) =>
          ServiceLogDialog(state: widget.state, vehicle: vehicle, task: task),
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Service record saved to your account.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final vehicle = widget.state.selectedVehicle;
    final records = vehicle == null
        ? <ServiceRecord>[]
        : widget.state.recordsFor(vehicle.id);
    final filtered = records
        .where((r) => _filter == 'All' || r.category == _filter)
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Maintenance'),
        backgroundColor: Theme.of(context).colorScheme.primaryContainer,
      ),
      body: !widget.state.signedIn
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'Sign in to register a vehicle and track maintenance. Emergency assistance and learning remain available.',
                ),
              ),
            )
          : ListView(
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                VehicleSelector(state: widget.state),
                if (vehicle == null)
                  const Padding(
                    padding: EdgeInsets.all(20),
                    child: Text(
                      'Your vehicle maintenance records will appear here.',
                    ),
                  )
                else
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Maintenance',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        const SizedBox(height: 12),
                        Text('Current odometer: ${vehicle.mileage} km'),
                        TextButton(
                          onPressed: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => VehicleProfilePage(
                                state: widget.state,
                                vehicle: vehicle,
                              ),
                            ),
                          ),
                          child: const Text('Update current odometer'),
                        ),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            ChoiceChip(
                              label: const Text('Schedule'),
                              selected: _schedule,
                              onSelected: (_) =>
                                  setState(() => _schedule = true),
                            ),
                            ChoiceChip(
                              label: const Text('History'),
                              selected: !_schedule,
                              onSelected: (_) =>
                                  setState(() => _schedule = false),
                            ),
                            FilledButton.icon(
                              onPressed: widget.state.saving ? null : _log,
                              icon: const Icon(Icons.add),
                              label: const Text('Log service'),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        if (_schedule) ...[
                          Card.outlined(
                            child: Padding(
                              padding: EdgeInsets.all(16),
                              child: Text(
                                vehicle.manufacturerScheduleAvailable
                                    ? 'Verified manufacturer information is available. Custom schedules are kept separately. Review schedule sources for each item.'
                                    : 'Manufacturer maintenance schedule unavailable. You can still record maintenance or create your own reminders.',
                              ),
                            ),
                          ),
                          Align(
                            alignment: Alignment.centerLeft,
                            child: OutlinedButton.icon(
                              onPressed: widget.state.saving
                                  ? null
                                  : () => showDialog(
                                      context: context,
                                      builder: (_) => AddTaskDialog(
                                        state: widget.state,
                                        vehicle: vehicle,
                                      ),
                                    ),
                              icon: const Icon(Icons.edit_note),
                              label: const Text('Add item'),
                            ),
                          ),
                          if (widget.state.tasksFor(vehicle.id).isEmpty)
                            const Padding(
                              padding: EdgeInsets.all(16),
                              child: Text(
                                'No maintenance items yet. Add an item or log a service.',
                              ),
                            ),
                          ...widget.state.tasksFor(vehicle.id).map((task) {
                            final matches = records.where(
                              (r) => r.taskId == task.id,
                            );
                            final last = matches.isEmpty ? null : matches.first;
                            return Card.outlined(
                              child: ListTile(
                                title: Text(task.title),
                                subtitle: Text(
                                  '${task.category} • ${task.action} • ${task.scheduleSource}\nLast serviced: ${last == null ? 'Not recorded' : '${last.mileage} km • ${formatDate(last.date)}'}\n${widget.state.statusFor(task).description}',
                                ),
                                isThreeLine: true,
                                onTap: () => _detail(task),
                              ),
                            );
                          }),
                        ] else ...[
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: ['All', ...maintenanceCategories]
                                .map(
                                  (category) => FilterChip(
                                    label: Text(category),
                                    selected: _filter == category,
                                    onSelected: (_) =>
                                        setState(() => _filter = category),
                                  ),
                                )
                                .toList(),
                          ),
                          const SizedBox(height: 16),
                          if (filtered.isEmpty)
                            const Text('No service records in this category.'),
                          for (var i = 0; i < filtered.length; i++) ...[
                            if (i == 0 ||
                                filtered[i].date.month !=
                                    filtered[i - 1].date.month ||
                                filtered[i].date.year !=
                                    filtered[i - 1].date.year)
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  vertical: 12,
                                ),
                                child: Text(
                                  '${filtered[i].date.month}/${filtered[i].date.year}',
                                  style: Theme.of(
                                    context,
                                  ).textTheme.titleMedium,
                                ),
                              ),
                            Card.outlined(
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      filtered[i].title,
                                      style: Theme.of(
                                        context,
                                      ).textTheme.titleMedium,
                                    ),
                                    Text(
                                      '${formatDate(filtered[i].date)} • ${filtered[i].mileage} km',
                                    ),
                                    Text(filtered[i].category),
                                    if (filtered[i].notes.isNotEmpty)
                                      Text(filtered[i].notes),
                                    TextButton(
                                      onPressed: () => showDialog(
                                        context: context,
                                        builder: (_) => ServiceLogDialog(
                                          state: widget.state,
                                          vehicle: vehicle,
                                          record: filtered[i],
                                        ),
                                      ),
                                      child: const Text('Correct this record'),
                                    ),
                                    Text(
                                      filtered[i].cost == null
                                          ? 'Cost not recorded'
                                          : 'RM ${filtered[i].cost!.toStringAsFixed(2)}',
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ],
                      ],
                    ),
                  ),
              ],
            ),
    );
  }
}

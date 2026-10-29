import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/module_widgets.dart';
import '../widgets/vehicle_selector.dart';
import '../widgets/sign_in_prompt.dart';
import 'service_forms.dart';
import 'vehicle_profile.dart';

class MyCar extends StatefulWidget {
  final AppState state;
  final int logRequest;
  final int scheduleRequest;
  final String? requestedItemId;
  final int itemRequestNumber;
  final void Function(Map<String, dynamic>)? onAsk;
  final void Function(String)? onLearn;
  final VoidCallback? onPlan;
  const MyCar({
    super.key,
    required this.state,
    this.logRequest = 0,
    this.scheduleRequest = 0,
    this.requestedItemId,
    this.itemRequestNumber = 0,
    this.onAsk,
    this.onLearn,
    this.onPlan,
  });
  @override
  State<MyCar> createState() => _MyCarState();
}

class _MyCarState extends State<MyCar> {
  bool _schedule = true;
  String _filter = 'All';

  void _garage() => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (sheetContext) => ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Your garage',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              for (final vehicle in widget.state.vehicles)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    widget.state.selectedVehicle?.id == vehicle.id
                        ? Icons.check_circle
                        : Icons.directions_car_outlined,
                  ),
                  title: Text(vehicle.name),
                  subtitle: Text(
                    '${vehicle.model}\n${vehicle.plateNumber} · ${vehicle.mileage} km',
                  ),
                  trailing: IconButton(
                    tooltip: 'Edit ${vehicle.name}',
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: widget.state.saving
                        ? null
                        : () {
                            Navigator.pop(sheetContext);
                            Navigator.push(
                              this.context,
                              MaterialPageRoute(
                                builder: (_) => VehicleProfilePage(
                                  state: widget.state,
                                  vehicle: vehicle,
                                ),
                              ),
                            );
                          },
                  ),
                  onTap: widget.state.saving
                      ? null
                      : () async {
                          try {
                            await widget.state.selectVehicle(vehicle.id);
                            if (sheetContext.mounted)
                              Navigator.pop(sheetContext);
                          } catch (_) {
                            if (context.mounted)
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Could not change vehicle. Please retry.',
                                  ),
                                ),
                              );
                          }
                        },
                ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: widget.state.saving
                    ? null
                    : () {
                        Navigator.pop(sheetContext);
                        Navigator.push(
                          this.context,
                          MaterialPageRoute(
                            builder: (_) =>
                                VehicleProfilePage(state: widget.state),
                          ),
                        );
                      },
                icon: const Icon(Icons.add),
                label: const Text('Add vehicle'),
              ),
            ],
          ),
        ),
      ),
    ),
  );

  @override
  void initState() {
    super.initState();
    if (widget.logRequest > 0 || widget.requestedItemId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        if (widget.requestedItemId != null) {
          _openRequested();
        } else {
          _log();
        }
      });
    }
  }

  @override
  void didUpdateWidget(MyCar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.scheduleRequest != oldWidget.scheduleRequest) {
      _schedule = true;
    }
    if (widget.logRequest != oldWidget.logRequest) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _log();
      });
    }
    if (widget.itemRequestNumber != oldWidget.itemRequestNumber &&
        widget.requestedItemId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _openRequested();
      });
    }
  }

  Future<void> _openRequested() async {
    final vehicle = widget.state.selectedVehicle;
    final tasks = widget.state
        .tasksFor(vehicle?.id ?? '')
        .where((t) => t.itemId == widget.requestedItemId);
    if (tasks.isNotEmpty) {
      _detail(tasks.first);
      return;
    }
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Add this maintenance item'),
        content: Text(
          vehicle == null
              ? 'Sign in and select a registered vehicle in My Car to manage this maintenance item.'
              : 'This item is not in ${vehicle.name}’s maintenance list. Add it to record work or set a personal schedule.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Close'),
          ),
          if (widget.state.signedIn && vehicle != null)
            FilledButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                _addItem(vehicle, initialItemId: widget.requestedItemId);
              },
              child: const Text('Add this item'),
            ),
        ],
      ),
    );
  }

  Future<void> _addItem(Vehicle vehicle, {String? initialItemId}) async {
    final id = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AddTaskDialog(
        state: widget.state,
        vehicle: vehicle,
        initialItemId: initialItemId,
      ),
    );
    if (id != null && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Maintenance item saved.')));
    }
  }

  void _detail(MaintenanceTask task) {
    Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => _MaintenanceDetail(
          state: widget.state,
          taskId: task.id,
          vehicleId: task.vehicleId,
          onAsk: widget.onAsk,
          onLearn: widget.onLearn,
        ),
      ),
    );
  }

  Future<void> _log() async {
    final vehicle = widget.state.selectedVehicle;
    if (vehicle == null || !widget.state.signedIn) return;
    final saved = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ServiceLogDialog(state: widget.state, vehicle: vehicle),
    );
    if (saved == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Service record saved to your account.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) {
      final state = widget.state;
      final vehicle = state.selectedVehicle;
      final records = vehicle == null
          ? <ServiceRecord>[]
          : state.recordsFor(vehicle.id);
      final tasks = vehicle == null
          ? <MaintenanceTask>[]
          : state.tasksFor(vehicle.id);
      final categories = {
        'All',
        ...maintenanceCategories,
        ...records.map((r) => r.category),
      };
      final filter = categories.contains(_filter) ? _filter : 'All';
      final filtered = records
          .where((r) => filter == 'All' || r.category == filter)
          .toList();
      final rows = <Widget>[
        if (state.loading)
          const LinearProgressIndicator(semanticsLabel: 'Loading maintenance'),
        if (state.loadError != null)
          ModuleMessage(
            title: 'Could not refresh maintenance',
            message:
                'Check your connection and try again. Any information already loaded is kept below.',
            action: OutlinedButton.icon(
              onPressed: state.loading ? null : state.refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ),
        if (vehicle == null && !state.loading && state.loadError == null)
          ModuleMessage(
            icon: Icons.directions_car_outlined,
            title: 'Add your first vehicle',
            message:
                'Keep its maintenance schedule and service history together.',
            action: FilledButton.icon(
              onPressed: state.saving
                  ? null
                  : () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => VehicleProfilePage(state: state),
                      ),
                    ),
              icon: const Icon(Icons.add),
              label: const Text('Add vehicle'),
            ),
          ),
        if (vehicle != null) ...[
          VehicleSelector(state: state),
          if (widget.onPlan != null)
            TextButton.icon(
              onPressed: state.loading ? null : widget.onPlan,
              icon: const Icon(Icons.event_note_outlined),
              label: const Text('Plan my next service'),
            ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                '${vehicle.mileage} km',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              TextButton.icon(
                icon: const Icon(Icons.edit_outlined, size: 18),
                label: const Text('Update odometer'),
                onPressed: state.saving || state.loading
                    ? null
                    : () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => VehicleProfilePage(
                            state: state,
                            vehicle: vehicle,
                          ),
                        ),
                      ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: state.saving || state.loading ? null : _log,
            icon: const Icon(Icons.add),
            label: const Text('Log service'),
          ),
          const SizedBox(height: 24),
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: true, label: Text('Schedule')),
              ButtonSegment(value: false, label: Text('History')),
            ],
            selected: {_schedule},
            onSelectionChanged: (v) => setState(() => _schedule = v.first),
          ),
          if (_schedule) ...[
            Padding(
              padding: const EdgeInsets.only(top: 20, bottom: 8),
              child: Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 12,
                children: [
                  Text(
                    'Maintenance',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  TextButton.icon(
                    onPressed: state.saving || state.loading
                        ? null
                        : () => _addItem(vehicle),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Add item'),
                  ),
                ],
              ),
            ),
            if (!vehicle.manufacturerScheduleAvailable)
              const Text(
                'No manufacturer schedule published. You can set personal intervals.',
              ),
            if (tasks.isEmpty)
              const ModuleMessage(
                icon: Icons.build_outlined,
                title: 'Start with a maintenance item',
                message:
                    'Add an item for work you want to track, then record its service history. A schedule is optional.',
              ),
            for (final task in tasks) ...[
              _TaskRow(
                task: task,
                status: state.statusFor(task),
                onTap: () => _detail(task),
              ),
              const Divider(height: 1),
            ],
          ] else ...[
            const ModuleSection(title: 'Service history'),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: categories
                  .map(
                    (category) => FilterChip(
                      label: Text(category),
                      selected: filter == category,
                      onSelected: (_) => setState(() => _filter = category),
                    ),
                  )
                  .toList(),
            ),
            if (filtered.isEmpty)
              ModuleMessage(
                icon: Icons.history,
                title: records.isEmpty
                    ? 'No service records yet'
                    : 'No records in this category',
                message: records.isEmpty
                    ? 'Use Log service to record work that has been done.'
                    : 'Choose another category or All to see more records.',
              ),
            for (var i = 0; i < filtered.length; i++) ...[
              if (i == 0 ||
                  filtered[i].date.month != filtered[i - 1].date.month ||
                  filtered[i].date.year != filtered[i - 1].date.year)
                ModuleSection(
                  title:
                      '${_months[filtered[i].date.month - 1]} ${filtered[i].date.year}',
                ),
              ListTile(
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
                title: Text(filtered[i].title),
                subtitle: Text(
                  '${formatDate(filtered[i].date)} · ${filtered[i].mileage} km\n${filtered[i].category}${filtered[i].cost == null ? '' : ' · RM ${filtered[i].cost!.toStringAsFixed(2)}'}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () =>
                    _recordDetail(context, state, vehicle, filtered[i]),
              ),
              const Divider(height: 1),
            ],
          ],
        ],
      ];
      return Scaffold(
        appBar: AppBar(
          title: const Text('My Car'),
          actions: [
            if (state.signedIn)
              IconButton(
                tooltip: 'Manage garage',
                onPressed: state.loading || state.saving ? null : _garage,
                icon: const Icon(Icons.garage_outlined),
              ),
            if (state.signedIn)
              IconButton(
                tooltip: 'Refresh maintenance',
                onPressed: state.loading || state.saving ? null : state.refresh,
                icon: const Icon(Icons.refresh),
              ),
          ],
        ),
        body: !state.signedIn
            ? const SignInPrompt(
                icon: Icons.directions_car_outlined,
                title: 'Your car, all in one place',
                message:
                    'Sign in to register a vehicle and track maintenance. Emergency assistance and learning remain available.',
              )
            : RefreshIndicator(
                onRefresh: state.refresh,
                child: ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
                  itemCount: rows.length,
                  itemBuilder: (_, i) => rows[i],
                ),
              ),
      );
    },
  );
}

const _months = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

class _TaskRow extends StatelessWidget {
  final MaintenanceTask task;
  final MaintenanceStatus status;
  final VoidCallback onTap;
  const _TaskRow({
    required this.task,
    required this.status,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  task.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${maintenanceActionLabel(task.action)} · ${scheduleSourceLabel(task.scheduleSource)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _StatusLabel(status: status),
              if (status.nextKm != null || status.nextDate != null)
                Text(_nextService(status)),
            ],
          ),
        ],
      ),
    ),
  );
}

String _nextService(MaintenanceStatus status) => [
  if (status.nextKm != null) 'At ${status.nextKm} km',
  if (status.nextDate != null) 'By ${formatDate(status.nextDate!)}',
].join(' · ');

class _StatusLabel extends StatelessWidget {
  final MaintenanceStatus status;
  const _StatusLabel({required this.status});
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final due = status.label == 'Due / Overdue';
    final soon = status.label == 'Due soon';
    return Semantics(
      label: 'Schedule status: ${status.label}',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: due
              ? colors.errorContainer
              : soon
              ? colors.primaryContainer
              : colors.surfaceContainer,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          status.label,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: due
                ? colors.onErrorContainer
                : soon
                ? colors.onPrimaryContainer
                : colors.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _MaintenanceDetail extends StatelessWidget {
  final AppState state;
  final String taskId, vehicleId;
  final void Function(Map<String, dynamic>)? onAsk;
  final void Function(String)? onLearn;
  const _MaintenanceDetail({
    required this.state,
    required this.taskId,
    required this.vehicleId,
    this.onAsk,
    this.onLearn,
  });

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: state,
    builder: (context, _) {
      final vehicles = state.vehicles.where((v) => v.id == vehicleId);
      final tasks = state.tasksFor(vehicleId).where((t) => t.id == taskId);
      if (!state.signedIn || vehicles.isEmpty || tasks.isEmpty) {
        return Scaffold(
          appBar: AppBar(title: const Text('Maintenance item')),
          body: const Padding(
            padding: EdgeInsets.all(20),
            child: ModuleMessage(
              title: 'Item no longer available',
              message:
                  'Return to My Car to view your current maintenance items.',
            ),
          ),
        );
      }
      final vehicle = vehicles.first, task = tasks.first;
      final status = state.statusFor(task);
      final history = state
          .recordsFor(vehicleId)
          .where((r) => r.taskId == task.id)
          .toList();
      return Scaffold(
        appBar: AppBar(title: const Text('Maintenance item')),
        body: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            Text(vehicle.name, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            Text(task.title, style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            Text('${task.category} · ${maintenanceActionLabel(task.action)}'),
            const SizedBox(height: 20),
            Align(
              alignment: Alignment.centerLeft,
              child: _StatusLabel(status: status),
            ),
            if (_nextService(status).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  _nextService(status),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            if (status.remainingKm != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  status.remainingKm! < 0
                      ? '${-status.remainingKm!} km past the scheduled distance'
                      : '${status.remainingKm} km to the scheduled distance',
                ),
              ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: state.saving || state.loading
                  ? null
                  : () async {
                      final saved = await showDialog<bool>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => ServiceLogDialog(
                          state: state,
                          vehicle: vehicle,
                          task: task,
                        ),
                      );
                      if (saved == true && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Service record saved.'),
                          ),
                        );
                      }
                    },
              icon: const Icon(Icons.add),
              label: const Text('Record maintenance'),
            ),
            ModuleSection(
              title: 'Schedule',
              description: scheduleSourceLabel(task.scheduleSource),
            ),
            if (task.activeRule == null)
              Text(
                task.scheduleSource == 'none'
                    ? 'This item keeps history without calculating when work is next due.'
                    : 'The selected schedule is unavailable. Edit this item to choose another schedule source.',
              ),
            if (task.activeRule != null) _RuleDetails(rule: task.activeRule!),
            if (task.scheduleSource == 'custom')
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text(
                  'This is your personal interval, not a manufacturer recommendation.',
                ),
              ),
            if (task.manufacturerRule != null &&
                task.scheduleSource != 'manufacturer')
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Available manufacturer schedule'),
                subtitle: const Text(
                  'Your current schedule is kept until you choose a different source.',
                ),
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: _RuleDetails(rule: task.manufacturerRule!),
                  ),
                ],
              ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: state.saving || state.loading
                    ? null
                    : () => showDialog<String>(
                        context: context,
                        barrierDismissible: false,
                        builder: (_) => AddTaskDialog(
                          state: state,
                          vehicle: vehicle,
                          task: task,
                        ),
                      ),
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Edit item or schedule'),
              ),
            ),
            ModuleSection(
              title: 'Recorded work',
              description: history.isEmpty
                  ? 'No work recorded yet. A recurring schedule needs a known service as its starting point.'
                  : '${history.length} ${history.length == 1 ? 'record' : 'records'} for this item',
            ),
            for (final record in history)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(
                  '${formatDate(record.date)} · ${record.mileage} km',
                ),
                subtitle: Text(record.title),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _recordDetail(context, state, vehicle, record),
              ),
            if (onLearn != null && task.lessonIds.isNotEmpty) ...[
              const ModuleSection(title: 'Understand this item'),
              for (var i = 0; i < task.lessonIds.length; i++)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.menu_book_outlined),
                  title: Text(
                    task.lessonIds.length == 1
                        ? 'Read related learning guide'
                        : 'Read related guide ${i + 1}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    Navigator.pop(context);
                    onLearn!(task.lessonIds[i]);
                  },
                ),
            ],
            if (onAsk != null) ...[
              const SizedBox(height: 16),
              OutlinedButton.icon(
                icon: const Icon(Icons.chat_bubble_outline),
                label: const Text('Ask AI about this item'),
                onPressed: () {
                  Navigator.pop(context);
                  onAsk!({
                    'kind': 'Maintenance item',
                    'id': task.id,
                    'title': task.title,
                    'details': {
                      'vehicle': '${vehicle.model} ${vehicle.year}',
                      'odometerKm': vehicle.mileage,
                      'action': task.action,
                      'scheduleSource': task.scheduleSource,
                      'schedule': task.activeRule?.toJson(),
                      'calculatedStatus': status.description,
                      'lastService': history.isEmpty
                          ? null
                          : history.first.toJson(),
                    },
                  });
                },
              ),
            ],
            if (task.manufacturerRule == null) ...[
              const Divider(height: 40),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  style: TextButton.styleFrom(
                    foregroundColor: Theme.of(context).colorScheme.error,
                  ),
                  onPressed: state.saving || state.loading
                      ? null
                      : () => _remove(context, task),
                  icon: const Icon(Icons.delete_outline),
                  label: const Text('Remove item'),
                ),
              ),
            ],
          ],
        ),
      );
    },
  );

  Future<void> _remove(BuildContext context, MaintenanceTask task) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Remove ${task.title}?'),
        content: const Text(
          'This removes the item and its schedule. Existing service records stay in this vehicle’s history.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Keep item'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Remove item'),
          ),
        ],
      ),
    );
    if (confirm != true || !context.mounted) return;
    try {
      await state.removeTask(task);
      if (context.mounted) Navigator.pop(context);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Item could not be removed. Refresh and try again. Items in a manufacturer schedule can use History only instead.',
            ),
          ),
        );
      }
    }
  }
}

class _RuleDetails extends StatelessWidget {
  final MaintenanceRule rule;
  const _RuleDetails({required this.rule});
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (rule.type == 'recurring')
        Text(
          [
            if (rule.distanceKm != null) 'Every ${rule.distanceKm} km',
            if (rule.months != null) 'Every ${rule.months} months',
          ].join(' or '),
        ),
      if (rule.distanceKm != null && rule.months != null)
        const Text('Whichever limit is reached first.'),
      if (rule.type == 'milestone') ...[
        const Text(
          'Published service milestones',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        if (rule.distanceMilestones.isNotEmpty)
          Text('Odometer (km): ${rule.distanceMilestones.join(', ')}'),
        if (rule.monthMilestones.isNotEmpty)
          Text('Vehicle age (months): ${rule.monthMilestones.join(', ')}'),
        if (rule.vehicleStartDate != null)
          Text('Vehicle start date: ${formatDate(rule.vehicleStartDate!)}'),
        if (rule.monthMilestones.isNotEmpty && rule.vehicleStartDate == null)
          const Text(
            'A vehicle start date is not supplied in the published schedule. Time-based due dates cannot be calculated.',
          ),
      ],
      if (rule.type == 'informational')
        const Text('Information only · no recurring interval'),
      if (rule.conditions.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('Conditions', style: Theme.of(context).textTheme.titleSmall),
        Text(rule.conditions),
      ],
      if (rule.notes.isNotEmpty) ...[
        const SizedBox(height: 12),
        Text('Notes', style: Theme.of(context).textTheme.titleSmall),
        Text(rule.notes),
      ],
      if (rule.sourceDocumentId != null)
        Padding(
          padding: const EdgeInsets.only(top: 12),
          child: SelectableText(
            'Source document: ${rule.sourceDocumentId}${rule.sourcePage == null ? '' : '\nPage ${rule.sourcePage}'}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
    ],
  );
}

Future<void> _recordDetail(
  BuildContext context,
  AppState state,
  Vehicle vehicle,
  ServiceRecord record,
) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  useSafeArea: true,
  builder: (sheetContext) => DraggableScrollableSheet(
    expand: false,
    initialChildSize: 0.7,
    maxChildSize: 0.95,
    builder: (_, controller) => ListView(
      controller: controller,
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
      children: [
        Text('Service record', style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 8),
        Text(record.title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        Text(vehicle.name),
        const ModuleSection(title: 'Work details'),
        Text('Date: ${formatDate(record.date)}'),
        Text('Odometer at service: ${record.mileage} km'),
        Text('Category: ${record.category}'),
        Text(
          record.cost == null
              ? 'Cost not recorded'
              : 'Cost: RM ${record.cost!.toStringAsFixed(2)}',
        ),
        if (record.notes.isNotEmpty) ...[
          const ModuleSection(title: 'Notes'),
          SelectableText(record.notes),
        ],
        const SizedBox(height: 24),
        OutlinedButton.icon(
          icon: const Icon(Icons.edit_outlined),
          label: const Text('Correct this record'),
          onPressed: state.saving
              ? null
              : () async {
                  Navigator.pop(sheetContext);
                  final saved = await showDialog<bool>(
                    context: context,
                    barrierDismissible: false,
                    builder: (_) => ServiceLogDialog(
                      state: state,
                      vehicle: vehicle,
                      record: record,
                    ),
                  );
                  if (saved == true && context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Service record updated.')),
                    );
                  }
                },
        ),
        TextButton(
          onPressed: () => Navigator.pop(sheetContext),
          child: const Text('Close'),
        ),
      ],
    ),
  ),
);

import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/api_client.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/module_widgets.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';
import '../widgets/car_model_view.dart';
import 'workshop_mode.dart';
import '../widgets/sign_in_prompt.dart';
import '../widgets/maintenance_spending_summary.dart';
import 'service_forms.dart';
import 'vehicle_profile.dart';

class MyCar extends StatefulWidget {
  final AppState state;
  final int logRequest;
  final int scheduleRequest;
  final String? requestedItemId;
  final String? requestedTaskId;
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
    this.requestedTaskId,
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
  String _statusFilter = 'All';
  int _taskPage = 0;
  String? _pageScope;
  String _query = '';
  String? _selectedTaskId;
  String? _draftOwner;

  void _garage() => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (sheetContext) => ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) => Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.screen,
          0,
          AppSpacing.screen,
          24,
        ),
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
    _draftOwner = widget.state.accountId;
    if (widget.logRequest > 0 ||
        widget.requestedItemId != null ||
        widget.requestedTaskId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        if (widget.requestedItemId != null || widget.requestedTaskId != null) {
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
    if (_draftOwner != widget.state.accountId) {
      _draftOwner = widget.state.accountId;
      _selectedTaskId = null;
      _schedule = true;
    }
    if (widget.scheduleRequest != oldWidget.scheduleRequest) {
      _schedule = true;
    }
    if (widget.logRequest != oldWidget.logRequest) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _log();
      });
    }
    if (widget.itemRequestNumber != oldWidget.itemRequestNumber &&
        (widget.requestedItemId != null || widget.requestedTaskId != null)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _openRequested();
      });
    }
  }

  Future<void> _openRequested() async {
    final vehicle = widget.state.selectedVehicle;
    final tasks = widget.state
        .tasksFor(vehicle?.id ?? '')
        .where(
          (t) => widget.requestedTaskId != null
              ? t.id == widget.requestedTaskId
              : t.itemId == widget.requestedItemId,
        );
    if (tasks.isNotEmpty) {
      _detail(tasks.first);
      return;
    }
    if (widget.requestedTaskId != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'This maintenance item is no longer available. Refresh and try again.',
          ),
        ),
      );
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

  Future<void> _workshop(Vehicle vehicle) async {
    final owner = widget.state.accountId;
    final saved = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => WorkshopMode(state: widget.state, vehicle: vehicle),
      ),
    );
    if (!mounted ||
        saved != true ||
        widget.state.accountId != owner ||
        !widget.state.signedIn ||
        widget.state.selectedVehicle?.id != vehicle.id)
      return;
    setState(() {
      _schedule = false;
    });
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) {
      final state = widget.state;
      final vehicle = state.selectedVehicle;
      final tasks = vehicle == null
          ? <MaintenanceTask>[]
          : state.tasksFor(vehicle.id);
      final records = vehicle == null
          ? <ServiceRecord>[]
          : state.recordsFor(vehicle.id);
      records.sort((a, b) => b.date.compareTo(a.date));
      final categories = {'All', ...records.map((r) => r.category)};
      final filtered = records
          .where(
            (r) =>
                (_filter == 'All' || r.category == _filter) &&
                r.title.toLowerCase().contains(_query.toLowerCase()),
          )
          .toList();
      final overdue = tasks
          .where((t) => state.statusFor(t).label == 'Due / Overdue')
          .toList();
      final upcoming = tasks
          .where(
            (t) =>
                state.statusFor(t).label == 'Due soon' ||
                state.statusFor(t).label == 'Upcoming',
          )
          .toList();
      final untracked = tasks
          .where((t) => !records.any((r) => r.taskId == t.id))
          .toList();
      final visible = _statusFilter == 'Untracked'
          ? untracked
          : _statusFilter == 'Overdue'
          ? overdue
          : _statusFilter == 'Upcoming'
          ? upcoming
          : tasks;
      final selected = tasks.where((t) => t.id == _selectedTaskId).firstOrNull;
      final scope = '${vehicle?.id}:$_statusFilter:$_selectedTaskId';
      if (_pageScope != scope) {
        _taskPage = 0;
        _pageScope = scope;
      }
      final matchingTasks = selected == null ? visible : [selected];
      final pageCount = ((matchingTasks.length + 9) ~/ 10).clamp(1, 1000000);
      _taskPage = _taskPage.clamp(0, pageCount - 1);
      final shownTasks = matchingTasks.skip(_taskPage * 10).take(10).toList();
      final busy = state.saving || state.loading;
      return Scaffold(
        appBar: AppBar(
          title: Text(_schedule ? 'My Car' : 'History'),
          leading: !_schedule
              ? IconButton(
                  tooltip: 'Back to My Car',
                  onPressed: () => setState(() => _schedule = true),
                  icon: const Icon(Icons.arrow_back_ios_new),
                )
              : null,
          actions: [
            if (state.signedIn && _schedule)
              TextButton(
                onPressed: busy || (vehicle == null && state.loadError != null)
                    ? null
                    : _garage,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(vehicle?.name ?? 'Garage'),
                    const Icon(Icons.expand_more),
                  ],
                ),
              ),
            if (state.signedIn)
              PopupMenuButton<String>(
                tooltip: _schedule ? 'Maintenance options' : 'History options',
                onSelected: (value) {
                  if (value == 'garage') {
                    _garage();
                  }
                  if (value == 'add' && vehicle != null) {
                    _addItem(vehicle);
                  }
                  if (value == 'all') {
                    setState(() {
                      _statusFilter = 'All';
                      _selectedTaskId = null;
                    });
                  }
                  if (value == 'refresh') {
                    state.refresh();
                  }
                  if (value == 'history') {
                    setState(() => _schedule = false);
                  }
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'garage',
                    enabled:
                        !busy && (vehicle != null || state.loadError == null),
                    child: const Text('Garage / update odometer'),
                  ),
                  if (_schedule) ...[
                    const PopupMenuItem(
                      value: 'add',
                      child: Text('Add maintenance item'),
                    ),
                    const PopupMenuItem(
                      value: 'all',
                      child: Text('All maintenance items'),
                    ),
                    const PopupMenuItem(
                      value: 'history',
                      child: Text('Service history'),
                    ),
                  ],
                  const PopupMenuItem(value: 'refresh', child: Text('Refresh')),
                ],
              ),
          ],
        ),
        floatingActionButton: state.signedIn && vehicle != null
            ? FloatingActionButton.extended(
                onPressed: busy ? null : _log,
                backgroundColor: AppColors.ink,
                foregroundColor: const Color(0xFFFFE08A),
                icon: const Icon(Icons.add),
                label: const Text('Add record'),
              )
            : null,
        body: !state.signedIn
            ? const SignInPrompt(
                icon: Icons.directions_car_outlined,
                title: 'Your car, all in one place',
                message:
                    'Sign in to register a vehicle and track maintenance. Guides and roadside help remain available.',
              )
            : RefreshIndicator(
                onRefresh: state.refresh,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screen,
                    0,
                    AppSpacing.screen,
                    96,
                  ),
                  children: [
                    if (state.loading) const LinearProgressIndicator(),
                    if (state.loadError != null)
                      SurfaceCard(
                        child: Column(
                          children: [
                            Text(state.loadError!),
                            if (vehicle != null)
                              const Text(
                                'Previously loaded information is kept.',
                              ),
                            TextButton(
                              onPressed: busy ? null : state.refresh,
                              child: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    if (vehicle == null &&
                        !state.loading &&
                        state.loadError == null)
                      ActionRow(
                        icon: Icons.add,
                        title: 'Add your first vehicle',
                        subtitle:
                            'Keep maintenance and service history together',
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => VehicleProfilePage(
                              state: state,
                              onboarding: true,
                            ),
                          ),
                        ),
                      ),
                    if (vehicle != null && _schedule) ...[
                      CarModelView(
                        pins: maintenanceCarPins(
                          context,
                          state,
                          vehicle.id,
                          _detail,
                        ),
                      ),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            for (final label in [
                              'All',
                              'Untracked',
                              'Overdue',
                              'Upcoming',
                              'Done',
                            ])
                              Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: ChoiceChip(
                                  label: Text(
                                    '$label ${label == 'All'
                                        ? tasks.length
                                        : label == 'Untracked'
                                        ? untracked.length
                                        : label == 'Overdue'
                                        ? overdue.length
                                        : label == 'Upcoming'
                                        ? upcoming.length
                                        : records.length}',
                                  ),
                                  selected: _statusFilter == label,
                                  onSelected: (_) => setState(() {
                                    if (label == 'Done') {
                                      _schedule = false;
                                    } else {
                                      _statusFilter = label;
                                      _selectedTaskId = null;
                                    }
                                  }),
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      SurfaceCard(
                        color: AppColors.accentLight,
                        borderColor: AppColors.accent,
                        child: Row(
                          children: [
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'At a workshop?',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 16,
                                    ),
                                  ),
                                  Text(
                                    'Hand your phone to the mechanic',
                                    style: TextStyle(color: AppColors.muted),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 8),
                            FilledButton(
                              onPressed: busy ? null : () => _workshop(vehicle),
                              child: const Text('Workshop mode'),
                            ),
                          ],
                        ),
                      ),
                      if (shownTasks.isEmpty)
                        SurfaceCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                tasks.isEmpty
                                    ? 'Start with a maintenance item'
                                    : 'No ${_statusFilter.toLowerCase()} items',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 8),
                              TextButton(
                                onPressed: () =>
                                    setState(() => _statusFilter = 'All'),
                                child: const Text('View all items'),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => _addItem(vehicle),
                                child: const Text('Add maintenance item'),
                              ),
                            ],
                          ),
                        ),
                      if (pageCount > 1)
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            TextButton(
                              onPressed: _taskPage == 0
                                  ? null
                                  : () => setState(() => _taskPage--),
                              child: const Text('Previous'),
                            ),
                            Text('Page ${_taskPage + 1} of $pageCount'),
                            TextButton(
                              onPressed: _taskPage + 1 >= pageCount
                                  ? null
                                  : () => setState(() => _taskPage++),
                              child: const Text('Next'),
                            ),
                          ],
                        ),
                      for (final task in shownTasks)
                        SurfaceCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (untracked.any((item) => item.id == task.id))
                                const Padding(
                                  padding: EdgeInsets.only(bottom: 8),
                                  child: Text(
                                    'Untracked — no service recorded',
                                  ),
                                ),
                              Row(
                                children: [
                                  StatusPill(
                                    state.statusFor(task).label ==
                                            'Due / Overdue'
                                        ? 'Overdue'
                                        : state.statusFor(task).label,
                                    color:
                                        state.statusFor(task).label ==
                                            'Due / Overdue'
                                        ? const Color(0xFFF9DAD6)
                                        : AppColors.pale,
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: InkWell(
                                      onTap: () => _detail(task),
                                      child: Text(
                                        task.title,
                                        style: Theme.of(
                                          context,
                                        ).textTheme.titleMedium,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Text(
                                state.statusFor(task).description,
                                style: const TextStyle(color: AppColors.muted),
                              ),
                              const SizedBox(height: 12),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  FilledButton(
                                    onPressed: busy
                                        ? null
                                        : () => showDialog<bool>(
                                            context: context,
                                            builder: (_) => ServiceLogDialog(
                                              state: state,
                                              vehicle: vehicle,
                                              task: task,
                                            ),
                                          ),
                                    child: const Text('Mark done'),
                                  ),
                                  if (task.lessonIds.isNotEmpty)
                                    OutlinedButton(
                                      onPressed: () => widget.onLearn?.call(
                                        task.lessonIds.first,
                                      ),
                                      child: const Text('Learn why'),
                                    ),
                                  if (widget.onAsk != null)
                                    FilledButton.tonal(
                                      onPressed: () => widget.onAsk!({
                                        'kind': 'Maintenance item',
                                        'id': task.id,
                                        'title': task.title,
                                        'details': state
                                            .statusFor(task)
                                            .description,
                                      }),
                                      child: const Text('Ask AI'),
                                    ),
                                  TextButton(
                                    onPressed: () => _detail(task),
                                    child: const Text('Details & schedule'),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                    ],
                    if (vehicle != null && !_schedule) ...[
                      Text(
                        vehicle.name,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      MaintenanceSpendingSummary(
                        records: records,
                        vehicleId: vehicle.id,
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      TextField(
                        decoration: const InputDecoration(
                          hintText: 'Search history',
                          prefixIcon: Icon(Icons.search),
                        ),
                        onChanged: (value) => setState(() => _query = value),
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            for (final category in categories)
                              Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: ChoiceChip(
                                  label: Text(category),
                                  selected: _filter == category,
                                  onSelected: (_) =>
                                      setState(() => _filter = category),
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      if (records.isEmpty)
                        EmptyHistory(onAdd: _log)
                      else if (filtered.isEmpty)
                        const Text(
                          'No matching records. Try another search or category.',
                        ),
                      for (final record in filtered)
                        Dismissible(
                          key: ValueKey(record.id),
                          direction: DismissDirection.endToStart,
                          confirmDismiss: (_) async {
                            if (!busy)
                              await _deleteRecord(context, state, record);
                            return false;
                          },
                          background: Container(
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.all(16),
                            color: AppColors.dangerSurface,
                            child: const Icon(
                              Icons.delete_outline,
                              color: AppColors.danger,
                            ),
                          ),
                          child: ActionRow(
                            icon: Icons.directions_car_outlined,
                            title: record.title,
                            subtitle:
                                '${formatDate(record.date)} · ${record.mileage} km',
                            trailing: const StatusPill(
                              'Done',
                              color: AppColors.success,
                              foreground: AppColors.successInk,
                            ),
                            onTap: () =>
                                _recordDetail(context, state, vehicle, record),
                          ),
                        ),
                    ],
                  ],
                ),
              ),
      );
    },
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
            padding: EdgeInsets.all(AppSpacing.screen),
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
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screen,
            8,
            AppSpacing.screen,
            32,
          ),
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
) {
  final owner = state.accountId;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (sheetContext) => ListenableBuilder(
      listenable: state,
      builder: (sheetContext, _) => state.accountId != owner || !state.signedIn
          ? const Padding(
              padding: EdgeInsets.all(AppSpacing.screen),
              child: Text(
                'Your account changed. Close this record and reopen history.',
              ),
            )
          : DraggableScrollableSheet(
              expand: false,
              initialChildSize: 0.7,
              maxChildSize: 0.95,
              builder: (_, controller) => ListView(
                controller: controller,
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screen,
                  0,
                  AppSpacing.screen,
                  32,
                ),
                children: [
                  Text(
                    'Service record',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    record.title,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  Text(vehicle.name),
                  const ModuleSection(title: 'Work details'),
                  Text('Date: ${formatDate(record.date)}'),
                  Text('Odometer at service: ${record.mileage} km'),
                  Text('Category: ${record.category}'),
                  if (record.workshopName.isNotEmpty)
                    Text('Workshop: ${record.workshopName}'),
                  Text(
                    'Performed by: ${switch (record.performedBy) {
                      'self' => 'You',
                      'mechanic' => 'Mechanic',
                      _ => 'Not recorded',
                    }}',
                  ),
                  Text(
                    record.cost == null
                        ? 'Cost not recorded'
                        : 'Cost: ${formatMyr(record.cost!)}',
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
                                const SnackBar(
                                  content: Text('Service record updated.'),
                                ),
                              );
                            }
                          },
                  ),
                  TextButton.icon(
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Delete record'),
                    onPressed: state.saving || state.loading
                        ? null
                        : () async {
                            final deleted = await _deleteRecord(
                              context,
                              state,
                              record,
                            );
                            if (deleted && sheetContext.mounted)
                              Navigator.pop(sheetContext);
                          },
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(sheetContext),
                    child: const Text('Close'),
                  ),
                ],
              ),
            ),
    ),
  );
}

Future<bool> _deleteRecord(
  BuildContext context,
  AppState state,
  ServiceRecord record,
) async {
  final owner = state.accountId;
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text('Delete ${record.title}?'),
      content: const Text(
        'This permanently deletes this service record from your account. The next service will be recalculated from the remaining history. This cannot be undone.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(dialogContext, true),
          child: const Text('Delete'),
        ),
      ],
    ),
  );
  if (confirmed != true || !context.mounted) return false;
  try {
    if (!state.signedIn || state.accountId != owner) {
      throw const ApiException(
        'Your account changed. Reopen history before deleting a record.',
      );
    }
    await state.removeRecord(record.id);
    if (context.mounted)
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Service record deleted.')));
    return true;
  } catch (error) {
    if (context.mounted)
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error is ApiException
                ? error.message
                : 'The record could not be deleted. Refresh history and retry.',
          ),
        ),
      );
    return false;
  }
}

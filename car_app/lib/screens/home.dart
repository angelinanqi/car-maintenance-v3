import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/module_widgets.dart';
import 'vehicle_profile.dart';
import 'profile.dart';

class Home extends StatelessWidget {
  final AppState state;
  final Future<void> Function(Vehicle, bool) onMaintenance;
  final VoidCallback? onEmergency, onLearn, onAsk;
  const Home({
    super.key,
    required this.state,
    required this.onMaintenance,
    this.onEmergency,
    this.onLearn,
    this.onAsk,
  });

  void _edit(BuildContext context, [Vehicle? vehicle]) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => VehicleProfilePage(state: state, vehicle: vehicle),
      ),
    );
  }

  void _account(BuildContext context) => Navigator.of(
    context,
  ).push(MaterialPageRoute(builder: (_) => Profile(state: state)));

  Widget _vehicle(
    BuildContext context,
    Vehicle vehicle, {
    bool active = false,
  }) {
    final theme = Theme.of(context);
    final busy = state.loading || state.saving;
    final details = [
      if (vehicle.year > 0) '${vehicle.year}',
      if (vehicle.engineSize.trim().isNotEmpty) vehicle.engineSize,
      if (vehicle.plateNumber.trim().isNotEmpty) vehicle.plateNumber,
    ];
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            vehicle.name.trim().isEmpty ? 'Your vehicle' : vehicle.name,
            style: theme.textTheme.titleLarge,
          ),
          if (vehicle.model.trim().isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(vehicle.model, style: theme.textTheme.bodyLarge),
          ],
          if (details.isNotEmpty) Text(details.join(' · ')),
          const SizedBox(height: 12),
          Text('${vehicle.mileage} km', style: theme.textTheme.titleMedium),
          Text('Recorded odometer', style: theme.textTheme.bodySmall),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: busy ? null : () => onMaintenance(vehicle, true),
                icon: const Icon(Icons.add, size: 20),
                label: const Text('Log service'),
              ),
              OutlinedButton(
                onPressed: busy ? null : () => onMaintenance(vehicle, false),
                child: const Text('View schedule'),
              ),
            ],
          ),
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: EdgeInsets.zero,
            title: const Text('Vehicle details'),
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Owner manual: ${vehicle.manualAvailable ? 'Available' : 'Unavailable'}\nManufacturer schedule: ${vehicle.manufacturerScheduleAvailable ? 'Available' : 'Unavailable'}',
                ),
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: busy ? null : () => _edit(context, vehicle),
                  icon: const Icon(Icons.edit_outlined, size: 20),
                  label: const Text('Edit vehicle'),
                ),
              ),
            ],
          ),
          if (!active)
            TextButton(
              onPressed: busy
                  ? null
                  : () async {
                      try {
                        await state.selectVehicle(vehicle.id);
                      } catch (_) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Could not change vehicle. Please try again.',
                              ),
                            ),
                          );
                        }
                      }
                    },
              child: const Text('Use as active vehicle'),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: state,
    builder: (context, _) {
      final theme = Theme.of(context);
      final vehicle = state.selectedVehicle;
      final tasks = vehicle == null
          ? <MaintenanceTask>[]
          : state.tasksFor(vehicle.id);
      // Use the server's status; Home must not infer service intervals.
      final due = tasks
          .where((task) => state.statusFor(task).label == 'Due / Overdue')
          .toList();
      final preview = [
        ...due,
        ...tasks.where((task) => !due.contains(task)),
      ].take(3);
      final busy = state.loading || state.saving;
      return Scaffold(
        appBar: AppBar(
          title: const Text('Car Assistance'),
          actions: [
            IconButton(
              tooltip: 'Account and guest preferences',
              icon: const Icon(Icons.person_outline),
              onPressed: state.loading ? null : () => _account(context),
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: RefreshIndicator(
            onRefresh: state.signedIn ? state.refresh : state.load,
            child: SingleChildScrollView(
              key: const PageStorageKey('home'),
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 720),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Material(
                        color: theme.colorScheme.errorContainer,
                        borderRadius: BorderRadius.circular(12),
                        clipBehavior: Clip.antiAlias,
                        child: ListTile(
                          leading: Icon(
                            Icons.emergency_outlined,
                            color: theme.colorScheme.error,
                          ),
                          title: Text(
                            'Emergency assistance',
                            style: TextStyle(
                              color: theme.colorScheme.onErrorContainer,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          subtitle: Text(
                            'Breakdown or accident? Get help now.',
                            style: TextStyle(
                              color: theme.colorScheme.onErrorContainer,
                            ),
                          ),
                          trailing: Icon(
                            Icons.chevron_right,
                            color: theme.colorScheme.onErrorContainer,
                          ),
                          onTap: onEmergency,
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        state.signedIn
                            ? 'Keep your car road-ready.'
                            : 'Get to know your car.',
                        style: theme.textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        state.signedIn
                            ? 'Keep track of care, understand your car and find help when you need it.'
                            : 'Practical guides and roadside help, with no sign-in needed.',
                        style: theme.textTheme.bodyLarge,
                      ),
                      if (state.signedIn) ...[
                        const ModuleSection(title: 'Your active vehicle'),
                        if (state.loading)
                          const LinearProgressIndicator(
                            semanticsLabel: 'Refreshing your garage',
                          ),
                        if (state.loadError != null)
                          ModuleMessage(
                            title: 'Your garage could not refresh',
                            message:
                                'Check your connection and try again. Previously loaded information is kept below.',
                            action: OutlinedButton.icon(
                              onPressed: busy ? null : state.refresh,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Try again'),
                            ),
                          ),
                        if (vehicle != null)
                          Material(
                            color: theme.colorScheme.surface,
                            borderRadius: BorderRadius.circular(12),
                            child: _vehicle(context, vehicle, active: true),
                          )
                        else if (!state.loading && state.loadError == null)
                          ModuleMessage(
                            icon: Icons.directions_car_outlined,
                            title: state.vehicles.isEmpty
                                ? 'Add your first vehicle'
                                : 'Choose your active vehicle',
                            message: state.vehicles.isEmpty
                                ? 'Keep its service history and maintenance schedule in one place.'
                                : 'Open your garage below to choose a vehicle.',
                            action: state.vehicles.isEmpty
                                ? FilledButton.icon(
                                    onPressed: busy
                                        ? null
                                        : () => _edit(context),
                                    icon: const Icon(Icons.add),
                                    label: const Text('Add vehicle'),
                                  )
                                : null,
                          ),
                        if (vehicle != null) ...[
                          ModuleSection(
                            title: 'Maintenance at a glance',
                            description:
                                '${state.recordsFor(vehicle.id).length} ${state.recordsFor(vehicle.id).length == 1 ? 'service record' : 'service records'} saved for this vehicle.',
                          ),
                          if (tasks.isEmpty)
                            const Text(
                              'No maintenance items yet. Open the schedule to add the work you want to track.',
                            )
                          else ...[
                            if (due.isNotEmpty)
                              Text(
                                '${due.length} ${due.length == 1 ? 'item needs' : 'items need'} attention.',
                                style: theme.textTheme.titleMedium,
                              ),
                            for (final task in preview)
                              ListTile(
                                contentPadding: const EdgeInsets.symmetric(
                                  vertical: 4,
                                ),
                                title: Text(task.title),
                                subtitle: Text(
                                  state.statusFor(task).description,
                                ),
                                trailing: const Icon(Icons.chevron_right),
                                onTap: busy
                                    ? null
                                    : () => onMaintenance(vehicle, false),
                              ),
                            if (tasks.length > 3)
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => onMaintenance(vehicle, false),
                                child: Text(
                                  'View all ${tasks.length} maintenance items',
                                ),
                              ),
                          ],
                        ],
                        const SizedBox(height: 12),
                        ExpansionTile(
                          title: Text('Your garage (${state.vehicles.length})'),
                          subtitle: const Text('Switch, edit or add a vehicle'),
                          tilePadding: EdgeInsets.zero,
                          children: [
                            for (final other in state.vehicles.where(
                              (v) => v.id != vehicle?.id,
                            ))
                              _vehicle(context, other),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: TextButton.icon(
                                onPressed: busy ? null : () => _edit(context),
                                icon: const Icon(Icons.add),
                                label: const Text('Add vehicle'),
                              ),
                            ),
                          ],
                        ),
                      ],
                      const ModuleSection(title: 'Learn and ask'),
                      _HomeLink(
                        icon: Icons.menu_book_outlined,
                        title: 'Learn about your car',
                        description:
                            'Simple explanations, one topic at a time.',
                        onTap: onLearn,
                      ),
                      const SizedBox(height: 8),
                      _HomeLink(
                        icon: Icons.chat_bubble_outline,
                        title: 'Ask AI',
                        description: state.signedIn
                            ? 'Ask a question and explore supporting sources.'
                            : 'Car questions in everyday language. Sign in to ask.',
                        onTap: onAsk,
                      ),
                      if (!state.signedIn) ...[
                        const SizedBox(height: 24),
                        Text(
                          'Your garage starts here',
                          style: theme.textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Sign in to add vehicles, track maintenance and save your learning progress.',
                        ),
                        const SizedBox(height: 16),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: FilledButton(
                            onPressed: () => _account(context),
                            child: const Text('Sign in or create an account'),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    },
  );
}

class _HomeLink extends StatelessWidget {
  final IconData icon;
  final String title, description;
  final VoidCallback? onTap;
  const _HomeLink({
    required this.icon,
    required this.title,
    required this.description,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: const EdgeInsets.symmetric(vertical: 8),
    leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
    title: Text(title, style: Theme.of(context).textTheme.titleMedium),
    subtitle: Text(description),
    trailing: const Icon(Icons.chevron_right),
    onTap: onTap,
  );
}

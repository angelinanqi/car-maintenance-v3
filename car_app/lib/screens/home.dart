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

  void _account(BuildContext context) => Navigator.of(
    context,
  ).push(MaterialPageRoute(builder: (_) => Profile(state: state)));

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: state,
    builder: (context, _) {
      final theme = Theme.of(context);
      final colors = theme.colorScheme;
      final vehicle = state.selectedVehicle;
      final tasks = vehicle == null
          ? <MaintenanceTask>[]
          : state.tasksFor(vehicle.id);
      // Prioritise the server's due status. Never invent intervals on Home.
      int priority(MaintenanceTask task) =>
          switch (state.statusFor(task).label) {
            'Due / Overdue' => 0,
            'Due soon' => 1,
            _ => 2,
          };
      tasks.sort((a, b) => priority(a).compareTo(priority(b)));
      final due = tasks.where((t) => priority(t) == 0).length;
      final busy = state.loading || state.saving;
      return Scaffold(
        appBar: AppBar(
          title: const Text('Car Assistance'),
          actions: [
            IconButton(
              tooltip: 'Account and guest preferences',
              icon: const Icon(Icons.account_circle_outlined),
              onPressed: () => _account(context),
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: RefreshIndicator(
            onRefresh: state.signedIn ? state.refresh : state.load,
            child: ListView(
              key: const PageStorageKey('home'),
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
              children: [
                Material(
                  color: colors.primary,
                  borderRadius: BorderRadius.circular(20),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: onAsk,
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Ask about your car',
                            style: theme.textTheme.headlineSmall?.copyWith(
                              color: colors.onPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            state.signedIn
                                ? 'Understand a warning light, your manual or your next service.'
                                : 'Sign in for answers with supporting sources.',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colors.onPrimary,
                            ),
                          ),
                          const SizedBox(height: 20),
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  'Ask the assistant',
                                  style: theme.textTheme.labelLarge?.copyWith(
                                    color: colors.onPrimary,
                                  ),
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward_rounded,
                                color: colors.onPrimary,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                if (state.signedIn) ...[
                  const ModuleSection(title: 'Your car'),
                  if (state.loading)
                    const LinearProgressIndicator(
                      semanticsLabel: 'Refreshing your garage',
                    ),
                  if (state.loadError != null)
                    ModuleMessage(
                      title: 'Could not refresh your garage',
                      message:
                          'Your last loaded information is kept. Pull down to retry.',
                      action: TextButton(
                        onPressed: busy ? null : state.refresh,
                        child: const Text('Retry'),
                      ),
                    ),
                  if (vehicle != null)
                    Material(
                      color: colors.surface,
                      borderRadius: BorderRadius.circular(16),
                      clipBehavior: Clip.antiAlias,
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        leading: const Icon(
                          Icons.directions_car_outlined,
                          size: 28,
                        ),
                        title: Text(
                          vehicle.name,
                          style: theme.textTheme.titleMedium,
                        ),
                        subtitle: Text(
                          '${vehicle.plateNumber.isEmpty ? vehicle.model : vehicle.plateNumber} · ${vehicle.mileage} km',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: busy
                            ? null
                            : () => onMaintenance(vehicle, false),
                      ),
                    )
                  else if (!busy && state.loadError == null)
                    ModuleMessage(
                      icon: Icons.directions_car_outlined,
                      title: 'Add your first vehicle',
                      message:
                          'Bring its service history and maintenance together.',
                      action: FilledButton.icon(
                        onPressed: () => Navigator.push(
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
                    ModuleSection(
                      title: due > 0 ? 'Needs attention' : 'Maintenance',
                      description: due > 0
                          ? '$due ${due == 1 ? 'item is' : 'items are'} due or overdue.'
                          : 'Based on your saved service records.',
                    ),
                    if (tasks.isEmpty)
                      const Text(
                        'Add maintenance items in My Car to start tracking.',
                      ),
                    for (final task in tasks.take(2))
                      ListTile(
                        contentPadding: const EdgeInsets.symmetric(vertical: 2),
                        leading: Icon(
                          priority(task) == 0
                              ? Icons.error_outline
                              : Icons.build_outlined,
                          color: priority(task) == 0
                              ? colors.error
                              : colors.primary,
                        ),
                        title: Text(task.title),
                        subtitle: Text(_statusSummary(state.statusFor(task))),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: busy
                            ? null
                            : () => onMaintenance(vehicle, false),
                      ),
                    Wrap(
                      spacing: 12,
                      children: [
                        FilledButton.tonalIcon(
                          onPressed: busy
                              ? null
                              : () => onMaintenance(vehicle, true),
                          icon: const Icon(Icons.add, size: 18),
                          label: const Text('Log service'),
                        ),
                        TextButton(
                          onPressed: busy
                              ? null
                              : () => onMaintenance(vehicle, false),
                          child: const Text('View maintenance'),
                        ),
                      ],
                    ),
                  ],
                ],
                const ModuleSection(title: 'On the road'),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    Icons.menu_book_outlined,
                    color: colors.primary,
                  ),
                  title: const Text('Get to know your car'),
                  subtitle: const Text('Practical guides and owner manuals'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: onLearn,
                ),
                const SizedBox(height: 8),
                Material(
                  color: colors.errorContainer,
                  borderRadius: BorderRadius.circular(16),
                  clipBehavior: Clip.antiAlias,
                  child: ListTile(
                    leading: Icon(
                      Icons.emergency_outlined,
                      color: colors.error,
                    ),
                    title: Text(
                      'Need roadside help?',
                      style: TextStyle(
                        color: colors.onErrorContainer,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    subtitle: Text(
                      'Emergency help · no sign-in needed',
                      style: TextStyle(color: colors.onErrorContainer),
                    ),
                    trailing: Icon(Icons.chevron_right, color: colors.error),
                    onTap: onEmergency,
                  ),
                ),
                if (!state.signedIn) ...[
                  const SizedBox(height: 24),
                  TextButton(
                    onPressed: () => _account(context),
                    child: const Text('Sign in to manage your car'),
                  ),
                ],
              ],
            ),
          ),
        ),
      );
    },
  );
}

// Home previews urgency; the full schedule stays in My Car.
String _statusSummary(MaintenanceStatus status) => [
  status.label,
  if (status.remainingKm != null)
    status.remainingKm! < 0
        ? '${-status.remainingKm!} km overdue'
        : status.remainingKm == 0
        ? 'Due at the recorded mileage'
        : '${status.remainingKm} km remaining'
  else if (status.nextKm != null)
    'At ${status.nextKm} km',
  if (status.nextDate != null) 'By ${formatDate(status.nextDate!)}',
].join(' · ');

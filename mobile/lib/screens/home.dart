import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../app_theme.dart';
import '../models/maintenance.dart';
import '../models/vehicle.dart';
import '../widgets/design_widgets.dart';
import '../widgets/car_model_view.dart';
import 'vehicle_profile.dart';
import 'profile.dart';
import 'service_forms.dart';
import 'account_form.dart';
import '../widgets/vehicle_selector.dart';

class Home extends StatelessWidget {
  final AppState state;
  final Future<void> Function(Vehicle, bool) onMaintenance;
  final void Function(String)? onTask;
  final VoidCallback? onEmergency, onLearn, onAsk, onPlan, onPrepare;
  const Home({
    super.key,
    required this.state,
    required this.onMaintenance,
    this.onTask,
    this.onEmergency,
    this.onLearn,
    this.onAsk,
    this.onPlan,
    this.onPrepare,
  });

  Future<void> _done(
    BuildContext context,
    Vehicle vehicle,
    MaintenanceTask task,
  ) => showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) =>
        ServiceLogDialog(state: state, vehicle: vehicle, task: task),
  );

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: state,
    builder: (context, _) {
      final vehicle = state.selectedVehicle;
      final tasks = vehicle == null
          ? <MaintenanceTask>[]
          : state.tasksFor(vehicle.id);
      int priority(MaintenanceTask task) =>
          switch (state.statusFor(task).label) {
            'Due / Overdue' => 0,
            'Due soon' => 1,
            'Upcoming' => 3,
            'No schedule' => 4,
            _ => 2,
          };
      tasks.sort((a, b) {
        final result = priority(a).compareTo(priority(b));
        return result != 0 ? result : a.title.compareTo(b.title);
      });
      final due = tasks.where((t) => priority(t) == 0).length;
      final task = tasks.where((t) => priority(t) < 4).firstOrNull;
      void signIn() => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const AccountForm(register: false)),
      );
      void chooseVehicle() => showModalBottomSheet<void>(
        context: context,
        useSafeArea: true,
        builder: (_) => Padding(
          padding: const EdgeInsets.all(AppSpacing.screen),
          child: ListenableBuilder(
            listenable: state,
            builder: (_, _) => VehicleSelector(state: state),
          ),
        ),
      );
      final theme = Theme.of(context);
      final hour = DateTime.now().hour;
      final greeting = hour < 12
          ? 'Good morning'
          : hour < 18
          ? 'Good afternoon'
          : 'Good evening';
      return Scaffold(
        body: SafeArea(
          bottom: false,
          child: state.loading && vehicle == null
              ? const HomeSkeleton()
              : RefreshIndicator(
                  onRefresh: state.signedIn ? state.refresh : state.load,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(AppSpacing.screen),
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: OutlinedButton(
                              onPressed:
                                  state.signedIn &&
                                      vehicle == null &&
                                      state.loadError != null
                                  ? null
                                  : vehicle == null
                                  ? state.signedIn
                                        ? () => Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) =>
                                                  VehicleProfilePage(
                                                    state: state,
                                                    onboarding: true,
                                                  ),
                                            ),
                                          )
                                        : signIn
                                  : chooseVehicle,
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Flexible(
                                    child: Text(
                                      vehicle?.name ?? 'Your car',
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  const Icon(Icons.expand_more),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Spacer(),
                          if (!state.signedIn) const StatusPill('Guest'),
                          const SizedBox(width: 12),
                          IconButton.filledTonal(
                            tooltip: 'Account',
                            style: IconButton.styleFrom(
                              backgroundColor: AppColors.pale,
                              minimumSize: const Size(44, 44),
                            ),
                            onPressed: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => Profile(state: state),
                              ),
                            ),
                            icon: const Icon(Icons.person_outline),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          const Mascot(size: 52),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  greeting,
                                  style: const TextStyle(
                                    color: AppColors.muted,
                                  ),
                                ),
                                Text(
                                  !state.signedIn
                                      ? 'Know your car better'
                                      : due == 0
                                      ? 'Let’s look after your car'
                                      : due == 1
                                      ? 'One thing needs attention'
                                      : '$due things need attention',
                                  style: theme.textTheme.headlineSmall,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 18),
                      if (state.signedIn && state.preferencesError != null)
                        SurfaceCard(
                          child: Column(
                            children: [
                              Text(state.preferencesError!),
                              TextButton(
                                onPressed: state.loading ? null : state.load,
                                child: const Text('Retry preferences'),
                              ),
                            ],
                          ),
                        ),
                      if (state.loadError != null)
                        SurfaceCard(
                          child: Column(
                            children: [
                              Text(
                                state.signedIn
                                    ? '${state.loadError}${vehicle == null ? '' : ' Previously loaded information is kept.'}'
                                    : 'Device preferences could not be loaded. Existing files are kept.',
                              ),
                              TextButton(
                                onPressed: state.loading
                                    ? null
                                    : state.signedIn
                                    ? state.refresh
                                    : state.load,
                                child: const Text('Retry'),
                              ),
                              if (state.signedIn &&
                                  state.loadErrorStatus == 401)
                                TextButton(
                                  onPressed: signIn,
                                  child: const Text('Sign in again'),
                                ),
                              if (state.signedIn &&
                                  state.loadErrorStatus == 403)
                                TextButton(
                                  onPressed: () => Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => Profile(state: state),
                                    ),
                                  ),
                                  child: const Text('Check account'),
                                ),
                            ],
                          ),
                        ),
                      if (vehicle != null)
                        CarModelView(
                          compact: true,
                          pins: [
                            for (final item in tasks.take(3))
                              CarPin(
                                label: item.title,
                                color: priority(item) == 0
                                    ? AppColors.danger
                                    : priority(item) == 1
                                    ? AppColors.accent
                                    : AppColors.success,
                                onTap: () => onTask != null
                                    ? onTask!(item.id)
                                    : onMaintenance(vehicle, false),
                              ),
                          ],
                        ),
                      if (state.cacheError != null)
                        SurfaceCard(child: Text(state.cacheError!)),
                      if (state.signedIn &&
                          vehicle == null &&
                          state.loadError != null)
                        const SurfaceCard(
                          child: Text(
                            'Your garage is unavailable. Retry before adding a vehicle.',
                          ),
                        )
                      else if (task != null && vehicle != null)
                        SurfaceCard(
                          color: AppColors.accent,
                          borderColor: AppColors.accent,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      task.title,
                                      style: theme.textTheme.titleLarge,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  StatusPill(
                                    state.statusFor(task).label,
                                    color: priority(task) == 0
                                        ? const Color(0xFFF9DAD6)
                                        : AppColors.pale,
                                    foreground: priority(task) == 0
                                        ? AppColors.danger
                                        : AppColors.ink,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(state.statusFor(task).description),
                              const SizedBox(height: AppSpacing.standard),
                              IntrinsicHeight(
                                child: Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(
                                      child: FilledButton(
                                        style: FilledButton.styleFrom(
                                          backgroundColor: Colors.white,
                                          foregroundColor: AppColors.muted,
                                        ),
                                        onPressed: state.saving
                                            ? null
                                            : () =>
                                                  _done(context, vehicle, task),
                                        child: const Text('I’ve done this'),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: FilledButton(
                                        onPressed: onPlan,
                                        child: const Text(
                                          'Plan maintenance',
                                          textAlign: TextAlign.center,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        )
                      else
                        SurfaceCard(
                          color: AppColors.accent,
                          borderColor: AppColors.accent,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                state.signedIn
                                    ? vehicle == null
                                          ? 'Let’s add your car'
                                          : 'Your car, all in one place'
                                    : 'Feel more confident',
                                style: theme.textTheme.titleLarge,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                state.signedIn
                                    ? 'Keep maintenance and service history together.'
                                    : 'Browse practical guides and roadside help. Sign in to manage your car.',
                              ),
                              const SizedBox(height: 12),
                              FilledButton(
                                onPressed: state.signedIn && vehicle == null
                                    ? () => Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => VehicleProfilePage(
                                            state: state,
                                            onboarding: true,
                                          ),
                                        ),
                                      )
                                    : state.signedIn
                                    ? () => onMaintenance(vehicle!, false)
                                    : signIn,
                                child: Text(
                                  state.signedIn
                                      ? vehicle == null
                                            ? 'Add vehicle'
                                            : 'View maintenance'
                                      : 'Sign in',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ActionRow(
                        icon: Icons.menu_book_outlined,
                        title: state.completedLessons.isEmpty
                            ? 'Start learning'
                            : 'Continue learning',
                        subtitle: 'Practical guides, at your own pace',
                        onTap: onLearn,
                      ),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            OutlinedButton(
                              onPressed: onPlan,
                              child: const Text('Review my service plan'),
                            ),
                            const SizedBox(width: 8),
                            OutlinedButton(
                              onPressed: onPrepare,
                              child: const Text('Prepare for my mechanic'),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 36),
                      SurfaceCard(
                        color: AppColors.dangerSurface,
                        borderColor: const Color(0xFFF1B3AD),
                        child: Row(
                          children: [
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Stuck on the road?',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  Text(
                                    'Safety steps, even offline',
                                    style: TextStyle(color: AppColors.muted),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 10),
                            FilledButton(
                              style: FilledButton.styleFrom(
                                backgroundColor: AppColors.danger,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: onEmergency,
                              child: const Text('Get help'),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      );
    },
  );
}

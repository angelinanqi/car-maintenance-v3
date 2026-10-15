import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/vehicle.dart';
import 'vehicle_profile.dart';
import 'profile.dart';

class Home extends StatelessWidget {
  final AppState state;
  final Future<void> Function(Vehicle, bool) onMaintenance;
  final VoidCallback? onEmergency, onLearn;
  const Home({
    super.key,
    required this.state,
    required this.onMaintenance,
    this.onEmergency,
    this.onLearn,
  });

  Future<void> _edit(BuildContext context, [Vehicle? vehicle]) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => VehicleProfilePage(state: state, vehicle: vehicle),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Home'),
      backgroundColor: Theme.of(context).colorScheme.primaryContainer,
      actions: [
        IconButton(
          tooltip: 'Account and guest preferences',
          icon: const Icon(Icons.person_outline),
          onPressed: state.loading
              ? null
              : () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => Profile(state: state)),
                ),
        ),
        IconButton(
          tooltip: 'Add vehicle',
          icon: const Icon(Icons.add_road_rounded),
          onPressed: !state.signedIn || state.loading || state.saving
              ? null
              : () => _edit(context),
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
          onPressed: onEmergency,
          icon: const Icon(Icons.emergency),
          label: const Text('Emergency assistance — works offline'),
        ),
        OutlinedButton.icon(
          onPressed: onLearn,
          icon: const Icon(Icons.menu_book),
          label: const Text('Explore learning content'),
        ),
        if (!state.signedIn) ...[
          const Text(
            'Welcome, guest. Read learning cards and access emergency guides, contacts and incident records.',
          ),
          OutlinedButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => Profile(state: state)),
            ),
            child: const Text('Log in or create an account'),
          ),
        ],
        if (state.signedIn) ...[
          Text('Your garage', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (state.vehicles.isEmpty)
            Card.outlined(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Add your first vehicle to track maintenance and set chatbot context.',
                    ),
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      onPressed: state.loading || state.saving
                          ? null
                          : () => _edit(context),
                      icon: const Icon(Icons.add),
                      label: const Text('Add vehicle'),
                    ),
                  ],
                ),
              ),
            ),
          ...state.vehicles.map(
            (vehicle) => Card.outlined(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          vehicle.name,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        if (state.selectedVehicle?.id == vehicle.id)
                          const Chip(
                            label: Text('Selected'),
                            avatar: Icon(Icons.check, size: 18),
                          ),
                      ],
                    ),
                    Text(
                      vehicle.model,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    Text(
                      '${vehicle.year} • ${vehicle.engineSize} • ${vehicle.plateNumber}',
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${vehicle.mileage} km',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      'Manual: ${vehicle.manualAvailable ? 'Available' : 'Unavailable'} • Manufacturer schedule: ${vehicle.manufacturerScheduleAvailable ? 'Available' : 'Unavailable'}',
                    ),
                    if (state.selectedVehicle?.id != vehicle.id)
                      TextButton(
                        onPressed: state.saving
                            ? null
                            : () async {
                                try {
                                  await state.selectVehicle(vehicle.id);
                                } catch (error) {
                                  if (context.mounted) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text('$error')),
                                    );
                                  }
                                }
                              },
                        child: const Text('Use as active vehicle'),
                      ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        FilledButton(
                          onPressed: state.saving
                              ? null
                              : () => onMaintenance(vehicle, true),
                          child: const Text('Log service'),
                        ),
                        OutlinedButton(
                          onPressed: state.saving
                              ? null
                              : () => onMaintenance(vehicle, false),
                          child: const Text('View schedule'),
                        ),
                        TextButton(
                          onPressed: () => _edit(context, vehicle),
                          child: const Text('Edit vehicle'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card.outlined(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Maintenance overview',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  if (state.selectedVehicle == null)
                    const Text('Select a vehicle to view its records.')
                  else ...[
                    Text(
                      '${state.recordsFor(state.selectedVehicle!.id).length} service records for ${state.selectedVehicle!.name}.',
                    ),
                    const SizedBox(height: 8),
                    ...state
                        .tasksFor(state.selectedVehicle!.id)
                        .map(
                          (task) => ListTile(
                            title: Text(task.title),
                            subtitle: Text(state.statusFor(task).description),
                            onTap: () =>
                                onMaintenance(state.selectedVehicle!, false),
                          ),
                        ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ],
    ),
  );
}

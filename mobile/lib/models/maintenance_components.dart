import 'maintenance.dart';

// Only reviewed category-to-area mappings. Unknown categories stay in the list.
String? maintenanceComponent(MaintenanceTask task) => switch (task.category) {
  'Engine and Fluids' ||
  'Engine and lubrication' ||
  'Air, fuel and ignition' ||
  'Cooling system' => 'Engine compartment',
  'Tyre Condition and Pressure' || 'Tyres and wheels' => 'Tyres and wheels',
  _ => null,
};

Map<String, List<MaintenanceTask>> maintenanceComponents(
  List<MaintenanceTask> tasks,
  MaintenanceStatus Function(MaintenanceTask) statusFor,
) {
  final groups = <String, List<MaintenanceTask>>{};
  final seen = <String>{};
  for (final task in tasks) {
    final component = maintenanceComponent(task);
    if (component == null || !seen.add(task.id)) continue;
    if (![
      'Due / Overdue',
      'Due soon',
      'Upcoming',
    ].contains(statusFor(task).label))
      continue;
    groups.putIfAbsent(component, () => []).add(task);
  }
  return groups;
}

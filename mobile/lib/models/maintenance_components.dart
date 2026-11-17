import 'maintenance.dart';

enum MaintenanceComponent {
  engine('Engine compartment', '1.5m 1.12m -0.75m', '0 1 0'),
  wheels('Tyres, wheels and brakes', '-1.35m 0.48m 1.13m', '0 0 1'),
  visibility('Lights and wipers', '0.8m 1.48m 0.65m', '1 1 0');

  const MaintenanceComponent(this.label, this.position, this.normal);

  final String label;
  final String position;
  final String normal;
}

final _visibilityParts = RegExp(
  r'\b(?:headlights?|headlamps?|tail lights?|taillights?|turn signals?|'
  r'(?:brake|fog|exterior|reverse|parking) lights?|wipers?|washer fluid)\b',
);
final _wheelParts = RegExp(
  r'\b(?:tyres?|tires?|wheels?|brakes?(?!\s+lights?)|braking)\b',
);
final _engineParts = RegExp(
  r'\b(?:engine oil|oil filters?|spark plugs?|coolant|radiators?|engine air filters?)\b',
);

MaintenanceComponent? maintenanceComponent(MaintenanceTask task) {
  final category = task.category.trim().toLowerCase();
  final component = switch (category) {
    'engine and lubrication' ||
    'air, fuel and ignition' ||
    'cooling system' => MaintenanceComponent.engine,
    'tyre condition and pressure' ||
    'tire condition and pressure' ||
    'tyres and wheels' ||
    'tires and wheels' ||
    'brakes' ||
    'braking' ||
    'brake system' ||
    'braking system' => MaintenanceComponent.wheels,
    'lights' ||
    'lighting' ||
    'exterior lights' ||
    'exterior lighting' ||
    'wipers' ||
    'wipers and washer' ||
    'wipers and washers' ||
    'lights and wipers' => MaintenanceComponent.visibility,
    _ => null,
  };
  if (component != null) return component;

  // Older items can share a broad category even when their titles name a part.
  final title = task.title.toLowerCase();
  final matches = [
    if (_visibilityParts.hasMatch(title)) MaintenanceComponent.visibility,
    if (_wheelParts.hasMatch(title)) MaintenanceComponent.wheels,
    if (_engineParts.hasMatch(title)) MaintenanceComponent.engine,
  ];
  if (matches.isEmpty && category == 'engine and fluids') {
    return MaintenanceComponent.engine;
  }
  return matches.singleOrNull;
}

Map<MaintenanceComponent, List<MaintenanceTask>> maintenanceComponents(
  List<MaintenanceTask> tasks,
  MaintenanceStatus Function(MaintenanceTask) statusFor,
) {
  final groups = <MaintenanceComponent, List<MaintenanceTask>>{};
  final seen = <String>{};
  for (final task in tasks) {
    final component = maintenanceComponent(task);
    if (component == null || !seen.add(task.id)) continue;
    final status = statusFor(task);
    if (!status.isDue && !status.isUpcoming) continue;
    groups.putIfAbsent(component, () => []).add(task);
  }
  return groups;
}

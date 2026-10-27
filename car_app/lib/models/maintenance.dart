class MaintenanceTask {
  final String id;
  final String vehicleId;
  final String title;
  final String category;
  final String? itemId;
  final String action;
  final MaintenanceRule? manufacturerRule;
  final MaintenanceRule? customRule;
  final String scheduleSource;
  final List<String> lessonIds;
  final bool isCustom;
  final MaintenanceStatus? serverStatus;

  const MaintenanceTask({
    required this.id,
    required this.vehicleId,
    required this.title,
    required this.category,
    this.itemId,
    this.action = 'service',
    this.manufacturerRule,
    this.customRule,
    this.scheduleSource = 'none',
    this.lessonIds = const [],
    this.isCustom = true,
    this.serverStatus,
  });

  factory MaintenanceTask.fromJson(Map<String, dynamic> json) =>
      MaintenanceTask(
        id: json['id'] as String,
        vehicleId: json['vehicleId'] as String,
        title: json['title'] as String,
        category: json['category'] as String,
        itemId: json['itemId'] as String?,
        action: json['action'] as String? ?? 'service',
        manufacturerRule: json['manufacturerRule'] == null
            ? null
            : MaintenanceRule.fromJson(
                Map<String, dynamic>.from(json['manufacturerRule'] as Map),
              ),
        customRule: json['customRule'] == null
            ? null
            : MaintenanceRule.fromJson(
                Map<String, dynamic>.from(json['customRule'] as Map),
              ),
        scheduleSource: json['scheduleSource'] as String? ?? 'none',
        lessonIds: (json['lessonIds'] as List? ?? []).cast<String>(),
        isCustom: json['isCustom'] != false,
        serverStatus: json['status'] is Map
            ? MaintenanceStatus.fromJson(
                Map<String, dynamic>.from(json['status'] as Map),
              )
            : null,
      );

  Map<String, dynamic> toJson() => {
    'id': id,
    'vehicleId': vehicleId,
    'title': title,
    'category': category,
    'itemId': itemId,
    'action': action,
    'manufacturerRule': manufacturerRule?.toJson(),
    'customRule': customRule?.toJson(),
    'scheduleSource': scheduleSource,
    'lessonIds': lessonIds,
    'isCustom': isCustom,
  };

  MaintenanceRule? get activeRule => scheduleSource == 'manufacturer'
      ? manufacturerRule
      : scheduleSource == 'custom'
      ? customRule
      : null;
}

class ServiceRecord {
  final String id;
  final String vehicleId;
  final String title;
  final String category;
  final int mileage;
  final DateTime date;
  final String notes;
  final double? cost;
  final String? taskId;

  const ServiceRecord({
    required this.id,
    required this.vehicleId,
    required this.title,
    required this.category,
    required this.mileage,
    required this.date,
    this.notes = '',
    this.cost,
    this.taskId,
  });

  factory ServiceRecord.fromJson(Map<String, dynamic> json) => ServiceRecord(
    id: json['id'] as String,
    vehicleId: json['vehicleId'] as String,
    title: json['title'] as String,
    category: json['category'] as String,
    mileage: json['mileage'] as int,
    date: DateTime.parse(json['date'] as String),
    notes: json['notes'] as String,
    cost: (json['cost'] as num?)?.toDouble(),
    taskId: json['taskId'] as String?,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'vehicleId': vehicleId,
    'title': title,
    'category': category,
    'mileage': mileage,
    'date': date.toIso8601String(),
    'notes': notes,
    'cost': cost,
    'taskId': taskId,
  };
}

class MaintenanceRule {
  final String type;
  final int? distanceKm, months;
  final List<int> distanceMilestones, monthMilestones;
  final DateTime? vehicleStartDate;
  final String conditions, notes;
  final String? sourceDocumentId;
  final int? sourcePage;
  const MaintenanceRule({
    this.type = 'recurring',
    this.distanceKm,
    this.months,
    this.distanceMilestones = const [],
    this.monthMilestones = const [],
    this.vehicleStartDate,
    this.conditions = '',
    this.notes = '',
    this.sourceDocumentId,
    this.sourcePage,
  });
  factory MaintenanceRule.fromJson(Map<String, dynamic> data) =>
      MaintenanceRule(
        type: data['type'] as String,
        distanceKm: data['distanceKm'] as int?,
        months: data['months'] as int?,
        distanceMilestones: (data['distanceMilestones'] as List? ?? [])
            .cast<int>(),
        monthMilestones: (data['monthMilestones'] as List? ?? []).cast<int>(),
        vehicleStartDate: DateTime.tryParse(
          data['vehicleStartDate'] as String? ?? '',
        ),
        conditions: data['conditions'] as String? ?? '',
        notes: data['notes'] as String? ?? '',
        sourceDocumentId: data['sourceDocumentId'] as String?,
        sourcePage: data['sourcePage'] as int?,
      );
  Map<String, dynamic> toJson() => {
    'type': type,
    'distanceKm': distanceKm,
    'months': months,
    'distanceMilestones': distanceMilestones,
    'monthMilestones': monthMilestones,
    'vehicleStartDate': vehicleStartDate?.toIso8601String(),
    'conditions': conditions,
    'notes': notes,
    'sourceDocumentId': sourceDocumentId,
    'sourcePage': sourcePage,
  };
}

class MaintenanceStatus {
  final String label;
  final int? nextKm, remainingKm;
  final DateTime? nextDate;
  const MaintenanceStatus(
    this.label, {
    this.nextKm,
    this.remainingKm,
    this.nextDate,
  });
  factory MaintenanceStatus.fromJson(Map<String, dynamic> json) =>
      MaintenanceStatus(
        json['label'] as String,
        nextKm: json['nextKm'] as int?,
        remainingKm: json['remainingKm'] as int?,
        nextDate: DateTime.tryParse(json['nextDate'] as String? ?? ''),
      );
  String get description => [
    label,
    if (nextKm != null) 'At $nextKm km',
    if (remainingKm != null)
      remainingKm! < 0
          ? '${-remainingKm!} km overdue'
          : remainingKm == 0
          ? 'Due at the recorded mileage'
          : '$remainingKm km remaining',
    if (nextDate != null) 'Next date: ${formatDate(nextDate!)}',
  ].join('\n');
}

const maintenanceCategories = [
  'Tyre Condition and Pressure',
  'Engine and Fluids',
  'Other',
];

String formatDate(DateTime date) => '${date.day}/${date.month}/${date.year}';

String maintenanceActionLabel(String action) => switch (action) {
  'inspect' => 'Check / inspect',
  'replace' => 'Replace',
  'service' => 'Service',
  _ => action,
};

String scheduleSourceLabel(String source) => switch (source) {
  'manufacturer' => 'Manufacturer schedule',
  'custom' => 'Personal schedule',
  _ => 'History only',
};

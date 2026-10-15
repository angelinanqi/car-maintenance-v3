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
    if (nextKm != null) 'Next: $nextKm km ($remainingKm km remaining)',
    if (nextDate != null) 'Next date: ${formatDate(nextDate!)}',
  ].join('\n');
}

// Retained for local rule checks. Production screens use FastAPI-calculated
// status from the snapshot; AI never supplies or changes intervals.
MaintenanceStatus maintenanceStatus(
  MaintenanceTask task,
  List<ServiceRecord> records,
  int odometer,
  DateTime now, {
  int dueSoonKm = 1000,
  int dueSoonDays = 30,
}) {
  final rule = task.activeRule;
  if (rule == null) return const MaintenanceStatus('No schedule');
  if (rule.type == 'informational' || rule.conditions.isNotEmpty) {
    return const MaintenanceStatus(
      'Information required — review schedule conditions',
    );
  }
  final history = records.where((r) => r.taskId == task.id).toList()
    ..sort((a, b) => b.date.compareTo(a.date));
  final last = history.isEmpty ? null : history.first;
  int? km;
  DateTime? date;
  var missing = false;
  if (rule.type == 'recurring') {
    if (last == null || (rule.distanceKm == null && rule.months == null)) {
      return const MaintenanceStatus('Information required');
    }
    if ((rule.distanceKm != null && rule.distanceKm! <= 0) ||
        (rule.months != null && rule.months! <= 0)) {
      return const MaintenanceStatus('Information required');
    }
    if (rule.distanceKm != null) km = last.mileage + rule.distanceKm!;
    if (rule.months != null) date = addMonths(last.date, rule.months!);
  } else if (rule.type == 'milestone') {
    final distances = [...rule.distanceMilestones]..sort();
    for (final milestone in distances) {
      if (last == null || milestone > last.mileage) {
        km = milestone;
        break;
      }
    }
    if (rule.monthMilestones.isNotEmpty && rule.vehicleStartDate == null) {
      missing = true;
    }
    if (rule.vehicleStartDate != null) {
      final months = [...rule.monthMilestones]..sort();
      for (final milestone in months) {
        final candidate = addMonths(rule.vehicleStartDate!, milestone);
        if (last == null || candidate.isAfter(last.date)) {
          date = candidate;
          break;
        }
      }
    }
    if (km == null && date == null && !missing) {
      return const MaintenanceStatus('Published milestones completed');
    }
  } else {
    return const MaintenanceStatus('Information required');
  }
  final today = DateTime(now.year, now.month, now.day);
  final remaining = km == null ? null : km - odometer;
  final days = date?.difference(today).inDays;
  if (rule.type == 'milestone' && last == null) {
    return MaintenanceStatus(
      'Published milestone — confirm service history',
      nextKm: km,
      remainingKm: remaining,
      nextDate: date,
    );
  }
  final due =
      (remaining != null && remaining <= 0) || (days != null && days <= 0);
  final soon =
      (remaining != null && remaining <= dueSoonKm) ||
      (days != null && days <= dueSoonDays);
  return MaintenanceStatus(
    due
        ? 'Due / Overdue'
        : missing
        ? 'Information required'
        : soon
        ? 'Due soon'
        : 'Upcoming',
    nextKm: km,
    remainingKm: remaining,
    nextDate: date,
  );
}

DateTime addMonths(DateTime date, int months) {
  final first = DateTime(date.year, date.month + months);
  final lastDay = DateTime(first.year, first.month + 1, 0).day;
  return DateTime(
    first.year,
    first.month,
    date.day > lastDay ? lastDay : date.day,
  );
}

const maintenanceCategories = [
  'Tyre Condition and Pressure',
  'Engine and Fluids',
  'Other',
];

String formatDate(DateTime date) => '${date.day}/${date.month}/${date.year}';

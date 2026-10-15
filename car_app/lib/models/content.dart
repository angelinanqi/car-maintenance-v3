class Lesson {
  final String id;
  final String title;
  final String content;
  final String? categoryId;
  final String introduction;
  final int? readingMinutes;
  final List<String> relatedLessonIds, maintenanceItemIds;
  const Lesson(
    this.id,
    this.title,
    this.content, {
    this.categoryId,
    this.introduction = '',
    this.readingMinutes,
    this.relatedLessonIds = const [],
    this.maintenanceItemIds = const [],
  });
}

class LearningTrack {
  final String title;
  final String subtitle;
  final List<Lesson> lessons;
  const LearningTrack(this.title, this.subtitle, this.lessons);
}

class EmergencyStep {
  final String id;
  final String title;
  final String description;
  final String imageUrl;
  final String? localImagePath;
  const EmergencyStep({
    required this.id,
    required this.title,
    required this.description,
    this.imageUrl = '',
    this.localImagePath,
  });

  factory EmergencyStep.fromJson(
    Map<String, dynamic> json, {
    bool remote = false,
  }) => EmergencyStep(
    id: json['id'] as String,
    title: json['title'] as String,
    description: json['description'] as String,
    imageUrl: json['imageUrl'] as String? ?? '',
    localImagePath: remote ? null : json['localImagePath'] as String?,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'description': description,
    'imageUrl': imageUrl,
    if (localImagePath != null) 'localImagePath': localImagePath,
  };
}

class EmergencyGuide {
  final String id;
  final String title;
  final List<EmergencyStep> steps;
  final bool reviewed;
  final String? source;
  final String? reviewedAt;
  final String? scenarioKey;
  final String? updatedAt;
  final bool savedOffline;
  final bool legacy;
  final bool bundled;
  const EmergencyGuide({
    required this.id,
    required this.title,
    required this.steps,
    required this.reviewed,
    this.source,
    this.reviewedAt,
    this.scenarioKey,
    this.updatedAt,
    this.savedOffline = false,
    this.legacy = false,
    this.bundled = false,
  });

  bool get available =>
      reviewed &&
      steps.isNotEmpty &&
      source != null &&
      source!.isNotEmpty &&
      reviewedAt != null &&
      reviewedAt!.isNotEmpty;

  factory EmergencyGuide.fromJson(
    Map<String, dynamic> json, {
    bool offline = false,
    bool remote = false,
  }) => EmergencyGuide(
    id: json['id'] as String,
    title: json['title'] as String,
    steps: (json['steps'] as List)
        .asMap()
        .entries
        .map(
          (entry) => entry.value is String
              ? EmergencyStep(
                  id: 'legacy-${entry.key}',
                  title: 'Step ${entry.key + 1}',
                  description: entry.value as String,
                )
              : EmergencyStep.fromJson(
                  Map<String, dynamic>.from(entry.value as Map),
                  remote: remote,
                ),
        )
        .toList(),
    reviewed: remote
        ? json['status'] == 'published'
        : json['reviewed'] == true || json['status'] == 'published',
    source: json['source'] as String?,
    reviewedAt: (json['reviewed_at'] ?? json['reviewedAt']) as String?,
    scenarioKey:
        json['scenario_key'] as String? ??
        (remote ? null : json['id'] as String),
    updatedAt: json['updated_at'] as String?,
    savedOffline: offline,
    legacy: !remote && (json['legacy'] == true || !json.containsKey('status')),
    bundled: !remote && json['bundled'] == true,
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'steps': steps.map((step) => step.toJson()).toList(),
    'status': reviewed ? 'published' : 'draft',
    'source': source,
    'reviewed_at': reviewedAt,
    'scenario_key': scenarioKey,
    'updated_at': updatedAt,
    'legacy': legacy,
  };
}

class OwnerManual {
  final String id, name, scope, sourceType;
  final int sizeBytes;
  const OwnerManual({
    required this.id,
    required this.name,
    required this.scope,
    required this.sourceType,
    required this.sizeBytes,
  });

  factory OwnerManual.fromJson(Map<String, dynamic> data) => OwnerManual(
    id: data['id'] as String,
    name: data['name'] as String,
    scope: data['car_model'] as String,
    sourceType: data['source_type'] as String,
    sizeBytes: data['size_bytes'] as int,
  );
}

import 'companion.dart';

class Lesson {
  final String id;
  final String title;
  final String content;
  final String? categoryId;
  final String introduction;
  final int? readingMinutes;
  final List<String> relatedLessonIds, maintenanceItemIds;
  final String revision;
  final bool beginnerFriendly, featured;
  final List<String> outcomes;
  final List<ExplorationSection> sections;
  const Lesson(
    this.id,
    this.title,
    this.content, {
    this.categoryId,
    this.introduction = '',
    this.readingMinutes,
    this.relatedLessonIds = const [],
    this.maintenanceItemIds = const [],
    this.revision = '',
    this.beginnerFriendly = false,
    this.featured = false,
    this.outcomes = const [],
    this.sections = const [],
  });

  factory Lesson.fromJson(Map<String, dynamic> data) => Lesson(
    data['id'] as String,
    data['title'] as String,
    data['content'] as String,
    categoryId: data['category_id'] as String?,
    introduction: data['description'] as String? ?? '',
    readingMinutes: data['reading_minutes'] as int?,
    relatedLessonIds: (data['related_lesson_ids'] as List? ?? [])
        .cast<String>(),
    maintenanceItemIds: (data['maintenance_item_ids'] as List? ?? [])
        .cast<String>(),
    revision: data['updated_at'] as String? ?? '',
    beginnerFriendly: data['beginner_friendly'] == true,
    featured: data['featured_in_companion'] == true,
    outcomes: (data['learning_outcomes'] as List? ?? []).cast<String>(),
    sections: ExplorationSection.fromGuide(data),
  );

  Map<String, dynamic> activityAt(int index) => {
    'kind': 'guide',
    'guide_id': id,
    if (sections.isNotEmpty) 'step_id': sections[index].id,
    'revision': revision,
  };
}

class LearningTrack {
  final String? id;
  final String title;
  final String subtitle;
  final List<Lesson> lessons;
  const LearningTrack(this.title, this.subtitle, this.lessons, {this.id});
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
  final String description;
  final String safetyWarnings;
  final String category;
  final int displayOrder;
  bool get isGeneralBreakdown =>
      scenarioKey == 'breakdown' || scenarioKey == 'roadside-breakdown';
  bool get isAccident =>
      scenarioKey == 'minor-accident' || scenarioKey == 'after-collision';
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
    this.description = '',
    this.safetyWarnings = '',
    this.category = '',
    this.displayOrder = 0,
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
    steps: _actionSteps(json, remote: remote)
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
    description: json['description'] as String? ?? '',
    safetyWarnings: json['safety_warnings'] as String? ?? '',
    category: json['category'] as String? ?? '',
    displayOrder: json['display_order'] as int? ?? 0,
  );

  // The public API prepends these exact compatibility steps for older readers.
  // Only remove a prefix backed by the corresponding structured field. Legacy
  // caches without metadata retain all their steps, including safety information.
  static List<dynamic> _actionSteps(
    Map<String, dynamic> json, {
    required bool remote,
  }) {
    final steps = List<dynamic>.from(json['steps'] as List);
    if (!remote) return steps;
    for (final field in ['description', 'safety_warnings']) {
      final text = json[field] as String? ?? '';
      final title = field == 'description' ? 'Situation' : 'Safety warnings';
      if (text.isNotEmpty &&
          steps.isNotEmpty &&
          steps.first is Map &&
          steps.first['title'] == title &&
          steps.first['description'] == text) {
        steps.removeAt(0);
      }
    }
    return steps;
  }

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
    'description': description,
    'safety_warnings': safetyWarnings,
    'category': category,
    'display_order': displayOrder,
  };
}

class OwnerManual {
  final String id, name, sourceType;
  final bool vehicleIndependent;
  final int sizeBytes;
  const OwnerManual({
    required this.id,
    required this.name,
    required this.vehicleIndependent,
    required this.sourceType,
    required this.sizeBytes,
  });

  factory OwnerManual.fromJson(Map<String, dynamic> data) => OwnerManual(
    id: data['id'] as String,
    name: data['name'] as String,
    vehicleIndependent: data['vehicle_independent'] as bool,
    sourceType: data['source_type'] as String,
    sizeBytes: data['size_bytes'] as int,
  );
}

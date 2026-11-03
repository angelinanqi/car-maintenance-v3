import 'package:html/parser.dart' as html;
import 'package:html/dom.dart' as dom;

class ExplorationOption {
  final String id, text, feedback;
  const ExplorationOption(this.id, this.text, this.feedback);
  factory ExplorationOption.fromJson(Map<String, dynamic> data) =>
      ExplorationOption(
        data['id'] as String,
        data['text'] as String,
        data['feedback'] as String,
      );
}

class ExplorationSection {
  final String id, title, content, example;
  final String? question;
  final String? sectionId;
  final List<ExplorationOption> options;
  const ExplorationSection({
    required this.id,
    required this.title,
    required this.content,
    this.example = '',
    this.question,
    this.sectionId,
    this.options = const [],
  });

  static List<ExplorationSection> fromGuide(Map<String, dynamic> guide) {
    final document = html.parseFragment(guide['content'] as String);
    final result = <ExplorationSection>[];
    final exploration = guide['exploration'] as Map?;
    for (final raw in exploration?['steps'] as List? ?? []) {
      final step = Map<String, dynamic>.from(raw as Map);
      final headings = document.querySelectorAll('h2[data-section-id]');
      final matching = headings.where(
        (heading) =>
            heading.attributes['data-section-id'] == step['section_id'],
      );
      if (matching.isEmpty) continue;
      final heading = matching.first;
      final siblings = heading.parentNode!.nodes;
      final buffer = StringBuffer();
      for (
        var index = siblings.indexOf(heading);
        index < siblings.length;
        index++
      ) {
        final node = siblings[index];
        if (index != siblings.indexOf(heading) &&
            node is dom.Element &&
            node.localName == 'h2')
          break;
        // Element.outerHtml preserves illustrations and ordered instructions.
        buffer.write(node is dom.Element ? node.outerHtml : node.text);
      }
      final activity = step['activity'] as Map?;
      result.add(
        ExplorationSection(
          id: step['id'] as String,
          sectionId: step['section_id'] as String?,
          title: heading.text,
          content: buffer.toString(),
          example: step['example_html'] as String? ?? '',
          question: activity?['prompt'] as String?,
          options: (activity?['options'] as List? ?? [])
              .map(
                (option) => ExplorationOption.fromJson(
                  Map<String, dynamic>.from(option as Map),
                ),
              )
              .toList(),
        ),
      );
    }
    return result;
  }
}

class ServicePlan {
  final String? id;
  final String fingerprint, vehicleId, date;
  final int mileage, totalTasks;
  final bool stale;
  final Map<String, List<Map<String, dynamic>>> groups;
  const ServicePlan({
    this.id,
    required this.fingerprint,
    required this.vehicleId,
    required this.date,
    required this.mileage,
    required this.totalTasks,
    required this.groups,
    this.stale = false,
  });
  factory ServicePlan.fromJson(Map<String, dynamic> data) {
    final snapshot = Map<String, dynamic>.from(data['snapshot'] as Map);
    return ServicePlan(
      id: data['id'] as String?,
      fingerprint: data['fingerprint'] as String,
      vehicleId: snapshot['vehicle_id'] as String,
      date: snapshot['as_of'] as String,
      mileage: snapshot['mileage'] as int,
      totalTasks: snapshot['total_tasks'] as int,
      stale: data['stale'] == true,
      groups: (snapshot['groups'] as Map).map(
        (key, value) => MapEntry(
          key as String,
          (value as List)
              .map((item) => Map<String, dynamic>.from(item as Map))
              .toList(),
        ),
      ),
    );
  }
  Map<String, dynamic> get activity => {
    'kind': 'plan',
    'plan_id': id,
    'revision': fingerprint,
  };

  String asNotes() {
    final lines = <String>[
      'Saved service proposal · $date',
      'Recorded mileage: $mileage km',
      '',
    ];
    var length = lines.join('\n').length;
    for (final group in ['due', 'discuss', 'check']) {
      for (final item in groups[group] ?? <Map<String, dynamic>>[]) {
        final timing = item['status'] as Map;
        final line =
            '${item['title']} · ${item['action']} · ${timing['label']}'
            '${timing['nextKm'] == null ? '' : ' · ${timing['nextKm']} km'}'
            '${timing['nextDate'] == null ? '' : ' · ${timing['nextDate']}'}';
        if (length + line.length > 10000) {
          lines.add(
            'Additional items are available in the saved service plan.',
          );
          return lines.join('\n');
        }
        lines.add(line);
        length += line.length + 1;
      }
    }
    return lines.join('\n');
  }
}

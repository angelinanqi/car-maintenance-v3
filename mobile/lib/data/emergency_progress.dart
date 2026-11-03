import 'dart:convert';
import 'package:crypto/crypto.dart';
import '../models/content.dart';
import 'local_store.dart';

/// Device-local navigation state, independent of incident records and accounts.
class EmergencyProgress {
  final String guideId, revision, stepId;
  final Set<String> completed;
  const EmergencyProgress({
    required this.guideId,
    required this.revision,
    required this.stepId,
    required this.completed,
  });

  static String fingerprint(EmergencyGuide guide) => sha256
      .convert(
        utf8.encode(
          jsonEncode([
            guide.updatedAt,
            guide.description,
            guide.safetyWarnings,
            for (final step in guide.steps)
              [
                step.id,
                step.title,
                step.description,
                step.imageUrl,
                for (final media in step.media)
                  [media['id'], media['url'], media['sha256']],
              ],
          ]),
        ),
      )
      .toString();

  bool matches(EmergencyGuide guide) =>
      guide.available &&
      guide.id == guideId &&
      revision == fingerprint(guide) &&
      guide.steps.any((s) => s.id == stepId);

  Map<String, dynamic> toJson() => {
    'guideId': guideId,
    'revision': revision,
    'stepId': stepId,
    'completed': completed.toList(),
  };

  static EmergencyProgress? parse(Object? value) {
    if (value is! Map ||
        value['guideId'] is! String ||
        value['revision'] is! String ||
        value['stepId'] is! String ||
        value['completed'] is! List ||
        !(value['completed'] as List).every((id) => id is String))
      return null;
    return EmergencyProgress(
      guideId: value['guideId'],
      revision: value['revision'],
      stepId: value['stepId'],
      completed: (value['completed'] as List).cast<String>().toSet(),
    );
  }
}

class EmergencyProgressStore {
  final LocalStore store;
  EmergencyProgressStore(this.store);
  static const filename = 'emergency_progress.json';
  static final _writes = Expando<Future<void>>();

  Future<Map<String, dynamic>> _read() async {
    try {
      return await store.read(filename) ?? {};
    } on TypeError {
      return {};
    } on FormatException {
      // A broken navigation checkpoint must remain recoverable by a new save.
      return {};
    }
  }

  Future<EmergencyProgress?> latest() async {
    await (_writes[store] ?? Future<void>.value());
    final data = await _read();
    return EmergencyProgress.parse(data['latest']);
  }

  Future<EmergencyProgress?> forGuide(String id) async {
    await (_writes[store] ?? Future<void>.value());
    final data = await _read();
    final guides = data['guides'];
    return EmergencyProgress.parse(guides is Map ? guides[id] : null);
  }

  /// Serialize writes so rapid navigation cannot overwrite a newer checkpoint.
  Future<void> save(EmergencyProgress progress) => _enqueue(() async {
    final data = await _read();
    final guides = Map<String, dynamic>.from(
      data['guides'] is Map ? data['guides'] : {},
    );
    guides.remove(progress.guideId);
    guides[progress.guideId] = progress.toJson();
    await store.write(filename, {
      'latest': progress.toJson(),
      'guides': guides,
    });
  });

  Future<void> clear(String id) => _enqueue(() async {
    final data = await _read();
    final guides = Map<String, dynamic>.from(
      data['guides'] is Map ? data['guides'] : {},
    )..remove(id);
    await store.write(filename, {
      'latest': EmergencyProgress.parse(data['latest'])?.guideId == id
          ? (guides.isEmpty ? null : guides.values.last)
          : data['latest'],
      'guides': guides,
    });
  });

  Future<void> _enqueue(Future<void> Function() operation) {
    final result = (_writes[store] ?? Future<void>.value()).then(
      (_) => operation(),
    );
    _writes[store] = result.catchError((Object _) {});
    return result;
  }
}

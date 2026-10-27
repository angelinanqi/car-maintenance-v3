import 'dart:io';
import 'package:image_picker/image_picker.dart';
import 'local_store.dart';
import 'mobile_repository.dart';

class AccidentRepository {
  final LocalStore store;
  final ImagePicker picker;
  final String? owner;
  final MobileRepository? remote;
  AccidentRepository(this.store, {ImagePicker? picker, this.owner, this.remote})
    : picker = picker ?? ImagePicker();
  String get _draftFile =>
      owner == null ? 'accident_draft.json' : 'accident_draft_$owner.json';
  String get _recordsFile => 'incidents_${owner ?? 'guest'}.json';
  String get _draftsFile => 'accident_drafts_${owner ?? 'guest'}.json';
  String get _photoTargetFile =>
      'accident_photo_target_${owner ?? 'guest'}.json';
  Future<void> _writes = Future.value();
  Future<void> _write(Future<void> Function() operation) {
    final result = _writes.then((_) => operation());
    _writes = result.catchError((_) {});
    return result;
  }

  Future<Map<String, dynamic>> load() async {
    final saved = await drafts();
    return saved.isEmpty ? newDraft() : saved.first;
  }

  Map<String, dynamic> newDraft() {
    final now = DateTime.now();
    return {
      'version': 1,
      'id': now.microsecondsSinceEpoch.toString(),
      'type': 'Road accident',
      'location': '',
      'occurredAt': now.toIso8601String(),
      'name': '',
      'plate': '',
      'phone': '',
      'insurer': '',
      'details': '',
      'photos': <String>[],
    };
  }

  Future<List<Map<String, dynamic>>> drafts() async {
    final manifest = await store.read(_draftsFile);
    if (manifest != null) {
      return (manifest['drafts'] as List)
          .map((row) => Map<String, dynamic>.from(row as Map))
          .toList();
    }
    // Import the earlier single draft without deleting its original file.
    final data = await store.read(_draftFile);
    if (data != null && data['version'] != 1) {
      throw const FormatException('Unsupported accident draft');
    }
    return data == null ? [] : [data];
  }

  Future<void> save(Map<String, dynamic> draft) => _write(() async {
    final rows = await drafts();
    rows.removeWhere((row) => row['id'] == draft['id']);
    rows.insert(0, {
      ...draft,
      'updatedAt': DateTime.now().toUtc().toIso8601String(),
    });
    await store.write(_draftsFile, {'drafts': rows});
  });

  Future<void> completeDraft(Map<String, dynamic> draft) => _write(() async {
    // Save history first. If removing the draft fails, the saved form is safe.
    await _saveRecord(draft);
    final rows = await drafts();
    rows.removeWhere((row) => row['id'] == draft['id']);
    await store.write(_draftsFile, {'drafts': rows});
  });

  Future<void> discardDraft(String id) => _write(() async {
    final rows = await drafts();
    rows.removeWhere((row) => row['id'] == id);
    await store.write(_draftsFile, {'drafts': rows});
    // Photos may also be referenced by saved forms; retain their files.
  });

  Future<List<Map<String, dynamic>>> records() async {
    final data = await store.read(_recordsFile);
    return (data?['records'] as List? ?? [])
        .map((r) => Map<String, dynamic>.from(r as Map))
        .toList()
      ..sort(
        (a, b) =>
            (b['updatedAt'] as String).compareTo(a['updatedAt'] as String),
      );
  }

  Future<void> saveRecord(Map<String, dynamic> record) =>
      _write(() => _saveRecord(record));

  Future<void> _saveRecord(Map<String, dynamic> record) async {
    final rows = await records();
    final id = record['id'] as String;
    Map<String, dynamic>? previous;
    for (final row in rows) {
      if (row['id'] == id) previous = row;
    }
    final next = {
      ...?previous,
      ...record,
      'updatedAt': DateTime.now().toUtc().toIso8601String(),
      'pendingSync': true,
    };
    rows.removeWhere((r) => r['id'] == id);
    rows.add(next);
    await store.write(_recordsFile, {'records': rows});
  }

  Future<bool> backupEnabled() async =>
      owner != null &&
      (await store.read('incident_backup_$owner.json'))?['enabled'] == true;
  Future<void> enableBackup(bool enabled) async {
    if (owner == null) throw StateError('Sign in to enable cloud backup.');
    await store.write('incident_backup_$owner.json', {'enabled': enabled});
  }

  Future<void> importGuestRecords() => _write(() async {
    if (owner == null) return;
    final guest = await AccidentRepository(store).records();
    final current = await records();
    final ids = current.map((r) => r['id']).toSet();
    current.addAll(
      guest
          .where((r) => !ids.contains(r['id']))
          .map((r) => {...r, 'pendingSync': true}),
    );
    await store.write(_recordsFile, {'records': current});
    // Only clear the guest list after the account copy is durable. Photos are
    // retained and can be referenced by both copies during this transaction.
    await store.write('incidents_guest.json', {'records': []});
  });
  Future<void> sync() async {
    if (!await backupEnabled() ||
        remote == null ||
        remote!.account.userId != owner) {
      return;
    }
    final token = remote!.token;
    final rows = await records();
    for (final record in rows.where((r) => r['pendingSync'] == true)) {
      if (remote!.account.userId != owner) return;
      final stamp = record['updatedAt'];
      // Durable local IDs make repeated PUT requests idempotent. Local photo
      // paths are never uploaded; photo-object support is a Pass 3 dependency.
      final result = await remote!.api.put(
        '/mobile/me/incidents/${Uri.encodeComponent(record['id'] as String)}',
        {
          ...record,
          'photos': [],
          'photoCount': (record['photos'] as List? ?? []).length,
        },
        token: token,
      );
      await _write(() async {
        final current = await records();
        for (final row in current) {
          if (row['id'] == record['id']) {
            row['cloudRevision'] = result['cloudRevision'];
            if (row['updatedAt'] == stamp) row['pendingSync'] = false;
          }
        }
        await store.write(_recordsFile, {'records': current});
      });
    }
    if (remote!.account.userId != owner) return;
    final cloud = await remote!.api.listAll(
      '/mobile/me/incidents',
      token: token,
    );
    await _write(() async {
      final local = await records();
      final byId = {for (final row in local) row['id']: row};
      for (final row in cloud) {
        final current = byId[row['id']];
        if (current != null && current['pendingSync'] == true) continue;
        final cloudTime = DateTime.parse(row['updatedAt'] as String);
        if (current == null ||
            cloudTime.isAfter(DateTime.parse(current['updatedAt'] as String))) {
          byId[row['id']] = {
            ...row,
            'pendingSync': false,
            'photos': current?['photos'] ?? <String>[],
          };
        }
      }
      await store.write(_recordsFile, {'records': byId.values.toList()});
    });
  }

  Future<String?> pickPhoto(ImageSource source) async {
    final image = await picker.pickImage(
      source: source,
      maxWidth: 2000,
      imageQuality: 85,
    );
    return image == null ? null : store.savePhoto(image.path);
  }

  Future<void> rememberPhotoTarget(String id, {required bool savedRecord}) =>
      store.write(_photoTargetFile, {'id': id, 'savedRecord': savedRecord});

  Future<void> clearPhotoTarget() => store.write(_photoTargetFile, {});

  Future<void> recoverLostPhotos() async {
    if (!Platform.isAndroid) return;
    final recovered = await picker.retrieveLostData();
    if (recovered.exception != null) throw recovered.exception!;
    if (recovered.files == null || recovered.files!.isEmpty) return;
    final target = await store.read(_photoTargetFile);
    final savedRecord = target?['savedRecord'] == true;
    final rows = savedRecord ? await records() : await drafts();
    final matches = rows.where((row) => row['id'] == target?['id']).toList();
    // Old app versions did not save a picker target; recover into the latest draft.
    final draft = matches.isNotEmpty ? matches.first : await load();
    final photos = (draft['photos'] as List).cast<String>().toList();
    for (final image in recovered.files!) {
      if (photos.length >= 6) break;
      photos.add(await store.savePhoto(image.path));
    }
    if (savedRecord && matches.isNotEmpty) {
      await saveRecord({...draft, 'photos': photos});
    } else {
      await save({...draft, 'photos': photos});
    }
    await clearPhotoTarget();
  }
}

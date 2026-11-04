import 'dart:io';
import 'package:image_picker/image_picker.dart';
import 'local_store.dart';
import 'mobile_repository.dart';
import 'api_client.dart';
import 'package:uuid/uuid.dart';

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
  Future<void> _write(Future<void> Function() operation) =>
      store.synchronized('incidents:${owner ?? 'guest'}', operation);

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

  Map<String, dynamic> _validatedRow(dynamic value) {
    if (value is! Map) throw const FormatException('Invalid incident row');
    final row = Map<String, dynamic>.from(value);
    if ((row['version'] ?? 1) != 1 ||
        row['id'] is! String ||
        (row['id'] as String).isEmpty ||
        row['type'] is! String ||
        (row['type'] as String).trim().isEmpty ||
        row['occurredAt'] is! String ||
        DateTime.tryParse(row['occurredAt'] as String) == null ||
        row['photos'] is! List ||
        (row['photos'] as List).length > 6 ||
        (row['photos'] as List).any((photo) => photo is! String)) {
      throw const FormatException('Invalid or unsupported incident record');
    }
    for (final field in [
      'location',
      'name',
      'plate',
      'phone',
      'insurer',
      'details',
    ]) {
      if (row[field] != null && row[field] is! String) {
        throw const FormatException('Invalid incident text');
      }
      row[field] ??= '';
    }
    if (row['mileage'] != null &&
        (row['mileage'] is! int ||
            row['mileage'] < 0 ||
            row['mileage'] > 2147483647)) {
      throw const FormatException('Invalid incident mileage');
    }
    row['version'] = 1;
    row['updatedAt'] ??= row['occurredAt'];
    if (row['updatedAt'] is! String ||
        DateTime.tryParse(row['updatedAt'] as String) == null) {
      throw const FormatException('Invalid incident update time');
    }
    return row;
  }

  List<Map<String, dynamic>> _validatedRows(dynamic rows) {
    if (rows is! List) throw const FormatException('Invalid incident list');
    final result = rows.map(_validatedRow).toList();
    if (result.map((row) => row['id']).toSet().length != result.length) {
      throw const FormatException('Duplicate incident identifiers');
    }
    return result;
  }

  Future<List<Map<String, dynamic>>> drafts() async {
    final manifest = await store.read(_draftsFile);
    if (manifest != null) {
      return _validatedRows(manifest['drafts']);
    }
    // Import the earlier single draft without deleting its original file.
    final data = await store.read(_draftFile);
    if (data != null && data['version'] != 1) {
      throw const FormatException('Unsupported accident draft');
    }
    return data == null ? [] : [_validatedRow(data)];
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
    final removed = rows.where((row) => row['id'] == id).toList();
    rows.removeWhere((row) => row['id'] == id);
    await store.write(_draftsFile, {'drafts': rows});
    await _cleanupPhotos(removed);
  });

  Future<List<Map<String, dynamic>>> records() async {
    final data = await store.read(_recordsFile);
    return (data == null
          ? <Map<String, dynamic>>[]
          : _validatedRows(data['records']))
      ..sort(
        (a, b) =>
            (b['updatedAt'] as String).compareTo(a['updatedAt'] as String),
      );
  }

  Future<void> saveRecord(Map<String, dynamic> record) =>
      _write(() => _saveRecord(record));

  Future<void> deleteGuestRecord(String id) => _write(() async {
    if (owner != null) {
      throw StateError('Account incident deletion is not supported yet.');
    }
    final rows = await records();
    final removed = rows.where((row) => row['id'] == id).toList();
    rows.removeWhere((row) => row['id'] == id);
    await store.write(_recordsFile, {'records': rows});
    await _cleanupPhotos(removed);
  });

  Future<void> _cleanupPhotos(List<Map<String, dynamic>> rows) async {
    for (final row in rows) {
      for (final photo in (row['photos'] as List).cast<String>()) {
        await store.removePhotoIfUnreferenced(photo);
      }
    }
  }

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

  Future<void> importGuestRecords() async {
    if (owner == null) return;
    final guestRepository = AccidentRepository(store);
    await _write(
      () => guestRepository._write(() async {
        final guest = await guestRepository.records();
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
      }),
    );
  }

  Future<void> sync() =>
      store.synchronized('incident-sync:${owner ?? 'guest'}', _sync);

  Future<void> _sync() async {
    if (!await backupEnabled() ||
        remote == null ||
        remote!.account.userId != owner) {
      return;
    }
    final token = remote!.token;
    final rows = await records();
    final conflicts = <String>{};
    for (final record in rows.where((r) => r['pendingSync'] == true)) {
      if (remote!.account.userId != owner) return;
      final stamp = record['updatedAt'];
      // Durable local IDs make repeated PUT requests idempotent. Local photo
      // paths are never uploaded; the incident API does not support photo uploads.
      Map<String, dynamic> result;
      try {
        result = await remote!.api.put(
          '/mobile/me/incidents/${Uri.encodeComponent(record['id'] as String)}',
          {
            for (final key in [
              'version',
              'id',
              'type',
              'mileage',
              'location',
              'occurredAt',
              'name',
              'plate',
              'phone',
              'insurer',
              'details',
              'updatedAt',
              'pendingSync',
              'cloudRevision',
            ])
              if (record.containsKey(key)) key: record[key],
            'photos': [],
            'photoCount': (record['photos'] as List? ?? []).length,
          },
          token: token,
        );
      } on ApiException catch (error) {
        if (error.statusCode != 409) rethrow;
        conflicts.add(record['id'] as String);
        continue;
      }
      await _write(() async {
        final current = await records();
        for (final row in current) {
          if (row['id'] == record['id']) {
            row['cloudRevision'] = result['cloudRevision'];
            row.remove('cloudConflict');
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
        if (current != null && current['pendingSync'] == true) {
          if (conflicts.contains(row['id'])) current['cloudConflict'] = true;
          continue;
        }
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
    if (conflicts.isNotEmpty) {
      throw const ApiException(
        'An incident changed on another device. Your local copy is safe. '
        'Choose Keep both copies in Incident options to finish its backup.',
        statusCode: 409,
      );
    }
  }

  Future<void> keepBothCopies(String id) => store.synchronized(
    'incident-sync:${owner ?? 'guest'}',
    () async {
      if (owner == null || remote?.account.userId != owner) {
        throw const ApiException(
          'Sign in to the original account to resolve this backup.',
        );
      }
      final cloud = await remote!.api.listAll(
        '/mobile/me/incidents',
        token: remote!.token,
      );
      final saved = cloud.where((row) => row['id'] == id).firstOrNull;
      if (saved == null) {
        throw const ApiException(
          'The cloud copy could not be found. Retry backup before continuing.',
        );
      }
      if (remote!.account.userId != owner) {
        throw const ApiException(
          'Your account changed. Reopen Incident options.',
        );
      }
      await _write(() async {
        final local = await records();
        final current = local.where((row) => row['id'] == id).firstOrNull;
        if (current == null || current['cloudConflict'] != true) return;
        final copy =
            {
                ...current,
                'id': const Uuid().v4(),
                'updatedAt': DateTime.now().toUtc().toIso8601String(),
                'pendingSync': true,
              }
              ..remove('cloudRevision')
              ..remove('cloudConflict');
        local.removeWhere((row) => row['id'] == id);
        local.addAll([
          _validatedRow({...saved, 'photos': <String>[], 'pendingSync': false}),
          copy,
        ]);
        await store.write(_recordsFile, {'records': local});
      });
    },
  );

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
    final copied = <String>[];
    try {
      for (final image in recovered.files!) {
        if (photos.length >= 6) break;
        final photo = await store.savePhoto(image.path);
        photos.add(photo);
        copied.add(photo);
      }
      if (savedRecord && matches.isNotEmpty) {
        await saveRecord({...draft, 'photos': photos});
      } else {
        await save({...draft, 'photos': photos});
      }
      await clearPhotoTarget();
    } catch (_) {
      for (final photo in copied) {
        await store.removePhotoIfUnreferenced(photo);
      }
      rethrow;
    }
  }
}

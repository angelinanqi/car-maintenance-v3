import 'dart:convert';
import 'dart:ui' as ui;
import 'package:flutter/services.dart';
import '../models/content.dart';
import 'local_store.dart';
import 'api_client.dart';

class ContentRepository {
  final LocalStore store;
  final AssetBundle bundle;
  final ApiClient? api;
  Future<void> _cacheWrites = Future.value();
  List<EmergencyGuide> _remoteGuides = [];
  String? warning;
  ContentRepository(this.store, {AssetBundle? bundle, this.api})
    : bundle = bundle ?? rootBundle;

  static const defaultChatStarters = [
    'Understanding my service records',
    'Finding the correct owner manual',
    'Understanding tyre pressure labels',
  ];

  Future<List<String>> chatStarters({bool refresh = false}) async {
    if (refresh && api != null) {
      final data = await api!.get('/mobile/chat-starters');
      final questions = (data['questions'] as List).cast<String>();
      await store.write('chat_starters.json', {'questions': questions});
      return questions;
    }
    final saved = await store.read('chat_starters.json');
    return saved == null
        ? List.of(defaultChatStarters)
        : (saved['questions'] as List).cast<String>();
  }

  Future<List<LearningTrack>> learningTracks() async {
    if (api == null) return [];
    final results = await Future.wait([
      api!.listAll('/guides'),
      api!.listAll('/categories'),
    ]);
    final categories = {
      for (final category in results[1]) category['id'] as String: category,
    };
    final grouped = <String, List<Lesson>>{
      for (final id in categories.keys) id: [],
    };
    for (final row in results[0]) {
      if (row['status'] != 'published') continue;
      final category = row['category_id'] as String?;
      final key = category ?? '';
      grouped
          .putIfAbsent(key, () => [])
          .add(
            Lesson(
              row['id'] as String,
              row['title'] as String,
              row['content'] as String,
              categoryId: category,
              introduction: row['description'] as String? ?? '',
              readingMinutes: row['reading_minutes'] as int?,
              relatedLessonIds: (row['related_lesson_ids'] as List? ?? [])
                  .cast<String>(),
              maintenanceItemIds: (row['maintenance_item_ids'] as List? ?? [])
                  .cast<String>(),
            ),
          );
    }
    return grouped.entries
        .map(
          (entry) => LearningTrack(
            categories[entry.key]?['name'] as String? ?? 'Uncategorised',
            categories[entry.key]?['description'] as String? ?? '',
            entry.value,
          ),
        )
        .toList();
  }

  Future<Lesson> lesson(String id) async {
    if (api == null) {
      throw const ApiException('No backend connection configured.');
    }
    final row = await api!.get('/guides/${Uri.encodeComponent(id)}');
    return Lesson(
      row['id'] as String,
      row['title'] as String,
      row['content'] as String,
      categoryId: row['category_id'] as String?,
      introduction: row['description'] as String? ?? '',
      readingMinutes: row['reading_minutes'] as int?,
      relatedLessonIds: (row['related_lesson_ids'] as List? ?? [])
          .cast<String>(),
      maintenanceItemIds: (row['maintenance_item_ids'] as List? ?? [])
          .cast<String>(),
    );
  }

  Future<List<OwnerManual>> manuals(String scope) async {
    if (api == null) return [];
    final rows = await api!.listAll('/manuals', query: {'car_model': scope});
    return rows.map(OwnerManual.fromJson).toList();
  }

  Uri manualUrl(OwnerManual manual) {
    if (api == null) {
      throw const ApiException('No backend connection is configured.');
    }
    return api!.endpoint('/documents/${manual.id}/download');
  }

  Future<String> manualText(OwnerManual manual) async {
    if (api == null) {
      throw const ApiException('No backend connection is configured.');
    }
    return utf8.decode(await api!.getBytes('/documents/${manual.id}/download'));
  }

  List<EmergencyGuide> _parse(Map<String, dynamic> data) {
    if (data['schemaVersion'] != 1 && data['schemaVersion'] != 2) {
      throw const FormatException('Unsupported emergency content version');
    }
    final guides = (data['guides'] as List)
        .map(
          (g) =>
              EmergencyGuide.fromJson(g as Map<String, dynamic>, offline: true),
        )
        .toList();
    if (guides.map((g) => g.id).toSet().length != guides.length) {
      throw const FormatException('Duplicate guide IDs');
    }
    for (final guide in guides) {
      if (guide.reviewed && !guide.available) {
        throw const FormatException('Incomplete reviewed guide');
      }
    }
    return guides;
  }

  Future<List<EmergencyGuide>> emergencyGuides() async {
    warning = null;
    final baseline = _parse(
      jsonDecode(await bundle.loadString('assets/emergency/guides.json'))
          as Map<String, dynamic>,
    );
    try {
      final cached = await store.read('emergency_content.json');
      if (cached == null) return baseline;
      final updates = _parse(cached);
      if (updates.any((guide) => !guide.available)) {
        throw const FormatException('Saved update has unreviewed guides');
      }
      final merged = {for (final guide in baseline) guide.id: guide};
      for (final guide in updates) {
        var complete = true;
        for (final step in guide.steps) {
          if (step.imageUrl.isNotEmpty &&
              (step.localImagePath == null ||
                  !await store.hasEmergencyImage(step.localImagePath!))) {
            complete = false;
          }
        }
        if (complete) {
          merged.removeWhere(
            (id, item) => item.bundled && item.scenarioKey == guide.scenarioKey,
          );
          merged[guide.id] = guide;
        } else {
          warning =
              'A saved guide is missing images. Download it again when online.';
        }
      }
      return _orderedGuides(merged.values.toList());
    } catch (_) {
      warning =
          'A saved content update could not be opened. The bundled catalogue is shown.';
      return baseline;
    }
  }

  Future<void> _editCache(Future<void> Function() action) {
    final operation = _cacheWrites.then((_) => action());
    _cacheWrites = operation.catchError((_) {});
    return operation;
  }

  Future<List<EmergencyGuide>> _savedGuides() async {
    final data = await store.read('emergency_content.json');
    return data == null ? [] : _parse(data);
  }

  Future<void> _writeGuides(List<EmergencyGuide> guides) =>
      store.write('emergency_content.json', {
        'schemaVersion': 2,
        'guides': guides.map((guide) => guide.toJson()).toList(),
      });

  Future<void> _removeImages(EmergencyGuide guide) async {
    for (final step in guide.steps) {
      if (step.localImagePath != null) {
        try {
          await store.removeEmergencyImage(step.localImagePath!);
        } catch (_) {
          // An orphaned image can be removed on a later save; the manifest is authoritative.
        }
      }
    }
  }

  Future<List<EmergencyGuide>> refreshEmergency() async {
    if (api == null) return emergencyGuides();
    try {
      final rows = await api!.listAll('/emergency/playbooks');
      final remote = rows
          .map((row) => EmergencyGuide.fromJson(row, remote: true))
          .toList();
      if (remote.any((guide) => !guide.available)) {
        throw const FormatException('Incomplete published emergency guide');
      }
      _remoteGuides = remote;
      final saved = await _savedGuides();
      for (final guide in saved.where(
        (guide) => !guide.legacy && !remote.any((item) => item.id == guide.id),
      )) {
        try {
          await api!.get('/emergency/playbooks/${guide.id}');
        } on ApiException catch (error) {
          if (error.statusCode == 404) await removeOfflineGuide(guide.id);
        }
      }
      return _catalogue();
    } catch (error) {
      final local = await emergencyGuides();
      warning =
          'Could not refresh emergency guides. Saved copies remain available. Check your connection and retry.';
      return local;
    }
  }

  Future<List<EmergencyGuide>> _catalogue() async {
    final local = await emergencyGuides();
    final merged = {for (final guide in local) guide.id: guide};
    for (final guide in _remoteGuides) {
      // Keep a bundled offline guide until a replacement has been downloaded
      // completely. Merely fetching an online catalogue cannot remove it.
      if (merged[guide.id]?.available != true) merged[guide.id] = guide;
    }
    return _orderedGuides(merged.values.toList(), useRemote: true);
  }

  List<EmergencyGuide> _orderedGuides(
    List<EmergencyGuide> guides, {
    bool useRemote = false,
  }) {
    final positions = {for (var i = 0; i < guides.length; i++) guides[i].id: i};
    final remote = useRemote ? _remoteGuides : <EmergencyGuide>[];
    final order = {for (final guide in remote) guide.id: guide.displayOrder};
    final remotePositions = {
      for (var i = 0; i < remote.length; i++) remote[i].id: i,
    };
    guides.sort((a, b) {
      final comparison = (order[a.id] ?? a.displayOrder).compareTo(
        order[b.id] ?? b.displayOrder,
      );
      if (comparison != 0) return comparison;
      return (remotePositions[a.id] ?? remote.length + positions[a.id]!)
          .compareTo(remotePositions[b.id] ?? remote.length + positions[b.id]!);
    });
    return guides;
  }

  Future<List<EmergencyGuide>> currentEmergencyCatalogue() => _catalogue();

  bool hasUpdate(EmergencyGuide guide) => _remoteGuides.any(
    (remote) => remote.id == guide.id && remote.updatedAt != guide.updatedAt,
  );

  Future<List<EmergencyGuide>> saveOfflineGuide(String id) async {
    if (api == null) {
      throw const ApiException('No backend connection is configured.');
    }
    final guide = EmergencyGuide.fromJson(
      await api!.get('/emergency/playbooks/$id'),
      remote: true,
    );
    if (!guide.available) {
      throw const FormatException(
        'Only complete published guides can be saved.',
      );
    }
    final downloaded = <String>[];
    try {
      final steps = <EmergencyStep>[];
      for (final step in guide.steps) {
        String? path;
        if (step.imageUrl.isNotEmpty) {
          final bytes = await api!.imageBytes(step.imageUrl);
          final codec = await ui.instantiateImageCodec(
            bytes,
            targetWidth: 1,
            targetHeight: 1,
          );
          codec.dispose();
          path = await store.saveEmergencyImage(bytes);
          downloaded.add(path);
        }
        steps.add(
          EmergencyStep(
            id: step.id,
            title: step.title,
            description: step.description,
            imageUrl: step.imageUrl,
            localImagePath: path,
          ),
        );
      }
      final saved = EmergencyGuide.fromJson({
        ...guide.toJson(),
        'steps': steps.map((step) => step.toJson()).toList(),
      }, offline: true);
      await _editCache(() async {
        final existing = await _savedGuides();
        final previous = existing.where((item) => item.id == id).toList();
        await _writeGuides([...existing.where((item) => item.id != id), saved]);
        for (final old in previous) {
          await _removeImages(old);
        }
      });
    } catch (_) {
      for (final path in downloaded) {
        await store.removeEmergencyImage(path);
      }
      rethrow;
    }
    return _catalogue();
  }

  Future<void> removeOfflineGuide(String id) => _editCache(() async {
    final existing = await _savedGuides();
    await _writeGuides(existing.where((guide) => guide.id != id).toList());
    for (final guide in existing.where((guide) => guide.id == id)) {
      await _removeImages(guide);
    }
  });

  Future<List<Map<String, dynamic>>> emergencyContacts({
    bool refresh = false,
  }) async {
    if (refresh && api != null) {
      final contacts = await api!.listAll('/emergency/contacts');
      await store.write('emergency_contacts.json', {
        'contacts': contacts,
        'savedAt': DateTime.now().toUtc().toIso8601String(),
      });
      return contacts;
    }
    final data = await store.read('emergency_contacts.json');
    final cached = (data?['contacts'] as List? ?? [])
        .cast<Map<String, dynamic>>();
    // An empty saved directory is an authoritative admin choice. Defaults only
    // apply before the first successful sync, including when offline.
    return data == null
        ? [
            {
              'id': 'my-emergency',
              'name': 'Malaysia emergency services',
              'phone': '999',
            },
            {
              'id': 'plus-line',
              'name': 'PLUS expressway assistance',
              'phone': '1800-88-0000',
              'description': 'For assistance on PLUS expressways',
            },
          ]
        : cached;
  }

}

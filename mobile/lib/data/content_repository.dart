import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../models/content.dart';
import 'local_store.dart';
import 'api_client.dart';

class ContentRepository {
  final LocalStore store;
  final ApiClient? api;
  Future<void> _cacheWrites = Future.value();
  Future<List<EmergencyGuide>>? _emergencyRefresh;
  List<EmergencyGuide> _remoteGuides = [];
  bool _catalogueLoaded = false;
  String? warning;
  ContentRepository(this.store, {this.api});

  Future<List<String>> chatStarters({bool refresh = false}) async {
    if (refresh && api != null) {
      final data = await api!.get('/mobile/chat-starters');
      final questions = (data['questions'] as List).cast<String>();
      await store.write('chat_starters.json', {'questions': questions});
      return questions;
    }
    final saved = await store.read('chat_starters.json');
    return saved == null
        ? <String>[]
        : (saved['questions'] as List).cast<String>();
  }

  Future<List<LearningTrack>> learningTracks() async {
    if (api == null)
      throw const ApiException('No backend connection configured.');
    final results = await Future.wait([
      api!.listAll('/guides', totalTimeout: api!.timeout),
      api!.listAll('/categories', totalTimeout: api!.timeout),
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
      grouped.putIfAbsent(key, () => []).add(Lesson.fromJson(row));
    }
    return grouped.entries
        .map(
          (entry) => LearningTrack(
            categories[entry.key]?['name'] as String? ?? 'Uncategorised',
            categories[entry.key]?['description'] as String? ?? '',
            entry.value,
            id: entry.key.isEmpty ? null : entry.key,
          ),
        )
        .toList();
  }

  Future<Lesson> lesson(String id) async {
    if (api == null) {
      throw const ApiException('No backend connection configured.');
    }
    final row = await api!.get('/guides/${Uri.encodeComponent(id)}');
    return Lesson.fromJson(row);
  }

  Future<List<OwnerManual>> manuals(String scope) async {
    if (api == null)
      throw const ApiException('No backend connection configured.');
    final rows = await api!.listAll(
      '/manuals',
      query: {'car_model': scope},
      totalTimeout: api!.timeout,
    );
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
    try {
      final cached = await store.read('emergency_content.json');
      if (cached == null) return [];
      final updates = _parse(cached);
      if (updates.any((guide) => !guide.available)) {
        throw const FormatException('Saved update has unreviewed guides');
      }
      for (final guide in updates) {
        if (!await _imagesPresent(guide)) {
          warning =
              'A saved guide is missing illustrations. Written instructions are available; download it again when online.';
        }
      }
      return _orderedGuides(updates);
    } catch (_) {
      warning =
          'Saved guides could not be opened. Connect to download published guides again.';
      return [];
    }
  }

  Future<bool> _imagesPresent(EmergencyGuide guide) async {
    for (final step in guide.steps) {
      if (step.imageUrl.isNotEmpty &&
          (step.localImagePath == null ||
              !await store.hasEmergencyImage(step.localImagePath!)))
        return false;
    }
    return true;
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

  Future<Set<String>> _excludedGuides() async {
    final data = await store.read('emergency_content.json');
    return (data?['excludedIds'] as List? ?? []).cast<String>().toSet();
  }

  Future<void> _writeGuides(
    List<EmergencyGuide> guides, {
    Set<String>? excludedIds,
  }) async {
    final excluded = excludedIds ?? await _excludedGuides();
    await store.write('emergency_content.json', {
      'schemaVersion': 2,
      'excludedIds': excluded.toList(),
      'guides': guides.map((guide) => guide.toJson()).toList(),
    });
  }

  Future<void> _removeImages(EmergencyGuide guide) async {
    for (final step in guide.steps) {
      if (step.localImagePath != null) {
        try {
          await store.removeEmergencyImage(step.localImagePath!);
        } catch (_) {
          debugPrint(
            'WARNING [emergency-content] Old illustration cleanup failed; manifest is authoritative.',
          );
        }
      }
    }
  }

  Future<List<EmergencyGuide>> refreshEmergency() {
    return _emergencyRefresh ??= _refreshEmergency().whenComplete(() {
      _emergencyRefresh = null;
    });
  }

  Future<List<EmergencyGuide>> _refreshEmergency() async {
    if (api == null) return emergencyGuides();
    warning = null;
    final warnings = <String>[];
    try {
      await emergencyContacts(refresh: true);
    } catch (_) {
      warnings.add(
        'Contacts could not be updated. Saved contacts are still available.',
      );
    }
    try {
      final rows = await api!.listAll('/emergency/playbooks');
      final remote = rows
          .map((row) => EmergencyGuide.fromJson(row, remote: true))
          .toList();
      if (remote.any((guide) => !guide.available)) {
        throw const FormatException('Incomplete published emergency guide');
      }
      _remoteGuides = remote;
      _catalogueLoaded = true;
      final saved = await emergencyGuides();
      // A successful complete catalogue is authoritative, including an empty one.
      // Remove withdrawn publications before saving any new revisions.
      await _editCache(
        () => _writeGuides(
          saved
              .where((guide) => remote.any((item) => item.id == guide.id))
              .toList(),
        ),
      );
      for (final guide in saved.where(
        (guide) => !remote.any((item) => item.id == guide.id),
      )) {
        await _removeImages(guide);
      }
      for (final guide in remote) {
        final existing = saved.where((item) => item.id == guide.id).firstOrNull;
        if (existing != null &&
            existing.updatedAt == guide.updatedAt &&
            await _imagesPresent(existing))
          continue;
        try {
          await _saveOfflineGuide(guide);
        } catch (_) {
          warnings.add(
            'Some guides could not be saved offline. Connect and retry.',
          );
        }
      }
    } catch (_) {
      warnings.add(
        'Could not refresh emergency guides. Saved copies remain available. Check your connection and retry.',
      );
    }
    warning = null;
    final result = await _catalogue();
    if (warnings.isNotEmpty) warning = warnings.toSet().join(' ');
    return result;
  }

  Future<List<EmergencyGuide>> _catalogue() async {
    final local = await emergencyGuides();
    if (!_catalogueLoaded) return local;
    final saved = {for (final guide in local) guide.id: guide};
    final guides = <EmergencyGuide>[];
    for (final guide in _remoteGuides) {
      final offline = saved[guide.id];
      guides.add(
        offline != null && offline.updatedAt == guide.updatedAt
            ? offline
            : guide,
      );
    }
    return _orderedGuides(guides, useRemote: true);
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
    await _saveOfflineGuide(guide, explicit: true);
    _remoteGuides = _remoteGuides
        .map((item) => item.id == guide.id ? guide : item)
        .toList();
    warning = null;
    return _catalogue();
  }

  Future<void> _saveOfflineGuide(
    EmergencyGuide guide, {
    bool explicit = false,
  }) async {
    if (!guide.available) {
      throw const FormatException(
        'Only complete published guides can be saved.',
      );
    }
    if (!explicit && (await _excludedGuides()).contains(guide.id)) return;
    final downloaded = <String>[];
    try {
      final steps = <EmergencyStep>[];
      for (final step in guide.steps) {
        String? path;
        if (step.imageUrl.isNotEmpty) {
          final bytes = await api!.imageBytes(step.imageUrl);
          await LocalStore.validateImage(bytes);
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
        final excluded = await _excludedGuides();
        if (!explicit && excluded.contains(guide.id)) {
          for (final path in downloaded) {
            await store.removeEmergencyImage(path);
          }
          return;
        }
        if (explicit) excluded.remove(guide.id);
        final existing = await _savedGuides();
        final previous = existing.where((item) => item.id == guide.id).toList();
        await _writeGuides([
          ...existing.where((item) => item.id != guide.id),
          saved,
        ], excludedIds: excluded);
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
  }

  Future<void> removeOfflineGuide(String id) => _editCache(() async {
    final existing = await _savedGuides();
    final excluded = await _excludedGuides();
    excluded.add(id);
    await _writeGuides(
      existing.where((guide) => guide.id != id).toList(),
      excludedIds: excluded,
    );
    for (final guide in existing.where((guide) => guide.id == id)) {
      await _removeImages(guide);
    }
  });

  Future<List<Map<String, dynamic>>> emergencyContacts({
    bool refresh = false,
  }) async {
    if (refresh && api != null) {
      final contacts = await api!.listAll('/emergency/contacts');
      _validateContacts(contacts);
      await store.write('emergency_contacts.json', {
        'contacts': contacts,
        'savedAt': DateTime.now().toUtc().toIso8601String(),
      });
      return contacts;
    }
    final data = await store.read('emergency_contacts.json');
    if (data == null) return [];
    return _validateContacts(data['contacts']);
  }

  List<Map<String, dynamic>> _validateContacts(dynamic value) {
    if (value is! List)
      throw const FormatException('Invalid emergency contacts');
    final contacts = <Map<String, dynamic>>[];
    for (final row in value) {
      if (row is! Map ||
          row['name'] is! String ||
          (row['name'] as String).trim().isEmpty ||
          row['phone'] is! String ||
          !RegExp(r'^[+0-9\s().-]+$').hasMatch(row['phone'] as String) ||
          (row['phone'] as String).replaceAll(RegExp(r'[^0-9]'), '').length <
              3 ||
          (row['description'] != null && row['description'] is! String)) {
        throw const FormatException('Invalid emergency contact');
      }
      contacts.add(Map<String, dynamic>.from(row));
    }
    return contacts;
  }
}

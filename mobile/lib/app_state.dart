import 'package:flutter/foundation.dart';
import 'data/local_store.dart';
import 'data/mobile_repository.dart';
import 'data/api_client.dart';
import 'data/learning_errors.dart';
import 'models/vehicle.dart';
import 'models/maintenance.dart';

class AppState extends ChangeNotifier {
  final LocalStore store;
  final MobileRepository? repository;
  AppState(this.store, {this.repository});
  List<Vehicle> _vehicles = [];
  List<MaintenanceTask> _tasks = [];
  List<ServiceRecord> _records = [];
  Set<String> _completedLessons = {};
  Map<String, Map<String, dynamic>> learningProgress = {};
  Set<String> completedRecaps = {};
  String? learningError;
  bool learningLoading = false;
  int _learningRequest = 0;

  String? _selectedVehicleId;
  String? accountId;
  String? emergencyOwnerId;
  void setEmergencyOwner(String? id) {
    if (emergencyOwnerId == id) return;
    emergencyOwnerId = id;
    _notify();
  }

  String contactName = '', contactPhone = '';
  bool loading = true, saving = false;
  bool _disposed = false;
  bool _localLoaded = false;
  int _accountGeneration = 0;
  int _snapshotRequest = 0;
  String? loadError;
  int? loadErrorStatus;
  String? cacheError;
  String? preferencesError;
  bool get signedIn => accountId != null;
  List<Vehicle> get vehicles => List.unmodifiable(_vehicles);
  Set<String> get completedLessons => Set.unmodifiable(_completedLessons);
  Vehicle? get selectedVehicle {
    for (final vehicle in _vehicles) {
      if (vehicle.id == _selectedVehicleId) return vehicle;
    }
    return null;
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  List<MaintenanceTask> tasksFor(String id) =>
      _tasks.where((t) => t.vehicleId == id).toList();
  List<ServiceRecord> recordsFor(String id) =>
      _records.where((r) => r.vehicleId == id).toList()
        ..sort((a, b) => b.date.compareTo(a.date));
  MaintenanceStatus statusFor(MaintenanceTask task) =>
      task.serverStatus ?? const MaintenanceStatus('Information required');

  int weeklyLearningCount(DateTime now) {
    final monday = DateTime(
      now.year,
      now.month,
      now.day,
    ).subtract(Duration(days: now.weekday - 1));
    return learningProgress.values.where((row) {
      final date = DateTime.tryParse(
        row['completed_at'] as String? ?? '',
      )?.toLocal();
      return date != null && !date.isBefore(monday) && !date.isAfter(now);
    }).length;
  }

  void _applyLearning(Map<String, dynamic> data) {
    final lessons = (data['completedLessons'] as List).cast<String>().toSet();
    final progress = <String, Map<String, dynamic>>{
      for (final row in data['learningProgress'] as List? ?? [])
        row['id'] as String: Map<String, dynamic>.from(row as Map),
    };
    final recaps = (data['completedRecaps'] as List? ?? [])
        .cast<String>()
        .toSet();
    for (final row in progress.values) {
      if (row['completed'] is! bool ||
          (row['current_step_id'] != null &&
              row['current_step_id'] is! String) ||
          (row['guide_revision'] != null && row['guide_revision'] is! String) ||
          (row['completed_at'] != null &&
              (row['completed_at'] is! String ||
                  DateTime.tryParse(row['completed_at'] as String) == null))) {
        throw const FormatException('Invalid learning progress.');
      }
    }
    _completedLessons = lessons;
    learningProgress = progress;
    completedRecaps = recaps;
    learningError = null;
  }

  Future<void> refreshLearning() async {
    if (!signedIn || repository == null) return;
    final generation = _accountGeneration;
    final request = ++_learningRequest;
    learningLoading = true;
    _notify();
    try {
      final data = await _remote.learning();
      if (generation == _accountGeneration && request == _learningRequest)
        _applyLearning(data);
    } catch (error) {
      if (generation == _accountGeneration && request == _learningRequest) {
        learningError = learningFailureMessage(
          error,
          fallback: 'Learning progress could not be refreshed. Try again.',
        );
      }
      if (error is TypeError || error is FormatException) {
        throw const ApiException(
          'Learning progress could not be read. Refresh and try again.',
        );
      }
      rethrow;
    } finally {
      if (generation == _accountGeneration && request == _learningRequest) {
        learningLoading = false;
        _notify();
      }
    }
  }

  Future<void> _saveLearning(
    String collection,
    String id,
    Map<String, dynamic> values,
  ) async {
    final remote = _remote;
    if (saving)
      throw const ApiException('Another change is being saved. Please retry.');
    final generation = _accountGeneration;
    saving = true;
    _notify();
    try {
      await remote.save(collection, id, values);
      if (generation != _accountGeneration) {
        throw const ApiException(
          'Your account changed. Reopen the guide before saving progress.',
        );
      }
      try {
        await refreshLearning();
      } catch (error) {
        if (generation != _accountGeneration) {
          throw const ApiException(
            'Your account changed. Reopen the guide before saving progress.',
          );
        }
        throw LearningRefreshFailure(error);
      }
      if (generation != _accountGeneration) {
        throw const ApiException(
          'Your account changed. Reopen the guide before saving progress.',
        );
      }
    } finally {
      if (generation == _accountGeneration) {
        saving = false;
        _notify();
      }
    }
  }

  Future<void> saveLessonStep(String id, String stepId, String revision) =>
      _saveLearning('progress', id, {
        'current_step_id': stepId,
        'guide_revision': revision,
      });

  Future<void> completeRecap(String id) => _saveLearning('recaps', id, {});

  Future<void> load() async {
    loading = true;
    loadError = null;
    preferencesError = null;
    _notify();
    try {
      // Legacy garage/progress files remain intact for manual export. Only the
      // roadside contact carries forward into guest-accessible preferences.
      final data =
          await store.read('preferences.json') ??
          await store.read('guest.json');
      final name = data?['contactName'] as String? ?? '';
      final phone = data?['contactPhone'] as String? ?? '';
      contactName = name;
      contactPhone = phone;
      _localLoaded = true;
    } catch (_) {
      _localLoaded = false;
      loadError =
          'Device preferences could not be opened. Existing files have been kept.';
      preferencesError = loadError;
    }
    loading = false;
    _notify();
    if (signedIn) await refresh();
  }

  Future<void> bindAccount(String? id) async {
    if (accountId == id) return;
    _accountGeneration++;
    accountId = id;
    _vehicles = [];
    _tasks = [];
    _records = [];
    _completedLessons = {};
    learningProgress = {};
    completedRecaps = {};
    learningError = null;
    learningLoading = false;
    _selectedVehicleId = null;
    loadError = null;
    loadErrorStatus = null;
    cacheError = null;
    saving = false;
    loading = false;
    _notify();
    if (id != null) await refresh();
  }

  MobileRepository get _remote {
    if (!signedIn || repository == null) {
      throw const ApiException(
        'Sign in to manage vehicles, maintenance and progress.',
      );
    }
    return repository!;
  }

  Future<void> refresh() async {
    if (!signedIn) return;
    final generation = _accountGeneration;
    final request = ++_snapshotRequest;
    final learningRequest = _learningRequest;
    final owner = accountId;
    loading = true;
    loadError = null;
    loadErrorStatus = null;
    cacheError = null;
    _notify();
    try {
      final data = await _remote.snapshot();
      final vehicles = (data['vehicles'] as List)
          .map((v) => Vehicle.fromJson(Map<String, dynamic>.from(v as Map)))
          .toList();
      final tasks = (data['tasks'] as List)
          .map(
            (v) =>
                MaintenanceTask.fromJson(Map<String, dynamic>.from(v as Map)),
          )
          .toList();
      final records = (data['records'] as List)
          .map(
            (v) => ServiceRecord.fromJson(Map<String, dynamic>.from(v as Map)),
          )
          .toList();
      final vehicleIds = vehicles.map((v) => v.id).toSet();
      if (vehicleIds.length != vehicles.length ||
          vehicles.any((v) => v.mileage < 0) ||
          tasks.map((t) => t.id).toSet().length != tasks.length ||
          tasks.any((t) => !vehicleIds.contains(t.vehicleId)) ||
          records.map((r) => r.id).toSet().length != records.length ||
          records.any((r) => !vehicleIds.contains(r.vehicleId))) {
        throw const FormatException('Invalid garage relationships.');
      }
      Map<String, dynamic>? preferences;
      var cacheReadFailed = false;
      if (!data.containsKey('activeVehicleId')) {
        try {
          preferences = await store.read('active_vehicle_$owner.json');
        } catch (_) {
          // Server data remains usable when the optional device cache is damaged.
          cacheReadFailed = true;
        }
      }
      var selectedId = data.containsKey('activeVehicleId')
          ? data['activeVehicleId'] as String?
          : preferences?['id'] is String
          ? preferences!['id'] as String
          : null;
      if (!vehicleIds.contains(selectedId)) {
        selectedId = vehicles.isEmpty ? null : vehicles.first.id;
      }
      if (generation != _accountGeneration ||
          request != _snapshotRequest ||
          _disposed)
        return;
      if (learningRequest == _learningRequest) {
        _applyLearning(data);
      }
      _vehicles = vehicles;
      _tasks = tasks;
      _records = records;
      _selectedVehicleId = selectedId;
      if (cacheReadFailed) {
        cacheError =
            'The device selection cache could not be read. Your garage was loaded from the server; check the selected vehicle.';
      }
      if (selectedId != null) {
        try {
          await store.write('active_vehicle_$owner.json', {'id': selectedId});
        } catch (_) {
          if (generation == _accountGeneration && request == _snapshotRequest) {
            cacheError =
                'Your garage was loaded, but the device selection cache could not be saved. Your account data remains on the server. Pull to refresh to retry.';
          }
        }
      }
    } catch (error) {
      if (generation == _accountGeneration && request == _snapshotRequest) {
        loadErrorStatus = error is ApiException ? error.statusCode : null;
        loadError = switch (loadErrorStatus) {
          401 => 'Sign in again to load your garage.',
          403 =>
            'Garage access is unavailable. Check your account before trying again.',
          429 => 'Too many requests. Wait before refreshing your garage again.',
          _ =>
            'Your garage could not be loaded. Check your connection and retry.',
        };
        if (learningRequest == _learningRequest) {
          learningError = 'Learning progress could not be loaded. Try again.';
        }
      }
    } finally {
      if (generation == _accountGeneration && request == _snapshotRequest) {
        loading = false;
        _notify();
      }
    }
  }

  Future<void> _change(Future<void> Function(MobileRepository) action) async {
    final remote = _remote;
    if (saving) {
      throw const ApiException('Another change is being saved. Please retry.');
    }
    final generation = _accountGeneration;
    saving = true;
    _notify();
    try {
      await action(remote);
      if (generation != _accountGeneration) {
        throw const ApiException(
          'Your account changed. Reopen this screen before continuing.',
        );
      }
      await refresh();
      if (generation != _accountGeneration) {
        throw const ApiException(
          'Your account changed. Reopen this screen before continuing.',
        );
      }
      if (loadError != null) {
        throw const ApiException(
          'The change was saved, but the updated account data could not be loaded. Retry to confirm it; your entries have been kept.',
        );
      }
    } finally {
      if (generation == _accountGeneration) {
        saving = false;
        _notify();
      }
    }
  }

  Future<void> saveVehicle(Vehicle vehicle) => _change((remote) async {
    await remote.save('vehicles', vehicle.id, {
      'catalogueId': vehicle.catalogueId,
      'name': vehicle.name,
      'plateNumber': vehicle.plateNumber,
      'mileage': vehicle.mileage,
    });
  });
  Future<void> deleteVehicle(String id) =>
      _change((remote) => remote.remove('vehicles', id));

  Future<void> selectVehicle(String id) async {
    if (!signedIn || !_vehicles.any((v) => v.id == id)) {
      throw const ApiException('Vehicle not found.');
    }
    if (repository != null) {
      await _change((remote) async {
        await remote.api.put('/mobile/me/active-vehicle', {
          'id': id,
        }, token: remote.token);
      });
      return;
    }
    final generation = _accountGeneration;
    await store.write('active_vehicle_$accountId.json', {'id': id});
    if (generation != _accountGeneration) return;
    _selectedVehicleId = id;
    _notify();
  }

  Future<void> addTask(MaintenanceTask task) => _change((remote) async {
    await remote.save('tasks', task.id, task.toJson());
  });
  Future<void> removeTask(MaintenanceTask task) =>
      _change((remote) => remote.remove('tasks', task.id));
  Future<void> addRecord(ServiceRecord record) => _change((remote) async {
    await remote.save('records', record.id, record.toJson());
  });
  Future<void> removeRecord(String id) =>
      _change((remote) => remote.remove('records', id));
  Future<void> completeLesson(String id, {String? revision}) => _saveLearning(
    'progress',
    id,
    {'completed': true, if (revision != null) 'guide_revision': revision},
  );
  Future<void> markLessonUnread(String id) =>
      _saveLearning('progress', id, {'completed': false});
  Future<void> saveContact(String name, String phone) async {
    if (!_localLoaded) {
      throw const ApiException('Retry loading device preferences first.');
    }
    await store.write('preferences.json', {
      'contactName': name.trim(),
      'contactPhone': phone.trim(),
    });
    contactName = name.trim();
    contactPhone = phone.trim();
    _notify();
  }
}

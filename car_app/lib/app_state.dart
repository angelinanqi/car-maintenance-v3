import 'package:flutter/foundation.dart';
import 'data/local_store.dart';
import 'data/mobile_repository.dart';
import 'data/api_client.dart';
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
  String? loadError;
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

  Future<void> load() async {
    loading = true;
    loadError = null;
    _notify();
    try {
      // Legacy garage/progress files remain intact for manual export. Only the
      // roadside contact carries forward into guest-accessible preferences.
      final data =
          await store.read('preferences.json') ??
          await store.read('guest.json');
      contactName = data?['contactName'] as String? ?? '';
      contactPhone = data?['contactPhone'] as String? ?? '';
      _localLoaded = true;
    } catch (_) {
      loadError =
          'Device preferences could not be opened. Existing files have been kept.';
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
    _selectedVehicleId = null;
    loadError = null;
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
    final owner = accountId;
    loading = true;
    loadError = null;
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
      final lessons = (data['completedLessons'] as List).cast<String>().toSet();
      final preferences = await store.read('active_vehicle_$owner.json');
      if (generation != _accountGeneration || _disposed) return;
      _vehicles = vehicles;
      _tasks = tasks;
      _records = records;
      _completedLessons = lessons;
      _selectedVehicleId = data.containsKey('activeVehicleId')
          ? data['activeVehicleId'] as String?
          : preferences?['id'] as String?;
      if (!vehicles.any((v) => v.id == _selectedVehicleId)) {
        _selectedVehicleId = vehicles.isEmpty ? null : vehicles.first.id;
      }
      if (_selectedVehicleId != null &&
          preferences?['id'] != _selectedVehicleId) {
        await store.write('active_vehicle_$owner.json', {
          'id': _selectedVehicleId,
        });
        if (generation != _accountGeneration || _disposed) return;
      }
    } catch (error) {
      if (generation == _accountGeneration) {
        loadError = 'Account data could not be loaded. $error';
      }
    } finally {
      if (generation == _accountGeneration) {
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
      if (generation == _accountGeneration) await refresh();
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
  Future<void> completeLesson(String id) => _change((remote) async {
    await remote.save('progress', id, {'completed': true});
  });
  Future<void> markLessonUnread(String id) => _change((remote) async {
    await remote.save('progress', id, {'completed': false});
  });
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

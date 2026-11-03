import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:car_app/app_state.dart';
import 'package:car_app/data/account_repository.dart';
import 'package:car_app/data/api_client.dart';
import 'package:car_app/data/local_store.dart';
import 'package:car_app/data/mobile_repository.dart';
import 'package:car_app/models/maintenance.dart';
import 'package:car_app/models/maintenance_spending.dart';
import 'package:car_app/models/vehicle.dart';
import 'package:car_app/screens/mycar.dart';
import 'package:car_app/screens/service_forms.dart';
import 'package:car_app/screens/workshop_mode.dart';
import 'package:car_app/widgets/maintenance_spending_summary.dart';

const vehicle = Vehicle(
  id: 'car',
  name: 'My car',
  model: 'Model',
  year: 2020,
  engineSize: '1.5',
  plateNumber: '',
  mileage: 10000,
);
const task = MaintenanceTask(
  id: 'task',
  vehicleId: 'car',
  title: 'Oil change',
  category: 'Engine and Fluids',
);

ServiceRecord record(
  String id,
  double? cost, {
  String car = 'car',
  int? year,
  String? performer,
  String category = 'Engine and Fluids',
}) => ServiceRecord(
  id: id,
  vehicleId: car,
  taskId: 'task',
  title: 'Oil change',
  category: category,
  mileage: 9000,
  date: DateTime(year ?? DateTime.now().year, 1, 1),
  cost: cost,
  performedBy: performer,
);

class FakeRepository extends MobileRepository {
  final Map<String, Map<String, dynamic>> records = {};
  final List<String> writes = [];
  final List<MaintenanceTask> tasks = [task];
  int attempts = 0;
  int? failAt;
  String active = 'car';
  bool failNext = false;
  FakeRepository(ApiClient api) : super(api, AccountRepository(api));
  @override
  String get token => 'test';
  @override
  Future<Map<String, dynamic>> snapshot() async => {
    'vehicles': [
      for (final id in ['car', 'other'])
        {
          'id': id,
          'name': id,
          'model': 'Model',
          'year': 2020,
          'engineSize': '1.5',
          'plateNumber': '',
          'mileage': 10000,
        },
    ],
    'tasks': tasks.map((task) => task.toJson()).toList(),
    'records': records.values.toList(),
    'completedLessons': [],
    'activeVehicleId': active,
  };
  @override
  Future<Map<String, dynamic>> save(
    String collection,
    String id,
    Map<String, dynamic> data,
  ) async {
    if (failNext || ++attempts == failAt) {
      failNext = false;
      throw const ApiException('Connection unavailable');
    }
    if (collection == 'active-vehicle') {
      active = data['id'] as String;
    } else {
      writes.add(id);
      records[id] = Map.of(data);
    }
    return data;
  }

  @override
  Future<void> remove(String collection, String id) async {
    records.remove(id);
  }
}

class MemoryStore extends LocalStore {
  final Map<String, Map<String, dynamic>> files = {};
  @override
  Future<Map<String, dynamic>?> read(String name) async => files[name];
  @override
  Future<void> write(String name, Map<String, dynamic> data) async {
    files[name] = jsonDecode(jsonEncode(data)) as Map<String, dynamic>;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FakeRepository repository;
  late AppState state;
  setUp(() async {
    repository = FakeRepository(
      ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          if (request.url.path == '/mobile/me/active-vehicle') {
            repository.active =
                (jsonDecode(request.body) as Map)['id'] as String;
            return http.Response('{}', 200);
          }
          throw StateError('Unexpected request: ${request.url.path}');
        }),
      ),
    );
    state = AppState(MemoryStore(), repository: repository);
    await state.bindAccount('owner');
    expect(state.loadError, isNull);
  });
  tearDown(() async {
    state.dispose();
    repository.api.client.close();
  });

  test(
    'cost validation accepts blank self work and zero; rejects invalid money',
    () {
      expect(validateMaintenanceCost('', required: false), isNull);
      expect(
        validateMaintenanceCost('', required: true),
        contains('Enter the mechanic'),
      );
      for (final value in ['0', '0.00', '12.34', ' 12.30 ']) {
        expect(validateMaintenanceCost(value, required: true), isNull);
      }
      for (final value in ['-1', 'abc', 'NaN', 'Infinity', '1.001', '1e2']) {
        expect(validateMaintenanceCost(value, required: false), isNotNull);
      }
    },
  );

  test(
    'spending separates vehicles, years, unknown and free services and duplicate IDs',
    () {
      final spending = MaintenanceSpending.fromRecords(
        [
          record('paid', 100.10, year: 2026),
          record('old', 50.20, year: 2025),
          record('free', 0, year: 2026),
          record('unknown', null, year: 2026),
          record('different-car', 999, car: 'other', year: 2026),
          record('paid', 100.10, year: 2026),
        ],
        vehicleId: 'car',
        year: 2026,
      );
      expect(spending.totalCents, 15030);
      expect(spending.yearCents, 10010);
      expect(spending.paidCount, 2);
      expect(spending.knownCount, 3);
      expect(spending.unknownCount, 1);
      expect(spending.averageCost, 50.10);
      expect(spending.categoryCents, {'Engine and Fluids': 15030});
    },
  );

  test('legacy records preserve null costs and attribution through JSON', () {
    final json = record('old', null).toJson()..remove('performedBy');
    final old = ServiceRecord.fromJson(json);
    expect(old.cost, isNull);
    expect(old.performedBy, isNull);
    expect(old.toJson()['cost'], isNull);
  });

  test(
    'average rounds half a sen and category totals use existing categories',
    () {
      final spending = MaintenanceSpending.fromRecords(
        [
          record('a', 5.35),
          record('b', 0, category: 'Other'),
          record('c', null, category: 'Other'),
        ],
        vehicleId: 'car',
        year: DateTime.now().year,
      );
      expect(formatMyr(spending.averageCost), 'RM 2.68');
      expect(spending.categoryCents, {'Engine and Fluids': 535, 'Other': 0});
    },
  );

  testWidgets(
    'summary shows friendly unknown empty state and genuine free spending',
    (tester) async {
      Future<void> show(List<ServiceRecord> records) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MaintenanceSpendingSummary(
              records: records,
              vehicleId: 'car',
            ),
          ),
        ),
      );
      await show([record('unknown', null)]);
      expect(find.textContaining('No costs recorded yet'), findsOneWidget);
      expect(find.text('RM 0.00'), findsNothing);
      await show([record('free', 0)]);
      expect(find.text('RM 0.00'), findsNWidgets(3));
      expect(find.textContaining('including free services'), findsOneWidget);
    },
  );

  testWidgets(
    'summary follows persisted add, edit, delete and vehicle selection',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListenableBuilder(
              listenable: state,
              builder: (_, _) => MaintenanceSpendingSummary(
                records: state.recordsFor(state.selectedVehicle!.id),
                vehicleId: state.selectedVehicle!.id,
              ),
            ),
          ),
        ),
      );
      await state.addRecord(record('a', 10));
      await tester.pumpAndSettle();
      expect(find.text('RM 10.00'), findsNWidgets(3));
      await state.addRecord(record('a', 24));
      await state.addRecord(record('b', 0));
      await state.addRecord(record('c', null));
      await state.addRecord(record('d', 88, car: 'other'));
      await tester.pumpAndSettle();
      expect(find.text('RM 12.00'), findsOneWidget);
      expect(
        find.textContaining('1 with unknown costs excluded'),
        findsOneWidget,
      );
      await state.selectVehicle('other');
      await tester.pumpAndSettle();
      expect(find.text('RM 88.00'), findsNWidgets(3));
      await state.selectVehicle('car');
      await state.removeRecord('a');
      await tester.pumpAndSettle();
      expect(find.text('RM 0.00'), findsNWidgets(3));
      await state.removeRecord('b');
      await tester.pumpAndSettle();
      expect(find.textContaining('No costs recorded yet'), findsOneWidget);
    },
  );

  Future<void> open(WidgetTester tester, Widget page) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(useMaterial3: true),
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(builder: (_) => page),
              ),
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
  }

  Finder field(String label) => find.byWidgetPredicate(
    (widget) => widget is TextField && widget.decoration?.labelText == label,
  );

  Future<void> mechanic(WidgetTester tester) async {
    final dropdown = find.byType(DropdownButtonFormField<String>).last;
    await tester.ensureVisible(dropdown);
    await tester.tap(dropdown);
    await tester.pumpAndSettle();
    await tester.tap(find.text('A mechanic').last);
    await tester.pumpAndSettle();
  }

  testWidgets('mechanic form blocks missing cost and accepts free work', (
    tester,
  ) async {
    await open(
      tester,
      ServiceLogDialog(state: state, vehicle: vehicle, task: task),
    );
    await mechanic(tester);
    await tester.tap(find.text('Save record'));
    await tester.pumpAndSettle();
    expect(repository.records, isEmpty);
    expect(
      find.textContaining('Enter the mechanic service cost'),
      findsOneWidget,
    );
    await tester.ensureVisible(field('Cost (required)'));
    await tester.enterText(field('Cost (required)'), '0');
    await tester.tap(find.text('Save record'));
    await tester.pumpAndSettle();
    expect(repository.records.values.single['cost'], 0);
    expect(repository.records.values.single['performedBy'], 'mechanic');
  });

  testWidgets('self form saves unknown cost', (tester) async {
    await open(
      tester,
      ServiceLogDialog(state: state, vehicle: vehicle, task: task),
    );
    await tester.tap(find.text('Save record'));
    await tester.pumpAndSettle();
    expect(repository.records.values.single['cost'], isNull);
    expect(repository.records.values.single['performedBy'], 'self');
  });

  testWidgets(
    'editing mechanic record rejects negative and fractional sen, keeps record ID',
    (tester) async {
      await open(
        tester,
        ServiceLogDialog(
          state: state,
          vehicle: vehicle,
          record: record('saved', 100, performer: 'mechanic'),
        ),
      );
      for (final cost in ['', '-1', '1.001', 'abc']) {
        await tester.ensureVisible(field('Cost (required)'));
        await tester.enterText(field('Cost (required)'), cost);
        await tester.tap(find.text('Save record'));
        await tester.pumpAndSettle();
        expect(repository.records, isEmpty);
      }
      await tester.enterText(field('Cost (required)'), '42.50');
      await tester.tap(find.text('Save record'));
      await tester.pumpAndSettle();
      expect(repository.records['saved']!['cost'], 42.50);
    },
  );

  testWidgets('historical record can be corrected without inventing a cost', (
    tester,
  ) async {
    await open(
      tester,
      ServiceLogDialog(
        state: state,
        vehicle: vehicle,
        record: record('old', null),
      ),
    );
    await tester.tap(find.text('Save record'));
    await tester.pumpAndSettle();
    expect(repository.records['old']!['cost'], isNull);
    expect(repository.records['old']!['performedBy'], isNull);
  });

  testWidgets('workshop needs per-item cost and retries with stable IDs', (
    tester,
  ) async {
    await open(tester, WorkshopMode(state: state, vehicle: vehicle));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    final done = find.text('Done — hand phone back');
    await tester.ensureVisible(done);
    await tester.tap(done);
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Enter the mechanic service cost'),
      findsOneWidget,
    );
    await tester.ensureVisible(field('Cost for Oil change (required)'));
    await tester.enterText(field('Cost for Oil change (required)'), '12.30');
    await tester.ensureVisible(done);
    await tester.tap(done);
    await tester.pumpAndSettle();
    repository.failNext = true;
    await tester.ensureVisible(find.text('Save service records'));
    await tester.tap(find.text('Save service records'));
    await tester.pumpAndSettle();
    final journal = await state.store.read('workshop_owner_car.json');
    final id = (journal!['records'] as List).single['id'];
    await tester.ensureVisible(find.text('Retry save'));
    await tester.tap(find.text('Retry save'));
    await tester.pumpAndSettle();
    expect(repository.records.keys, [id]);
    expect(repository.records[id]!['cost'], 12.30);
    expect(repository.records[id]!['performedBy'], 'mechanic');
  });

  testWidgets(
    'legacy workshop recovery collects unknown cost without resaving confirmed work',
    (tester) async {
      await state.store.write('workshop_owner_car.json', {
        'records': [
          record('confirmed', null).toJson(),
          record('pending', null).toJson(),
        ],
        'confirmed': ['confirmed'],
      });
      await open(tester, WorkshopMode(state: state, vehicle: vehicle));
      expect(find.textContaining('Cost not recorded'), findsOneWidget);
      await tester.ensureVisible(find.text('Retry save'));
      await tester.tap(find.text('Retry save'));
      await tester.pumpAndSettle();
      expect(repository.writes, isEmpty);
      await tester.ensureVisible(field('Cost for Oil change (required)'));
      await tester.enterText(field('Cost for Oil change (required)'), '0');
      await tester.ensureVisible(find.text('Retry save'));
      await tester.tap(find.text('Retry save'));
      await tester.pumpAndSettle();
      expect(repository.writes, ['pending']);
      expect(repository.records['pending']!['cost'], 0);
    },
  );

  testWidgets(
    'multi-item workshop resumes a partial save without repeating costs or records',
    (tester) async {
      repository.tasks.add(
        const MaintenanceTask(
          id: 'tyres',
          vehicleId: 'car',
          title: 'Tyre check',
          category: 'Tyre Condition and Pressure',
        ),
      );
      await state.refresh();
      await open(tester, WorkshopMode(state: state, vehicle: vehicle));
      for (final checkbox
          in find.byType(CheckboxListTile).evaluate().toList()) {
        final finder = find.byWidget(checkbox.widget);
        await tester.ensureVisible(finder);
        await tester.tap(finder);
        await tester.pumpAndSettle();
      }
      await tester.ensureVisible(field('Cost for Oil change (required)'));
      await tester.enterText(field('Cost for Oil change (required)'), '60');
      await tester.ensureVisible(field('Cost for Tyre check (required)'));
      await tester.enterText(field('Cost for Tyre check (required)'), '40');
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Done — hand phone back'));
      await tester.tap(find.text('Done — hand phone back'));
      await tester.pumpAndSettle();
      repository.failAt = 2;
      await tester.ensureVisible(find.text('Save service records'));
      await tester.tap(find.text('Save service records'));
      await tester.pumpAndSettle();
      expect(repository.records.length, 1);
      final journal = await state.store.read('workshop_owner_car.json');
      expect((journal!['confirmed'] as List).length, 1);
      // Recreate the screen with the same owner/vehicle journal.
      await tester.pumpWidget(const SizedBox.shrink());
      await open(tester, WorkshopMode(state: state, vehicle: vehicle));
      await tester.ensureVisible(find.text('Retry save'));
      await tester.tap(find.text('Retry save'));
      await tester.pumpAndSettle();
      expect(repository.records.length, 2);
      expect(repository.writes.toSet().length, repository.writes.length);
      final spending = MaintenanceSpending.fromRecords(
        state.recordsFor('car'),
        vehicleId: 'car',
        year: DateTime.now().year,
      );
      expect(spending.totalCents, 10000);
      expect(spending.paidCount, 2);
    },
  );

  testWidgets('guest retains sign-in prompt and cannot record maintenance', (
    tester,
  ) async {
    await state.bindAccount(null);
    await tester.pumpWidget(MaterialApp(home: MyCar(state: state)));
    expect(find.text('Your car, all in one place'), findsOneWidget);
    expect(find.text('Recorded maintenance spending'), findsNothing);
    await expectLater(
      state.addRecord(record('guest', 10)),
      throwsA(isA<ApiException>()),
    );
    expect(repository.records, isEmpty);
  });

  testWidgets('summary fits narrow screens and larger text', (tester) async {
    tester.view.physicalSize = const Size(320, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(fontFamily: 'Inter'),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.8)),
          child: Scaffold(
            body: SingleChildScrollView(
              child: MaintenanceSpendingSummary(
                records: [record('a', 12345.67)],
                vehicleId: 'car',
              ),
            ),
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });
}

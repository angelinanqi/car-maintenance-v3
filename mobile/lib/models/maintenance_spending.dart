import 'maintenance.dart';

class MaintenanceSpending {
  int totalCents = 0;
  int yearCents = 0;
  int knownCount = 0;
  int unknownCount = 0;
  int paidCount = 0;
  final Map<String, int> categoryCents = {};

  MaintenanceSpending.fromRecords(
    Iterable<ServiceRecord> records, {
    required String vehicleId,
    required int year,
  }) {
    final seen = <String>{};
    for (final record in records) {
      if (record.vehicleId != vehicleId || !seen.add(record.id)) continue;
      final cost = record.cost;
      if (cost == null || !cost.isFinite || cost < 0) {
        unknownCount++;
        continue;
      }
      // Sum cents so ordinary monetary additions do not accumulate float errors.
      final cents = (cost * 100).round();
      knownCount++;
      totalCents += cents;
      if (record.date.year == year) yearCents += cents;
      if (cost > 0) paidCount++;
      final category = record.category.trim().isEmpty
          ? 'Uncategorised'
          : record.category;
      categoryCents[category] = (categoryCents[category] ?? 0) + cents;
    }
  }

  double get averageCost =>
      knownCount == 0 ? 0 : (totalCents / knownCount).round() / 100;
}

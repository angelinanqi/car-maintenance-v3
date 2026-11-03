import 'package:flutter/material.dart';
import '../app_spacing.dart';
import '../models/maintenance.dart';
import '../models/maintenance_spending.dart';
import 'design_widgets.dart';

class MaintenanceSpendingSummary extends StatelessWidget {
  final List<ServiceRecord> records;
  final String vehicleId;
  const MaintenanceSpendingSummary({
    super.key,
    required this.records,
    required this.vehicleId,
  });

  @override
  Widget build(BuildContext context) {
    final year = DateTime.now().year;
    final spending = MaintenanceSpending.fromRecords(
      records,
      vehicleId: vehicleId,
      year: year,
    );
    final categories = spending.categoryCents.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Recorded maintenance spending',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.small),
          if (spending.knownCount == 0)
            const Text(
              'No costs recorded yet for this vehicle. Add a cost to a service record to see your spending here. Unknown costs are left out.',
            )
          else ...[
            _amount(
              context,
              'Total recorded',
              formatMyr(spending.totalCents / 100),
            ),
            _amount(
              context,
              'This year ($year)',
              formatMyr(spending.yearCents / 100),
            ),
            _amount(context, 'Paid services', '${spending.paidCount}'),
            _amount(
              context,
              'Average per recorded service',
              formatMyr(spending.averageCost),
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              'Based on ${spending.knownCount} services with known costs, including free services. '
              '${spending.unknownCount} with unknown costs excluded. '
              'This may not include all your maintenance spending.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (categories.isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                childrenPadding: EdgeInsets.zero,
                title: const Text('Spending by maintenance type'),
                children: [
                  for (final category in categories)
                    _amount(
                      context,
                      category.key,
                      formatMyr(category.value / 100),
                    ),
                ],
              ),
          ],
        ],
      ),
    );
  }

  Widget _amount(BuildContext context, String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.minimal),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label)),
        const SizedBox(width: AppSpacing.small),
        Flexible(
          child: Text(value, style: Theme.of(context).textTheme.titleSmall),
        ),
      ],
    ),
  );
}

import 'package:flutter/material.dart';

import '../app_theme.dart';
import '../models/maintenance.dart';
import 'design_widgets.dart';

/// Give the title the full card width, independently of status text length.
class MaintenanceItemHeading extends StatelessWidget {
  final String title;
  final MaintenanceStatus status;
  final VoidCallback? onTap;

  const MaintenanceItemHeading({
    super.key,
    required this.title,
    required this.status,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
      ),
      const SizedBox(height: 8),
      Semantics(
        label: 'Schedule status: ${status.label}',
        child: ExcludeSemantics(
          child: StatusPill(
            status.shortLabel,
            color: status.isDue ? AppColors.dangerSurface : AppColors.pale,
            foreground: status.isDue ? AppColors.danger : AppColors.ink,
          ),
        ),
      ),
    ],
  );
}

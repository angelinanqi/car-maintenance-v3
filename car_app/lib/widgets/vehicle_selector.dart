import 'package:flutter/material.dart';
import '../app_state.dart';

class VehicleSelector extends StatelessWidget {
  final AppState state;
  const VehicleSelector({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    if (state.vehicles.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('No vehicle selected. Add a vehicle in Home.'),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: DropdownButtonFormField<String>(
        key: ValueKey(state.selectedVehicle?.id),
        initialValue: state.selectedVehicle?.id,
        isExpanded: true,
        decoration: const InputDecoration(
          labelText: 'Selected vehicle',
          border: OutlineInputBorder(),
        ),
        items: state.vehicles
            .map(
              (v) => DropdownMenuItem(
                value: v.id,
                child: Text(
                  '${v.name} • ${v.model} (${v.year})',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            )
            .toList(),
        onChanged: state.saving
            ? null
            : (id) async {
                try {
                  await state.selectVehicle(id!);
                } catch (_) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Vehicle selection could not be saved. Please retry.',
                        ),
                      ),
                    );
                  }
                }
              },
      ),
    );
  }
}

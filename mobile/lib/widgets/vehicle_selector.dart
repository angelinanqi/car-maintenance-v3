import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/api_client.dart';

class VehicleSelector extends StatefulWidget {
  final AppState state;
  const VehicleSelector({super.key, required this.state});

  @override
  State<VehicleSelector> createState() => _VehicleSelectorState();
}

class _VehicleSelectorState extends State<VehicleSelector> {
  AppState get state => widget.state;
  int _selectionAttempt = 0;

  @override
  Widget build(BuildContext context) {
    if (state.vehicles.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('No vehicle selected. Add one in My Car.'),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: DropdownButtonFormField<String>(
        key: ValueKey('${state.selectedVehicle?.id}:$_selectionAttempt'),
        initialValue: state.selectedVehicle?.id,
        isExpanded: true,
        decoration: const InputDecoration(
          labelText: 'Selected vehicle',
          prefixIcon: Icon(Icons.directions_car_outlined),
        ),
        items: state.vehicles
            .map(
              (v) => DropdownMenuItem(
                value: v.id,
                child: Text(
                  '${v.name} · ${v.plateNumber.isEmpty ? v.model : v.plateNumber}',
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
                } catch (error) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          error is ApiException
                              ? error.message
                              : 'Vehicle selection could not be confirmed. Refresh your garage before retrying.',
                        ),
                      ),
                    );
                  }
                } finally {
                  // Also reset after a fast failure that finishes between frames.
                  if (mounted) setState(() => _selectionAttempt++);
                }
              },
      ),
    );
  }
}

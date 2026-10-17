import 'package:flutter/material.dart';
import '../app_state.dart';
import '../models/vehicle.dart';

class VehicleProfilePage extends StatefulWidget {
  final AppState state;
  final Vehicle? vehicle;
  const VehicleProfilePage({super.key, required this.state, this.vehicle});
  @override
  State<VehicleProfilePage> createState() => _VehicleProfilePageState();
}

class _VehicleProfilePageState extends State<VehicleProfilePage> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController(),
      _plate = TextEditingController(),
      _mileage = TextEditingController();
  List<CatalogueVehicle> _catalogue = [];
  CatalogueVehicle? _selected;
  String _search = '';
  String? _manufacturer, _model, _year;
  bool _busy = false, _loading = true;
  String? _error;
  @override
  void initState() {
    super.initState();
    _name.text = widget.vehicle?.name ?? '';
    _plate.text = widget.vehicle?.plateNumber ?? '';
    _mileage.text = widget.vehicle?.mileage.toString() ?? '';
    if (widget.vehicle == null) {
      _load();
    } else {
      _loading = false;
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final repository = widget.state.repository;
      if (repository == null) {
        throw StateError('No backend connection configured.');
      }
      final catalogue = await repository.catalogue();
      if (mounted) setState(() => _catalogue = catalogue);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = 'Vehicle catalogue could not be loaded. $error',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _plate.dispose();
    _mileage.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    if (widget.vehicle == null && _selected == null) {
      setState(() => _error = 'Select a vehicle from the catalogue.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final old = widget.vehicle;
    try {
      await widget.state.saveVehicle(
        Vehicle(
          id: old?.id ?? DateTime.now().microsecondsSinceEpoch.toString(),
          catalogueId: old?.catalogueId ?? _selected!.id,
          name: _name.text.trim().isEmpty
              ? old?.model ?? _selected!.label
              : _name.text.trim(),
          model: old?.model ?? '${_selected!.manufacturer} ${_selected!.model}',
          year: old?.year ?? _selected!.year,
          engineSize: old?.engineSize ?? _selected!.engine,
          plateNumber: _plate.text.trim().toUpperCase(),
          mileage: int.parse(_mileage.text.trim()),
          knowledgeScopeId: old?.knowledgeScopeId,
        ),
      );
      if (mounted) Navigator.pop(context);
    } catch (error) {
      if (mounted) {
        setState(() => _error = 'Vehicle could not be saved. $error');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    final answer = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Remove vehicle?'),
        content: const Text(
          'Remove this vehicle and its personal maintenance data from your account?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (answer != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await widget.state.deleteVehicle(widget.vehicle!.id);
      if (mounted) Navigator.pop(context);
    } catch (error) {
      if (mounted) {
        setState(() => _error = 'Vehicle could not be removed. $error');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _filter(
    String label,
    String? value,
    Iterable<String> options,
    void Function(String?) change,
  ) {
    final values = options.toSet().toList()..sort();
    return DropdownButtonFormField<String>(
      key: ValueKey('$label:$value'),
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        const DropdownMenuItem<String>(value: null, child: Text('All')),
        ...values.map((v) => DropdownMenuItem(value: v, child: Text(v))),
      ],
      onChanged: _busy ? null : change,
    );
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _catalogue
        .where(
          (v) =>
              (_manufacturer == null || v.manufacturer == _manufacturer) &&
              (_model == null || v.model == _model) &&
              (_year == null || '${v.year}' == _year) &&
              v.label.toLowerCase().contains(_search.toLowerCase()),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.vehicle == null ? 'Add vehicle' : 'Edit vehicle'),
        actions: [
          if (widget.vehicle != null)
            IconButton(
              onPressed: _busy ? null : _delete,
              tooltip: 'Remove vehicle',
              icon: const Icon(Icons.delete_outline),
            ),
        ],
      ),
      body: !widget.state.signedIn
          ? const Center(child: Text('Sign in to manage your vehicles.'))
          : Form(
              key: _form,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  if (widget.vehicle == null) ...[
                    const Text(
                      'Choose your petrol or diesel vehicle from the central catalogue.',
                    ),
                    if (_loading) const LinearProgressIndicator(),
                    TextButton(
                      onPressed: _loading ? null : _load,
                      child: const Text('Refresh catalogue'),
                    ),
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Search manufacturer, model or variant',
                      ),
                      onChanged: (v) => setState(() => _search = v),
                    ),
                    const SizedBox(height: 12),
                    _filter(
                      'Manufacturer',
                      _manufacturer,
                      _catalogue.map((v) => v.manufacturer),
                      (v) => setState(() {
                        _manufacturer = v;
                        _model = null;
                        _year = null;
                        _selected = null;
                      }),
                    ),
                    _filter(
                      'Model',
                      _model,
                      _catalogue
                          .where(
                            (v) =>
                                _manufacturer == null ||
                                v.manufacturer == _manufacturer,
                          )
                          .map((v) => v.model),
                      (v) => setState(() {
                        _model = v;
                        _year = null;
                        _selected = null;
                      }),
                    ),
                    _filter(
                      'Year',
                      _year,
                      _catalogue
                          .where(
                            (v) =>
                                (_manufacturer == null ||
                                    v.manufacturer == _manufacturer) &&
                                (_model == null || v.model == _model),
                          )
                          .map((v) => '${v.year}'),
                      (v) => setState(() {
                        _year = v;
                        _selected = null;
                      }),
                    ),
                    if (!_loading && filtered.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 16),
                        child: Text(
                          'Your vehicle is not listed. Try different filters. Only catalogue vehicles can be registered.',
                        ),
                      ),
                    SizedBox(
                      height: 220,
                      child: ListView(
                        children: filtered
                            .map(
                              (v) => ListTile(
                                selected: _selected?.id == v.id,
                                title: Text(v.label),
                                subtitle: Text('${v.engine} • ${v.powertrain}'),
                                trailing: _selected?.id == v.id
                                    ? const Icon(Icons.check)
                                    : null,
                                onTap: _busy
                                    ? null
                                    : () => setState(() => _selected = v),
                              ),
                            )
                            .toList(),
                      ),
                    ),
                  ] else
                    Text(
                      '${widget.vehicle!.model} ${widget.vehicle!.year} • ${widget.vehicle!.engineSize}',
                    ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _name,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'Nickname (optional)',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _plate,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'Number plate (optional)',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _mileage,
                    enabled: !_busy,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Current odometer (km)',
                    ),
                    validator: (v) => (int.tryParse(v?.trim() ?? '') ?? -1) < 0
                        ? 'Enter zero or more kilometres'
                        : null,
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy || _loading ? null : _save,
                    child: Text(_busy ? 'Saving...' : 'Save vehicle'),
                  ),
                ],
              ),
            ),
    );
  }
}

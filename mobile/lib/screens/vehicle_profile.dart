import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/api_client.dart';
import '../models/vehicle.dart';
import '../widgets/design_widgets.dart';
import '../app_theme.dart';

class VehicleProfilePage extends StatefulWidget {
  final AppState state;
  final Vehicle? vehicle;
  final bool onboarding;
  final List<CatalogueVehicle>? previewCatalogue;
  const VehicleProfilePage({
    super.key,
    required this.state,
    this.vehicle,
    this.onboarding = false,
    this.previewCatalogue,
  });
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
  int _step = 0;
  final _contactName = TextEditingController(),
      _contactPhone = TextEditingController();
  String? _error;
  late final String? _owner;
  late final String _vehicleId;
  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    _vehicleId =
        widget.vehicle?.id ?? DateTime.now().microsecondsSinceEpoch.toString();
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
      if (widget.previewCatalogue != null) {
        setState(() => _catalogue = widget.previewCatalogue!);
        return;
      }
      final repository = widget.state.repository;
      if (repository == null) {
        throw StateError('No backend connection configured.');
      }
      final catalogue = await repository.catalogue();
      if (mounted) setState(() => _catalogue = catalogue);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Vehicle catalogue could not be loaded. Please retry.',
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
    _contactName.dispose();
    _contactPhone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy) return;
    if (!_form.currentState!.validate()) return;
    if (!widget.state.signedIn || widget.state.accountId != _owner) {
      setState(
        () =>
            _error = 'Your account changed. Close this form and open it again.',
      );
      return;
    }
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
          id: _vehicleId,
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
      if (mounted) {
        if (widget.onboarding) {
          setState(() => _step = 2);
        } else {
          Navigator.pop(context);
        }
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Vehicle could not be saved. Your entries have been kept. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    if (_busy) return;
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
    if (!widget.state.signedIn || widget.state.accountId != _owner) {
      setState(
        () =>
            _error = 'Your account changed. Close this form and open it again.',
      );
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.state.deleteVehicle(widget.vehicle!.id);
      if (mounted) {
        if (widget.onboarding) {
          setState(() => _step = 2);
        } else {
          Navigator.pop(context);
        }
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is ApiException
              ? error.message
              : 'Vehicle could not be removed. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<T?> _pick<T>(String title, List<T> values, String Function(T) label) =>
      showModalBottomSheet<T>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        builder: (context) => DraggableScrollableSheet(
          expand: false,
          initialChildSize: .65,
          builder: (context, controller) => StatefulBuilder(
            builder: (context, update) => Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: TextField(
                    decoration: InputDecoration(labelText: 'Search $title'),
                    onChanged: (value) => update(() => _search = value),
                  ),
                ),
                Expanded(
                  child: ListView(
                    controller: controller,
                    children: [
                      for (final value in values.where(
                        (v) => label(
                          v,
                        ).toLowerCase().contains(_search.toLowerCase()),
                      ))
                        ListTile(
                          title: Text(label(value)),
                          onTap: () => Navigator.pop(context, value),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );

  Widget _choice(String label, String value, VoidCallback? tap) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.standard),
    child: InkWell(
      onTap: _busy ? null : tap,
      borderRadius: BorderRadius.circular(14),
      child: InputDecorator(
        decoration: InputDecoration(
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 12,
          ),
          suffixIcon: tap == null ? null : const Icon(Icons.expand_more),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: const TextStyle(color: AppColors.muted, fontSize: 13),
            ),
            const SizedBox(height: 2),
            Text(
              value.isEmpty ? 'Select' : value,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    ),
  );

  Future<void> _contactDone() async {
    if (_contactPhone.text.trim().isEmpty && _contactName.text.trim().isEmpty) {
      Navigator.pop(context);
      return;
    }
    final digits = _contactPhone.text.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.length < 3 || _contactName.text.trim().isEmpty) {
      setState(
        () => _error = 'Enter a contact name and valid phone number, or skip.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.state.saveContact(_contactName.text, _contactPhone.text);
      if (mounted) Navigator.pop(context);
    } catch (_) {
      if (mounted)
        setState(
          () => _error = 'Could not save the contact. Try again or skip.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final old = widget.vehicle;
    final onboarding = widget.onboarding;
    final makeValues = _catalogue.map((v) => v.manufacturer).toSet().toList()
      ..sort();
    final models =
        _catalogue
            .where((v) => v.manufacturer == _manufacturer)
            .map((v) => v.model)
            .toSet()
            .toList()
          ..sort();
    final years =
        _catalogue
            .where((v) => v.manufacturer == _manufacturer && v.model == _model)
            .map((v) => '${v.year}')
            .toSet()
            .toList()
          ..sort();
    final variants = _catalogue
        .where(
          (v) =>
              v.manufacturer == _manufacturer &&
              v.model == _model &&
              '${v.year}' == _year,
        )
        .toList();
    return Scaffold(
      appBar: onboarding
          ? null
          : AppBar(
              title: Text(old == null ? 'Add vehicle' : 'Edit vehicle'),
              actions: [
                if (old != null)
                  IconButton(
                    tooltip: 'Remove vehicle',
                    onPressed: _busy ? null : _delete,
                    icon: const Icon(Icons.delete_outline),
                  ),
              ],
            ),
      body: SafeArea(
        child: !widget.state.signedIn
            ? const Center(child: Text('Sign in to manage your vehicles.'))
            : Form(
                key: _form,
                child: FormList(
                  padding: const EdgeInsets.all(AppSpacing.screen),
                  children: [
                    if (onboarding) ...[
                      Row(
                        children: [
                          for (var i = 0; i < 3; i++)
                            Container(
                              width: i == _step ? 28 : 8,
                              height: 8,
                              margin: const EdgeInsets.only(right: 6),
                              decoration: BoxDecoration(
                                color: i <= _step
                                    ? Theme.of(
                                        context,
                                      ).colorScheme.primaryContainer
                                    : Theme.of(
                                        context,
                                      ).colorScheme.surfaceContainer,
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                          const Spacer(),
                          Text('Step ${_step + 1} of 3'),
                        ],
                      ),
                      const SizedBox(height: 30),
                      const Center(child: Mascot(size: 80)),
                      const SizedBox(height: 20),
                      Text(
                        _step == 0
                            ? 'Let’s add your car'
                            : _step == 1
                            ? 'A few more details'
                            : 'Help is a call away',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _step == 2
                            ? 'Add your roadside contact. You can do this later in Account.'
                            : 'It takes a minute and lets us tailor your reminders.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 20),
                    ],
                    if (_loading) const LinearProgressIndicator(),
                    if (_error != null) ...[
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (_catalogue.isEmpty && old == null && _step < 2)
                        TextButton(
                          onPressed: _load,
                          child: const Text('Retry catalogue'),
                        ),
                    ],
                    if (!onboarding || _step == 0) ...[
                      _choice(
                        'Make',
                        old?.model ?? _manufacturer ?? '',
                        old != null
                            ? null
                            : () async {
                                _search = '';
                                final value = await _pick(
                                  'make',
                                  makeValues,
                                  (v) => v,
                                );
                                if (value != null && mounted)
                                  setState(() {
                                    _manufacturer = value;
                                    _model = null;
                                    _year = null;
                                    _selected = null;
                                  });
                              },
                      ),
                      if (old == null) ...[
                        _choice(
                          'Model',
                          _model ?? '',
                          _manufacturer == null
                              ? null
                              : () async {
                                  _search = '';
                                  final value = await _pick(
                                    'model',
                                    models,
                                    (v) => v,
                                  );
                                  if (value != null && mounted)
                                    setState(() {
                                      _model = value;
                                      _year = null;
                                      _selected = null;
                                    });
                                },
                        ),
                        _choice(
                          'Year',
                          _year ?? '',
                          _model == null
                              ? null
                              : () async {
                                  _search = '';
                                  final value = await _pick(
                                    'year',
                                    years,
                                    (v) => v,
                                  );
                                  if (value != null && mounted)
                                    setState(() {
                                      _year = value;
                                      _selected = null;
                                    });
                                },
                        ),
                      ] else
                        _choice('Year', '${old.year}', null),
                    ],
                    if (!onboarding || _step == 1) ...[
                      _choice(
                        'Variant',
                        old?.engineSize ?? _selected?.variant ?? '',
                        old != null || _year == null
                            ? null
                            : () async {
                                _search = '';
                                final value = await _pick(
                                  'variant',
                                  variants,
                                  (v) => '${v.variant} · ${v.engine}',
                                );
                                if (value != null && mounted)
                                  setState(() => _selected = value);
                              },
                      ),
                      ReferenceTextField(
                        controller: _mileage,
                        label: 'Odometer (km)',
                        keyboardType: TextInputType.number,
                        validator: (value) {
                          final mileage = int.tryParse(
                            value?.replaceAll(',', '').trim() ?? '',
                          );
                          if (mileage == null ||
                              mileage < 0 ||
                              mileage > 2147483647)
                            return 'Enter a valid odometer reading';
                          if (widget.state
                              .recordsFor(old?.id ?? '')
                              .any((r) => r.mileage > mileage))
                            return 'Cannot be below recorded service mileage';
                          return null;
                        },
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      ExpansionTile(
                        title: const Text('Optional details'),
                        children: [
                          TextFormField(
                            controller: _name,
                            maxLength: 200,
                            decoration: const InputDecoration(
                              labelText: 'Nickname',
                            ),
                          ),
                          TextFormField(
                            controller: _plate,
                            maxLength: 40,
                            decoration: const InputDecoration(
                              labelText: 'Number plate',
                            ),
                          ),
                        ],
                      ),
                    ],
                    if (onboarding && _step == 2) ...[
                      TextField(
                        controller: _contactName,
                        decoration: const InputDecoration(
                          labelText: 'Roadside provider / contact name',
                        ),
                      ),
                      const SizedBox(height: AppSpacing.standard),
                      TextField(
                        controller: _contactPhone,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          labelText: 'Phone number',
                        ),
                      ),
                    ],
                    const SizedBox(height: AppSpacing.large),
                    FilledButton(
                      onPressed: _busy || _loading
                          ? null
                          : () {
                              if (onboarding && _step == 0) {
                                if (_year == null) {
                                  setState(
                                    () =>
                                        _error = 'Select make, model and year.',
                                  );
                                  return;
                                }
                                setState(() {
                                  _step = 1;
                                  _error = null;
                                });
                              } else if (onboarding && _step == 2) {
                                _contactDone();
                              } else {
                                _mileage.text = _mileage.text.replaceAll(
                                  ',',
                                  '',
                                );
                                _save();
                              }
                            },
                      child: Text(
                        _busy
                            ? 'Saving…'
                            : onboarding
                            ? _step == 2
                                  ? 'Finish'
                                  : 'Continue'
                            : 'Save vehicle',
                      ),
                    ),
                    if (onboarding) ...[
                      if (_step == 1)
                        TextButton(
                          onPressed: _busy
                              ? null
                              : () => setState(() => _step = 0),
                          child: const Text('Back'),
                        ),
                      TextButton(
                        onPressed: _busy ? null : () => Navigator.pop(context),
                        child: const Text('Skip for now'),
                      ),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

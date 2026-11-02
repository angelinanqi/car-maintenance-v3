import '../app_spacing.dart';
import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../data/accident_repository.dart';
import '../data/accident_location.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';

class AccidentForm extends StatefulWidget {
  final AccidentRepository repository;
  final Map<String, dynamic>? record;
  final Map<String, dynamic>? draft;
  final Future<String> Function()? currentLocation;
  final String incidentType;
  final VoidCallback? onHelp;
  const AccidentForm({
    super.key,
    required this.repository,
    this.record,
    this.draft,
    this.currentLocation,
    this.incidentType = 'Road accident',
    this.onHelp,
  });
  @override
  State<AccidentForm> createState() => _AccidentFormState();
}

class _AccidentFormState extends State<AccidentForm>
    with WidgetsBindingObserver {
  final _name = TextEditingController();
  final _plate = TextEditingController();
  final _phone = TextEditingController();
  final _insurer = TextEditingController();
  final _details = TextEditingController();
  final _location = TextEditingController();
  final _mileage = TextEditingController();
  DateTime _occurredAt = DateTime.now();
  late String _id;
  Timer? _autosave;
  int _revision = 0;
  List<String> _photos = [];
  bool _loading = true;
  bool _loaded = false;
  bool _busy = false;
  bool _dirty = false;
  bool _locating = false;
  bool _finishing = false;
  int _locationVersion = 0;
  String? _locationFeedback;
  String? _feedback;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    for (final controller in [
      _name,
      _plate,
      _phone,
      _insurer,
      _details,
      _location,
      _mileage,
    ]) {
      controller.addListener(() {
        if (_loaded && mounted) _changed();
      });
    }
    _location.addListener(() => _locationVersion++);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _name.dispose();
    _plate.dispose();
    _phone.dispose();
    _insurer.dispose();
    _details.dispose();
    _location.dispose();
    _mileage.dispose();
    _autosave?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      _save();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _feedback = null;
    });
    try {
      final isNew = widget.record == null && widget.draft == null;
      final draft =
          widget.record ?? widget.draft ?? widget.repository.newDraft();
      if (!mounted) return;
      final photos = (draft['photos'] as List).cast<String>().toList();
      _name.text = draft['name'] as String;
      _plate.text = draft['plate'] as String;
      _phone.text = draft['phone'] as String;
      _insurer.text = draft['insurer'] as String;
      _details.text = draft['details'] as String;
      _id =
          draft['id'] as String? ??
          DateTime.now().microsecondsSinceEpoch.toString();
      _mileage.text = draft['mileage']?.toString() ?? '';
      _location.text = draft['location'] as String? ?? '';
      _occurredAt =
          DateTime.tryParse(draft['occurredAt'] as String? ?? '')?.toLocal() ??
          DateTime.now();
      setState(() {
        _photos = photos;
        _loaded = true;
        _dirty = false;
      });
      if (isNew) {
        await _save();
        if (mounted) _captureLocation();
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _feedback =
              'Saved draft could not be opened. Its file has been kept. Retry before saving.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Map<String, dynamic> _draft([List<String>? photos]) => {
    'version': 1,
    'id': _id,
    'type':
        widget.record?['type'] ?? widget.draft?['type'] ?? widget.incidentType,
    'mileage': int.tryParse(_mileage.text.trim()),
    'location': _location.text.trim(),
    'occurredAt': _occurredAt.toUtc().toIso8601String(),
    'name': _name.text.trim(),
    'plate': _plate.text.trim().toUpperCase(),
    'phone': _phone.text.trim(),
    'insurer': _insurer.text.trim(),
    'details': _details.text.trim(),
    'photos': photos ?? _photos,
  };

  void _changed() {
    _revision++;
    setState(() => _dirty = true);
    _autosave?.cancel();
    _autosave = Timer(const Duration(milliseconds: 350), _save);
  }

  Future<void> _persist(Map<String, dynamic> data) => widget.record == null
      ? widget.repository.save(data)
      : widget.repository.saveRecord(data);

  Future<bool> _save() async {
    if (!_loaded || _busy) return false;
    final mileageText = _mileage.text.trim();
    final mileage = int.tryParse(mileageText);
    if (mileageText.isNotEmpty &&
        (mileage == null || mileage < 0 || mileage > 2147483647)) {
      setState(() => _feedback = 'Enter a valid mileage or leave it empty.');
      return false;
    }
    _autosave?.cancel();
    final revision = _revision;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    try {
      await _persist(_draft());
      if (mounted) {
        setState(() {
          _dirty = revision != _revision;
          _feedback = widget.record == null
              ? 'Draft saved on this device.'
              : 'Changes saved to this accident form.';
        });
      }
      return true;
    } catch (_) {
      if (mounted) {
        setState(
          () => _feedback =
              'Could not save the draft. Keep this screen open and retry.',
        );
      }
      return false;
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        if (_dirty && revision != _revision) {
          _autosave = Timer(const Duration(milliseconds: 350), _save);
        }
      }
    }
  }

  Future<void> _captureLocation() async {
    if (_locating || _finishing) return;
    final version = _locationVersion;
    setState(() {
      _locating = true;
      _locationFeedback = null;
    });
    try {
      final location =
          await (widget.currentLocation ?? AccidentLocation().current)();
      if (!mounted || _finishing || version != _locationVersion) return;
      _location.text = location;
      setState(
        () => _locationFeedback =
            'Current location filled. Edit it if the accident happened elsewhere.',
      );
    } on AccidentLocationException catch (error) {
      if (mounted) setState(() => _locationFeedback = error.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => _locationFeedback =
              'Current location could not be retrieved. Enter the accident location yourself, or retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _finish() async {
    if (!await _save() || !mounted) return;
    _autosave?.cancel();
    setState(() {
      _finishing = true;
      _busy = true;
    });
    try {
      if (widget.record == null) {
        await widget.repository.completeDraft(_draft());
      }
      if (mounted) {
        setState(() {
          _dirty = false;
          _busy = false;
        });
        Navigator.pop(context, true);
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _feedback =
              'The accident form could not be moved to history. Your draft is kept. Please retry.',
        );
      }
    } finally {
      if (mounted)
        setState(() {
          _busy = false;
          _finishing = false;
        });
    }
  }

  Future<void> _pick(ImageSource source) async {
    if (_photos.length >= 6 || !await _save() || !mounted) return;
    setState(() {
      _busy = true;
      _feedback = null;
    });
    String? copiedPhoto;
    try {
      await widget.repository.rememberPhotoTarget(
        _id,
        savedRecord: widget.record != null,
      );
      final photo = await widget.repository.pickPhoto(source);
      copiedPhoto = photo;
      if (photo == null) {
        try {
          await widget.repository.clearPhotoTarget();
        } catch (_) {
          debugPrint(
            'WARNING [emergency-picker] Cancelled picker target cleanup failed.',
          );
        }
        return;
      }
      final photos = [..._photos, photo];
      await _persist(_draft(photos));
      if (mounted) {
        setState(() {
          _photos = photos;
          _dirty = false;
          _feedback = 'Photo attached and saved on this device.';
        });
      }
      try {
        await widget.repository.clearPhotoTarget();
      } catch (_) {
        debugPrint(
          'WARNING [emergency-picker] Saved photo target cleanup failed.',
        );
      }
    } catch (error) {
      if (copiedPhoto != null)
        await widget.repository.store.removePhotoIfUnreferenced(copiedPhoto);
      if (mounted) {
        setState(
          () => _feedback = error is FormatException
              ? 'Choose a valid image smaller than 10 MB. Your saved form is kept.'
              : 'Photo could not be attached. Your saved form is kept. Check camera or photo access and retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(String photo) async {
    setState(() => _busy = true);
    try {
      final photos = _photos.where((p) => p != photo).toList();
      await _persist(_draft(photos));
      if (mounted) {
        setState(() {
          _photos = photos;
          _dirty = false;
        });
      }
      await widget.repository.store.removePhotoIfUnreferenced(photo);
    } catch (_) {
      if (mounted) {
        setState(
          () => _feedback = 'Could not complete photo removal. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _leave() async {
    if (_busy) return;
    if (!_dirty) {
      Navigator.pop(context);
      return;
    }
    if (await _save() && mounted && !_dirty) {
      Navigator.pop(context);
      return;
    }
    final discard = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Leave without saving?'),
        content: const Text(
          'Unsaved text changes will be lost. The previously saved draft will remain.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep editing'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Discard changes'),
          ),
        ],
      ),
    );
    if (discard == true && mounted) {
      setState(() => _dirty = false);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.pop(context);
      });
    }
  }

  Future<void> _date() async {
    final day = await showDatePicker(
      context: context,
      initialDate: _occurredAt.isAfter(DateTime.now())
          ? DateTime.now()
          : _occurredAt.isBefore(DateTime(2000))
          ? DateTime(2000)
          : _occurredAt,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (day == null || !mounted) return;
    _occurredAt = DateTime(
      day.year,
      day.month,
      day.day,
      _occurredAt.hour,
      _occurredAt.minute,
    );
    _changed();
  }

  Future<void> _time() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_occurredAt),
      initialEntryMode: TimePickerEntryMode.input,
    );
    if (time == null || !mounted) return;
    _occurredAt = DateTime(
      _occurredAt.year,
      _occurredAt.month,
      _occurredAt.day,
      time.hour,
      time.minute,
    );
    _changed();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_dirty && !_busy,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop) _leave();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(widget.record != null ? 'Saved incident' : 'Save incident'),
        leading: IconButton(
          tooltip: 'Back',
          onPressed: _leave,
          icon: const Icon(Icons.arrow_back_ios_new),
        ),
        actions: [
          if (widget.onHelp != null)
            IconButton(
              tooltip: 'Call for help',
              onPressed: widget.onHelp,
              icon: const Icon(Icons.phone_outlined),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(AppSpacing.screen),
              children: [
                if (_feedback != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      _feedback!,
                      style: const TextStyle(color: AppColors.muted),
                    ),
                  ),
                if (!_loaded)
                  OutlinedButton(
                    onPressed: _load,
                    child: const Text('Retry opening draft'),
                  ),
                InkWell(
                  key: const Key('incident-date'),
                  onTap: !_loaded || _busy ? null : _date,
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: 'Date'),
                    child: Text(
                      MaterialLocalizations.of(
                        context,
                      ).formatMediumDate(_occurredAt),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.standard),
                InkWell(
                  key: const Key('incident-time'),
                  onTap: !_loaded || _busy ? null : _time,
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: 'Time'),
                    child: Text(
                      TimeOfDay.fromDateTime(_occurredAt).format(context),
                    ),
                  ),
                ),
                TextButton(
                  onPressed: !_loaded || _busy
                      ? null
                      : () {
                          _occurredAt = DateTime.now();
                          _changed();
                        },
                  child: const Text('Use current date and time'),
                ),
                TextField(
                  key: const Key('incident-location'),
                  controller: _location,
                  enabled: _loaded && !_busy,
                  maxLength: 2000,
                  decoration: const InputDecoration(
                    labelText: 'Incident location',
                    helperText: 'Road name, landmark or coordinates',
                  ),
                ),
                TextButton.icon(
                  onPressed: !_loaded || _busy || _locating
                      ? null
                      : _captureLocation,
                  icon: const Icon(Icons.my_location),
                  label: Text(
                    _locating ? 'Getting location…' : 'Use current location',
                  ),
                ),
                if (_locationFeedback != null) Text(_locationFeedback!),
                const SizedBox(height: AppSpacing.standard),
                ReferenceTextField(
                  key: const Key('incident-mileage'),
                  controller: _mileage,
                  enabled: _loaded && !_busy,
                  keyboardType: TextInputType.number,
                  label: 'Mileage (km)',
                  helper:
                      'Optional odometer reading at the time of the incident.',
                ),
                const SizedBox(height: AppSpacing.standard),
                ReferenceTextField(
                  controller: _details,
                  enabled: _loaded && !_busy,
                  minLines: 2,
                  maxLines: 5,
                  maxLength: 20000,
                  label: 'What happened?',
                ),
                const SizedBox(height: 18),
                Text('Photos', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: AppSpacing.standard),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final width = (constraints.maxWidth - 16) / 3;
                    return Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (var i = 0; i < _photos.length; i++)
                          SizedBox(
                            width: width,
                            child: Column(
                              children: [
                                InkWell(
                                  onTap: () => showDialog<void>(
                                    context: context,
                                    builder: (_) => Dialog(
                                      child: InteractiveViewer(
                                        child: Image.file(
                                          File(_photos[i]),
                                          errorBuilder: (_, _, _) =>
                                              const Padding(
                                                padding: EdgeInsets.all(
                                                  AppSpacing.screen,
                                                ),
                                                child: Text(
                                                  'Photo unavailable',
                                                ),
                                              ),
                                        ),
                                      ),
                                    ),
                                  ),
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(14),
                                    child: Image.file(
                                      File(_photos[i]),
                                      width: width,
                                      height: 80,
                                      fit: BoxFit.cover,
                                      errorBuilder: (_, _, _) => const SizedBox(
                                        height: 80,
                                        child: Center(
                                          child: Text('Photo unavailable'),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                                TextButton(
                                  onPressed: _busy
                                      ? null
                                      : () => _remove(_photos[i]),
                                  child: const Text('Remove'),
                                ),
                              ],
                            ),
                          ),
                        if (_photos.length < 6)
                          for (
                            var i = 0;
                            i < (_photos.length < 3 ? 3 - _photos.length : 1);
                            i++
                          )
                            PopupMenuButton<ImageSource>(
                              enabled: _loaded && !_busy,
                              tooltip: 'Add photo',
                              onSelected: _pick,
                              itemBuilder: (_) => const [
                                PopupMenuItem(
                                  value: ImageSource.camera,
                                  child: Text('Take photo'),
                                ),
                                PopupMenuItem(
                                  value: ImageSource.gallery,
                                  child: Text('Choose from gallery'),
                                ),
                              ],
                              child: Container(
                                width: width,
                                height: 80,
                                decoration: BoxDecoration(
                                  border: Border.all(color: AppColors.border),
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                child: const Icon(
                                  Icons.add,
                                  color: AppColors.muted,
                                ),
                              ),
                            ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                ExpansionTile(
                  title: const Text('Additional accident details'),
                  subtitle: const Text('Other driver and insurer'),
                  children: [
                    for (final field in [
                      (_name, 'Other driver name', 200),
                      (_plate, 'Other vehicle plate', 40),
                      (_phone, 'Contact phone', 100),
                      (_insurer, 'Insurer (if known)', 200),
                    ])
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: TextField(
                          controller: field.$1,
                          maxLength: field.$3,
                          enabled: _loaded && !_busy,
                          decoration: InputDecoration(labelText: field.$2),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 50),
                FilledButton(
                  onPressed: !_loaded || _busy ? null : _finish,
                  child: Text(
                    _busy
                        ? 'Saving…'
                        : widget.record == null
                        ? 'Save incident'
                        : 'Save changes',
                  ),
                ),
                if (widget.record == null)
                  TextButton(
                    onPressed: !_loaded || _busy
                        ? null
                        : () async {
                            if (await _save() && mounted && !_dirty)
                              Navigator.pop(context);
                          },
                    child: const Text('Save draft and close'),
                  ),
                const Text(
                  'Incident details and photos stay on this device unless you enable text backup. Photos remain local.',
                  style: TextStyle(fontSize: 12, color: AppColors.muted),
                ),
              ],
            ),
    ),
  );
}

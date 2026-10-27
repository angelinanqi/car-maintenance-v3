import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../data/accident_repository.dart';
import '../data/accident_location.dart';

class AccidentForm extends StatefulWidget {
  final AccidentRepository repository;
  final Map<String, dynamic>? record;
  final Map<String, dynamic>? draft;
  final Future<String> Function()? currentLocation;
  final VoidCallback? onHelp;
  const AccidentForm({
    super.key,
    required this.repository,
    this.record,
    this.draft,
    this.currentLocation,
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
    'type': widget.record?['type'] ?? widget.draft?['type'] ?? 'Road accident',
    'location': _location.text.trim(),
    'occurredAt': _occurredAt.toIso8601String(),
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
    try {
      await widget.repository.rememberPhotoTarget(
        _id,
        savedRecord: widget.record != null,
      );
      final photo = await widget.repository.pickPhoto(source);
      if (photo == null) {
        await widget.repository.clearPhotoTarget();
        return;
      }
      final photos = [..._photos, photo];
      await _persist(_draft(photos));
      await widget.repository.clearPhotoTarget();
      if (mounted) {
        setState(() {
          _photos = photos;
          _dirty = false;
          _feedback = 'Photo attached and saved on this device.';
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _feedback =
              'Photo could not be attached. Check camera or photo access and retry.',
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
      // Saved incident history may reference this photo. Retain the file;
      // removing an attachment must never break another saved incident.
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

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_dirty && !_busy,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop) _leave();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(
          widget.record != null
              ? 'Saved accident form'
              : widget.draft != null
              ? 'Accident draft'
              : 'New accident form',
        ),
        actions: [
          if (widget.onHelp != null)
            TextButton(
              onPressed: widget.onHelp,
              child: const Text('Call for help'),
            ),
        ],
        leading: IconButton(
          tooltip: 'Back',
          icon: const Icon(Icons.arrow_back),
          onPressed: _leave,
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Text(
                  'You can leave fields empty and continue later. Changes save on this device as you edit. Saving a record does not submit a police report or insurance claim.',
                ),
                const SizedBox(height: 16),
                if (_feedback != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_feedback!),
                  ),
                if (!_loaded)
                  OutlinedButton(
                    onPressed: _load,
                    child: const Text('Retry loading draft'),
                  ),
                Text(
                  '1. What happened',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(
                  widget.draft != null || widget.record != null
                      ? 'Your saved accident time and location are kept. You can correct them below.'
                      : 'The accident time starts at the current time. Edit the time and location if you are recording an earlier accident.',
                ),
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: !_loaded || _busy
                      ? null
                      : () async {
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
                          if (day == null || !context.mounted) return;
                          final time = await showTimePicker(
                            context: context,
                            initialTime: TimeOfDay.fromDateTime(_occurredAt),
                          );
                          if (time == null || !mounted) return;
                          _occurredAt = DateTime(
                            day.year,
                            day.month,
                            day.day,
                            time.hour,
                            time.minute,
                          );
                          _changed();
                        },
                  child: Text(
                    'Accident time: ${MaterialLocalizations.of(context).formatMediumDate(_occurredAt)} at ${MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(_occurredAt))}',
                  ),
                ),
                TextButton.icon(
                  onPressed: !_loaded || _busy
                      ? null
                      : () {
                          _occurredAt = DateTime.now();
                          _changed();
                        },
                  icon: const Icon(Icons.schedule),
                  label: const Text('Use current time'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _location,
                  enabled: _loaded && !_busy,
                  decoration: const InputDecoration(
                    labelText: 'Accident location',
                    helperText:
                        'Address, road name, landmark or GPS coordinates',
                  ),
                ),
                TextButton.icon(
                  onPressed: !_loaded || _busy || _locating
                      ? null
                      : _captureLocation,
                  icon: const Icon(Icons.my_location),
                  label: Text(
                    _locating
                        ? 'Getting current location...'
                        : 'Use current location',
                  ),
                ),
                if (_locationFeedback != null) Text(_locationFeedback!),
                const SizedBox(height: 20),
                ExpansionTile(
                  title: const Text('2. Other driver and vehicle'),
                  subtitle: const Text('Add only what you know'),
                  childrenPadding: const EdgeInsets.symmetric(vertical: 12),
                  children: [
                    TextField(
                      controller: _name,
                      enabled: _loaded && !_busy,
                      decoration: const InputDecoration(
                        labelText: 'Other driver name',
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _plate,
                      enabled: _loaded && !_busy,
                      textCapitalization: TextCapitalization.characters,
                      decoration: const InputDecoration(
                        labelText: 'Other vehicle plate',
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _phone,
                      enabled: _loaded && !_busy,
                      keyboardType: TextInputType.phone,
                      decoration: const InputDecoration(
                        labelText: 'Contact phone',
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _insurer,
                      enabled: _loaded && !_busy,
                      decoration: const InputDecoration(
                        labelText: 'Insurer (if known)',
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                ),
                const SizedBox(height: 20),
                Text(
                  '3. Notes and photos',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _details,
                  enabled: _loaded && !_busy,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: 'What you noticed (optional)',
                  ),
                ),
                const SizedBox(height: 20),
                Text('${_photos.length}/6 photos attached'),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: _photos
                      .map(
                        (photo) => SizedBox(
                          width: 140,
                          child: Column(
                            children: [
                              Image.file(
                                File(photo),
                                height: 110,
                                width: 140,
                                fit: BoxFit.cover,
                                errorBuilder: (_, _, _) => const SizedBox(
                                  height: 110,
                                  child: Center(
                                    child: Text('Photo unavailable'),
                                  ),
                                ),
                              ),
                              TextButton(
                                onPressed: _busy ? null : () => _remove(photo),
                                child: const Text('Remove photo'),
                              ),
                            ],
                          ),
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 12),
                PopupMenuButton<ImageSource>(
                  enabled: _loaded && !_busy && _photos.length < 6,
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
                  child: const Padding(
                    padding: EdgeInsets.all(16),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.add_a_photo_outlined),
                        SizedBox(width: 8),
                        Text('Add photo'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  '4. Keep your record',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Save a draft to continue later, or save this completed form to past accidents. Photos stay on this device.',
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: !_loaded || _busy
                      ? null
                      : () async {
                          if (await _save() && context.mounted && !_dirty)
                            Navigator.pop(context);
                        },
                  child: Text(
                    _busy
                        ? 'Saving...'
                        : widget.record != null
                        ? 'Save changes and close'
                        : 'Save draft and close',
                  ),
                ),
                if (widget.record == null)
                  OutlinedButton(
                    onPressed: !_loaded || _busy ? null : _finish,
                    child: const Text('Save to past accidents'),
                  ),
              ],
            ),
    ),
  );
}

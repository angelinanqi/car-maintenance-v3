import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/chat_repository.dart';
import '../data/nearby_repository.dart';
import '../models/mechanic_preparation.dart';
import '../widgets/workshop_notes.dart';
import 'nearby_assistance.dart';
import '../data/companion_repository.dart';

class MechanicPreparationPage extends StatefulWidget {
  final AppState state;
  final FastApiChatRepository repository;
  final String initialQuestion;
  final String? sessionId;
  final String? sessionToken;
  final String? planId;
  final String initialNotes;
  const MechanicPreparationPage({
    super.key,
    required this.state,
    required this.repository,
    this.initialQuestion = '',
    this.sessionId,
    this.sessionToken,
    this.planId,
    this.initialNotes = '',
  });

  @override
  State<MechanicPreparationPage> createState() =>
      _MechanicPreparationPageState();
}

class _MechanicPreparationPageState extends State<MechanicPreparationPage> {
  late final TextEditingController _question;
  final _notes = TextEditingController();
  String? _accountId;
  String? _vehicleId;
  String? _error;
  String? _savedNoteId;
  MechanicPreparation? _preparation;
  bool _busy = false;
  bool _contextChanged = false;

  @override
  void initState() {
    super.initState();
    _question = TextEditingController(text: widget.initialQuestion);
    _notes.text = widget.initialNotes;
    _accountId = widget.state.accountId;
    _vehicleId = widget.state.selectedVehicle?.id;
    widget.state.addListener(_selectionChanged);
  }

  void _selectionChanged() {
    if (widget.state.accountId != _accountId ||
        widget.state.selectedVehicle?.id != _vehicleId) {
      _question.clear();
      _notes.clear();
      if (mounted)
        setState(() {
          _contextChanged = true;
          _preparation = null;
        });
    }
  }

  @override
  void dispose() {
    widget.state.removeListener(_selectionChanged);
    _question.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _prepare() async {
    if (_busy || _contextChanged) return;
    final question = _question.text.trim();
    if (question.isEmpty || question.length > 4000) {
      setState(() => _error = 'Describe your concern in 1 to 4000 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _preparation = null;
    });
    try {
      final result = await widget.repository.prepareQuestions(
        question: question,
        vehicleId: _vehicleId,
        sessionId: widget.sessionId,
        sessionToken: widget.sessionToken,
        planId: widget.planId,
      );
      if (!mounted || _contextChanged) return;
      setState(() {
        _preparation = result;
        _notes.text = [
          if (widget.initialNotes.isNotEmpty) widget.initialNotes,
          result.asText(),
        ].join('\n\n');
      });
    } catch (error) {
      if (mounted && !_contextChanged)
        setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _findWorkshops() {
    if (_contextChanged) return;
    final notes = _notes.text.trim().isEmpty ? null : _notes.text.trim();
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => NearbyAssistance(
          repository: NearbyRepository(widget.repository.api),
          consultationNotes: notes,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Prepare for a mechanic')),
    body: _contextChanged
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'The account or active vehicle changed. Return to chat and reopen question preparation.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Make the conversation easier',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Turn what you are unsure about into questions a mechanic can explain or investigate.',
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _question,
                enabled: !_busy,
                minLines: 2,
                maxLines: 5,
                maxLength: 4000,
                decoration: const InputDecoration(
                  labelText: 'What would you like clarified?',
                ),
                onChanged: (_) => setState(() {
                  _preparation = null;
                }),
              ),
              FilledButton.icon(
                onPressed: _busy ? null : _prepare,
                icon: _busy
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.format_list_bulleted),
                label: Text(
                  _busy ? 'Preparing questions...' : 'Prepare my questions',
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ...[
                const SizedBox(height: 20),
                Text(
                  _preparation == null
                      ? 'Your discussion notes'
                      : _preparation!.tailored
                      ? 'Review your discussion notes'
                      : 'General checklist — adapt these questions to your concern',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _notes,
                  minLines: 8,
                  maxLines: null,
                  decoration: const InputDecoration(
                    labelText: 'Review or edit before sharing',
                    alignLabelWithHint: true,
                  ),
                ),
                TextButton.icon(
                  onPressed: () => copyWorkshopNotes(context, _notes.text),
                  icon: const Icon(Icons.copy),
                  label: const Text('Copy discussion notes'),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.bookmark_add_outlined),
                  label: const Text('Save notes'),
                  onPressed: _busy
                      ? null
                      : () async {
                          setState(() {
                            _busy = true;
                            _error = null;
                          });
                          try {
                            final repository = CompanionRepository(
                              widget.repository,
                            );
                            final saved = _savedNoteId != null
                                ? await repository.api.patch(
                                    '/mobile/me/saved-items/$_savedNoteId',
                                    {
                                      'title': 'Questions for my mechanic',
                                      'text': _notes.text,
                                    },
                                    token: repository.token,
                                  )
                                : await repository.save({
                                    'kind': 'notes',
                                    'title': 'Questions for my mechanic',
                                    'vehicle_id': _vehicleId,
                                    if (widget.planId != null)
                                      'plan_id': widget.planId,
                                    'text': _notes.text,
                                  });
                            if (mounted && !_contextChanged)
                              _savedNoteId = saved['id'] as String;
                            if (mounted && !_contextChanged)
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Notes saved')),
                              );
                          } catch (error) {
                            if (mounted)
                              setState(() => _error = error.toString());
                          } finally {
                            if (mounted) setState(() => _busy = false);
                          }
                        },
                ),
              ],
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _findWorkshops,
                icon: const Icon(Icons.location_on_outlined),
                label: const Text('Find nearby workshops'),
              ),
              const Text(
                'Call to confirm that a workshop can help with your vehicle. Your notes are not sent to the workshop.',
              ),
              const SizedBox(height: 16),
              Text(
                aiReferenceNotice,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
  );
}

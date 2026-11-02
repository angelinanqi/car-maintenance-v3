import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../data/companion_repository.dart';
import '../data/api_client.dart';
import '../app_state.dart';

class SavedItemsPage extends StatefulWidget {
  final CompanionRepository repository;
  final AppState state;
  const SavedItemsPage({
    super.key,
    required this.repository,
    required this.state,
  });
  @override
  State<SavedItemsPage> createState() => _SavedItemsPageState();
}

class _SavedItemsPageState extends State<SavedItemsPage> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;
  late final String? _owner;
  bool _accountChanged = false;
  int _request = 0;
  @override
  void initState() {
    super.initState();
    _owner = widget.state.accountId;
    widget.state.addListener(_checkAccount);
    _load();
  }

  void _checkAccount() {
    if (widget.state.accountId == _owner || _accountChanged) return;
    _request++;
    setState(() {
      _accountChanged = true;
      _items = [];
      _loading = false;
      _error = 'Your account changed. Return to chat and reopen Saved.';
    });
  }

  @override
  void dispose() {
    widget.state.removeListener(_checkAccount);
    super.dispose();
  }

  Future<void> _load() async {
    if (_accountChanged) return;
    final request = ++_request;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.repository.saved();
      if (mounted && request == _request)
        setState(() => _items = items.reversed.toList());
    } catch (error) {
      if (mounted && request == _request)
        setState(() => _error = error.toString());
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  Future<void> _notes(Map<String, dynamic> item) async {
    final saved = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => SavedNoteEditor(
        state: widget.state,
        title: item['title'] as String,
        text: (item['payload'] as Map)['text'] as String? ?? '',
        onSave: (text) async {
          await widget.repository.api.patch(
            '/mobile/me/saved-items/${item['id']}',
            {'title': item['title'], 'text': text},
            token: widget.repository.token,
          );
        },
      ),
    );
    if (saved == true && mounted && !_accountChanged) await _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Saved')),
    body: RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: [
          if (_loading) const LinearProgressIndicator(),
          if (_error != null) ...[
            Text(_error!),
            if (!_accountChanged)
              TextButton(onPressed: _load, child: const Text('Try again')),
          ],
          if (!_loading && _items.isEmpty)
            const Text(
              'Save explanations, guides, service plans or mechanic notes while you explore.',
            ),
          for (final item in _items)
            ListTile(
              contentPadding: const EdgeInsets.symmetric(vertical: 8),
              title: Text(item['title'] as String),
              subtitle: Text(
                item['available'] == false
                    ? 'Original content is no longer available'
                    : item['kind'] == 'explanation'
                    ? 'Saved explanation · Historical answer'
                    : item['kind'] as String,
              ),
              onTap: item['available'] == false
                  ? null
                  : () {
                      if (item['kind'] == 'notes') {
                        _notes(item);
                      } else {
                        Navigator.pop(context, item);
                      }
                    },
              trailing: IconButton(
                tooltip: 'Remove saved item',
                icon: const Icon(Icons.bookmark_remove_outlined),
                onPressed: () async {
                  try {
                    await widget.repository.remove(item['id'] as String);
                    if (mounted) await _load();
                  } catch (error) {
                    if (mounted)
                      setState(
                        () => _error = error is ApiException
                            ? error.message
                            : 'Could not remove the saved item.',
                      );
                  }
                },
              ),
            ),
        ],
      ),
    ),
  );
}

class SavedNoteEditor extends StatefulWidget {
  final String title, text;
  final AppState state;
  final Future<void> Function(String text) onSave;
  const SavedNoteEditor({
    super.key,
    required this.title,
    required this.text,
    required this.state,
    required this.onSave,
  });
  @override
  State<SavedNoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends State<SavedNoteEditor> {
  late final TextEditingController _text;
  late final String? _owner, _vehicle;
  bool _busy = false, _changed = false;
  String? _error;
  @override
  void initState() {
    super.initState();
    _text = TextEditingController(text: widget.text);
    _owner = widget.state.accountId;
    _vehicle = widget.state.selectedVehicle?.id;
    widget.state.addListener(_checkContext);
  }

  void _checkContext() {
    if (_owner == widget.state.accountId &&
        _vehicle == widget.state.selectedVehicle?.id)
      return;
    _text.clear();
    setState(() {
      _changed = true;
      _error = 'Your account or vehicle changed. Close and reopen these notes.';
    });
  }

  Future<void> _save() async {
    if (_busy || _changed) return;
    if (_text.text.trim().isEmpty || _text.text.length > 20000) {
      setState(() => _error = 'Enter notes within 20000 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.onSave(_text.text);
      if (mounted && !_changed) Navigator.pop(context, true);
    } catch (error) {
      if (mounted && !_changed) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _text.dispose();
    widget.state.removeListener(_checkContext);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_busy,
    child: AlertDialog(
      scrollable: true,
      title: Text(widget.title),
      content: SizedBox(
        width: 480,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _text,
              enabled: !_busy && !_changed,
              minLines: 6,
              maxLines: 12,
              maxLength: 20000,
              decoration: const InputDecoration(labelText: 'Your notes'),
            ),
            if (_error != null) Text(_error!),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _busy ? null : () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: _busy || _changed ? null : _save,
          child: Text(_busy ? 'Saving…' : 'Save changes'),
        ),
      ],
    ),
  );
}

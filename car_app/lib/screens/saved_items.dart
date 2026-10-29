import 'package:flutter/material.dart';
import '../data/companion_repository.dart';
import '../data/api_client.dart';

class SavedItemsPage extends StatefulWidget {
  final CompanionRepository repository;
  const SavedItemsPage({super.key, required this.repository});
  @override
  State<SavedItemsPage> createState() => _SavedItemsPageState();
}

class _SavedItemsPageState extends State<SavedItemsPage> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final items = await widget.repository.saved();
      if (mounted) setState(() => _items = items.reversed.toList());
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _notes(Map<String, dynamic> item) async {
    final text = await showDialog<String>(
      context: context,
      builder: (_) => _NoteEditor(
        title: item['title'] as String,
        text: (item['payload'] as Map)['text'] as String? ?? '',
      ),
    );
    if (text != null) {
      try {
        await widget.repository.api.patch(
          '/mobile/me/saved-items/${item['id']}',
          {'title': item['title'], 'text': text},
          token: widget.repository.token,
        );
        if (mounted) await _load();
      } catch (error) {
        if (mounted) setState(() => _error = error.toString());
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Saved')),
    body: RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading) const LinearProgressIndicator(),
          if (_error != null) ...[
            Text(_error!),
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

class _NoteEditor extends StatefulWidget {
  final String title, text;
  const _NoteEditor({required this.title, required this.text});
  @override
  State<_NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends State<_NoteEditor> {
  late final TextEditingController _text;
  @override
  void initState() {
    super.initState();
    _text = TextEditingController(text: widget.text);
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.title),
    content: SizedBox(
      width: 480,
      child: TextField(
        controller: _text,
        minLines: 6,
        maxLines: 12,
        maxLength: 20000,
        decoration: const InputDecoration(labelText: 'Your notes'),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Close'),
      ),
      FilledButton(
        onPressed: () => Navigator.pop(context, _text.text),
        child: const Text('Save changes'),
      ),
    ],
  );
}

import 'dart:async';
import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/chat_repository.dart';
import '../data/api_client.dart';
import '../data/content_repository.dart';
import '../models/chat_message.dart';
import '../models/mechanic_preparation.dart';
import 'mechanic_preparation.dart';
import '../widgets/vehicle_selector.dart';
import '../widgets/sign_in_prompt.dart';
import '../widgets/chat_message_view.dart';

class Chat extends StatefulWidget {
  final AppState state;
  final ChatRepository repository;
  final int requestNumber;
  final String? topic;
  final String? prompt;
  final Map<String, dynamic>? contextData;
  final VoidCallback? onEmergency;
  const Chat({
    super.key,
    required this.state,
    required this.repository,
    this.requestNumber = 0,
    this.topic,
    this.prompt,
    this.contextData,
    this.onEmergency,
  });
  @override
  State<Chat> createState() => _ChatState();
}

class _ChatState extends State<Chat> {
  final _text = TextEditingController();
  final _scroll = ScrollController();
  final _inputFocus = FocusNode();
  final List<ChatMessage> _messages = [];
  final List<ChatMessage> _history = [];
  String? _vehicleId;
  String? _scope;
  String? _topic;
  String? _error;
  ChatRequest? _failedRequest;
  bool _pending = false;
  int _generation = 0;
  List<Map<String, dynamic>> _knowledgeScopes = [];
  Map<String, dynamic>? _knowledgeScope;
  String? _sessionId;
  String? _sessionToken;
  String? _accountId;
  Map<String, dynamic>? _contextData;
  final Map<String, Map<String, dynamic>> _conversations = {};
  String _conversationKey = '';
  bool _scopesLoading = false;
  String? _scopeError;
  bool _showLatest = false;
  List<String> _starterQuestions = [];

  @override
  void initState() {
    super.initState();
    _vehicleId = widget.state.selectedVehicle?.id;
    _scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    _accountId = widget.state.accountId;
    _contextData = widget.contextData;
    _topic = widget.topic;
    _text.text = widget.prompt ?? '';
    _scroll.addListener(_scrollChanged);
    _loadScopes();
  }

  void _scrollChanged() {
    if (!_scroll.hasClients) return;
    final show = _scroll.position.extentAfter > 240;
    if (show != _showLatest) setState(() => _showLatest = show);
  }

  Future<void> _loadScopes() async {
    unawaited(_loadStarterQuestions());
    if (widget.repository is! FastApiChatRepository) return;
    setState(() {
      _scopesLoading = true;
      _scopeError = null;
    });
    try {
      final repository = widget.repository as FastApiChatRepository;
      final scopes = await repository.api.getList('/knowledge/scopes');
      if (!mounted) return;
      setState(() {
        _knowledgeScopes = scopes;
        if (_knowledgeScope != null) {
          final matches = scopes.where(
            (s) =>
                s['scope_id'] == _knowledgeScope!['scope_id'] &&
                s['scope_type'] == _knowledgeScope!['scope_type'] &&
                s['available'] == true,
          );
          if (matches.isEmpty) {
            _knowledgeScope = null;
          }
        }
        if (_knowledgeScope == null) {
          final draft = _text.text;
          final topic = _topic;
          _selectActiveScope();
          if (_text.text.isEmpty) _text.text = draft;
          _topic ??= topic;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => _scopeError =
              'Sources could not refresh. Check your connection and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _scopesLoading = false);
    }
  }

  Future<void> _loadStarterQuestions() async {
    final repository = widget.repository;
    final content = ContentRepository(
      widget.state.store,
      api: repository is FastApiChatRepository ? repository.api : null,
    );
    try {
      final cached = await content.chatStarters();
      if (mounted) setState(() => _starterQuestions = cached);
    } catch (_) {
      // A corrupt local preference must not block source selection or chat.
    }
    if (content.api == null) return;
    try {
      final current = await content.chatStarters(refresh: true);
      if (mounted) setState(() => _starterQuestions = current);
    } catch (_) {
      // Keep the last synced list, including an intentionally empty list.
    }
  }

  void _selectActiveScope() {
    final vehicle = widget.state.selectedVehicle;
    final matches = _knowledgeScopes.where(
      (s) =>
          s['available'] == true &&
          (vehicle != null
              ? s['scope_type'] == 'vehicle' &&
                    s['scope_id'] == vehicle.knowledgeScopeId
              : _contextData?['categoryId'] != null &&
                    s['scope_type'] == 'category' &&
                    s['scope_id'] == _contextData!['categoryId']),
    );
    _switchScope(matches.isEmpty ? null : matches.first);
  }

  void _switchScope(Map<String, dynamic>? scope) {
    if (_pending) {
      _generation++;
      _pending = false;
    }
    if (_conversationKey.isNotEmpty) {
      _conversations[_conversationKey] = {
        'messages': List<ChatMessage>.of(_messages),
        'history': List<ChatMessage>.of(_history),
        'sessionId': _sessionId,
        'sessionToken': _sessionToken,
        'draft': _text.text,
        'error': _error,
        'failedRequest': _failedRequest,
        'offset': _scroll.hasClients ? _scroll.offset : 0.0,
        'topic': _topic,
      };
    }
    final key =
        '${widget.state.accountId}:${widget.state.selectedVehicle?.id}:${scope?['scope_type']}:${scope?['scope_id']}:${_contextData?['kind']}:${_contextData?['id']}';
    _clear();
    _knowledgeScope = scope;
    _conversationKey = key;
    _topic = _contextData?['title'] as String?;
    _text.clear();
    final saved = _conversations[key];
    if (saved != null) {
      _messages.addAll(saved['messages'] as List<ChatMessage>);
      _history.addAll(saved['history'] as List<ChatMessage>);
      _sessionId = saved['sessionId'] as String?;
      _sessionToken = saved['sessionToken'] as String?;
      _text.text = saved['draft'] as String? ?? '';
      _error = saved['error'] as String?;
      _failedRequest = saved['failedRequest'] as ChatRequest?;
      _topic = saved['topic'] as String?;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scroll.hasClients) {
        final offset = saved?['offset'] as double? ?? 0;
        _scroll.jumpTo(offset.clamp(0, _scroll.position.maxScrollExtent));
      }
    });
  }

  @override
  void didUpdateWidget(Chat oldWidget) {
    super.didUpdateWidget(oldWidget);
    final selected = widget.state.selectedVehicle?.id;
    final scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    if (_accountId != widget.state.accountId) {
      _accountId = widget.state.accountId;
      _conversations.clear();
      _conversationKey = '';
      _knowledgeScope = null;
      _contextData = null;
      _clear();
      _text.clear();
      _selectActiveScope();
    }
    if (selected != _vehicleId || scope != _scope) {
      if (_contextData?['kind'] == 'Maintenance item') _contextData = null;
      _vehicleId = selected;
      _scope = scope;
      _selectActiveScope();
    }
    if (widget.requestNumber != oldWidget.requestNumber) {
      _contextData = widget.contextData;
      _selectActiveScope();
      _topic = widget.topic;
      _text.text = widget.prompt ?? '';
    }
  }

  @override
  void dispose() {
    _generation++;
    _text.dispose();
    _inputFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _clear() {
    _generation++;
    _messages.clear();
    _history.clear();
    _pending = false;
    _error = null;
    _failedRequest = null;
    _topic = null;
    _sessionId = null;
    _sessionToken = null;
  }

  void _prepareForMechanic() {
    final repository = widget.repository;
    if (_pending || repository is! FastApiChatRepository) return;
    final userMessages = _messages.where((message) => message.isUser).toList();
    var initialQuestion = _text.text.trim();
    if (initialQuestion.isEmpty && userMessages.isNotEmpty) {
      initialQuestion = userMessages.last.text;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MechanicPreparationPage(
          state: widget.state,
          repository: repository,
          initialQuestion: initialQuestion,
          sessionId: _sessionId,
          sessionToken: _sessionToken,
        ),
      ),
    );
  }

  void _scrollDown() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (mounted && _scroll.hasClients) {
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: MediaQuery.disableAnimationsOf(context)
            ? Duration.zero
            : const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    }
  });

  Future<void> _send([ChatRequest? retry]) async {
    if (_pending) return;
    if (!widget.state.signedIn) return;
    if (_failedRequest != null && retry == null) {
      setState(
        () => _error =
            'Retry the failed question or start a new conversation before sending another question.',
      );
      return;
    }
    if (_knowledgeScope == null) {
      setState(
        () => _error =
            'Choose an available vehicle manual or published category in Conversation settings.',
      );
      return;
    }
    final text = _text.text.trim();
    if (retry == null && text.isEmpty) return;
    final limit = widget.repository is FastApiChatRepository
        ? (widget.repository as FastApiChatRepository).api.maxMessageLength
        : 4000;
    if ((retry?.message ?? text).length > limit) {
      setState(() => _error = 'Keep your question within $limit characters.');
      return;
    }
    final request =
        retry ??
        ChatRequest(
          message: text,
          vehicle: widget.state.selectedVehicle,
          topic: _topic,
          context: _contextData,
          history: List.of(_history),
          scopeType: _knowledgeScope?['scope_type'] as String?,
          scopeId: _knowledgeScope?['scope_id'] as String?,
          sessionId: _sessionId,
          sessionToken: _sessionToken,
        );
    if (request.backendMessage.length > limit) {
      setState(
        () => _error =
            'The question and context exceed $limit characters. Shorten your question or start a chat without topic context.',
      );
      return;
    }
    final generation = _generation;
    setState(() {
      if (retry == null) {
        _messages.add(ChatMessage(text: text, isUser: true));
        _text.clear();
      }
      _pending = true;
      _error = null;
      _failedRequest = null;
    });
    _scrollDown();
    // Lay out the submitted question before a fast reply can replace the
    // loading row. Otherwise scrolling may jump to the end of a long answer.
    await WidgetsBinding.instance.endOfFrame;
    if (!mounted || generation != _generation) return;
    try {
      final reply = await widget.repository.send(request);
      if (!mounted || generation != _generation) return;
      setState(() {
        _sessionId = reply.sessionId;
        _sessionToken = reply.sessionToken;
        final answer = ChatMessage(
          text: reply.text,
          isUser: false,
          reply: reply,
        );
        _messages.add(answer);
        _history.addAll([
          ChatMessage(text: request.message, isUser: true),
          answer,
        ]);
      });
      // Keep the beginning of a long answer in view. Do not interrupt someone
      // who scrolled back to read an earlier message while waiting.
    } catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is ApiException && error.statusCode == 503
            ? 'The AI service is temporarily unavailable. Your question is kept here; try again shortly.'
            : error is ApiException && [401, 403].contains(error.statusCode)
            ? 'Your account or source access has changed. Sign in again or choose an available source. Your question is kept here.'
            : 'The answer could not be loaded. Check your connection and try again. Your question is kept here.';
        _failedRequest = request;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _pending = false);
      }
    }
  }

  Future<void> _settings() async {
    FocusManager.instance.primaryFocus?.unfocus();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) => FractionallySizedBox(
        heightFactor: 0.9,
        child: StatefulBuilder(
          builder: (context, updateSheet) => ListenableBuilder(
            listenable: widget.state,
            builder: (context, _) => Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 8, 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Conversation settings',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Close conversation settings',
                        onPressed: () => Navigator.pop(sheetContext),
                        icon: const Icon(Icons.close),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.only(bottom: 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        VehicleSelector(state: widget.state),
                        const Padding(
                          padding: EdgeInsets.fromLTRB(20, 8, 20, 16),
                          child: Text(
                            'Your active vehicle supplies saved vehicle details. Choose published material for the assistant to use below.',
                          ),
                        ),
                        if (_scopesLoading)
                          const LinearProgressIndicator(
                            semanticsLabel: 'Loading knowledge sources',
                          ),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 20),
                          child: DropdownButtonFormField<String>(
                            initialValue: _knowledgeScope == null
                                ? null
                                : '${_knowledgeScope!['scope_type']}:${_knowledgeScope!['scope_id']}',
                            key: ValueKey(
                              '${_knowledgeScope?['scope_type']}:${_knowledgeScope?['scope_id']}',
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Knowledge source',
                            ),
                            items: _knowledgeScopes
                                .where(
                                  (s) =>
                                      s['scope_type'] == 'category' ||
                                      s['scope_id'] ==
                                          widget
                                              .state
                                              .selectedVehicle
                                              ?.knowledgeScopeId,
                                )
                                .map(
                                  (s) => DropdownMenuItem<String>(
                                    value:
                                        '${s['scope_type']}:${s['scope_id']}',
                                    enabled: s['available'] == true,
                                    child: Text(
                                      '${s['label']}${s['available'] == true ? '' : ' (unavailable)'}',
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(),
                            isExpanded: true,
                            onChanged: _pending
                                ? null
                                : (value) {
                                    setState(
                                      () => _switchScope(
                                        _knowledgeScopes.firstWhere(
                                          (s) =>
                                              '${s['scope_type']}:${s['scope_id']}' ==
                                              value,
                                        ),
                                      ),
                                    );
                                    updateSheet(() {});
                                  },
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                          child: Text(
                            _knowledgeScope == null
                                ? 'No source selected. Choose an available vehicle manual or published category to ask a question.'
                                : 'Each source has its own conversation. Switching back restores its messages during this visit.',
                          ),
                        ),
                        if (_scopeError != null)
                          Padding(
                            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                            child: Text(
                              _scopeError!,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                          ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: _pending || _scopesLoading
                                ? null
                                : () async {
                                    final future = _loadScopes();
                                    updateSheet(() {});
                                    await future;
                                    if (sheetContext.mounted) {
                                      updateSheet(() {});
                                    }
                                  },
                            icon: const Icon(Icons.refresh),
                            label: const Text('Refresh knowledge sources'),
                          ),
                        ),
                        if (_topic != null)
                          Padding(
                            padding: const EdgeInsets.all(20),
                            child: Text('Topic: $_topic'),
                          ),
                        const Padding(
                          padding: EdgeInsets.fromLTRB(20, 12, 20, 0),
                          child: Text(aiReferenceNotice),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _newConversation() async {
    if (_pending) return;
    if (_messages.isNotEmpty) {
      final start = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Start a new conversation?'),
          content: const Text(
            'This clears the messages for the current source. Other conversations are kept during this visit.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep conversation'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Start new'),
            ),
          ],
        ),
      );
      if (start != true || !mounted) return;
    }
    setState(() {
      _conversations.remove(_conversationKey);
      _conversationKey = '';
      _clear();
      _text.clear();
      _contextData = null;
      _selectActiveScope();
    });
    _scrollDown();
  }

  Widget _introduction() => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'A car question? Start here.',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const Text(
          'Describe what you noticed, or ask about a word in your manual. Everyday language is fine.',
        ),
        const SizedBox(height: 20),
        Text(aiReferenceNotice, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 24),
        if (_starterQuestions.isNotEmpty)
          Text(
            'Try a question',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        if (_starterQuestions.isNotEmpty) const SizedBox(height: 8),
        for (final prompt in _starterQuestions)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _pending
                  ? null
                  : () {
                      _text.text = prompt;
                      _inputFocus.requestFocus();
                    },
              icon: const Icon(Icons.north_west, size: 18),
              label: Text(prompt),
            ),
          ),
      ],
    ),
  );

  Widget _feedback() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (_scopeError != null || (!_scopesLoading && _knowledgeScope == null))
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_scopeError ?? 'Choose a published source before sending.'),
              TextButton(
                onPressed: _settings,
                child: const Text('Choose source'),
              ),
            ],
          ),
        ),
      if (_pending)
        Semantics(
          liveRegion: true,
          child: const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Row(
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Looking through your selected sources…\nSome answers take a little longer.',
                  ),
                ),
              ],
            ),
          ),
        ),
      if (_error != null)
        Semantics(
          liveRegion: true,
          child: Container(
            margin: const EdgeInsets.symmetric(vertical: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
                if (_failedRequest != null)
                  TextButton.icon(
                    onPressed: _pending ? null : () => _send(_failedRequest),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry reply'),
                  ),
              ],
            ),
          ),
        ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final signedIn = widget.state.signedIn;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ask AI'),
        actions: [
          if (signedIn && widget.repository is FastApiChatRepository)
            IconButton(
              tooltip: 'Prepare questions for a mechanic',
              onPressed: _pending ? null : _prepareForMechanic,
              icon: const Icon(Icons.question_answer_outlined),
            ),
          if (signedIn)
            IconButton(
              tooltip: 'Clear conversation',
              onPressed: _pending ? null : _newConversation,
              icon: const Icon(Icons.edit_square),
            ),
        ],
      ),
      body: !signedIn
          ? const SignInPrompt(
              icon: Icons.chat_bubble_outline,
              title: 'Make sense of your car questions',
              message:
                  'Sign in to use the AI Assistant. Learning and emergency guidance work independently.',
            )
          : SafeArea(
              top: false,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: LayoutBuilder(
                    builder: (context, constraints) => Column(
                      children: [
                        Material(
                          color: theme.colorScheme.surface,
                          child: ListTile(
                            dense: true,
                            leading: const Icon(Icons.tune),
                            title: const Text('Conversation settings'),
                            subtitle: constraints.maxHeight < 500
                                ? null
                                : Text(
                                    _scopesLoading
                                        ? 'Loading sources…'
                                        : _topic ??
                                              _knowledgeScope?['label']
                                                  as String? ??
                                              'Choose a source to get started',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: _settings,
                          ),
                        ),
                        Expanded(
                          child: Stack(
                            children: [
                              ListView.builder(
                                controller: _scroll,
                                keyboardDismissBehavior:
                                    ScrollViewKeyboardDismissBehavior.onDrag,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 20,
                                  vertical: 8,
                                ),
                                itemCount: _messages.isEmpty
                                    ? 2
                                    : _messages.length + 1,
                                itemBuilder: (context, index) {
                                  if (_messages.isEmpty) {
                                    return index == 0
                                        ? _feedback()
                                        : _introduction();
                                  }
                                  if (index == _messages.length) {
                                    return _feedback();
                                  }
                                  return ChatMessageView(
                                    key: ValueKey('$_conversationKey:$index'),
                                    message: _messages[index],
                                    repository: widget.repository,
                                    onEmergency: widget.onEmergency,
                                  );
                                },
                              ),
                              if (_showLatest)
                                Positioned(
                                  bottom: 8,
                                  left: 0,
                                  right: 0,
                                  child: Center(
                                    child: FilledButton.tonalIcon(
                                      onPressed: _scrollDown,
                                      icon: const Icon(
                                        Icons.arrow_downward,
                                        size: 18,
                                      ),
                                      label: const Text('Latest messages'),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        Material(
                          color: theme.colorScheme.surface,
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: _text,
                                    focusNode: _inputFocus,
                                    minLines: 1,
                                    maxLines: constraints.maxHeight < 500
                                        ? 2
                                        : 4,
                                    textCapitalization:
                                        TextCapitalization.sentences,
                                    textInputAction: TextInputAction.send,
                                    onSubmitted: (_) => _send(),
                                    decoration: const InputDecoration(
                                      labelText: 'Your question',
                                      hintText: 'Ask a question',
                                      hintMaxLines: 1,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                ValueListenableBuilder<TextEditingValue>(
                                  valueListenable: _text,
                                  builder: (context, value, _) =>
                                      IconButton.filled(
                                        constraints: const BoxConstraints(
                                          minWidth: 48,
                                          minHeight: 48,
                                        ),
                                        tooltip: 'Send question',
                                        onPressed:
                                            _pending ||
                                                _knowledgeScope == null ||
                                                _failedRequest != null ||
                                                value.text.trim().isEmpty
                                            ? null
                                            : () => _send(),
                                        icon: const Icon(Icons.arrow_upward),
                                      ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
    );
  }
}

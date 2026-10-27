import 'package:flutter/material.dart';
import '../app_state.dart';
import '../data/chat_repository.dart';
import '../data/api_client.dart';
import '../data/content_repository.dart';
import '../models/chat_message.dart';
import 'mechanic_preparation.dart';
import 'vehicle_profile.dart';
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
  final VoidCallback? onMaintenance;
  const Chat({
    super.key,
    required this.state,
    required this.repository,
    this.requestNumber = 0,
    this.topic,
    this.prompt,
    this.contextData,
    this.onEmergency,
    this.onMaintenance,
  });
  @override
  State<Chat> createState() => _ChatState();
}

class _ChatState extends State<Chat> {
  final _text = TextEditingController();
  final _scroll = ScrollController();
  final _inputFocus = FocusNode();
  final List<ChatMessage> _messages = [];
  String? _vehicleId;
  String? _topic;
  String? _error;
  ChatRequest? _failedRequest;
  ChatRequest? _inFlightRequest;
  bool _pending = false;
  int _generation = 0;
  String? _sessionId;
  String? _sessionToken;
  String? _accountId;
  Map<String, dynamic>? _contextData;
  final Map<String, Map<String, dynamic>> _conversations = {};
  String _conversationKey = '';
  bool _showLatest = false;
  List<String> _starterQuestions = [];

  @override
  void initState() {
    super.initState();
    _vehicleId = widget.state.selectedVehicle?.id;
    _accountId = widget.state.accountId;
    _contextData = widget.contextData;
    _scroll.addListener(_scrollChanged);
    _switchConversation();
    _topic = widget.topic;
    _text.text = widget.prompt ?? '';
    _loadStarterQuestions();
  }

  void _scrollChanged() {
    if (!_scroll.hasClients) return;
    final show = _scroll.position.extentAfter > 240;
    if (show != _showLatest) setState(() => _showLatest = show);
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
      // A corrupt local preference must not block chat.
    }
    if (content.api == null) return;
    try {
      final current = await content.chatStarters(refresh: true);
      if (mounted) setState(() => _starterQuestions = current);
    } catch (_) {
      // Keep the last synced list, including an intentionally empty list.
    }
  }

  void _switchConversation() {
    final key = '${widget.state.accountId}:${widget.state.selectedVehicle?.id}';
    if (key == _conversationKey) return;
    if (_pending) {
      _generation++;
      _pending = false;
      _failedRequest = _inFlightRequest;
      _error =
          'The vehicle changed before this reply arrived. Retry your question to continue.';
    }
    if (_conversationKey.isNotEmpty) {
      _conversations[_conversationKey] = {
        'messages': List<ChatMessage>.of(_messages),
        'sessionId': _sessionId,
        'sessionToken': _sessionToken,
        'draft': _text.text,
        'error': _error,
        'failedRequest': _failedRequest,
        'offset': _scroll.hasClients ? _scroll.offset : 0.0,
        'topic': _topic,
      };
    }
    _clear();
    _conversationKey = key;
    _topic = _contextData?['title'] as String?;
    _text.clear();
    final saved = _conversations[key];
    if (saved != null) {
      _messages.addAll(saved['messages'] as List<ChatMessage>);
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
    if (_accountId != widget.state.accountId) {
      _accountId = widget.state.accountId;
      _conversations.clear();
      _conversationKey = '';
      _contextData = null;
      _clear();
      _text.clear();
      _switchConversation();
    }
    if (selected != _vehicleId) {
      _contextData = null;
      _vehicleId = selected;
      _switchConversation();
    }
    if (widget.requestNumber != oldWidget.requestNumber) {
      _contextData = widget.contextData;
      _switchConversation();
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
    _pending = false;
    _error = null;
    _failedRequest = null;
    _inFlightRequest = null;
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
          context: _contextData,
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
      _inFlightRequest = request;
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
        // A lesson/item link supplies context for its initial question only.
        // Later questions resolve their topic from the conversation itself.
        _contextData = null;
        final answer = ChatMessage(
          text: reply.text,
          isUser: false,
          reply: reply,
        );
        _messages.add(answer);
      });
      // Keep the beginning of a long answer in view. Do not interrupt someone
      // who scrolled back to read an earlier message while waiting.
    } catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is ApiException && error.statusCode == 503
            ? 'The AI service is temporarily unavailable. Your question is kept here; try again shortly.'
            : error is ApiException && [401, 403].contains(error.statusCode)
            ? 'Your account access has changed. Sign in again to continue. Your question is kept here.'
            : 'The answer could not be loaded. Check your connection and try again. Your question is kept here.';
        _failedRequest = request;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() {
          _pending = false;
          _inFlightRequest = null;
        });
      }
    }
  }

  Future<void> _chooseVehicle() async {
    FocusManager.instance.primaryFocus?.unfocus();
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: SingleChildScrollView(
          child: ListenableBuilder(
            listenable: widget.state,
            builder: (context, _) => Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Your vehicle',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                VehicleSelector(state: widget.state),
                const SizedBox(height: 12),
                const Text(
                  'Questions use the selected vehicle details and maintenance. Each vehicle keeps a separate conversation during this visit.',
                ),
                if (widget.state.vehicles.isEmpty) ...[
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      Navigator.push(
                        this.context,
                        MaterialPageRoute(
                          builder: (_) =>
                              VehicleProfilePage(state: widget.state),
                        ),
                      );
                    },
                    icon: const Icon(Icons.add),
                    label: const Text('Add vehicle'),
                  ),
                ],
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Done'),
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
            'This clears the current conversation. Conversations for other vehicles are kept during this visit.',
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
      _switchConversation();
    });
    _scrollDown();
  }

  List<String> _suggestions() {
    final vehicle = widget.state.selectedVehicle;
    final suggestions = <String>[];
    if (vehicle != null && widget.state.tasksFor(vehicle.id).isNotEmpty) {
      suggestions.add('What maintenance is due?');
    } else if (vehicle != null &&
        widget.state.recordsFor(vehicle.id).isNotEmpty) {
      suggestions.add('Summarise my recent services.');
    }
    for (final prompt in _starterQuestions) {
      final value = prompt.trim();
      if (value.isNotEmpty &&
          value.length <= 100 &&
          !suggestions.any((s) => s.toLowerCase() == value.toLowerCase())) {
        suggestions.add(value);
      }
      if (suggestions.length == 3) break;
    }
    return suggestions;
  }

  Widget _introduction() => Padding(
    padding: const EdgeInsets.only(top: 32, bottom: 24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'What’s on your mind?',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const Text(
          'A warning light, a service record, a word in your manual. Ask in your own words.',
        ),
        const SizedBox(height: 24),
        for (final prompt in _suggestions())
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 4,
                  vertical: 12,
                ),
                alignment: Alignment.centerLeft,
              ),
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
        const SizedBox(height: 24),
        Text(
          'AI guidance can be incomplete. Confirm repairs and specifications with a qualified mechanic.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    ),
  );

  Widget _feedback() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
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
                Expanded(child: Text('Checking your sources…')),
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
      backgroundColor: theme.colorScheme.surface,
      appBar: AppBar(
        backgroundColor: theme.colorScheme.surface,
        title: const Text('Assistant'),
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
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 20,
                            ),
                            leading: Icon(
                              Icons.directions_car_outlined,
                              color: theme.colorScheme.primary,
                            ),
                            title: Text(
                              widget.state.selectedVehicle?.name ??
                                  'General car questions',
                              style: theme.textTheme.titleSmall,
                            ),
                            subtitle: constraints.maxHeight < 500
                                ? null
                                : Text(
                                    widget.state.selectedVehicle == null
                                        ? 'Add a vehicle for personalised help'
                                        : widget
                                              .state
                                              .selectedVehicle!
                                              .plateNumber
                                              .isEmpty
                                        ? 'Saved details and relevant references'
                                        : '${widget.state.selectedVehicle!.plateNumber} · Change vehicle',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                            trailing: const Icon(Icons.expand_more, size: 20),
                            onTap: _pending ? null : _chooseVehicle,
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
                                  final message = _messages[index];
                                  final hasCurrentMaintenance =
                                      message.reply?.sources.any(
                                        (source) =>
                                            source['source_type'] ==
                                                'personal_maintenance' &&
                                            source['vehicle_id'] ==
                                                widget
                                                    .state
                                                    .selectedVehicle
                                                    ?.id,
                                      ) ??
                                      false;
                                  return ChatMessageView(
                                    key: ValueKey('$_conversationKey:$index'),
                                    message: message,
                                    repository: widget.repository,
                                    onEmergency: widget.onEmergency,
                                    onMaintenance: hasCurrentMaintenance
                                        ? widget.onMaintenance
                                        : null,
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
                                      hintText: 'Ask about your car…',
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

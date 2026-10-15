import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../app_state.dart';
import '../data/chat_repository.dart';
import '../data/api_client.dart';
import '../models/chat_message.dart';
import '../widgets/vehicle_selector.dart';
import '../widgets/chat_attachment.dart';

class Chat extends StatefulWidget {
  final AppState state;
  final ChatRepository repository;
  final int requestNumber;
  final String? topic;
  final String? prompt;
  final Map<String, dynamic>? contextData;
  const Chat({
    super.key,
    required this.state,
    required this.repository,
    this.requestNumber = 0,
    this.topic,
    this.prompt,
    this.contextData,
  });
  @override
  State<Chat> createState() => _ChatState();
}

class _ChatState extends State<Chat> {
  final _text = TextEditingController();
  final _scroll = ScrollController();
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

  @override
  void initState() {
    super.initState();
    _vehicleId = widget.state.selectedVehicle?.id;
    _scope = widget.state.selectedVehicle?.effectiveScope ?? 'general';
    _accountId = widget.state.accountId;
    _contextData = widget.contextData;
    _loadScopes();
  }

  Future<void> _loadScopes() async {
    if (widget.repository is! FastApiChatRepository) return;
    setState(() => _scopesLoading = true);
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
            _clear();
          }
        }
        if (_sessionId == null) _selectActiveScope();
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _scopesLoading = false);
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
      };
    }
    final key =
        '${widget.state.accountId}:${widget.state.selectedVehicle?.id}:${scope?['scope_type']}:${scope?['scope_id']}:${_contextData?['kind']}:${_contextData?['id']}';
    _clear();
    _knowledgeScope = scope;
    _conversationKey = key;
    _topic = _contextData?['title'] as String?;
    final saved = _conversations[key];
    if (saved != null) {
      _messages.addAll(saved['messages'] as List<ChatMessage>);
      _history.addAll(saved['history'] as List<ChatMessage>);
      _sessionId = saved['sessionId'] as String?;
      _sessionToken = saved['sessionToken'] as String?;
    }
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
      _text.clear();
    }
    if (widget.requestNumber != oldWidget.requestNumber) {
      _topic = widget.topic;
      _contextData = widget.contextData;
      _selectActiveScope();
      _text.text = widget.prompt ?? '';
    }
  }

  @override
  void dispose() {
    _generation++;
    _text.dispose();
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

  void _scrollDown() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (mounted && _scroll.hasClients) {
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
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
        () =>
            _error = 'Select an available vehicle or category knowledge scope.',
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
      _scrollDown();
    } catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is ApiException && error.statusCode == 503
            ? 'The AI service is temporarily unavailable. Your question is kept below; retry when the service is available.'
            : error.toString();
        _failedRequest = request;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _pending = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Ask AI'),
      backgroundColor: Theme.of(context).colorScheme.primaryContainer,
      actions: [
        IconButton(
          tooltip: 'Clear conversation',
          icon: const Icon(Icons.clear_all),
          onPressed: _pending
              ? null
              : () => setState(() {
                  _conversations.remove(_conversationKey);
                  _clear();
                  _contextData = null;
                  _selectActiveScope();
                }),
        ),
      ],
    ),
    body: !widget.state.signedIn
        ? const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Sign in to use the AI Assistant. Learning and emergency guidance work independently.',
              ),
            ),
          )
        : SafeArea(
            child: Column(
              children: [
                VehicleSelector(state: widget.state),
                if (_scopesLoading) const LinearProgressIndicator(),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          initialValue: _knowledgeScope == null
                              ? null
                              : '${_knowledgeScope!['scope_type']}:${_knowledgeScope!['scope_id']}',
                          key: ValueKey(_knowledgeScope?['scope_id']),
                          decoration: const InputDecoration(
                            labelText: 'Knowledge scope',
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
                                  value: '${s['scope_type']}:${s['scope_id']}',
                                  enabled: s['available'] == true,
                                  child: Text(
                                    '${s['label']}${s['available'] == true ? '' : ' (empty)'}',
                                  ),
                                ),
                              )
                              .toList(),
                          isExpanded: true,
                          onChanged: _pending
                              ? null
                              : (value) => setState(() {
                                  final scope = _knowledgeScopes.firstWhere(
                                    (s) =>
                                        '${s['scope_type']}:${s['scope_id']}' ==
                                        value,
                                  );
                                  _switchScope(scope);
                                }),
                        ),
                      ),
                      IconButton(
                        onPressed: _pending || _scopesLoading
                            ? null
                            : _loadScopes,
                        icon: const Icon(Icons.refresh),
                        tooltip: 'Refresh knowledge scopes',
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 4,
                  ),
                  child: Text(
                    'Knowledge: ${_knowledgeScope?['label'] ?? 'No indexed sources for this vehicle. Select a published category to ask a general question.'}. Each conversation keeps its original scope.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                if (_topic != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text('Topic: $_topic'),
                  ),
                Expanded(
                  child: ListView(
                    controller: _scroll,
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_messages.isEmpty)
                        const Text(
                          'Ask a car question or choose a suggestion below.',
                        ),
                      ..._messages.map(
                        (message) => Align(
                          alignment: message.isUser
                              ? Alignment.centerRight
                              : Alignment.centerLeft,
                          child: Container(
                            constraints: BoxConstraints(
                              maxWidth: MediaQuery.sizeOf(context).width * 0.8,
                            ),
                            margin: const EdgeInsets.symmetric(vertical: 6),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(16),
                              color: message.isUser
                                  ? Theme.of(
                                      context,
                                    ).colorScheme.primaryContainer
                                  : Theme.of(
                                      context,
                                    ).colorScheme.surfaceContainerHigh,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SelectableText(message.text),
                                if (widget.repository is FastApiChatRepository)
                                  for (final attachment
                                      in message.reply?.attachments ??
                                          <Map<String, dynamic>>[])
                                    ChatAttachment(
                                      key: ValueKey(
                                        '${attachment['document_id']}:${attachment['source_revision']}:${attachment['element_id']}',
                                      ),
                                      attachment: attachment,
                                      api:
                                          (widget.repository
                                                  as FastApiChatRepository)
                                              .api,
                                      token:
                                          (widget.repository
                                                  as FastApiChatRepository)
                                              .account
                                              ?.token,
                                    ),
                                if (message.reply?.externalWarning == true)
                                  const Text(
                                    'This answer includes information outside the available manuals.',
                                  ),
                                if (message.reply?.manualRelevant == true)
                                  const Text(
                                    'Relevant manual information was found.',
                                  ),
                                if ([
                                  'generation_error',
                                  'retrieval_error',
                                ].contains(message.reply?.responseType))
                                  const Text(
                                    'The AI service could not complete this answer. Try again shortly.',
                                  ),
                                for (final source
                                    in message.reply?.sources ??
                                        <Map<String, dynamic>>[])
                                  SelectableText(
                                    '${source['label'] ?? 'Source'}: ${source['document_title'] ?? source['document_id'] ?? 'Reference'}${source['page'] == null ? '' : ', page ${source['page']}'}${source['chunk_id'] == null ? '' : '\nReference: ${source['chunk_id']}'}',
                                  ),
                                for (final video
                                    in message.reply?.videos ??
                                        <Map<String, dynamic>>[])
                                  TextButton(
                                    onPressed: () async {
                                      final uri = Uri.tryParse(
                                        video['url'] as String? ?? '',
                                      );
                                      if (uri == null ||
                                          ![
                                            'https',
                                            'http',
                                          ].contains(uri.scheme)) {
                                        return;
                                      }
                                      final stamp =
                                          (video['timestamp'] as num? ?? 0)
                                              .toInt();
                                      try {
                                        if (!await launchUrl(
                                          uri.replace(
                                            queryParameters: {
                                              ...uri.queryParameters,
                                              't': '${stamp}s',
                                            },
                                          ),
                                          mode: LaunchMode.externalApplication,
                                        )) {
                                          throw StateError('No video handler');
                                        }
                                      } catch (_) {
                                        if (context.mounted) {
                                          ScaffoldMessenger.of(
                                            context,
                                          ).showSnackBar(
                                            const SnackBar(
                                              content: Text(
                                                'Could not open the video link.',
                                              ),
                                            ),
                                          );
                                        }
                                      }
                                    },
                                    child: Text(
                                      video['title'] as String? ?? 'Open video',
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      if (_pending)
                        const Padding(
                          padding: EdgeInsets.all(12),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              ),
                              SizedBox(width: 12),
                              Expanded(child: Text('Waiting for a reply...')),
                            ],
                          ),
                        ),
                      if (_error != null)
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _error!,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                            TextButton(
                              onPressed: _pending
                                  ? null
                                  : () => _send(_failedRequest),
                              child: const Text('Retry reply'),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
                SizedBox(
                  height: 56,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    children:
                        [
                              'Understanding my service records',
                              'Finding the correct owner manual',
                              'Understanding tyre pressure labels',
                            ]
                            .map(
                              (topic) => Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 4,
                                ),
                                child: ActionChip(
                                  label: Text(topic),
                                  onPressed: _pending
                                      ? null
                                      : () {
                                          _text.text = topic;
                                        },
                                ),
                              ),
                            )
                            .toList(),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _text,
                          minLines: 1,
                          maxLines: 3,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => _send(),
                          decoration: const InputDecoration(
                            labelText: 'Your question',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Send question',
                        onPressed: _pending || _knowledgeScope == null
                            ? null
                            : () => _send(),
                        icon: const Icon(Icons.send),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
  );
}

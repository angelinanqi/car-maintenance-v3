import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../app_theme.dart';
import '../widgets/design_widgets.dart';
import '../app_state.dart';
import '../data/chat_repository.dart';
import '../data/api_client.dart';
import '../data/learning_errors.dart';
import '../data/content_repository.dart';
import '../models/chat_message.dart';
import 'mechanic_preparation.dart';
import 'vehicle_profile.dart';
import '../widgets/vehicle_selector.dart';
import '../widgets/sign_in_prompt.dart';
import '../widgets/chat_message_view.dart';
import '../data/companion_repository.dart';
import '../models/companion.dart';
import '../models/content.dart';
import '../widgets/learning_activity.dart';
import '../widgets/service_plan_view.dart';
import '../widgets/guide_content.dart';
import 'saved_items.dart';
import 'service_forms.dart';
import 'dart:convert';
import 'package:uuid/uuid.dart';

class Chat extends StatefulWidget {
  final AppState state;
  final ChatRepository repository;
  final CompanionRepository? companion;
  final int requestNumber;
  final String? topic;
  final String? prompt;
  final Map<String, dynamic>? contextData;
  final VoidCallback? onEmergency;
  final VoidCallback? onMaintenance;
  final VoidCallback? onLearn;
  const Chat({
    super.key,
    required this.state,
    required this.repository,
    this.companion,
    this.requestNumber = 0,
    this.topic,
    this.prompt,
    this.contextData,
    this.onEmergency,
    this.onMaintenance,
    this.onLearn,
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
  late final String _conversationChannel;
  String _conversationKey = '';
  bool _showLatest = false;
  List<String> _starterQuestions = [];
  Map<String, dynamic>? _discovery;
  Lesson? _lesson;
  ServicePlan? _plan;
  int _step = 0;
  bool _showActivity = false, _toolBusy = false;
  bool _home = true;
  String? _toolError;
  int _activityGeneration = 0;
  String? _savedExplanationId;
  bool _restoring = false;
  bool _restoreFailed = false;
  final Map<String, Future<void>> _restoreRequests = {};
  final Map<String, int> _restoreGenerations = {};
  String get _sessionFile =>
      'chat_${base64Url.encode(utf8.encode(_conversationKey))}.json';
  CompanionRepository? get _companion =>
      widget.companion ??
      (widget.repository is FastApiChatRepository
          ? CompanionRepository(widget.repository as FastApiChatRepository)
          : null);
  Map<String, dynamic>? get _activity => _lesson != null
      ? _lesson!.activityAt(_step)
      : _plan?.id != null
      ? _plan!.activity
      : _contextData?['kind'] == 'guide_step'
      ? {
          'kind': 'guide',
          'guide_id': _contextData!['guide_id'],
          if (_contextData!['step_id'] != null)
            'step_id': _contextData!['step_id'],
          'revision': _contextData!['revision'],
        }
      : null;

  @override
  void initState() {
    super.initState();
    // Contextual guide windows must not rotate or replace the tab's session.
    _conversationChannel = widget.contextData?['kind'] == 'guide_step'
        ? 'guide:${widget.contextData?['guide_id']}:${widget.contextData?['step_id']}'
        : 'main';
    _vehicleId = widget.state.selectedVehicle?.id;
    _accountId = widget.state.accountId;
    _contextData = widget.contextData;
    _scroll.addListener(_scrollChanged);
    _switchConversation();
    _topic = widget.topic;
    _text.text = widget.prompt ?? '';
    _loadStarterQuestions();
    _loadCompanion();
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
    final key =
        '${widget.state.accountId}:${widget.state.selectedVehicle?.id}:$_conversationChannel';
    if (key == _conversationKey) return;
    if (_pending) {
      _generation++;
      _pending = false;
      _failedRequest = _inFlightRequest;
      _error =
          'The vehicle changed before this reply arrived. Retry your question to continue.';
    }
    if (_conversationKey.isNotEmpty && !_restoring && !_restoreFailed) {
      _conversations[_conversationKey] = {
        'messages': List<ChatMessage>.of(_messages),
        'sessionId': _sessionId,
        'sessionToken': _sessionToken,
        'draft': _text.text,
        'error': _error,
        'failedRequest': _failedRequest,
        'offset': _scroll.hasClients ? _scroll.offset : 0.0,
        'topic': _topic,
        'lesson': _lesson,
        'plan': _plan,
        'step': _step,
        'showActivity': _showActivity,
        'home': _home,
      };
    }
    if (_restoring || _restoreFailed) _conversations.remove(_conversationKey);
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
      _lesson = saved['lesson'] as Lesson?;
      _plan = saved['plan'] as ServicePlan?;
      _step = saved['step'] as int? ?? 0;
      _showActivity = saved['showActivity'] == true;
      _home = saved['home'] == true;
    } else {
      _restoreSession(key);
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
      _discovery = null;
      _loadCompanion();
    }
    if (selected != _vehicleId) {
      _contextData = null;
      _vehicleId = selected;
      _switchConversation();
      _loadCompanion();
    }
    if (widget.requestNumber != oldWidget.requestNumber) {
      _contextData = widget.contextData;
      _switchConversation();
      _topic = widget.topic;
      _text.text = widget.prompt ?? '';
      if (_contextData?['kind'] == 'explore_guide') {
        final id = _contextData!['guide_id'] as String;
        _contextData = null;
        _text.clear();
        _openGuide(id);
      } else if (_contextData?['kind'] == 'service_plan') {
        _contextData = null;
        _text.clear();
        _openPlan();
      }
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
    _savedExplanationId = null;
    _home = true;
    _lesson = null;
    _plan = null;
    _step = 0;
    _showActivity = false;
    _toolError = null;
    _toolBusy = false;
    _restoring = false;
    _restoreFailed = false;
  }

  Future<void> _loadCompanion() async {
    if (_companion == null || !widget.state.signedIn) return;
    final key = _conversationKey;
    try {
      final data = await _companion!.discovery();
      if (mounted && key == _conversationKey) setState(() => _discovery = data);
    } catch (error) {
      if (mounted && key == _conversationKey)
        setState(() => _toolError = error.toString());
    }
  }

  Future<void> _refreshLearningAfterSave() async {
    try {
      await widget.state.refreshLearning();
    } catch (error) {
      throw LearningRefreshFailure(error);
    }
  }

  Future<void> _refreshStartingPoints() async {
    await Future.wait([_loadStarterQuestions(), _loadCompanion()]);
  }

  Future<void> _rememberSession({bool clear = false}) async {
    final pending = _inFlightRequest ?? _failedRequest;
    final request = pending?.toJson();
    request?.remove('session_token');
    final userMessages = _messages.where((message) => message.isUser).toList();
    await widget.state.store.write(
      _sessionFile,
      clear
          ? {'cleared': true}
          : {
              'session_id': _sessionId,
              if (request != null) 'pending': request,
              if (request != null)
                'pending_text': userMessages.isNotEmpty
                    ? userMessages.last.text
                    : pending!.message,
            },
    );
  }

  Future<void> _restoreSession(
    String key, {
    String? sessionId,
    String? messageId,
  }) {
    final existing = _restoreRequests[key];
    if (existing != null) {
      if (_restoreGenerations[key] == _generation) return existing;
      final generation = _generation;
      _restoring = true;
      return existing.then((_) async {
        if (mounted && key == _conversationKey && generation == _generation) {
          await _restoreSession(
            key,
            sessionId: sessionId,
            messageId: messageId,
          );
        }
      });
    }
    _restoreGenerations[key] = _generation;
    final task =
        _restoreSessionData(
          key,
          sessionId: sessionId,
          messageId: messageId,
        ).whenComplete(() {
          _restoreRequests.remove(key);
          _restoreGenerations.remove(key);
        });
    _restoreRequests[key] = task;
    return task;
  }

  Future<void> _restoreSessionData(
    String key, {
    String? sessionId,
    String? messageId,
  }) async {
    if (_companion == null || !widget.state.signedIn) return;
    final generation = _generation;
    final activityGeneration = _activityGeneration;
    _restoring = true;
    _restoreFailed = false;
    try {
      final journal = await widget.state.store.read(_sessionFile);
      final saved = journal == null
          ? await widget.state.store.read('companion_sessions.json')
          : null;
      final legacyKey =
          '${widget.state.accountId}:${widget.state.selectedVehicle?.id}';
      String? legacyIdentity;
      if (_conversationChannel == 'main' && saved != null) {
        legacyIdentity = saved[legacyKey] as String?;
      }
      final identity =
          sessionId ?? (journal?['session_id'] as String?) ?? legacyIdentity;
      if (identity == null || !mounted || key != _conversationKey || _pending)
        return;
      final pending = sessionId == null && journal?['pending'] is Map
          ? Map<String, dynamic>.from(journal!['pending'] as Map)
          : null;
      Map<String, dynamic> data;
      var createSession = false;
      try {
        data = await _companion!.resume(identity, messageId: messageId);
      } on ApiException catch (error) {
        if (error.statusCode != 404 || pending == null) rethrow;
        // The app may have stopped after journalling but before creating the session.
        createSession = true;
        data = {
          'session_id': identity,
          'session_token': '${const Uuid().v4()}${const Uuid().v4()}',
          'messages': [],
        };
      }
      if (!mounted ||
          key != _conversationKey ||
          generation != _generation ||
          activityGeneration != _activityGeneration ||
          _pending)
        return;
      setState(() {
        _sessionId = data['session_id'] as String;
        _sessionToken = data['session_token'] as String;
        _messages.clear();
        _failedRequest = null;
        _error = null;
        _home = false;
        _savedExplanationId = messageId;
        for (final raw in data['messages'] as List) {
          final row = Map<String, dynamic>.from(raw as Map);
          _messages.add(
            ChatMessage(
              text: row['content'] as String,
              isUser: row['role'] == 'user',
              reply: row['reply'] == null
                  ? null
                  : ChatReply.fromJson(
                      Map<String, dynamic>.from(row['reply'] as Map),
                    ),
            ),
          );
        }
        if (pending != null &&
            !_messages.any(
              (message) => message.reply?.messageId == pending['request_id'],
            )) {
          _failedRequest = ChatRequest.restore(
            pending,
            _sessionToken!,
            createSession: createSession,
          );
          _messages.add(
            ChatMessage(
              text:
                  journal?['pending_text'] as String? ??
                  _failedRequest!.message,
              isUser: true,
            ),
          );
          _error =
              'Your last question was interrupted. Retry to recover its answer.';
        }
      });
      await _rememberSession();
      if (!mounted || key != _conversationKey || generation != _generation)
        return;
      setState(() => _restoring = false);
      final activity = data['activity'] as Map?;
      if (activity?['kind'] == 'guide') {
        await _openGuide(
          activity!['guide_id'] as String,
          stepId: activity['step_id'] as String?,
        );
      } else if (activity?['kind'] == 'plan') {
        await _openPlan(planId: activity!['plan_id'] as String);
      }
    } catch (error) {
      if (mounted && key == _conversationKey && generation == _generation) {
        setState(() {
          _restoreFailed = true;
          _toolError =
              'Could not restore the previous activity. ${error.toString()}';
        });
      }
    } finally {
      if (mounted && key == _conversationKey && generation == _generation) {
        setState(() => _restoring = false);
      }
    }
  }

  Future<void> _tool(Future<void> Function(String key) action) async {
    if (_toolBusy ||
        _pending ||
        _restoring ||
        _restoreFailed ||
        _companion == null)
      return;
    final key = _conversationKey;
    _activityGeneration++;
    setState(() {
      _toolBusy = true;
      _toolError = null;
    });
    try {
      await action(key);
    } catch (error) {
      if (mounted && key == _conversationKey)
        setState(() => _toolError = error.toString());
    } finally {
      if (mounted && key == _conversationKey) setState(() => _toolBusy = false);
    }
  }

  Future<void> _openGuide(String id, {String? stepId}) => _tool((key) async {
    final lesson = await _companion!.guide(id);
    if (!mounted || key != _conversationKey) return;
    final found = lesson.sections.indexWhere((section) => section.id == stepId);
    setState(() {
      _lesson = lesson;
      _plan = null;
      _step = found < 0 ? 0 : found;
      _showActivity = true;
      _home = false;
    });
    _scrollToStart();
    await _companion!.progress(lesson, _step);
    if (!mounted || key != _conversationKey) return;
    await _refreshLearningAfterSave();
    if (!mounted || key != _conversationKey) return;
    if (_sessionId != null) await _companion!.activity(_sessionId!, _activity);
  });

  Future<void> _openPlan({String? planId}) => _tool((key) async {
    final vehicle = widget.state.selectedVehicle;
    if (vehicle == null)
      throw const ApiException(
        'Add or select a vehicle to prepare its service plan.',
      );
    final plan = planId == null
        ? await _companion!.preview(vehicle.id)
        : await _companion!.plan(planId);
    if (!mounted || key != _conversationKey) return;
    setState(() {
      _plan = plan;
      _lesson = null;
      _showActivity = true;
      _home = false;
    });
    _scrollToStart();
  });

  Future<void> _savePlan({bool notes = false, bool ask = false}) =>
      _tool((key) async {
        var plan = _plan!;
        if (plan.id == null) plan = await _companion!.savePlan(plan);
        if (!mounted || key != _conversationKey) return;
        setState(() => _plan = plan);
        if (notes && widget.repository is FastApiChatRepository) {
          await Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => MechanicPreparationPage(
                state: widget.state,
                repository: widget.repository as FastApiChatRepository,
                planId: plan.id,
                initialNotes: plan.asNotes(),
                initialQuestion:
                    'Help me prepare questions about my saved service plan.',
              ),
            ),
          );
        } else if (ask) {
          setState(() => _showActivity = false);
          _inputFocus.requestFocus();
        } else {
          await _companion!.save({
            'kind': 'plan',
            'title': 'My next service',
            'plan_id': plan.id,
          });
          if (mounted && key == _conversationKey)
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(const SnackBar(content: Text('Plan saved')));
        }
      });

  Future<void> _saved() async {
    if (_companion == null || _pending || _toolBusy) return;
    if (_failedRequest != null || _restoring || _restoreFailed) {
      setState(
        () => _toolError =
            'Recover the current conversation or start a new one before opening Saved.',
      );
      return;
    }
    final key = _conversationKey;
    final item = await Navigator.push<Map<String, dynamic>>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            SavedItemsPage(repository: _companion!, state: widget.state),
      ),
    );
    if (!mounted || item == null || key != _conversationKey) return;
    final vehicleId = item['vehicle_id'] as String?;
    if (vehicleId != null && vehicleId != widget.state.selectedVehicle?.id) {
      setState(
        () => _toolError =
            'Select the vehicle associated with this saved item, then reopen it.',
      );
      return;
    }
    if (item['kind'] == 'guide') {
      await _openGuide(item['guide_id'] as String);
    } else if (item['kind'] == 'plan') {
      await _openPlan(planId: item['plan_id'] as String);
    } else if (item['kind'] == 'explanation') {
      await _restoreSession(
        key,
        sessionId: (item['payload'] as Map)['session_id'] as String,
        messageId: item['message_id'] as String,
      );
      if (mounted && key == _conversationKey) {
        setState(() {
          _showActivity = false;
          _lesson = null;
          _plan = null;
        });
        _scrollToStart();
      }
    }
  }

  Future<void> _addNote(ChatMessage message) async {
    final repository = _companion;
    if (repository == null || _toolBusy || _pending) return;
    final key = _conversationKey;
    final vehicleId = widget.state.selectedVehicle?.id;
    final id = const Uuid().v4();
    final saved = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => SavedNoteEditor(
        state: widget.state,
        title: 'Add note',
        text: '',
        onSave: (note) async {
          if (key != _conversationKey)
            throw const ApiException(
              'Your account or vehicle changed. Reopen these notes.',
            );
          await repository.save({
            'id': id,
            'kind': 'notes',
            'title': message.text.length > 80
                ? '${message.text.substring(0, 77)}…'
                : message.text,
            'vehicle_id': vehicleId,
            'text': note,
          });
        },
      ),
    );
    if (saved == true && mounted && key == _conversationKey)
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Note saved. Open Saved from conversation options.'),
        ),
      );
  }

  void _readGuide() {
    final lesson = _lesson!;
    Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: Text(lesson.title)),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.screen),
            child: GuideContent(content: lesson.content),
          ),
        ),
      ),
    );
  }

  Widget _activityView() {
    if (_lesson != null)
      return LearningActivity(
        lesson: _lesson!,
        index: _step,
        busy: _pending || _toolBusy,
        onStep: (index) => _tool((key) async {
          await _companion!.progress(_lesson!, index);
          if (!mounted || key != _conversationKey) return;
          setState(() => _step = index);
          await _refreshLearningAfterSave();
          if (!mounted || key != _conversationKey) return;
          _scrollToStart();
          if (_sessionId != null)
            await _companion!.activity(_sessionId!, _activity);
        }),
        onAsk: () {
          setState(() => _showActivity = false);
          _inputFocus.requestFocus();
        },
        onSimplify: () {
          _text.text = 'Please explain this section more simply.';
          _send(null, 'simplify');
        },
        onPlan: () => _openPlan(),
        onRead: _readGuide,
        onSave: () => _tool((key) async {
          await _companion!.save({
            'kind': 'guide',
            'title': _lesson!.title,
            'guide_id': _lesson!.id,
          });
          if (mounted && key == _conversationKey)
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(const SnackBar(content: Text('Guide saved')));
        }),
        onComplete: () => _tool((key) async {
          await _companion!.progress(_lesson!, _step, completed: true);
          if (!mounted || key != _conversationKey) return;
          await _refreshLearningAfterSave();
          await _loadCompanion();
          if (mounted && key == _conversationKey)
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Guide marked as completed')),
            );
        }),
        onRelated: (id) => _openGuide(id),
      );
    return ServicePlanView(
      plan: _plan!,
      busy: _pending || _toolBusy,
      onSave: () => _savePlan(),
      onRefresh: () => _openPlan(),
      onNotes: () => _savePlan(notes: true),
      onAsk: () => _savePlan(ask: true),
      onGuide: (id) => _openGuide(id),
      onRecord: (id) => _tool((key) async {
        await widget.state.refresh();
        if (!mounted || key != _conversationKey) return;
        final tasks = widget.state
            .tasksFor(_plan!.vehicleId)
            .where((task) => task.id == id);
        if (tasks.isEmpty)
          throw const ApiException(
            'Refresh maintenance before recording this item.',
          );
        await showDialog<bool>(
          context: context,
          builder: (_) => ServiceLogDialog(
            state: widget.state,
            vehicle: widget.state.selectedVehicle!,
            task: tasks.first,
          ),
        );
        if (!mounted || key != _conversationKey) return;
        final refreshed = await _companion!.preview(_plan!.vehicleId);
        if (mounted && key == _conversationKey)
          setState(() => _plan = refreshed);
      }),
    );
  }

  void _prepareForMechanic() {
    final repository = widget.repository;
    if (_pending ||
        _restoring ||
        _restoreFailed ||
        _toolBusy ||
        repository is! FastApiChatRepository)
      return;
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

  void _scrollToStart() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (mounted && _scroll.hasClients) _scroll.jumpTo(0);
  });

  Future<void> _send([ChatRequest? retry, String? assistance]) async {
    if (_pending || _restoring || _restoreFailed || _toolBusy) return;
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
    final createSession = _sessionId == null;
    final sessionId = _sessionId ?? const Uuid().v4();
    final sessionToken =
        _sessionToken ?? '${const Uuid().v4()}${const Uuid().v4()}';
    final request =
        retry ??
        ChatRequest(
          requestId: const Uuid().v4(),
          createSession: createSession,
          message: text,
          vehicle: widget.state.selectedVehicle,
          context: _contextData,
          sessionId: sessionId,
          sessionToken: sessionToken,
          activity: _activity,
          assistance: assistance,
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
      _sessionId = request.sessionId;
      _sessionToken = request.sessionToken;
      if (retry == null) {
        _messages.add(ChatMessage(text: text, isUser: true));
        _text.clear();
      }
      _pending = true;
      _inFlightRequest = request;
      _error = null;
      _failedRequest = null;
      _showActivity = false;
      _home = false;
      _savedExplanationId = null;
    });
    _scrollDown();
    // Lay out the submitted question before a fast reply can replace the
    // loading row. Otherwise scrolling may jump to the end of a long answer.
    await WidgetsBinding.instance.endOfFrame;
    if (!mounted || generation != _generation) return;
    try {
      // Keep the original operation identity across a restart or lost response.
      await _rememberSession();
      if (!mounted || generation != _generation) return;
      final reply = await widget.repository.send(request);
      if (!mounted || generation != _generation) return;
      setState(() {
        _sessionId = reply.sessionId;
        _sessionToken = reply.sessionToken;
        if (reply.activityNotice != null) _toolError = reply.activityNotice;
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
      try {
        _inFlightRequest = null;
        await _rememberSession();
      } catch (_) {
        if (mounted && generation == _generation)
          setState(
            () => _toolError =
                'Your answer is saved online, but this device could not update its recovery file. Reopening will recover the saved turn.',
          );
      }
      // Keep the beginning of a long answer in view. Do not interrupt someone
      // who scrolled back to read an earlier message while waiting.
    } catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is ApiException && error.statusCode == 503
            ? 'The AI service is temporarily unavailable. Your question is kept here; try again shortly.'
            : error is ApiException && [401, 403].contains(error.statusCode)
            ? 'Your account access has changed. Sign in again to continue. Your question is kept here.'
            : error is ApiException && error.statusCode == 409
            ? error.message
            : 'The answer could not be loaded. Check your connection and try again. Your question is kept here.';
        _failedRequest = request;
        if (error is ApiException &&
            error.statusCode == 403 &&
            error.message.contains('chat session is not accessible')) {
          _restoreFailed = true;
          _toolError =
              'Restore this conversation to refresh its access before retrying your question.';
        }
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
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.screen,
          0,
          AppSpacing.screen,
          24,
        ),
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
    if (_pending || _toolBusy || _restoring) return;
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
    try {
      await _rememberSession(clear: true);
    } catch (_) {
      if (mounted)
        setState(
          () => _toolError =
              'Could not reset the saved session on this device. Retry before starting a new conversation.',
        );
      return;
    }
    if (!mounted) return;
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
    final suggestions = <String>[];
    for (final prompt in _starterQuestions) {
      final value = prompt.trim();
      if (value.isNotEmpty &&
          value.length <= 300 &&
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
          'Start with something\nyou can use.',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const Text(
          'Begin with the basics, explore your next service, or bring a question of your own.',
        ),
        const SizedBox(height: 24),
        if ((_discovery?['resume'] as List? ?? []).isNotEmpty)
          ...(_discovery!['resume'] as List).map((raw) {
            final item = raw as Map;
            return Padding(
              padding: const EdgeInsets.only(bottom: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Continue exploring',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(item['title'] as String),
                  if (item['changed'] == true)
                    const Text(
                      'The guide has been updated since your last visit.',
                    ),
                  FilledButton(
                    onPressed: _toolBusy
                        ? null
                        : () => _openGuide(
                            item['guide_id'] as String,
                            stepId: item['step_id'] as String?,
                          ),
                    child: const Text('Continue learning'),
                  ),
                ],
              ),
            );
          }),
        if ((_discovery?['featured'] as List? ?? []).isNotEmpty)
          Container(
            padding: const EdgeInsets.all(AppSpacing.screen),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Builder(
              builder: (context) {
                final guide = (_discovery!['featured'] as List).first as Map;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (guide['beginner_friendly'] == true)
                      const Text('A starting point for new owners'),
                    const SizedBox(height: 8),
                    Text(
                      guide['title'] as String,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(guide['description'] as String? ?? ''),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: _toolBusy
                          ? null
                          : () => _openGuide(guide['id'] as String),
                      child: const Text('Explore with me'),
                    ),
                  ],
                );
              },
            ),
          ),
        if (_companion != null) ...[
          const SizedBox(height: 16),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Plan my next service'),
            subtitle: const Text('Use my records and service schedule'),
            trailing: const Icon(Icons.arrow_forward),
            onTap: _toolBusy ? null : () => _openPlan(),
          ),
        ],
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Browse learning guides'),
          subtitle: const Text('Choose a topic to explore'),
          trailing: const Icon(Icons.arrow_forward),
          onTap: widget.onLearn,
        ),
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
      backgroundColor: AppColors.canvas,
      appBar: AppBar(
        backgroundColor: AppColors.canvas,
        title: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Mascot(size: 38, artwork: MascotArtwork.chatbot),
            SizedBox(width: 10),
            Flexible(
              child: Text(
                'Ask AI',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          if (signedIn)
            IconButton(
              tooltip: 'Refresh starting points',
              onPressed: _toolBusy ? null : _refreshStartingPoints,
              icon: const Icon(Icons.refresh),
            ),
          if (signedIn)
            TextButton(
              onPressed: _pending ? null : _chooseVehicle,
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  maxWidth: MediaQuery.sizeOf(context).width * .3,
                ),
                child: Text(
                  widget.state.selectedVehicle?.name ?? 'General',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          if (signedIn)
            PopupMenuButton<String>(
              tooltip: 'Conversation options',
              onSelected: (value) {
                if (value == 'saved') _saved();
                if (value == 'prepare') _prepareForMechanic();
                if (value == 'new') _newConversation();
              },
              itemBuilder: (_) => [
                if (_companion != null)
                  const PopupMenuItem(
                    value: 'saved',
                    child: Text('Saved explanations, guides & notes'),
                  ),
                if (widget.repository is FastApiChatRepository)
                  const PopupMenuItem(
                    value: 'prepare',
                    child: Text('Prepare for my mechanic'),
                  ),
                const PopupMenuItem(
                  value: 'new',
                  child: Text('New conversation'),
                ),
              ],
            ),
        ],
      ),
      body: !signedIn
          ? const SignInPrompt(
              icon: Icons.chat_bubble_outline,
              title: 'Make sense of your car questions',
              message:
                  'Sign in to explore with Car guide. Learning guides and emergency help are also available without an account.',
            )
          : SafeArea(
              top: false,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 760),
                  child: LayoutBuilder(
                    builder: (context, constraints) => Column(
                      children: [
                        const Padding(
                          padding: EdgeInsets.fromLTRB(
                            AppSpacing.screen,
                            0,
                            AppSpacing.screen,
                            12,
                          ),
                          child: Text(
                            'General guidance, not a diagnosis. For faults, see a mechanic.',
                            style: TextStyle(color: AppColors.muted),
                          ),
                        ),
                        if (_toolBusy || _restoring)
                          const LinearProgressIndicator(
                            semanticsLabel: 'Loading activity',
                          ),
                        if (_toolError != null)
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.screen,
                              vertical: 8,
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (_restoreFailed)
                                  TextButton(
                                    onPressed: () =>
                                        _restoreSession(_conversationKey),
                                    child: const Text('Retry restore'),
                                  ),
                                if (!_restoreFailed)
                                  IconButton(
                                    tooltip: 'Refresh starting points',
                                    onPressed: _refreshStartingPoints,
                                    icon: const Icon(Icons.refresh),
                                  ),
                                Expanded(
                                  child: Semantics(
                                    liveRegion: true,
                                    child: Text(
                                      _toolError!,
                                      style: TextStyle(
                                        color: theme.colorScheme.error,
                                      ),
                                    ),
                                  ),
                                ),
                                IconButton(
                                  tooltip: 'Dismiss activity message',
                                  onPressed: _restoreFailed
                                      ? null
                                      : () => setState(() => _toolError = null),
                                  icon: const Icon(Icons.close),
                                ),
                              ],
                            ),
                          ),
                        if (_messages.isNotEmpty ||
                            _lesson != null ||
                            _plan != null)
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.screen,
                            ),
                            child: Align(
                              alignment: Alignment.centerLeft,
                              child: Wrap(
                                spacing: 8,
                                children: [
                                  TextButton(
                                    onPressed: _pending
                                        ? null
                                        : () => setState(() {
                                            _showActivity = false;
                                            _home = true;
                                          }),
                                    child: const Text('Starting points'),
                                  ),
                                  if (!_showActivity &&
                                      (_lesson != null || _plan != null))
                                    TextButton(
                                      onPressed: () => setState(() {
                                        _showActivity = true;
                                        _home = false;
                                      }),
                                      child: Text(
                                        _lesson == null
                                            ? 'Return to service plan'
                                            : 'Return to learning',
                                      ),
                                    ),
                                  if (_messages.isNotEmpty &&
                                      (_home || _showActivity))
                                    TextButton(
                                      onPressed: () => setState(() {
                                        _showActivity = false;
                                        _home = false;
                                      }),
                                      child: const Text('Conversation'),
                                    ),
                                ],
                              ),
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
                                  horizontal: AppSpacing.screen,
                                  vertical: 8,
                                ),
                                itemCount:
                                    _showActivity || _home || _messages.isEmpty
                                    ? 2
                                    : _messages.length + 1,
                                itemBuilder: (context, index) {
                                  if (_showActivity &&
                                      (_lesson != null || _plan != null)) {
                                    return index == 0
                                        ? _feedback()
                                        : _activityView();
                                  }
                                  if (_home || _messages.isEmpty) {
                                    return index == 0
                                        ? _feedback()
                                        : _introduction();
                                  }
                                  if (index == _messages.length) {
                                    return _feedback();
                                  }
                                  final message = _messages[index];
                                  if (_savedExplanationId != null &&
                                      message.reply?.messageId !=
                                          _savedExplanationId)
                                    return const SizedBox.shrink();
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
                                  return Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.stretch,
                                    children: [
                                      if (_savedExplanationId != null)
                                        const Text(
                                          'Saved explanation · Historical answer. Ask a specific question for a current explanation.',
                                        ),
                                      ChatMessageView(
                                        key: ValueKey(
                                          '$_conversationKey:$index',
                                        ),
                                        message: message,
                                        repository: widget.repository,
                                        onEmergency: widget.onEmergency,
                                        onGuide: _toolBusy || _companion == null
                                            ? null : (id) => _openGuide(id),
                                        onMaintenance: hasCurrentMaintenance
                                            ? widget.onMaintenance
                                            : null,
                                      ),
                                      if (!message.isUser && _companion != null)
                                        Align(
                                          alignment: Alignment.centerLeft,
                                          child: FilledButton.tonal(
                                            onPressed: _toolBusy
                                                ? null
                                                : () => _addNote(message),
                                            child: const Text('Add note'),
                                          ),
                                        ),
                                      if (!message.isUser &&
                                          message.reply?.suggestServicePlan ==
                                              true)
                                        Align(
                                          alignment: Alignment.centerLeft,
                                          child: FilledButton.tonal(
                                            onPressed: _toolBusy || _pending
                                                ? null
                                                : () => _openPlan(),
                                            child: const Text(
                                              'Plan my next service',
                                            ),
                                          ),
                                        ),
                                      if (!message.isUser &&
                                          message.reply?.messageId != null &&
                                          _companion != null)
                                        Align(
                                          alignment: Alignment.centerLeft,
                                          child: TextButton.icon(
                                            icon: const Icon(
                                              Icons.bookmark_add_outlined,
                                              size: 18,
                                            ),
                                            label: const Text(
                                              'Save explanation',
                                            ),
                                            onPressed: _toolBusy
                                                ? null
                                                : () => _tool((key) async {
                                                    await _companion!.save({
                                                      'kind': 'explanation',
                                                      'title':
                                                          message.text.length >
                                                              80
                                                          ? '${message.text.substring(0, 77)}…'
                                                          : message.text,
                                                      'message_id': message
                                                          .reply!
                                                          .messageId,
                                                    });
                                                    if (mounted &&
                                                        key == _conversationKey)
                                                      ScaffoldMessenger.of(
                                                        context,
                                                      ).showSnackBar(
                                                        const SnackBar(
                                                          content: Text(
                                                            'Explanation saved',
                                                          ),
                                                        ),
                                                      );
                                                  }),
                                          ),
                                        ),
                                    ],
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
                        Padding(
                          padding: const EdgeInsets.fromLTRB(20, 4, 0, 0),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'I want to…',
                                style: TextStyle(color: AppColors.muted),
                              ),
                              SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: Row(
                                  children: [
                                    OutlinedButton(
                                      onPressed: _pending
                                          ? null
                                          : widget.onLearn,
                                      child: const Text('Learn a task'),
                                    ),
                                    const SizedBox(width: 8),
                                    OutlinedButton(
                                      onPressed:
                                          _pending ||
                                              _toolBusy ||
                                              _companion == null
                                          ? null
                                          : () => _openPlan(),
                                      child: const Text('Plan maintenance'),
                                    ),
                                    const SizedBox(width: 8),
                                    if (widget.repository
                                        is FastApiChatRepository)
                                      OutlinedButton(
                                        onPressed: _pending
                                            ? null
                                            : _prepareForMechanic,
                                        child: const Text(
                                          'Prepare for my mechanic',
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                        Material(
                          color: AppColors.canvas,
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
                                      hintText: 'Ask a question…',
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
                                                _restoring ||
                                                _restoreFailed ||
                                                _toolBusy ||
                                                _failedRequest != null ||
                                                value.text.trim().isEmpty
                                            ? null
                                            : () => _send(),
                                        icon: const Icon(Icons.send_outlined),
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

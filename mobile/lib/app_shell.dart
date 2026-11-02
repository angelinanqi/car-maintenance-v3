import 'package:flutter/material.dart';
import 'app_state.dart';
import 'data/chat_repository.dart';
import 'data/content_repository.dart';
import 'data/companion_repository.dart';
import 'models/vehicle.dart';
import 'screens/home.dart';
import 'screens/mycar.dart';
import 'screens/learn.dart';
import 'screens/chat.dart';
import 'screens/emergency.dart';
import 'screens/account_form.dart';
import 'account_state.dart';
import 'screens/account_security.dart';
import 'screens/mechanic_preparation.dart';
import 'widgets/pill_nav_bar.dart';
import 'data/api_client.dart';

class AppShell extends StatefulWidget {
  final AppState state;
  final ChatRepository chat;
  final ContentRepository? content;
  final CompanionRepository? companion;
  const AppShell({
    super.key,
    required this.state,
    required this.chat,
    this.content,
    this.companion,
  });
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late final ContentRepository _content;
  String? _chatOwner;
  int _selectedIndex = 0,
      _logRequest = 0,
      _scheduleRequest = 0,
      _chatRequest = 0;
  String? _topic, _prompt, _maintenanceItemId, _lessonId;
  String? _requestedTaskId;
  Map<String, dynamic>? _chatContext;
  int _maintenanceRequest = 0, _lessonRequest = 0;
  bool _entered = false;

  @override
  void initState() {
    super.initState();
    _content = widget.content ?? ContentRepository(widget.state.store);
    _chatOwner = widget.state.accountId;
    widget.state.addListener(_accountChanged);
  }

  void _accountChanged() {
    if (_chatOwner == widget.state.accountId) return;
    _chatOwner = widget.state.accountId;
    setState(() {
      _chatContext = null;
      _topic = null;
      _prompt = null;
      _maintenanceItemId = null;
      _requestedTaskId = null;
      _lessonId = null;
      if (_selectedIndex == 3) _selectedIndex = 0;
    });
  }

  @override
  void dispose() {
    widget.state.removeListener(_accountChanged);
    super.dispose();
  }

  Future<void> _openMaintenance(Vehicle vehicle, bool logService) async {
    try {
      if (widget.state.selectedVehicle?.id != vehicle.id) {
        await widget.state.selectVehicle(vehicle.id);
      }
      if (!mounted) return;
      setState(() {
        _selectedIndex = 1;
        if (logService) {
          _logRequest++;
        } else {
          _scheduleRequest++;
        }
      });
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              error is ApiException
                  ? error.message
                  : 'Vehicle selection could not be confirmed. Refresh your garage before retrying.',
            ),
          ),
        );
    }
  }

  void _askAbout(String topic) =>
      _askContext({'kind': 'topic', 'title': topic});
  void _askContext(Map<String, dynamic> details) => setState(() {
    _chatContext = details;
    _topic = details['title'] as String;
    _prompt = 'Help me understand $_topic.';
    _chatRequest++;
    _selectedIndex = 3;
  });

  void _prepare() {
    if (!widget.state.signedIn || widget.chat is! FastApiChatRepository) {
      setState(() => _selectedIndex = 3);
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MechanicPreparationPage(
          state: widget.state,
          repository: widget.chat as FastApiChatRepository,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) {
      final account = AccountScope.of(context);
      if (account != null &&
          (account.recoveringPassword || account.pendingSession != null)) {
        return AccountSecurity(
          requiredFlow: true,
          onEmergency: () => Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) =>
                  Emergency(state: widget.state, repository: _content),
            ),
          ),
        );
      }
      if (!_entered && !widget.state.signedIn) {
        return AccountForm(
          register: false,
          onGuest: () => setState(() => _entered = true),
          onEmergency: () => setState(() {
            _entered = true;
            _selectedIndex = 4;
          }),
        );
      }
      return PopScope<Object?>(
        canPop: _selectedIndex == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop && _selectedIndex != 0) {
            setState(() => _selectedIndex = 0);
          }
        },
        child: Scaffold(
          extendBody: true,
          body: Column(
            children: [
              if (widget.state.loading)
                const LinearProgressIndicator(
                  semanticsLabel: 'Loading saved preferences',
                ),
              if (widget.state.loadError != null && _selectedIndex != 0)
                SafeArea(
                  bottom: false,
                  child: MaterialBanner(
                    content: const Text(
                      'Your account could not refresh. Check your connection and try again.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: widget.state.loading
                            ? null
                            : widget.state.load,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              Expanded(
                child: SafeArea(
                  child: IndexedStack(
                    index: _selectedIndex,
                    children: [
                      TickerMode(
                        enabled: _selectedIndex == 0,
                        child: Home(
                          state: widget.state,
                          onMaintenance: _openMaintenance,
                          onTask: (id) => setState(() {
                            _requestedTaskId = id;
                            _maintenanceItemId = null;
                            _maintenanceRequest++;
                            _selectedIndex = 1;
                          }),
                          onEmergency: () => setState(() => _selectedIndex = 4),
                          onLearn: () => setState(() => _selectedIndex = 2),
                          onAsk: () => setState(() => _selectedIndex = 3),
                          onPlan: () => _askContext({
                            'kind': 'service_plan',
                            'title': 'My next service',
                          }),
                          onPrepare: _prepare,
                        ),
                      ),
                      TickerMode(
                        enabled: _selectedIndex == 1,
                        child: MyCar(
                          state: widget.state,
                          logRequest: _logRequest,
                          scheduleRequest: _scheduleRequest,
                          requestedItemId: _maintenanceItemId,
                          requestedTaskId: _requestedTaskId,
                          itemRequestNumber: _maintenanceRequest,
                          onAsk: _askContext,
                          onPlan: () => _askContext({
                            'kind': 'service_plan',
                            'title': 'My next service',
                          }),
                          onLearn: (id) => setState(() {
                            _lessonId = id;
                            _lessonRequest++;
                            _selectedIndex = 2;
                          }),
                        ),
                      ),
                      TickerMode(
                        enabled: _selectedIndex == 2,
                        child: Learn(
                          state: widget.state,
                          repository: _content,
                          chat: widget.chat,
                          onAsk: _askAbout,
                          onAskContext: _askContext,
                          requestedLessonId: _lessonId,
                          lessonRequestNumber: _lessonRequest,
                          onMaintenanceItem: (id) => setState(() {
                            _requestedTaskId = null;
                            _maintenanceItemId = id;
                            _maintenanceRequest++;
                            _selectedIndex = 1;
                          }),
                        ),
                      ),
                      TickerMode(
                        enabled: _selectedIndex == 3,
                        child: Chat(
                          state: widget.state,
                          repository: widget.chat,
                          companion: widget.companion,
                          requestNumber: _chatRequest,
                          topic: _topic,
                          prompt: _prompt,
                          contextData: _chatContext,
                          onEmergency: () => setState(() => _selectedIndex = 4),
                          onMaintenance: () => setState(() {
                            _selectedIndex = 1;
                            _scheduleRequest++;
                          }),
                          onLearn: () => setState(() => _selectedIndex = 2),
                        ),
                      ),
                      TickerMode(
                        enabled: _selectedIndex == 4,
                        child: Emergency(
                          state: widget.state,
                          repository: _content,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          bottomNavigationBar: MediaQuery.viewInsetsOf(context).bottom > 0
              ? null
              : PillNavBar(
                  selectedIndex: _selectedIndex,
                  onTap: (index) {
                    FocusManager.instance.primaryFocus?.unfocus();
                    setState(() => _selectedIndex = index);
                  },
                  destinations: const [
                    PillNavDestination(
                      icon: Icons.home_outlined,
                      label: 'Home',
                    ),
                    PillNavDestination(
                      icon: Icons.directions_car_outlined,
                      label: 'My Car',
                    ),
                    PillNavDestination(
                      icon: Icons.menu_book_outlined,
                      label: 'Learn',
                    ),
                    PillNavDestination(
                      icon: Icons.chat_bubble_outline,
                      label: 'Ask AI',
                    ),
                    PillNavDestination(
                      icon: Icons.warning_amber_outlined,
                      label: 'Emergency',
                      itemWidth: pillNavLongLabelWidth,
                    ),
                  ],
                ),
        ),
      );
    },
  );
}

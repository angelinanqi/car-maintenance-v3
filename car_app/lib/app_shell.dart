import 'package:flutter/material.dart';
import 'app_state.dart';
import 'data/chat_repository.dart';
import 'data/content_repository.dart';
import 'models/vehicle.dart';
import 'screens/home.dart';
import 'screens/mycar.dart';
import 'screens/learn.dart';
import 'screens/chat.dart';
import 'screens/emergency.dart';
import 'screens/account_form.dart';

class AppShell extends StatefulWidget {
  final AppState state;
  final ChatRepository chat;
  final ContentRepository? content;
  const AppShell({
    super.key,
    required this.state,
    required this.chat,
    this.content,
  });
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  // Keep existing module indices stable for contextual links.
  static const _destinationOrder = [0, 1, 3, 2, 4];
  late final ContentRepository _content;
  String? _chatOwner;
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
      _lessonId = null;
      if (_selectedIndex == 3) _selectedIndex = 0;
    });
  }

  @override
  void dispose() {
    widget.state.removeListener(_accountChanged);
    super.dispose();
  }

  int _selectedIndex = 0;
  int _logRequest = 0;
  int _scheduleRequest = 0;
  int _chatRequest = 0;
  String? _topic;
  String? _prompt;
  Map<String, dynamic>? _chatContext;
  String? _maintenanceItemId;
  String? _lessonId;
  int _maintenanceRequest = 0, _lessonRequest = 0;
  bool _entered = false;

  Future<void> _openMaintenance(Vehicle vehicle, bool logService) async {
    try {
      await widget.state.selectVehicle(vehicle.id);
      if (!mounted) return;
      setState(() {
        _selectedIndex = 1;
        if (logService) {
          _logRequest++;
        } else {
          _scheduleRequest++;
        }
      });
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not save vehicle selection. Please retry.'),
          ),
        );
      }
    }
  }

  void _askAbout(String topic) => setState(() {
    _chatContext = null;
    _topic = topic;
    _prompt = 'Help me understand $topic.';
    _chatRequest++;
    _selectedIndex = 3;
  });

  void _askContext(Map<String, dynamic> context) => setState(() {
    _chatContext = context;
    _topic = context['title'] as String;
    _prompt = 'Help me understand $_topic.';
    _chatRequest++;
    _selectedIndex = 3;
  });

  Widget _welcome() => Scaffold(
    appBar: AppBar(title: const Text('Car Assistance')),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () => setState(() {
                _entered = true;
                _selectedIndex = 4;
              }),
              icon: const Icon(Icons.emergency),
              label: const Text('Emergency help · no sign-in'),
            ),
            const SizedBox(height: 40),
            Icon(
              Icons.chat_bubble_outline_rounded,
              size: 48,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 20),
            Text(
              'Know your car.\nFeel more confident.',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            const Text(
              'Learn with Car guide, make sense of maintenance and prepare for your next service.',
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const AccountForm(register: false),
                ),
              ),
              child: const Text('Sign in'),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => setState(() => _entered = true),
              child: const Text('Explore as guest'),
            ),
            TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const AccountForm(register: true),
                ),
              ),
              child: const Text('Create account'),
            ),
            const SizedBox(height: 20),
            Text(
              'Guides and emergency help are available without an account.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.state,
    builder: (context, _) => !_entered && !widget.state.signedIn
        ? _welcome()
        : Scaffold(
            body: Column(
              children: [
                if (widget.state.loading)
                  const LinearProgressIndicator(
                    semanticsLabel: 'Loading saved preferences',
                  ),
                if (widget.state.loadError != null &&
                    (_selectedIndex != 0 || !widget.state.signedIn))
                  SafeArea(
                    bottom: false,
                    child: MaterialBanner(
                      content: Text(
                        widget.state.signedIn
                            ? 'Your account could not refresh. Check your connection and try again.'
                            : widget.state.loadError!,
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
                  child: IndexedStack(
                    index: _selectedIndex,
                    children: [
                      TickerMode(
                        enabled: _selectedIndex == 0,
                        child: Home(
                          state: widget.state,
                          onMaintenance: _openMaintenance,
                          onEmergency: () => setState(() => _selectedIndex = 4),
                          onLearn: () => setState(() => _selectedIndex = 2),
                          onAsk: () => setState(() => _selectedIndex = 3),
                        ),
                      ),
                      TickerMode(
                        enabled: _selectedIndex == 1,
                        child: MyCar(
                          state: widget.state,
                          logRequest: _logRequest,
                          scheduleRequest: _scheduleRequest,
                          requestedItemId: _maintenanceItemId,
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
                          onAsk: _askAbout,
                          repository: _content,
                          onAskContext: _askContext,
                          requestedLessonId: _lessonId,
                          lessonRequestNumber: _lessonRequest,
                          onMaintenanceItem: (id) => setState(() {
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
              ],
            ),
            bottomNavigationBar: MediaQuery.viewInsetsOf(context).bottom > 0
                ? null
                : MediaQuery.withClampedTextScaling(
                    maxScaleFactor: MediaQuery.sizeOf(context).width < 360
                        ? 1
                        : 1.3,
                    child: NavigationBar(
                      selectedIndex: _destinationOrder.indexOf(_selectedIndex),
                      onDestinationSelected: (index) {
                        FocusManager.instance.primaryFocus?.unfocus();
                        setState(
                          () => _selectedIndex = _destinationOrder[index],
                        );
                      },
                      destinations: [
                        NavigationDestination(
                          icon: Icon(Icons.home_rounded),
                          label: 'Home',
                        ),
                        NavigationDestination(
                          icon: Icon(Icons.directions_car_rounded),
                          label: 'My Car',
                        ),
                        NavigationDestination(
                          icon: Icon(Icons.chat_bubble_outline_rounded),
                          selectedIcon: Icon(Icons.chat_bubble_rounded),
                          label: 'Car guide',
                        ),
                        NavigationDestination(
                          icon: Icon(Icons.menu_book_outlined),
                          selectedIcon: Icon(Icons.menu_book_rounded),
                          label: 'Learn',
                        ),
                        NavigationBarTheme(
                          data: NavigationBarThemeData(
                            labelTextStyle: WidgetStatePropertyAll(
                              TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: Theme.of(
                                  context,
                                ).colorScheme.onErrorContainer,
                              ),
                            ),
                          ),
                          child: MediaQuery.withClampedTextScaling(
                            // Keep the complete label legible within a fixed-width
                            // navigation target. Emergency content still scales fully.
                            maxScaleFactor:
                                MediaQuery.sizeOf(context).width < 360
                                ? 1
                                : 1.3,
                            child: NavigationDestination(
                              icon: _EmergencyNavIcon(
                                selected: _selectedIndex == 4,
                              ),
                              tooltip: 'Emergency help - no sign-in needed',
                              label: 'Emergency',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
          ),
  );
}

class _EmergencyNavIcon extends StatelessWidget {
  final bool selected;
  const _EmergencyNavIcon({required this.selected});
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: 60,
      padding: const EdgeInsets.symmetric(vertical: 4),
      decoration: BoxDecoration(
        color: selected ? colors.error : Colors.transparent,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        Icons.emergency_outlined,
        color: selected ? colors.onError : colors.onErrorContainer,
      ),
    );
  }
}

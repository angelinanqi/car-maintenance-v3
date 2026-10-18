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
    body: Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
                foregroundColor: Theme.of(context).colorScheme.onError,
              ),
              onPressed: () => setState(() {
                _entered = true;
                _selectedIndex = 4;
              }),
              icon: const Icon(Icons.emergency),
              label: const Text('Emergency help - no sign-in needed'),
            ),
            const SizedBox(height: 24),
            Align(
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(24),
                ),
                child: const Icon(Icons.directions_car_outlined, size: 56),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'A little more confidence on the road.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            const Text(
              'Learn about your car and keep emergency guides close, even offline. Sign in to manage vehicles and maintenance.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => setState(() => _entered = true),
              child: const Text('Continue as guest'),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const AccountForm(register: false),
                ),
              ),
              child: const Text('Sign in'),
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
            bottomNavigationBar: NavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: (index) {
                FocusManager.instance.primaryFocus?.unfocus();
                setState(() => _selectedIndex = index);
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
                  icon: Icon(Icons.menu_book_rounded),
                  label: 'Learn',
                ),
                NavigationDestination(
                  icon: Icon(Icons.auto_awesome_rounded),
                  label: 'Ask AI',
                ),
                NavigationBarTheme(
                  data: NavigationBarThemeData(
                    labelTextStyle: WidgetStatePropertyAll(
                      TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                    ),
                  ),
                  child: MediaQuery.withClampedTextScaling(
                    // Keep the complete label legible within a fixed-width
                    // navigation target. Emergency content still scales fully.
                    maxScaleFactor: MediaQuery.sizeOf(context).width < 360
                        ? 1
                        : 1.3,
                    child: NavigationDestination(
                      icon: _EmergencyNavIcon(selected: _selectedIndex == 4),
                      tooltip: 'Emergency help - no sign-in needed',
                      label: 'Emergency',
                    ),
                  ),
                ),
              ],
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
        color: selected ? colors.error : colors.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        Icons.emergency_outlined,
        color: selected ? colors.onError : colors.onErrorContainer,
      ),
    );
  }
}

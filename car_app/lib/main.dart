import 'package:flutter/material.dart';
import 'app_shell.dart';
import 'app_state.dart';
import 'data/local_store.dart';
import 'data/api_client.dart';
import 'data/chat_repository.dart';
import 'data/content_repository.dart';
import 'data/account_repository.dart';
import 'account_state.dart';
import 'data/mobile_repository.dart';

void main() => runApp(const MyApp());

class MyApp extends StatefulWidget {
  final AppState? state;
  final ChatRepository? chatRepository;
  const MyApp({super.key, this.state, this.chatRepository});
  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> with WidgetsBindingObserver {
  late final AppState state;
  late final ChatRepository chat;
  late final ContentRepository content;
  late final AccountState account;
  final api = ApiClient();
  final navigatorKey = GlobalKey<NavigatorState>();
  String? _lastAccountId;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    account = AccountState(AccountRepository(api));
    state =
        widget.state ??
        AppState(
          LocalStore(),
          repository: MobileRepository(api, account.repository),
        );
    account.addListener(_accountChanged);
    account.restore();
    content = ContentRepository(state.store, api: api);
    chat =
        widget.chatRepository ??
        FastApiChatRepository(api, account: account.repository);
    state.load();
    api
        .loadConfiguration()
        .then((_) {
          if (mounted) state.setVehicleScopes(api.vehicleScopes);
        })
        .catchError((_) {
          /* Emergency startup does not depend on backend configuration. */
        });
  }

  void _accountChanged() {
    final id = account.user?.id;
    if (_lastAccountId != null && _lastAccountId != id) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        navigatorKey.currentState?.pushAndRemoveUntil(
          MaterialPageRoute(
            builder: (_) =>
                AppShell(state: state, chat: chat, content: content),
          ),
          (_) => false,
        );
      });
    }
    _lastAccountId = id;
    state.setEmergencyOwner(account.repository.incidentOwnerId);
    state.bindAccount(id);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    account.removeListener(_accountChanged);
    account.dispose();
    api.close();
    if (widget.state == null) state.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState lifecycle) {
    if (lifecycle == AppLifecycleState.resumed) account.restore();
  }

  @override
  Widget build(BuildContext context) => AccountScope(
    state: account,
    child: MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Car Assistance',
      navigatorKey: navigatorKey,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.amber),
        scaffoldBackgroundColor: Colors.orange[50],
        bottomNavigationBarTheme: BottomNavigationBarThemeData(
          backgroundColor: Colors.white,
          selectedItemColor: Colors.amber[900],
          unselectedItemColor: Colors.grey[600],
          type: BottomNavigationBarType.fixed,
        ),
      ),
      home: AppShell(state: state, chat: chat, content: content),
    ),
  );
}

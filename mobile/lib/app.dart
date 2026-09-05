import 'package:flutter/material.dart';
import 'core/api_client.dart';
import 'shared/widgets.dart';
import 'features/auth/screens.dart';
import 'features/attendance/home.dart';
class AttendanceApp extends StatefulWidget {
  final AttendanceGateway? gateway;
  const AttendanceApp({super.key, this.gateway});

  @override
  State<AttendanceApp> createState() => _AttendanceAppState();
}

class _AttendanceAppState extends State<AttendanceApp> {
  late final AttendanceGateway gateway = widget.gateway ?? ApiClient();
  Map<String, dynamic>? user;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    try {
      final restored = await gateway.restoreSession();
      if (mounted) setState(() => user = restored);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Attendance Control',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: canvas,
        colorScheme: ColorScheme.fromSeed(seedColor: blue, brightness: Brightness.light),
        fontFamily: 'Roboto',
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFFDDE4EF))),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFFDDE4EF))),
        ),
      ),
      home: loading
          ? const SplashView()
          : user == null
              ? LoginView(gateway: gateway, onAuthenticated: (value) => setState(() => user = value))
              : user!['must_change_password'] == true
                  ? ChangePasswordView(gateway: gateway, onChanged: () => setState(() => user = {...user!, 'must_change_password': false}))
                  : HomeShell(gateway: gateway, user: user!, onLogout: () => setState(() => user = null)),
    );
  }
}

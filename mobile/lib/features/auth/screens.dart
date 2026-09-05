import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../shared/widgets.dart';
class LoginView extends StatefulWidget {
  final AttendanceGateway gateway;
  final ValueChanged<Map<String, dynamic>> onAuthenticated;
  const LoginView({super.key, required this.gateway, required this.onAuthenticated});
  @override
  State<LoginView> createState() => _LoginViewState();
}

class _LoginViewState extends State<LoginView> {
  final email = TextEditingController();
  final password = TextEditingController();
  bool submitting = false;
  String error = '';

  Future<void> submit() async {
    setState(() { submitting = true; error = ''; });
    try { widget.onAuthenticated(await widget.gateway.login(email.text, password.text)); }
    catch (cause) { if (mounted) setState(() => error = cause.toString()); }
    finally { if (mounted) setState(() => submitting = false); }
  }

  @override
  void dispose() { email.dispose(); password.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(child: ListView(padding: const EdgeInsets.fromLTRB(24, 42, 24, 30), children: [
      const Align(alignment: Alignment.centerLeft, child: BrandIcon(size: 56)),
      const SizedBox(height: 48),
      const Text('Welcome back', style: TextStyle(color: navy, fontSize: 34, fontWeight: FontWeight.w900, letterSpacing: -1.4)),
      const SizedBox(height: 10),
      const Text('Sign in to record and review your attendance.', style: TextStyle(color: Color(0xFF708097), fontSize: 16)),
      if (error.isNotEmpty) ErrorBox(error),
      const SizedBox(height: 30),
      TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email address')),
      const SizedBox(height: 16),
      TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
      const SizedBox(height: 24),
      PrimaryButton(label: 'Sign in', loading: submitting, onPressed: submit),
      const SizedBox(height: 34),
      const SecurityNote(),
    ])),
  );
}

class ChangePasswordView extends StatefulWidget {
  final AttendanceGateway gateway;
  final VoidCallback onChanged;
  const ChangePasswordView({super.key, required this.gateway, required this.onChanged});
  @override
  State<ChangePasswordView> createState() => _ChangePasswordViewState();
}

class _ChangePasswordViewState extends State<ChangePasswordView> {
  final current = TextEditingController();
  final next = TextEditingController();
  final confirm = TextEditingController();
  @override
  void dispose() {
    current.dispose();
    next.dispose();
    confirm.dispose();
    super.dispose();
  }
  String error = '';
  bool loading = false;
  Future<void> submit() async {
    if (next.text != confirm.text) { setState(() => error = 'New passwords do not match.'); return; }
    setState(() { loading = true; error = ''; });
    try { await widget.gateway.changePassword(current.text, next.text); widget.onChanged(); }
    catch (cause) { if (mounted) setState(() => error = cause.toString()); }
    finally { if (mounted) setState(() => loading = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(body: SafeArea(child: ListView(padding: const EdgeInsets.all(24), children: [
    const SizedBox(height: 26), const BrandIcon(size: 56), const SizedBox(height: 36),
    const Text('Secure your account', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: navy)),
    const SizedBox(height: 10), const Text('Replace the temporary password before recording attendance.', style: TextStyle(color: Color(0xFF708097), fontSize: 16)),
    if (error.isNotEmpty) ErrorBox(error), const SizedBox(height: 24),
    TextField(controller: current, obscureText: true, decoration: const InputDecoration(labelText: 'Temporary password')), const SizedBox(height: 14),
    TextField(controller: next, obscureText: true, decoration: const InputDecoration(labelText: 'New password')), const SizedBox(height: 14),
    TextField(controller: confirm, obscureText: true, decoration: const InputDecoration(labelText: 'Confirm new password')), const SizedBox(height: 24),
    PrimaryButton(label: 'Save password', loading: loading, onPressed: submit),
  ])));
}

import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../shared/widgets.dart';
import 'history.dart';
import 'scanner.dart';
class HomeShell extends StatefulWidget {
  final AttendanceGateway gateway;
  final Map<String, dynamic> user;
  final VoidCallback onLogout;
  const HomeShell({super.key, required this.gateway, required this.user, required this.onLogout});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: index == 0
        ? TodayView(gateway: widget.gateway, user: widget.user)
        : HistoryView(gateway: widget.gateway),
    bottomNavigationBar: NavigationBar(
      selectedIndex: index,
      indicatorColor: const Color(0xFFDDE5FF),
      onDestinationSelected: (value) => setState(() => index = value),
      destinations: const [NavigationDestination(icon: Icon(Icons.today_outlined), selectedIcon: Icon(Icons.today), label: 'Today'), NavigationDestination(icon: Icon(Icons.history), label: 'History')],
    ),
    appBar: AppBar(
      backgroundColor: navy,
      foregroundColor: Colors.white,
      title: const Row(children: [BrandIcon(size: 34), SizedBox(width: 10), Text('Attendance Control', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800))]),
      actions: [IconButton(tooltip: 'Sign out', onPressed: () async { await widget.gateway.logout(); widget.onLogout(); }, icon: const Icon(Icons.logout))],
    ),
  );
}

class TodayView extends StatefulWidget {
  final AttendanceGateway gateway;
  final Map<String, dynamic> user;
  const TodayView({super.key, required this.gateway, required this.user});
  @override
  State<TodayView> createState() => _TodayViewState();
}

class _TodayViewState extends State<TodayView> {
  Map<String, dynamic>? today;
  String error = '';
  bool loading = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async { setState(() { loading = true; error = ''; }); try { final data = await widget.gateway.today(); if (mounted) setState(() => today = data); } catch (cause) { if (mounted) setState(() => error = cause.toString()); } finally { if (mounted) setState(() => loading = false); } }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    if (error.isNotEmpty) return Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [ErrorBox(error), OutlinedButton(onPressed: load, child: const Text('Try again'))])));
    final assignment = Map<String, dynamic>.from(today?['assignment'] as Map? ?? {});
    final site = Map<String, dynamic>.from(assignment['site'] as Map? ?? {});
    final shift = Map<String, dynamic>.from(assignment['shift'] as Map? ?? {});
    final record = today?['attendance'] is Map ? Map<String, dynamic>.from(today!['attendance'] as Map) : null;
    final checkedIn = today?['is_checked_in'] == true;
    final checkedOut = today?['is_checked_out'] == true;
    final state = today?['day_state']?.toString() ?? 'NOT_RECORDED';
    return RefreshIndicator(onRefresh: load, child: ListView(padding: const EdgeInsets.fromLTRB(20, 24, 20, 34), children: [
      Text('Hello, ${widget.user['first_name'] ?? 'there'}', style: const TextStyle(color: navy, fontSize: 29, fontWeight: FontWeight.w900, letterSpacing: -1)),
      const SizedBox(height: 6), Text('${today?['work_date'] ?? ''}', style: const TextStyle(color: Color(0xFF718096), fontSize: 15)),
      const SizedBox(height: 22),
      Container(padding: const EdgeInsets.all(22), decoration: BoxDecoration(color: navy, borderRadius: BorderRadius.circular(20)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [const Text('TODAY', style: TextStyle(color: Color(0xFF8EA3C0), fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 1.4)), StateBadge(state)]),
        const SizedBox(height: 30), Text(site['name']?.toString() ?? 'Assigned site', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w900)),
        const SizedBox(height: 8), Row(children: [const Icon(Icons.schedule, color: green, size: 18), const SizedBox(width: 7), Text('${shift['start_time'] ?? '—'} – ${shift['end_time'] ?? '—'} · ${shift['grace_minutes'] ?? 0} min grace', style: const TextStyle(color: Color(0xFFB8C6D9)))])
      ])),
      const SizedBox(height: 16),
      Row(children: [Expanded(child: TimeCard(label: 'CLOCK IN', value: displayTime(record?['clock_in']))), const SizedBox(width: 12), Expanded(child: TimeCard(label: 'CLOCK OUT', value: displayTime(record?['clock_out'])))]),
      const SizedBox(height: 20),
      if (checkedOut) const DoneCard()
      else PrimaryButton(label: checkedIn ? 'Scan QR to clock out' : 'Scan QR to clock in', icon: Icons.qr_code_scanner, onPressed: state == 'HOLIDAY' || state == 'EXCUSED' ? null : () async {
        final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => ScannerView(gateway: widget.gateway, clockOut: checkedIn)));
        if (changed == true) await load();
      }),
      const SizedBox(height: 18), const SecurityNote(),
    ]));
  }
}

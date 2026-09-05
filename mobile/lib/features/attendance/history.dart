import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../shared/widgets.dart';

class HistoryView extends StatefulWidget {
  final AttendanceGateway gateway;
  const HistoryView({super.key, required this.gateway});
  @override
  State<HistoryView> createState() => _HistoryViewState();
}

class _HistoryViewState extends State<HistoryView> {
  List<Map<String, dynamic>> rows = [];
  bool loading = true;
  String error = '';
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await widget.gateway.history();
      if (mounted) setState(() => rows = data);
    } catch (cause) {
      if (mounted) setState(() => error = cause.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => loading
      ? const Center(child: CircularProgressIndicator())
      : RefreshIndicator(
          onRefresh: load,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Text(
                'Attendance history',
                style: TextStyle(
                  color: navy,
                  fontSize: 29,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -1,
                ),
              ),
              const SizedBox(height: 7),
              const Text(
                'Your effective records and worked time.',
                style: TextStyle(color: Color(0xFF718096)),
              ),
              if (error.isNotEmpty) ErrorBox(error),
              const SizedBox(height: 20),
              if (rows.isEmpty)
                const EmptyHistory()
              else
                ...rows.map((row) => HistoryCard(row: row)),
            ],
          ),
        );
}

class HistoryCard extends StatelessWidget {
  final Map<String, dynamic> row;
  const HistoryCard({super.key, required this.row});
  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      border: Border.all(color: const Color(0xFFE0E6EF)),
    ),
    child: Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              row['work_date']?.toString() ?? '',
              style: const TextStyle(
                fontWeight: FontWeight.w900,
                color: navy,
                fontSize: 16,
              ),
            ),
            StateBadge(row['state']?.toString() ?? ''),
          ],
        ),
        const Divider(height: 28),
        Row(
          children: [
            Expanded(
              child: HistoryTime(
                label: 'IN',
                value: displayTime(row['clock_in']),
              ),
            ),
            Expanded(
              child: HistoryTime(
                label: 'OUT',
                value: displayTime(row['clock_out']),
              ),
            ),
            Expanded(
              child: HistoryTime(
                label: 'WORKED',
                value: row['worked_minutes'] == null
                    ? '—'
                    : '${(row['worked_minutes'] as num) ~/ 60}h ${(row['worked_minutes'] as num).toInt() % 60}m',
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

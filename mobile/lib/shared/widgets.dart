import 'package:flutter/material.dart';
const navy = Color(0xFF0B1628);
const blue = Color(0xFF315DFB);
const green = Color(0xFF16B981);
const canvas = Color(0xFFF4F7FB);
class SplashView extends StatelessWidget {
  const SplashView({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(
    backgroundColor: navy,
    body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [BrandIcon(size: 72), SizedBox(height: 22), Text('ATTENDANCE CONTROL', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, letterSpacing: 2))])),
  );
}
class HistoryTime extends StatelessWidget { final String label; final String value; const HistoryTime({super.key, required this.label, required this.value}); @override Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(color: Color(0xFF8B96A7), fontSize: 11, fontWeight: FontWeight.w800)), const SizedBox(height: 5), Text(value, style: const TextStyle(color: navy, fontWeight: FontWeight.w800))]); }
class EmptyHistory extends StatelessWidget { const EmptyHistory({super.key}); @override Widget build(BuildContext context) => const Padding(padding: EdgeInsets.only(top: 100), child: Column(children: [Icon(Icons.event_available_outlined, size: 55, color: Color(0xFFA5B0BF)), SizedBox(height: 14), Text('No attendance records yet', style: TextStyle(color: navy, fontWeight: FontWeight.w800, fontSize: 17))])); }
class TimeCard extends StatelessWidget { final String label; final String value; const TimeCard({super.key, required this.label, required this.value}); @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.all(18), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFFE0E6EF))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(color: Color(0xFF8793A5), fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1)), const SizedBox(height: 9), Text(value, style: const TextStyle(color: navy, fontWeight: FontWeight.w900, fontSize: 22))])); }
class DoneCard extends StatelessWidget { const DoneCard({super.key}); @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.all(18), decoration: BoxDecoration(color: const Color(0xFFE5F8F1), borderRadius: BorderRadius.circular(14)), child: const Row(children: [Icon(Icons.check_circle, color: Color(0xFF07855F)), SizedBox(width: 12), Expanded(child: Text('Attendance complete for this shift', style: TextStyle(color: Color(0xFF087655), fontWeight: FontWeight.w800))) ])); }
class SecurityNote extends StatelessWidget { const SecurityNote({super.key}); @override Widget build(BuildContext context) => const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.shield_outlined, color: Color(0xFF66768D), size: 19), SizedBox(width: 10), Expanded(child: Text('QR and GPS are verified by the server. Invalid attempts do not alter your attendance.', style: TextStyle(color: Color(0xFF66768D), height: 1.45, fontSize: 13))) ]); }
class BrandIcon extends StatelessWidget { final double size; const BrandIcon({super.key, required this.size}); @override Widget build(BuildContext context) => Container(width: size, height: size, decoration: BoxDecoration(color: blue, borderRadius: BorderRadius.circular(size * .24)), child: Icon(Icons.schedule_rounded, color: Colors.white, size: size * .58)); }
class ErrorBox extends StatelessWidget { final String message; const ErrorBox(this.message, {super.key}); @override Widget build(BuildContext context) => Container(width: double.infinity, margin: const EdgeInsets.only(top: 18), padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0xFFFFECEF), borderRadius: BorderRadius.circular(10)), child: Row(children: [const Icon(Icons.error_outline, color: Color(0xFFC8374C)), const SizedBox(width: 10), Expanded(child: Text(message, style: const TextStyle(color: Color(0xFFAE2D40), fontWeight: FontWeight.w700))) ])); }
class PrimaryButton extends StatelessWidget { final String label; final bool loading; final IconData? icon; final VoidCallback? onPressed; const PrimaryButton({super.key, required this.label, this.loading = false, this.icon, this.onPressed}); @override Widget build(BuildContext context) => SizedBox(width: double.infinity, height: 56, child: FilledButton(onPressed: loading ? null : onPressed, style: FilledButton.styleFrom(backgroundColor: blue, disabledBackgroundColor: const Color(0xFFAAB8E5), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))), child: loading ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white)) : Row(mainAxisAlignment: MainAxisAlignment.center, children: [if (icon != null) ...[Icon(icon), const SizedBox(width: 9)], Text(label, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16))]))); }

class StateBadge extends StatelessWidget {
  final String state;
  const StateBadge(this.state, {super.key});
  @override
  Widget build(BuildContext context) {
    final colors = switch (state) { 'PRESENT' => (const Color(0xFFE4F8F1), const Color(0xFF087A58)), 'LATE' => (const Color(0xFFFFF1DA), const Color(0xFFAD650A)), 'ABSENT' => (const Color(0xFFFFE8EC), const Color(0xFFBD3549)), 'EXCUSED' || 'HOLIDAY' => (const Color(0xFFE9EDFF), const Color(0xFF4459C8)), _ => (const Color(0xFFEAF0F7), const Color(0xFF66768D)) };
    return Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: colors.$1, borderRadius: BorderRadius.circular(20)), child: Text(state.replaceAll('_', ' '), style: TextStyle(color: colors.$2, fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: .5)));
  }
}

String displayTime(dynamic value) {
  if (value == null || value.toString().isEmpty) return '—';
  final date = DateTime.tryParse(value.toString())?.toLocal();
  if (date == null) return '—';
  final hour = date.hour % 12 == 0 ? 12 : date.hour % 12;
  return '$hour:${date.minute.toString().padLeft(2, '0')} ${date.hour >= 12 ? 'PM' : 'AM'}';
}

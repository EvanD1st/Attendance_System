import 'package:attendance_mobile/core/api_client.dart';
import 'package:attendance_mobile/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeGateway implements AttendanceGateway {
  Map<String, dynamic>? restored;
  bool loginRequiresChange;
  FakeGateway({this.restored, this.loginRequiresChange = false});

  Map<String, dynamic> get user => {
    'id': 1, 'email': 'employee@example.com', 'first_name': 'Amara', 'last_name': 'Okafor',
    'role': 'employee', 'must_change_password': loginRequiresChange, 'employee_number': 'EMP-001',
  };

  @override Future<Map<String, dynamic>?> restoreSession() async => restored;
  @override Future<Map<String, dynamic>> login(String email, String password) async => user;
  @override Future<void> changePassword(String currentPassword, String newPassword) async {}
  @override Future<void> logout() async {}
  @override Future<List<Map<String, dynamic>>> history() async => [{
    'id': 1, 'work_date': '2026-09-03', 'state': 'PRESENT', 'clock_in': '2026-09-03T08:55:00Z',
    'clock_out': '2026-09-03T17:00:00Z', 'worked_minutes': 485,
  }];
  @override Future<Map<String, dynamic>> today() async => {
    'work_date': '2026-09-04', 'day_state': 'NOT_RECORDED', 'is_checked_in': false, 'is_checked_out': false,
    'attendance': null,
    'assignment': {
      'employee_name': 'Amara Okafor', 'employee_number': 'EMP-001',
      'site': {'id': 1, 'name': 'Lagos HQ'},
      'department': {'id': 1, 'name': 'Engineering'},
      'shift': {'id': 1, 'name': 'Day', 'start_time': '09:00:00', 'end_time': '17:00:00', 'grace_minutes': 15},
    },
  };
  @override Future<Map<String, dynamic>> punch({required bool clockOut, required String requestId, required String qrToken, required double latitude, required double longitude, required double accuracyMeters, required DateTime capturedAt}) async => {'state': 'PRESENT'};
}

void main() {
  testWidgets('signed-out employees see the attendance login', (tester) async {
    await tester.pumpWidget(AttendanceApp(gateway: FakeGateway()));
    await tester.pumpAndSettle();
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });

  testWidgets('authenticated employees see assigned site and scan action', (tester) async {
    final gateway = FakeGateway();
    gateway.restored = gateway.user;
    await tester.pumpWidget(AttendanceApp(gateway: gateway));
    await tester.pumpAndSettle();
    expect(find.text('Hello, Amara'), findsOneWidget);
    expect(find.text('Lagos HQ'), findsOneWidget);
    expect(find.text('Scan QR to clock in'), findsOneWidget);
  });

  testWidgets('temporary password routes to password change', (tester) async {
    final gateway = FakeGateway(loginRequiresChange: true);
    gateway.restored = gateway.user;
    await tester.pumpWidget(AttendanceApp(gateway: gateway));
    await tester.pumpAndSettle();
    expect(find.text('Secure your account'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(3));
  });
}

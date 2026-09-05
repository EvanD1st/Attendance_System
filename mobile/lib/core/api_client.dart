import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

abstract class AttendanceGateway {
  Future<Map<String, dynamic>?> restoreSession();
  Future<Map<String, dynamic>> login(String email, String password);
  Future<void> changePassword(String currentPassword, String newPassword);
  Future<Map<String, dynamic>> today();
  Future<List<Map<String, dynamic>>> history();
  Future<Map<String, dynamic>> punch({
    required bool clockOut,
    required String requestId,
    required String qrToken,
    required double latitude,
    required double longitude,
    required double accuracyMeters,
    required DateTime capturedAt,
  });
  Future<void> logout();
}

class ApiException implements Exception {
  final String message;
  final String? code;
  ApiException(this.message, {this.code});
  @override
  String toString() => message;
}

class ApiClient implements AttendanceGateway {
  static const _configuredBaseUrl = String.fromEnvironment('API_BASE_URL');
  static String get defaultBaseUrl {
    if (_configuredBaseUrl.isNotEmpty) return _configuredBaseUrl.replaceFirst(RegExp(r'/$'), '');
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:8000/api/v1';
    return 'http://localhost:8000/api/v1';
  }

  final String baseUrl;
  final http.Client httpClient;
  final FlutterSecureStorage storage;

  ApiClient({String? baseUrl, http.Client? httpClient, FlutterSecureStorage? storage})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        httpClient = httpClient ?? http.Client(),
        storage = storage ?? const FlutterSecureStorage(
          aOptions: AndroidOptions(encryptedSharedPreferences: true),
        );

  Map<String, dynamic> _object(http.Response response) {
    final decoded = jsonDecode(response.body);
    return Map<String, dynamic>.from(decoded as Map);
  }

  ApiException _error(http.Response response, String fallback) {
    try {
      final data = _object(response);
      final detail = data['detail'] ?? (data.values.firstOrNull is List ? (data.values.first as List).firstOrNull : null);
      return ApiException(detail is String ? detail : fallback, code: data['code']?.toString());
    } catch (_) {
      return ApiException(fallback);
    }
  }

  @override
  Future<Map<String, dynamic>?> restoreSession() async {
    try {
      final access = await storage.read(key: 'access');
      if (access == null) return null;
      final response = await _send('GET', '/auth/me/');
      if (response.statusCode == 200) return _object(response);
    } catch (_) {}
    try { await _clear(); } catch (_) { /* Storage may be temporarily unavailable. */ }
    return null;
  }

  @override
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await httpClient.post(
      Uri.parse('$baseUrl/auth/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email.trim(), 'password': password}),
    ).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw _error(response, 'Unable to sign in.');
    final data = _object(response);
    await storage.write(key: 'access', value: data['access'].toString());
    await storage.write(key: 'refresh', value: data['refresh'].toString());
    return Map<String, dynamic>.from(data['user'] as Map);
  }

  Future<bool> _refresh() async {
    final refresh = await storage.read(key: 'refresh');
    if (refresh == null) return false;
    final response = await httpClient.post(
      Uri.parse('$baseUrl/auth/refresh/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refresh}),
    ).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) { await _clear(); return false; }
    final data = _object(response);
    await storage.write(key: 'access', value: data['access'].toString());
    await storage.write(key: 'refresh', value: data['refresh'].toString());
    return true;
  }

  Future<http.Response> _send(String method, String path, {Map<String, dynamic>? body}) async {
    Future<http.Response> request() async {
      final access = await storage.read(key: 'access');
      if (access == null) throw ApiException('Your session has expired. Sign in again.');
      final headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer $access'};
      final uri = Uri.parse('$baseUrl$path');
      return (method == 'GET'
          ? httpClient.get(uri, headers: headers)
          : httpClient.post(uri, headers: headers, body: body == null ? null : jsonEncode(body)))
          .timeout(const Duration(seconds: 20));
    }
    var response = await request();
    if (response.statusCode == 401 && await _refresh()) response = await request();
    if (response.statusCode == 401) throw ApiException('Your session has expired. Sign in again.');
    return response;
  }

  @override
  Future<void> changePassword(String currentPassword, String newPassword) async {
    final response = await _send('POST', '/auth/change-password/', body: {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
    if (response.statusCode != 200) throw _error(response, 'Unable to change password.');
  }

  @override
  Future<Map<String, dynamic>> today() async {
    final response = await _send('GET', '/attendance/today/');
    if (response.statusCode != 200) throw _error(response, 'Unable to load today’s attendance.');
    return _object(response);
  }

  @override
  Future<List<Map<String, dynamic>>> history() async {
    final response = await _send('GET', '/attendance/history/');
    if (response.statusCode != 200) throw _error(response, 'Unable to load attendance history.');
    final decoded = jsonDecode(response.body);
    final rows = decoded is Map ? decoded['results'] as List : decoded as List;
    return rows.map((row) => Map<String, dynamic>.from(row as Map)).toList();
  }

  @override
  Future<Map<String, dynamic>> punch({
    required bool clockOut,
    required String requestId,
    required String qrToken,
    required double latitude,
    required double longitude,
    required double accuracyMeters,
    required DateTime capturedAt,
  }) async {
    final response = await _send('POST', clockOut ? '/attendance/clock-out/' : '/attendance/clock-in/', body: {
      'request_id': requestId,
      'qr_token': qrToken,
      'latitude': latitude.toStringAsFixed(6),
      'longitude': longitude.toStringAsFixed(6),
      'accuracy_meters': accuracyMeters.toStringAsFixed(2),
      'captured_at': capturedAt.toUtc().toIso8601String(),
    });
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw _error(response, clockOut ? 'Clock-out failed.' : 'Clock-in failed.');
    }
    return _object(response);
  }

  @override
  Future<void> logout() async {
    final refresh = await storage.read(key: 'refresh');
    try { if (refresh != null) await _send('POST', '/auth/logout/', body: {'refresh': refresh}); } catch (_) {}
    await _clear();
  }

  Future<void> _clear() async {
    await storage.delete(key: 'access');
    await storage.delete(key: 'refresh');
  }
}

String newRequestId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

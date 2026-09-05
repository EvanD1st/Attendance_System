import 'dart:async';
import 'dart:convert';
import 'package:attendance_mobile/core/api_client.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const storage = FlutterSecureStorage();

  setUp(() {
    FlutterSecureStorage.setMockInitialValues({
      'access': 'old-access',
      'refresh': 'old-refresh',
    });
  });

  ApiClient client(FutureOr<http.Response> Function(http.Request) handler) =>
      ApiClient(
        baseUrl: 'http://test/api/v1',
        httpClient: MockClient((request) async => handler(request)),
        storage: storage,
      );

  test('concurrent unauthorized requests rotate refresh tokens once', () async {
    var refreshCount = 0;
    var unauthorized = 0;
    final bothUnauthorized = Completer<void>();
    final gateway = client((request) async {
      if (request.url.path.endsWith('/auth/refresh/')) {
        refreshCount++;
        return http.Response(
          jsonEncode({'access': 'new-access', 'refresh': 'new-refresh'}),
          200,
        );
      }
      if (request.headers['Authorization'] == 'Bearer old-access') {
        if (++unauthorized == 2) bothUnauthorized.complete();
        await bothUnauthorized.future;
        return http.Response('{}', 401);
      }
      return http.Response(
        request.url.path.endsWith('/history/') ? '{"results":[]}' : '{}',
        200,
      );
    });
    await Future.wait<Object>([gateway.today(), gateway.history()]);
    expect(refreshCount, 1);
    expect(await storage.read(key: 'refresh'), 'new-refresh');
  });

  test('transient startup failures preserve secure tokens', () async {
    final gateway = client((_) => throw http.ClientException('offline'));
    expect(await gateway.restoreSession(), isNull);
    expect(await storage.read(key: 'refresh'), 'old-refresh');
  });

  test('failed refresh authentication clears invalid tokens', () async {
    final gateway = client((_) => http.Response('{}', 401));
    expect(await gateway.restoreSession(), isNull);
    expect(await storage.read(key: 'access'), isNull);
    expect(await storage.read(key: 'refresh'), isNull);
  });

  test('server failures during refresh do not erase saved tokens', () async {
    final gateway = client(
      (request) => http.Response(
        '{}',
        request.url.path.endsWith('/auth/refresh/') ? 503 : 401,
      ),
    );
    expect(await gateway.restoreSession(), isNull);
    expect(await storage.read(key: 'refresh'), 'old-refresh');
  });

  test(
    'logout does not rotate an expired token and clears local credentials',
    () async {
      final paths = <String>[];
      final gateway = client((request) {
        paths.add(request.url.path);
        return http.Response('{}', 401);
      });
      await gateway.logout();
      expect(paths, ['/api/v1/auth/logout/']);
      expect(await storage.read(key: 'refresh'), isNull);
    },
  );

  test('field validation messages are shown to the employee', () async {
    final gateway = client(
      (_) => http.Response(
        '{"new_password":["Choose a stronger password."]}',
        400,
      ),
    );
    await expectLater(
      gateway.changePassword('old', 'new'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.message,
          'message',
          'Choose a stronger password.',
        ),
      ),
    );
  });

  test(
    'punch requests preserve the request ID and use UTC capture timestamps',
    () async {
      const requestId = 'd82e3945-0c51-4b8f-a8ba-b81e6aabfc80';
      final gateway = client((request) {
        final body = jsonDecode(request.body) as Map;
        expect(body['request_id'], requestId);
        expect(body['captured_at'], '2026-09-01T08:00:00.000Z');
        expect(body['latitude'], '6.454100');
        expect(body['accuracy_meters'], '12.00');
        return http.Response('{"state":"PRESENT"}', 201);
      });
      expect(
        await gateway.punch(
          clockOut: false,
          requestId: requestId,
          qrToken: 'qr',
          latitude: 6.4541,
          longitude: 3.3947,
          accuracyMeters: 12,
          capturedAt: DateTime.parse('2026-09-01T09:00:00+01:00'),
        ),
        {'state': 'PRESENT'},
      );
    },
  );

  test(
    'retryable server errors are distinguishable from final scan rejections',
    () async {
      for (final status in [400, 429, 503]) {
        final gateway = client(
          (_) => http.Response('{"detail":"Scan failed"}', status),
        );
        await expectLater(
          gateway.punch(
            clockOut: false,
            requestId: newRequestId(),
            qrToken: 'qr',
            latitude: 6,
            longitude: 3,
            accuracyMeters: 12,
            capturedAt: DateTime.now(),
          ),
          throwsA(
            isA<ApiException>().having(
              (error) => error.retryable,
              'retryable',
              status != 400,
            ),
          ),
        );
      }
    },
  );
}

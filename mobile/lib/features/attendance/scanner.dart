import 'package:flutter/material.dart';
import '../../core/api_client.dart';
import '../../shared/widgets.dart';
import 'package:geolocator/geolocator.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerView extends StatefulWidget {
  final AttendanceGateway gateway;
  final bool clockOut;
  const ScannerView({super.key, required this.gateway, required this.clockOut});
  @override
  State<ScannerView> createState() => _ScannerViewState();
}

class _ScannerViewState extends State<ScannerView> {
  final controller = MobileScannerController(formats: [BarcodeFormat.qrCode]);
  bool processing = false;
  String error = '';
  Map<String, dynamic>? result;
  String requestId = newRequestId();

  Future<Position> location() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw ApiException(
        'Turn on location services and try again.',
        code: 'location_disabled',
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw ApiException(
        'Location permission is required to record attendance.',
        code: 'location_denied',
      );
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 15),
      ),
    );
  }

  Future<void> detected(BarcodeCapture capture) async {
    if (processing ||
        capture.barcodes.isEmpty ||
        capture.barcodes.first.rawValue == null) {
      return;
    }
    setState(() {
      processing = true;
      error = '';
    });
    try {
      await controller.stop();
      final position = await location();
      final data = await widget.gateway.punch(
        clockOut: widget.clockOut,
        requestId: requestId,
        qrToken: capture.barcodes.first.rawValue!,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracy,
        capturedAt: position.timestamp,
      );
      if (mounted) setState(() => result = data);
    } catch (cause) {
      if (mounted) {
        setState(() {
          error = cause.toString();
          processing = false;
          // A server rejection is final for that request ID. A transport failure
          // keeps the ID so a retry can safely recover an accepted punch response.
          if (cause is ApiException && !cause.retryable) {
            requestId = newRequestId();
          }
        });
        await controller.start();
      }
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (result != null) {
      return SuccessView(record: result!, clockOut: widget.clockOut);
    }
    return Scaffold(
      backgroundColor: navy,
      appBar: AppBar(
        backgroundColor: navy,
        foregroundColor: Colors.white,
        title: Text(widget.clockOut ? 'Clock out' : 'Clock in'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 18, 24, 22),
            child: Column(
              children: [
                Text(
                  widget.clockOut
                      ? 'Scan the site QR to finish your shift'
                      : 'Scan the site QR to start your shift',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Location is captured only when you submit attendance.',
                  style: TextStyle(color: Color(0xFF9FB0C7)),
                ),
              ],
            ),
          ),
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                MobileScanner(controller: controller, onDetect: detected),
                Center(
                  child: Container(
                    width: 270,
                    height: 270,
                    decoration: BoxDecoration(
                      border: Border.all(color: green, width: 4),
                      borderRadius: BorderRadius.circular(24),
                    ),
                  ),
                ),
                if (processing)
                  Container(
                    color: Colors.black54,
                    child: const Center(
                      child: CircularProgressIndicator(color: green),
                    ),
                  ),
              ],
            ),
          ),
          if (error.isNotEmpty)
            Padding(padding: const EdgeInsets.all(18), child: ErrorBox(error)),
        ],
      ),
    );
  }
}

class SuccessView extends StatelessWidget {
  final Map<String, dynamic> record;
  final bool clockOut;
  const SuccessView({super.key, required this.record, required this.clockOut});
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const Spacer(),
            Container(
              width: 108,
              height: 108,
              decoration: const BoxDecoration(
                color: Color(0xFFE4F8F1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_rounded, size: 62, color: green),
            ),
            const SizedBox(height: 28),
            Text(
              clockOut ? 'Clocked out' : 'Clocked in',
              style: const TextStyle(
                color: navy,
                fontSize: 32,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 9),
            const Text(
              'Your attendance was verified and recorded.',
              style: TextStyle(color: Color(0xFF718096), fontSize: 16),
            ),
            const SizedBox(height: 28),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFDDE5EF)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'TIME',
                        style: TextStyle(
                          color: Color(0xFF8793A5),
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        displayTime(
                          record[clockOut ? 'clock_out' : 'clock_in'],
                        ),
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                  StateBadge(record['state']?.toString() ?? 'PRESENT'),
                ],
              ),
            ),
            const Spacer(),
            PrimaryButton(
              label: 'Back to today',
              onPressed: () => Navigator.pop(context, true),
            ),
          ],
        ),
      ),
    ),
  );
}

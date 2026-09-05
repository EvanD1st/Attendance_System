# Attendance Control

A standalone attendance repository with a Django REST backend, React administration and kiosk portal, and an Android-first Flutter employee app. It shares no database, authentication, code imports, or synchronization with NuruX.

## Repository layout

- `backend/` — Django 5.2 LTS, Django REST Framework, SimpleJWT, OpenAPI, SQLite by default, PostgreSQL-ready.
- `web/` — React + TypeScript administration portal and full-screen rotating-QR kiosk.
- `mobile/` — Flutter Android employee client with QR scanning, live GPS capture, secure token storage, and personal history.

All timestamps are stored in UTC. Shift interpretation and work dates use the employee's assigned work-site timezone.

## Quick start

Prerequisites: Python 3.11+, Node.js 22.12+, and Flutter 3.44.8 with an Android SDK.

### 1. Backend

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt -c backend\constraints.txt
Copy-Item backend\.env.example backend\.env
python backend\manage.py migrate
python backend\manage.py seed_demo
python backend\manage.py runserver 0.0.0.0:8000
```

API documentation is available at [http://127.0.0.1:8000/api/v1/docs/](http://127.0.0.1:8000/api/v1/docs/) and the health check at [http://127.0.0.1:8000/api/v1/health/](http://127.0.0.1:8000/api/v1/health/).

To use PostgreSQL later, set `DATABASE_URL` in `backend/.env`, for example:

```text
DATABASE_URL=postgresql://attendance:password@localhost:5432/attendance
```

### 2. Web portal and kiosk

In a second terminal:

```powershell
Set-Location web
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the local Django server. To use a different backend, copy `web/.env.example` to `web/.env` and change `VITE_API_URL`.

### 3. Android employee app

With an emulator or Android device ready:

```powershell
Set-Location mobile
flutter pub get
flutter run
```

The Android emulator uses `http://10.0.2.2:8000/api/v1` by default. For a physical device or another environment:

```powershell
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/v1
```

The backend must be reachable from the device; update `ALLOWED_HOSTS` as needed for local network testing.

## Deterministic demo data

`python backend/manage.py seed_demo` is safe to run repeatedly and creates:

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@attendance.local` | `DemoAdmin!2026` |
| Manager | `manager@attendance.local` | `DemoManager!2026` |
| Employee | `employee@attendance.local` | `DemoEmployee!2026` |
| Night employee | `night@attendance.local` | `DemoNight!2026` |

Employee accounts are forced to replace their temporary password before using attendance actions. The demo kiosk is named **HQ Entrance** and receives pairing code `123456`; its device UUID is printed by the seed command.

Seeding preserves existing passwords unless `--reset-passwords` is supplied and is disabled with `DEBUG=False`. Use these public credentials only in an isolated local demo.

## Updating an existing checkout

Run `python backend/manage.py migrate` after updating. Migration `core.0004` adds random kiosk pairing identifiers; displays paired before this migration must be paired again. Administrators can issue a fresh code from Configuration → Kiosks. Existing attendance and audit records are preserved.

## Attendance rules

A clock request must contain a client UUID (`request_id`), a signed rotating kiosk QR token, latitude, longitude, accuracy, and location capture time. The API uses its own server time for the punch. It verifies active assignments, a 60-second signed site-bound QR, freshness, accuracy, geofence distance, scheduled weekdays, holidays, approved exceptions, and punch sequence.

Accepted and rejected requests create immutable audit entries without storing the raw QR token. Request UUID uniqueness and transactional record updates provide retry safety and concurrency protection. A completed punch pair produces worked minutes; missing clock-out remains a separate warning and does not replace Present/Late.

Default thresholds live in `backend/.env`:

- QR lifetime: 60 seconds
- GPS freshness: 120 seconds
- Future GPS tolerance: 30 seconds
- Maximum GPS accuracy: 100 metres
- Default timezone: `Africa/Lagos`

## Daily finalization

Run after the relevant shifts have ended:

```powershell
python backend\manage.py finalize_attendance --date 2026-09-04
```

The command is idempotent. It creates Absent records for scheduled no-shows, produces Excused records for approved exceptions, skips company/site holidays, and marks open records with a missing-clock-out warning. Omitting `--date` finalizes yesterday.

## API map

All application endpoints are below `/api/v1/`.

- `auth/` — login, refresh, logout, current user, mandatory password change.
- `attendance/` — today's employee state, history, clock-in, clock-out.
- `management/attendance/` — scoped history, summary, filters, CSV export.
- `management/attempts/` — accepted/rejected scan audit review.
- `management/exceptions/` and `management/corrections/` — admin-only audited changes.
- `management/employees/`, `departments/`, `sites/`, `shifts/`, `holidays/`, `manager-scopes/`, `kiosks/` — administration resources.
- `kiosk/pair/` and `kiosk/devices/<device-id>/qr/` — device pairing and rotating tokens.

Administrators can manage configuration and correct attendance. Managers are read-only and their records/configuration views are limited to assigned sites or departments. Employees can access only their own attendance endpoints.

## Validation

```powershell
# Backend
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py test core attendance_app
.\.venv\Scripts\python.exe backend\manage.py spectacular --file backend\schema.yml --validate

# Web
Set-Location web
npm run lint
npm test
npm run build

# Mobile
Set-Location mobile
flutter analyze
flutter test
```

The backend test suite covers role and scope boundaries, forced password change, pairing and revocation, QR validation, geofence edges, GPS freshness/accuracy, cross-site rejection, idempotency conflicts, grace thresholds, overnight shifts, holidays, exceptions, absence finalization, correction snapshots, and filtered CSV output. Web and Flutter suites exercise their key permission and authentication flows with isolated clients.

Run the CI-equivalent checks from the repository root with `python scripts/check.py backend`, `python scripts/check.py web`, or `python scripts/check.py mobile`. Activate the virtual environment first. Backend checks include lint, formatting, migration drift, tests, and OpenAPI validation. CI also tests PostgreSQL and builds an Android debug APK; local SQLite tests do not substitute for PostgreSQL or physical-device camera/GPS acceptance.

## Production boundary

SQLite and the checked-in demo settings are for local/demo use only. Before production, use PostgreSQL, a secret manager, HTTPS, strict host/origin configuration, production static serving, external monitoring, database backups, and a real scheduler for the daily finalizer. Payroll, leave, remote/offline attendance, overtime, half-days, biometrics, face recognition, push notifications, iOS release work, NuruX integration, and cloud deployment are intentionally out of scope.

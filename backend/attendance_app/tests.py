import uuid
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone

from core.models import (
    Department,
    Employee,
    Holiday,
    KioskDevice,
    ManagerScope,
    Shift,
    User,
    WorkSite,
)
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import AdminException, AttendanceAttempt, AttendanceCorrection, AttendanceRecord
from .services import finalize_attendance, record_state, scheduled_bounds


class AttendanceTestCase(APITestCase):
    def setUp(self):
        self.site = WorkSite.objects.create(
            name="HQ",
            latitude="6.454100",
            longitude="3.394700",
            geofence_radius_meters=200,
            timezone="Africa/Lagos",
        )
        self.other_site = WorkSite.objects.create(
            name="Annex",
            latitude="6.601800",
            longitude="3.351500",
            geofence_radius_meters=100,
            timezone="Africa/Lagos",
        )
        self.department = Department.objects.create(name="Engineering")
        local_now = timezone.localtime(timezone.now())
        self.shift = Shift.objects.create(
            name="Always open test shift",
            start_time=(local_now - timedelta(hours=2)).time().replace(microsecond=0),
            end_time=(local_now + timedelta(hours=2)).time().replace(microsecond=0),
            grace_minutes=15,
            working_weekdays=list(range(7)),
        )
        self.user = User.objects.create_user(
            username="employee@example.com",
            email="employee@example.com",
            password="ValidPass!234",
            first_name="Ada",
            last_name="Okoro",
            role=User.Role.EMPLOYEE,
            must_change_password=False,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            employee_number="EMP-1",
            department=self.department,
            work_site=self.site,
            shift=self.shift,
        )
        self.kiosk = KioskDevice.objects.create(name="Entrance", site=self.site)
        self.kiosk.set_credential("test-kiosk-credential")
        self.kiosk.save()
        self.kiosk.is_active = True
        self.client.force_authenticate(self.user)

    def qr(self, kiosk=None, expired=False):
        kiosk = kiosk or self.kiosk
        if not kiosk.paired_at:
            kiosk.set_credential("test-kiosk-credential")
            kiosk.save()
        token = AccessToken()
        token["kind"] = "attendance_qr"
        token["kiosk_id"] = str(kiosk.pk)
        token["site_id"] = kiosk.site_id
        token["pairing_id"] = str(kiosk.pairing_id)
        if expired:
            token.set_exp(
                from_time=timezone.now() - timedelta(minutes=2), lifetime=timedelta(seconds=1)
            )
        return str(token)

    def payload(self, **overrides):
        data = {
            "request_id": str(uuid.uuid4()),
            "qr_token": self.qr(),
            "latitude": "6.454100",
            "longitude": "3.394700",
            "accuracy_meters": "12.00",
            "captured_at": timezone.now().isoformat(),
        }
        data.update(overrides)
        return data

    def test_clock_in_out_and_idempotent_replay(self):
        payload = self.payload()
        first = self.client.post(reverse("attendance-clock-in"), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        replay = self.client.post(reverse("attendance-clock-in"), payload, format="json")
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data["idempotent_replay"])
        out = self.client.post(reverse("attendance-clock-out"), self.payload(), format="json")
        self.assertEqual(out.status_code, status.HTTP_200_OK, out.data)
        self.assertIsNotNone(out.data["worked_minutes"])
        self.assertEqual(AttendanceAttempt.objects.filter(accepted=True).count(), 2)

    def test_outside_geofence_is_hard_rejected_and_logged_without_raw_token(self):
        response = self.client.post(
            reverse("attendance-clock-in"),
            self.payload(latitude="7.000000", longitude="4.000000"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "outside_geofence")
        self.assertFalse(AttendanceRecord.objects.exists())
        attempt = AttendanceAttempt.objects.get()
        self.assertFalse(attempt.accepted)
        self.assertGreater(attempt.distance_meters, self.site.geofence_radius_meters)
        self.assertFalse(hasattr(attempt, "qr_token"))

    def test_stale_inaccurate_expired_and_cross_site_scans_are_rejected(self):
        cases = [
            (
                self.payload(captured_at=(timezone.now() - timedelta(minutes=5)).isoformat()),
                "stale_location",
            ),
            (self.payload(accuracy_meters="150.00"), "poor_accuracy"),
            (self.payload(qr_token=self.qr(expired=True)), "invalid_qr"),
        ]
        other_kiosk = KioskDevice.objects.create(name="Other", site=self.other_site)
        cases.append((self.payload(qr_token=self.qr(other_kiosk)), "wrong_site"))
        for payload, expected in cases:
            response = self.client.post(reverse("attendance-clock-in"), payload, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], expected)

    def test_geofence_boundary_tampering_revocation_and_rejected_replay(self):
        near_edge = self.payload(latitude="6.455880")
        accepted = self.client.post(reverse("attendance-clock-in"), near_edge, format="json")
        self.assertEqual(accepted.status_code, 201, accepted.data)

        outside = self.payload(latitude="6.455920")
        first = self.client.post(reverse("attendance-clock-out"), outside, format="json")
        self.assertEqual(first.status_code, 400)
        self.assertEqual(first.data["code"], "outside_geofence")
        attempt_count = AttendanceAttempt.objects.count()
        replay = self.client.post(reverse("attendance-clock-out"), outside, format="json")
        self.assertEqual(replay.data["code"], "outside_geofence")
        self.assertEqual(AttendanceAttempt.objects.count(), attempt_count)

        token = self.qr()
        header, payload, signature = token.split(".")
        tampered = ".".join(
            [header, payload, ("a" if signature[0] != "a" else "b") + signature[1:]]
        )
        invalid = self.client.post(
            reverse("attendance-clock-out"), self.payload(qr_token=tampered), format="json"
        )
        self.assertEqual(invalid.data["code"], "invalid_qr")

        valid_before_revocation = self.qr()
        self.kiosk.is_active = False
        self.kiosk.save(update_fields=["is_active"])
        revoked = self.client.post(
            reverse("attendance-clock-out"),
            self.payload(qr_token=valid_before_revocation),
            format="json",
        )
        self.assertEqual(revoked.data["code"], "inactive_kiosk")

    def test_unscheduled_holiday_future_location_and_idempotency_conflict(self):
        current_weekday = timezone.localtime(timezone.now()).date().weekday()
        self.shift.working_weekdays = [(current_weekday + 1) % 7]
        self.shift.save(update_fields=["working_weekdays"])
        unscheduled = self.client.post(
            reverse("attendance-clock-in"), self.payload(), format="json"
        )
        self.assertEqual(unscheduled.data["code"], "not_scheduled")

        self.shift.working_weekdays = list(range(7))
        self.shift.save(update_fields=["working_weekdays"])
        Holiday.objects.create(name="Today", date=timezone.localdate())
        holiday = self.client.post(reverse("attendance-clock-in"), self.payload(), format="json")
        self.assertEqual(holiday.data["code"], "holiday")
        Holiday.objects.all().delete()

        future = self.client.post(
            reverse("attendance-clock-in"),
            self.payload(captured_at=(timezone.now() + timedelta(minutes=2)).isoformat()),
            format="json",
        )
        self.assertEqual(future.data["code"], "future_location")

        request_id = str(uuid.uuid4())
        clock_in = self.client.post(
            reverse("attendance-clock-in"), self.payload(request_id=request_id), format="json"
        )
        self.assertEqual(clock_in.status_code, 201)
        conflict = self.client.post(
            reverse("attendance-clock-out"), self.payload(request_id=request_id), format="json"
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data["code"], "idempotency_conflict")

    def test_status_grace_and_overnight_bounds(self):
        start = datetime(2026, 9, 1, 8, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(
            record_state(start + timedelta(minutes=15), start, 15), AttendanceRecord.State.PRESENT
        )
        self.assertEqual(
            record_state(start + timedelta(minutes=16), start, 15), AttendanceRecord.State.LATE
        )
        overnight = Shift.objects.create(
            name="Overnight",
            start_time=time(22),
            end_time=time(6),
            grace_minutes=10,
            working_weekdays=list(range(7)),
        )
        self.employee.shift = overnight
        self.employee.save(update_fields=["shift"])
        scheduled_start, scheduled_end = scheduled_bounds(self.employee, date(2026, 9, 1))
        self.assertEqual((scheduled_end - scheduled_start).total_seconds(), 8 * 3600)

    def test_finalizer_creates_absent_skips_holiday_and_marks_missing_out(self):
        work_date = date(2026, 9, 1)
        past_shift = Shift.objects.create(
            name="Historic",
            start_time=time(9),
            end_time=time(17),
            grace_minutes=15,
            working_weekdays=list(range(7)),
        )
        self.employee.shift = past_shift
        self.employee.save(update_fields=["shift"])
        counts = finalize_attendance(work_date, now=datetime(2026, 9, 3, tzinfo=dt_timezone.utc))
        self.assertEqual(counts["absent_created"], 1)
        self.assertEqual(AttendanceRecord.objects.get().state, AttendanceRecord.State.ABSENT)
        second = finalize_attendance(work_date, now=datetime(2026, 9, 3, tzinfo=dt_timezone.utc))
        self.assertEqual(second["absent_created"], 0)

        Holiday.objects.create(name="Holiday", date=date(2026, 9, 2))
        finalize_attendance(date(2026, 9, 2), now=datetime(2026, 9, 4, tzinfo=dt_timezone.utc))
        self.assertFalse(AttendanceRecord.objects.filter(work_date=date(2026, 9, 2)).exists())

        AdminException.objects.create(
            employee=self.employee,
            date=date(2026, 9, 3),
            reason="Approved appointment",
            approved_by=self.user,
        )
        finalize_attendance(date(2026, 9, 3), now=datetime(2026, 9, 5, tzinfo=dt_timezone.utc))
        self.assertEqual(
            AttendanceRecord.objects.get(work_date=date(2026, 9, 3)).state,
            AttendanceRecord.State.EXCUSED,
        )

    def test_admin_correction_recalculates_and_audits(self):
        admin = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="ValidPass!234",
            role=User.Role.ADMIN,
            must_change_password=False,
        )
        self.client.force_authenticate(admin)
        start, _ = scheduled_bounds(self.employee, timezone.localdate())
        response = self.client.post(
            reverse("correction-list"),
            {
                "employee": self.employee.pk,
                "work_date": timezone.localdate().isoformat(),
                "clock_in": (start + timedelta(minutes=20)).isoformat(),
                "clock_out": (start + timedelta(hours=8)).isoformat(),
                "reason": "Verified paper register",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.state, AttendanceRecord.State.LATE)
        self.assertEqual(record.worked_minutes, 460)
        correction = AttendanceCorrection.objects.get()
        self.assertEqual(correction.before_data, {})
        self.assertEqual(correction.after_data["state"], "LATE")


class ScopeAndReportingTests(APITestCase):
    def setUp(self):
        self.site = WorkSite.objects.create(
            name="HQ", latitude="6", longitude="3", timezone="Africa/Lagos"
        )
        self.other = WorkSite.objects.create(
            name="Other", latitude="7", longitude="4", timezone="Africa/Lagos"
        )
        self.dept = Department.objects.create(name="Ops")
        self.shift = Shift.objects.create(
            name="Day", start_time=time(9), end_time=time(17), working_weekdays=list(range(7))
        )
        self.manager = User.objects.create_user(
            username="m@example.com",
            email="m@example.com",
            password="Pass!23456",
            role=User.Role.MANAGER,
            must_change_password=False,
        )
        ManagerScope.objects.create(manager=self.manager, site=self.site)
        self.inside = self.employee("inside@example.com", "IN", self.site)
        self.outside = self.employee("outside@example.com", "OUT", self.other)
        for employee in [self.inside, self.outside]:
            start, end = scheduled_bounds(employee, date(2026, 9, 1))
            AttendanceRecord.objects.create(
                employee=employee,
                work_date=date(2026, 9, 1),
                site=employee.work_site,
                shift=self.shift,
                scheduled_start=start,
                scheduled_end=end,
                state=AttendanceRecord.State.PRESENT,
            )
        self.client.force_authenticate(self.manager)

    def employee(self, email, number, site):
        user = User.objects.create_user(
            username=email, email=email, password="Pass!23456", must_change_password=False
        )
        return Employee.objects.create(
            user=user,
            employee_number=number,
            department=self.dept,
            work_site=site,
            shift=self.shift,
        )

    def test_manager_scope_and_csv_filter(self):
        response = self.client.get(reverse("management-attendance-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["employee_number"], "IN")
        export = self.client.get(
            reverse("management-attendance-export-csv"), {"site": self.site.pk}
        )
        self.assertEqual(export.status_code, 200)
        body = export.content.decode()
        self.assertIn("IN", body)
        self.assertNotIn("OUT", body)

    def test_manager_configuration_scope_is_read_only_and_employee_cannot_use_management_api(self):
        other_department = Department.objects.create(name="Private")
        other_shift = Shift.objects.create(
            name="Private shift",
            start_time=time(10),
            end_time=time(18),
            working_weekdays=list(range(7)),
        )
        self.outside.department = other_department
        self.outside.shift = other_shift
        self.outside.save(update_fields=["department", "shift"])
        Holiday.objects.create(name="Company day", date=date(2026, 10, 1))
        Holiday.objects.create(name="HQ day", date=date(2026, 10, 2), site=self.site)
        Holiday.objects.create(name="Other day", date=date(2026, 10, 3), site=self.other)

        sites = self.client.get(reverse("site-list"))
        self.assertEqual([item["name"] for item in sites.data["results"]], ["HQ"])
        departments = self.client.get(reverse("department-list"))
        self.assertEqual([item["name"] for item in departments.data["results"]], ["Ops"])
        shifts = self.client.get(reverse("shift-list"))
        self.assertEqual([item["name"] for item in shifts.data["results"]], ["Day"])
        holidays = self.client.get(reverse("holiday-list"))
        self.assertEqual(
            {item["name"] for item in holidays.data["results"]}, {"Company day", "HQ day"}
        )
        scopes = self.client.get(reverse("manager-scope-list"))
        self.assertEqual(scopes.data["count"], 1)
        self.assertEqual(self.client.post(reverse("site-list"), {}, format="json").status_code, 403)
        self.assertEqual(
            self.client.post(reverse("correction-list"), {}, format="json").status_code, 403
        )

        self.client.force_authenticate(self.inside.user)
        self.assertEqual(self.client.get(reverse("management-attendance-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("attempt-list")).status_code, 403)

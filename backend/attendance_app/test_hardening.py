"""Regression tests for trust boundaries and real database contention."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from core.models import User
from django.contrib import admin
from django.db import connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from . import tests as fixtures
from .models import AttendanceAttempt, AttendanceCorrection, AttendanceRecord
from .serializers import PunchSerializer
from .services import PunchError, process_punch


class HardeningTests(APITestCase):
    setUp = fixtures.AttendanceTestCase.setUp
    qr = fixtures.AttendanceTestCase.qr
    payload = fixtures.AttendanceTestCase.payload

    def administrator(self):
        user = User.objects.create_user(
            username="admin-hardening@example.com",
            email="admin-hardening@example.com",
            password="TestPassword!234",
            role=User.Role.ADMIN,
            must_change_password=False,
        )
        self.client.force_authenticate(user)
        return user

    def test_revocation_invalidates_already_issued_qr_without_deactivating_device(self):
        token = self.qr()
        self.administrator()
        response = self.client.post(reverse("kiosk-revoke", args=[self.kiosk.pk]))
        self.assertEqual(response.status_code, 200)
        self.kiosk.refresh_from_db()
        self.assertTrue(self.kiosk.is_active)
        self.client.force_authenticate(self.user)
        rejected = self.client.post(
            reverse("attendance-clock-in"), self.payload(qr_token=token), format="json"
        )
        self.assertEqual(rejected.data["code"], "revoked_qr")
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertEqual(AttendanceAttempt.objects.get().reason_code, "revoked_qr")

    def test_repairing_invalidates_previous_pairing_qr(self):
        old_token = self.qr()
        self.kiosk.set_credential("replacement-credential")
        self.kiosk.save()
        response = self.client.post(
            reverse("attendance-clock-in"), self.payload(qr_token=old_token), format="json"
        )
        self.assertEqual(response.data["code"], "revoked_qr")

    def test_public_kiosk_authentication_ignores_expired_portal_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer expired-portal-token")
        response = client.get(
            reverse("kiosk-qr", args=[self.kiosk.pk]),
            HTTP_X_KIOSK_CREDENTIAL="test-kiosk-credential",
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_with_temporary_password_cannot_create_employee(self):
        user = self.administrator()
        user.must_change_password = True
        user.save()
        self.assertEqual(self.client.post(reverse("employee-list"), {}).status_code, 403)

    def test_employee_response_exposes_account_id_for_manager_scopes(self):
        self.administrator()
        response = self.client.get(reverse("employee-detail", args=[self.employee.pk]))
        self.assertEqual(response.data["user"], self.user.pk)

    def test_every_correction_preserves_previous_snapshot(self):
        response = self.client.post(reverse("attendance-clock-in"), self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        original = AttendanceRecord.objects.get()
        administrator = self.administrator()
        clock_in = original.scheduled_start
        for minutes in (0, 20):
            response = self.client.post(
                reverse("correction-list"),
                {
                    "employee": self.employee.pk,
                    "work_date": original.work_date,
                    "clock_in": (clock_in + timedelta(minutes=minutes)).isoformat(),
                    "clock_out": None,
                    "reason": "Verified against signed register",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
        corrections = list(AttendanceCorrection.objects.order_by("created_at", "pk"))
        self.assertEqual(corrections[0].before_data["clock_in"], original.clock_in.isoformat())
        self.assertEqual(corrections[1].before_data, corrections[0].after_data)
        self.assertEqual(corrections[1].after_data["state"], "LATE")
        self.assertEqual(corrections[1].corrected_by, administrator)
        self.assertFalse(corrections[1].after_data["missing_clock_out"])
        self.assertEqual(
            self.client.patch(
                reverse("correction-detail", args=[corrections[0].pk]), {}
            ).status_code,
            405,
        )

    def test_django_admin_cannot_mutate_attendance_outside_correction_api(self):
        model_admin = admin.site._registry[AttendanceRecord]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertIn("clock_in", model_admin.get_readonly_fields(None))


class PunchConcurrencyTests(TransactionTestCase):
    """Separate connections start together, exercising locks instead of mocks."""

    qr = fixtures.AttendanceTestCase.qr
    payload = fixtures.AttendanceTestCase.payload

    def setUp(self):
        self.client = APIClient()
        fixtures.AttendanceTestCase.setUp(self)

    def parsed_payload(self):
        serializer = PunchSerializer(data=self.payload())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def race(self, payloads, action=AttendanceAttempt.Action.CLOCK_IN):
        barrier = Barrier(2)

        def punch(payload):
            try:
                barrier.wait(timeout=10)
                try:
                    _, replay = process_punch(self.employee, action, payload)
                    return "replay" if replay else "accepted"
                except PunchError as error:
                    return error.code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(punch, payloads))

    def test_same_request_id_is_accepted_once_under_contention(self):
        payload = self.parsed_payload()
        self.assertCountEqual(self.race([payload, payload]), ["accepted", "replay"])
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceAttempt.objects.count(), 1)

    def test_competing_clock_ins_do_not_overwrite_and_rejection_is_audited(self):
        results = self.race([self.parsed_payload(), self.parsed_payload()])
        self.assertCountEqual(results, ["accepted", "already_clocked_in"])
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceAttempt.objects.filter(accepted=True).count(), 1)
        self.assertEqual(AttendanceAttempt.objects.filter(accepted=False).count(), 1)

    def test_competing_clock_outs_produce_only_one_accepted_punch(self):
        process_punch(self.employee, AttendanceAttempt.Action.CLOCK_IN, self.parsed_payload())
        results = self.race(
            [self.parsed_payload(), self.parsed_payload()], AttendanceAttempt.Action.CLOCK_OUT
        )
        self.assertCountEqual(results, ["accepted", "not_clocked_in"])
        self.assertEqual(AttendanceAttempt.objects.filter(accepted=True).count(), 2)
        self.assertIsNotNone(AttendanceRecord.objects.get().clock_out)

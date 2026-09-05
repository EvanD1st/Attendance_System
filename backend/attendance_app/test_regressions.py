import csv
import io

from core.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from . import test_hardening as fixtures
from .models import AttendanceRecord


class ApiRegressionTests(APITestCase):
    setUp = fixtures.HardeningTests.setUp
    qr = fixtures.HardeningTests.qr
    payload = fixtures.HardeningTests.payload
    administrator = fixtures.HardeningTests.administrator

    def employee_data(self, **overrides):
        return {
            "email": "new@example.com",
            "first_name": "New",
            "last_name": "Person",
            "temporary_password": "StrongPass!234",
            "employee_number": "NEW-1",
            "department": self.department.pk,
            "work_site": self.site.pk,
            "shift": self.shift.pk,
            **overrides,
        }

    def test_creating_an_inactive_employee_also_disables_login(self):
        self.administrator()
        response = self.client.post(
            reverse("employee-list"), self.employee_data(is_active=False), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(User.objects.get(email="new@example.com").is_active)
        response = self.client.post(
            reverse("login"),
            {"email": "new@example.com", "password": "StrongPass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_email_changes_release_the_old_login_identifier(self):
        self.administrator()
        old_email = self.user.email
        response = self.client.patch(
            reverse("employee-detail", args=[self.employee.pk]),
            {"email": "renamed@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed@example.com")
        response = self.client.post(
            reverse("employee-list"), self.employee_data(email=old_email), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_legacy_username_collisions_are_validation_errors(self):
        self.administrator()
        User.objects.create_user(username="reserved@example.com", email="other@example.com")
        response = self.client.post(
            reverse("employee-list"),
            self.employee_data(email="reserved@example.com"),
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_malformed_filters_are_client_errors_for_history_summary_and_csv(self):
        self.administrator()
        for endpoint in (
            "management-attendance-list",
            "management-attendance-summary",
            "management-attendance-export-csv",
        ):
            for query in (
                {"from": "not-a-date"},
                {"to": "2026-99-99"},
                {"site": "not-an-id"},
                {"department": "-1"},
                {"employee": "x"},
                {"state": "unknown"},
                {"missing_clock_out": "perhaps"},
                {"from": "2026-09-05", "to": "2026-09-01"},
            ):
                with self.subTest(endpoint=endpoint, query=query):
                    response = self.client.get(reverse(endpoint), query)
                    self.assertEqual(response.status_code, 400, response.data)

    def test_csv_neutralizes_spreadsheet_formulas_without_mutating_records(self):
        response = self.client.post(reverse("attendance-clock-in"), self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.user.first_name = "=1+1"
        self.user.save()
        self.department.name = "  @SUM(A1)"
        self.department.save()
        self.administrator()
        response = self.client.get(reverse("management-attendance-export-csv"))
        self.assertEqual(response.status_code, 200)
        row = list(csv.reader(io.StringIO(response.content.decode())))[1]
        self.assertTrue(row[2].startswith("'="))
        self.assertTrue(row[3].startswith("'  @"))
        self.assertEqual(AttendanceRecord.objects.get().employee.department.name, "  @SUM(A1)")

    def test_missing_and_null_refresh_tokens_return_validation_errors(self):
        for endpoint in ("refresh", "logout"):
            for body in ({}, {"refresh": None}, {"refresh": ""}):
                with self.subTest(endpoint=endpoint, body=body):
                    response = self.client.post(reverse(endpoint), body, format="json")
                    self.assertEqual(response.status_code, 400, response.data)

    def test_logout_cannot_blacklist_another_accounts_refresh_token(self):
        employee_token = str(RefreshToken.for_user(self.user))
        self.administrator()
        response = self.client.post(reverse("logout"), {"refresh": employee_token}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(str(RefreshToken(employee_token)), employee_token)

    def test_legacy_kiosk_credentials_require_repairing(self):
        self.kiosk.pairing_id = None
        self.kiosk.save()
        self.client.force_authenticate(None)
        response = self.client.get(
            reverse("kiosk-qr", args=[self.kiosk.pk]),
            HTTP_X_KIOSK_CREDENTIAL="test-kiosk-credential",
        )
        self.assertEqual(response.status_code, 401)

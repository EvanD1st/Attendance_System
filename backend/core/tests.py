from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import KioskDevice, User, WorkSite


class AuthenticationAndKioskTests(APITestCase):
    def test_login_and_required_password_change(self):
        user = User.objects.create_user(
            username="person@example.com",
            email="person@example.com",
            password="OldPass!234",
            must_change_password=True,
        )
        login = self.client.post(
            reverse("login"), {"email": user.email, "password": "OldPass!234"}, format="json"
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        blocked = self.client.get(reverse("attendance-history"))
        self.assertEqual(blocked.status_code, 403)
        changed = self.client.post(
            reverse("change-password"),
            {"current_password": "OldPass!234", "new_password": "NewPass!567"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)

    def test_kiosk_pairing_is_single_use_and_revocable(self):
        site = WorkSite.objects.create(name="HQ", latitude="6", longitude="3")
        kiosk = KioskDevice.objects.create(name="Door", site=site)
        kiosk.set_pairing_code("123456", timezone.now() + timedelta(minutes=10))
        kiosk.save()
        paired = self.client.post(
            reverse("kiosk-pair"), {"device_id": kiosk.pk, "pairing_code": "123456"}, format="json"
        )
        self.assertEqual(paired.status_code, 200)
        reused = self.client.post(
            reverse("kiosk-pair"), {"device_id": kiosk.pk, "pairing_code": "123456"}, format="json"
        )
        self.assertEqual(reused.status_code, 400)
        qr = self.client.get(
            reverse("kiosk-qr", args=[kiosk.pk]), HTTP_X_KIOSK_CREDENTIAL=paired.data["credential"]
        )
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr.data["expires_in_seconds"], 60)

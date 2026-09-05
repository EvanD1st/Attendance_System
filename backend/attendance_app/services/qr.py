from core.models import KioskDevice
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from .errors import PunchError


def parse_qr(qr_token):
    try:
        token = UntypedToken(qr_token)
    except TokenError as exc:
        raise PunchError("invalid_qr", "QR code is invalid or has expired.") from exc
    if token.get("kind") != "attendance_qr":
        raise PunchError("invalid_qr", "QR code is not an attendance token.")
    try:
        kiosk = (
            KioskDevice.objects.select_related("site")
            .filter(pk=token.get("kiosk_id"), is_active=True)
            .first()
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise PunchError("invalid_qr", "QR code contains an invalid kiosk identifier.") from exc
    if not kiosk or not kiosk.site.is_active or str(kiosk.site_id) != str(token.get("site_id")):
        raise PunchError("inactive_kiosk", "Kiosk or work site is no longer active.")
    if (
        not kiosk.credential_hash
        or not kiosk.paired_at
        or not kiosk.pairing_id
        or token.get("pairing_id") != str(kiosk.pairing_id)
    ):
        raise PunchError(
            "revoked_qr",
            "This QR belongs to a revoked kiosk pairing. Scan the current display.",
            kiosk=kiosk,
        )
    return kiosk

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminExceptionViewSet,
    AttemptViewSet,
    AttendanceManagementViewSet,
    CorrectionViewSet,
    EmployeeAttendanceViewSet,
    KioskQRView,
)

router = DefaultRouter()
router.register("attendance", EmployeeAttendanceViewSet, basename="attendance")
router.register(
    "management/attendance", AttendanceManagementViewSet, basename="management-attendance"
)
router.register("management/attempts", AttemptViewSet, basename="attempt")
router.register("management/exceptions", AdminExceptionViewSet, basename="exception")
router.register("management/corrections", CorrectionViewSet, basename="correction")

urlpatterns = [
    path("kiosk/devices/<uuid:device_id>/qr/", KioskQRView.as_view(), name="kiosk-qr"),
    path("", include(router.urls)),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    DepartmentViewSet,
    EmployeeViewSet,
    HealthView,
    HolidayViewSet,
    KioskDeviceViewSet,
    KioskPairView,
    LoginView,
    LogoutView,
    ManagerScopeViewSet,
    MeView,
    RefreshView,
    ShiftViewSet,
    WorkSiteViewSet,
)

router = DefaultRouter()
router.register("management/sites", WorkSiteViewSet, basename="site")
router.register("management/departments", DepartmentViewSet, basename="department")
router.register("management/shifts", ShiftViewSet, basename="shift")
router.register("management/holidays", HolidayViewSet, basename="holiday")
router.register("management/employees", EmployeeViewSet, basename="employee")
router.register("management/manager-scopes", ManagerScopeViewSet, basename="manager-scope")
router.register("management/kiosks", KioskDeviceViewSet, basename="kiosk")

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("kiosk/pair/", KioskPairView.as_view(), name="kiosk-pair"),
    path("", include(router.urls)),
]

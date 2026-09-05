import secrets
from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Department, Employee, Holiday, KioskDevice, ManagerScope, Shift, User, WorkSite
from .permissions import IsAdministrator, IsAdminWriteManagerRead, PasswordChanged
from .serializers import (
    ChangePasswordSerializer,
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeWriteSerializer,
    HolidaySerializer,
    KioskDeviceSerializer,
    KioskPairSerializer,
    LoginSerializer,
    ManagerScopeSerializer,
    RefreshTokenSerializer,
    ShiftSerializer,
    UserSummarySerializer,
    WorkSiteSerializer,
)


def user_payload(user):
    data = UserSummarySerializer(user).data
    employee = getattr(user, "employee_profile", None)
    data["employee_id"] = employee.pk if employee else None
    data["employee_number"] = employee.employee_number if employee else None
    return data


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        request=LoginSerializer,
        responses=inline_serializer(
            name="LoginResponse",
            fields={
                "access": drf_serializers.CharField(),
                "refresh": drf_serializers.CharField(),
                "user": UserSummarySerializer(),
            },
        ),
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        authenticated = (
            authenticate(
                request, username=user.username, password=serializer.validated_data["password"]
            )
            if user
            else None
        )
        if not authenticated or not authenticated.is_active:
            return Response(
                {"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED
            )
        refresh = RefreshToken.for_user(authenticated)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_payload(authenticated),
            }
        )


class HealthView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses=inline_serializer(
            name="HealthResponse", fields={"status": drf_serializers.CharField()}
        ),
        auth=[],
    )
    def get(self, request):
        return Response({"status": "ok"})


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        request=RefreshTokenSerializer,
        responses=inline_serializer(
            name="RefreshResponse",
            fields={"access": drf_serializers.CharField(), "refresh": drf_serializers.CharField()},
        ),
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            user = User.objects.get(pk=refresh["user_id"], is_active=True)
            refresh.blacklist()
            rotated = RefreshToken.for_user(user)
        except (TokenError, User.DoesNotExist):
            return Response(
                {"detail": "Refresh token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"access": str(rotated.access_token), "refresh": str(rotated)})


class LogoutView(APIView):
    @extend_schema(request=RefreshTokenSerializer, responses={204: None})
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            if str(refresh["user_id"]) != str(request.user.pk):
                return Response({"detail": "Refresh token belongs to another account."}, status=400)
            refresh.blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSummarySerializer)
    def get(self, request):
        return Response(user_payload(request.user))


class ChangePasswordView(APIView):
    @extend_schema(
        request=ChangePasswordSerializer,
        responses=inline_serializer(
            name="PasswordChangedResponse", fields={"detail": drf_serializers.CharField()}
        ),
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response({"current_password": ["Current password is incorrect."]}, status=400)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        return Response({"detail": "Password changed successfully."})


class ManagedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminWriteManagerRead, PasswordChanged]
    http_method_names = ["get", "post", "patch", "head", "options"]


class WorkSiteViewSet(ManagedModelViewSet):
    queryset = WorkSite.objects.all()
    serializer_class = WorkSiteSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.MANAGER and not self.request.user.is_superuser:
            return queryset.filter(manager_scopes__manager=self.request.user).distinct()
        return queryset


class DepartmentViewSet(ManagedModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role != User.Role.MANAGER or user.is_superuser:
            return queryset
        allowed = Q(pk__in=[])
        for scope in user.manager_scopes.all():
            if scope.department_id:
                allowed |= Q(pk=scope.department_id)
            else:
                allowed |= Q(employees__work_site=scope.site)
        return queryset.filter(allowed).distinct()


class ShiftViewSet(ManagedModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role != User.Role.MANAGER or user.is_superuser:
            return queryset
        employees = Employee.objects.none()
        for scope in user.manager_scopes.all():
            scoped = Employee.objects.filter(work_site=scope.site)
            if scope.department_id:
                scoped = scoped.filter(department=scope.department)
            employees = employees | scoped
        return queryset.filter(employees__in=employees).distinct()


class HolidayViewSet(ManagedModelViewSet):
    queryset = Holiday.objects.select_related("site")
    serializer_class = HolidaySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == User.Role.MANAGER and not user.is_superuser:
            return queryset.filter(
                Q(site__isnull=True) | Q(site__manager_scopes__manager=user)
            ).distinct()
        return queryset


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    permission_classes = [permissions.IsAuthenticated, PasswordChanged]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        return (
            EmployeeWriteSerializer
            if self.action in {"create", "partial_update"}
            else EmployeeSerializer
        )

    def get_permissions(self):
        if self.action in {"create", "partial_update"}:
            return [IsAdministrator(), PasswordChanged()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Employee.objects.select_related("user", "department", "work_site", "shift")
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return queryset
        if user.role == User.Role.MANAGER:
            scope_filter = Q(pk__in=[])
            for scope in user.manager_scopes.all():
                item = Q(work_site=scope.site)
                if scope.department_id:
                    item &= Q(department=scope.department)
                scope_filter |= item
            return queryset.filter(scope_filter).distinct()
        employee = getattr(user, "employee_profile", None)
        return queryset.filter(pk=employee.pk) if employee else queryset.none()


class ManagerScopeViewSet(ManagedModelViewSet):
    queryset = ManagerScope.objects.select_related("manager", "site", "department")
    serializer_class = ManagerScopeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.MANAGER and not self.request.user.is_superuser:
            return queryset.filter(manager=self.request.user)
        return queryset


class KioskDeviceViewSet(viewsets.ModelViewSet):
    queryset = KioskDevice.objects.select_related("site")
    serializer_class = KioskDeviceSerializer
    permission_classes = [IsAdministrator, PasswordChanged]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=True, methods=["post"], url_path="pairing-code")
    def pairing_code(self, request, pk=None):
        kiosk = self.get_object()
        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = timezone.now() + timedelta(minutes=10)
        kiosk.set_pairing_code(code, expires_at)
        kiosk.save(update_fields=["pairing_code_hash", "pairing_expires_at"])
        return Response({"device_id": kiosk.pk, "pairing_code": code, "expires_at": expires_at})

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        kiosk = self.get_object()
        kiosk.credential_hash = ""
        kiosk.pairing_code_hash = ""
        kiosk.pairing_expires_at = None
        kiosk.paired_at = None
        kiosk.pairing_id = None
        kiosk.save(
            update_fields=[
                "credential_hash",
                "pairing_code_hash",
                "pairing_expires_at",
                "paired_at",
                "pairing_id",
            ]
        )
        return Response({"detail": "Kiosk credential revoked."})


class KioskPairView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "kiosk"

    @extend_schema(
        request=KioskPairSerializer,
        responses=inline_serializer(
            name="KioskPairResponse",
            fields={
                "device_id": drf_serializers.UUIDField(),
                "credential": drf_serializers.CharField(),
                "site": WorkSiteSerializer(),
            },
        ),
        auth=[],
    )
    def post(self, request):
        serializer = KioskPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            kiosk = (
                KioskDevice.objects.select_for_update()
                .select_related("site")
                .filter(pk=serializer.validated_data["device_id"])
                .first()
            )
            if (
                not kiosk
                or not kiosk.site.is_active
                or not kiosk.pairing_code_is_valid(serializer.validated_data["pairing_code"])
            ):
                return Response({"detail": "Pairing code is invalid or expired."}, status=400)
            credential = secrets.token_urlsafe(48)
            kiosk.set_credential(credential)
            kiosk.save(
                update_fields=[
                    "credential_hash",
                    "paired_at",
                    "pairing_id",
                    "pairing_code_hash",
                    "pairing_expires_at",
                ]
            )
        return Response(
            {
                "device_id": kiosk.pk,
                "credential": credential,
                "site": WorkSiteSerializer(kiosk.site).data,
            }
        )

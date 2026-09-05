import csv
from datetime import timedelta

from core.models import Employee, KioskDevice, User
from core.permissions import IsAdministrator, IsAdminWriteManagerRead, PasswordChanged
from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, permissions, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from .models import AdminException, AttendanceAttempt, AttendanceCorrection, AttendanceRecord
from .serializers import (
    AdminExceptionSerializer,
    AttendanceAttemptSerializer,
    AttendanceCorrectionSerializer,
    AttendanceCorrectionWriteSerializer,
    AttendanceRecordSerializer,
    PunchSerializer,
)
from .services import PunchError, holiday_for, process_punch, resolve_clock_in_date


def scoped_records(queryset, user):
    if user.is_superuser or user.role == User.Role.ADMIN:
        return queryset
    if user.role != User.Role.MANAGER:
        employee = getattr(user, "employee_profile", None)
        return queryset.filter(employee=employee) if employee else queryset.none()
    allowed = Q(pk__in=[])
    for scope in user.manager_scopes.all():
        item = Q(site=scope.site)
        if scope.department_id:
            item &= Q(employee__department=scope.department)
        allowed |= item
    return queryset.filter(allowed).distinct()


def apply_record_filters(queryset, params):
    if params.get("from"):
        queryset = queryset.filter(work_date__gte=params["from"])
    if params.get("to"):
        queryset = queryset.filter(work_date__lte=params["to"])
    if params.get("site"):
        queryset = queryset.filter(site_id=params["site"])
    if params.get("department"):
        queryset = queryset.filter(employee__department_id=params["department"])
    if params.get("employee"):
        queryset = queryset.filter(employee_id=params["employee"])
    if params.get("state"):
        queryset = queryset.filter(state=params["state"].upper())
    if params.get("missing_clock_out") in {"true", "false"}:
        queryset = queryset.filter(missing_clock_out=params["missing_clock_out"] == "true")
    return queryset


class EmployeeAttendanceViewSet(viewsets.GenericViewSet):
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated, PasswordChanged]
    throttle_scope = None

    def _employee(self):
        employee = getattr(self.request.user, "employee_profile", None)
        if not employee:
            raise PunchError("missing_profile", "This account has no employee profile.", 400)
        return Employee.objects.select_related("user", "department", "work_site", "shift").get(
            pk=employee.pk
        )

    @action(detail=False, methods=["get"])
    def today(self, request):
        try:
            employee = self._employee()
        except PunchError as error:
            return Response({"code": error.code, "detail": error.detail}, status=error.status_code)
        open_record = (
            AttendanceRecord.objects.filter(
                employee=employee, clock_in__isnull=False, clock_out__isnull=True
            )
            .order_by("-work_date")
            .first()
        )
        work_date = (
            open_record.work_date
            if open_record
            else resolve_clock_in_date(employee, timezone.now())
        )
        record = (
            open_record
            or AttendanceRecord.objects.filter(employee=employee, work_date=work_date).first()
        )
        holiday = holiday_for(employee, work_date)
        return Response(
            {
                "work_date": work_date,
                "day_state": "HOLIDAY"
                if holiday and not record
                else (record.state if record else "NOT_RECORDED"),
                "holiday_name": holiday.name if holiday else None,
                "assignment": {
                    "employee_number": employee.employee_number,
                    "employee_name": employee.full_name,
                    "site": {"id": employee.work_site_id, "name": employee.work_site.name},
                    "department": {"id": employee.department_id, "name": employee.department.name},
                    "shift": {
                        "id": employee.shift_id,
                        "name": employee.shift.name,
                        "start_time": employee.shift.start_time,
                        "end_time": employee.shift.end_time,
                        "grace_minutes": employee.shift.grace_minutes,
                    },
                },
                "attendance": AttendanceRecordSerializer(record).data if record else None,
                "is_checked_in": bool(record and record.clock_in and not record.clock_out),
                "is_checked_out": bool(record and record.clock_out),
            }
        )

    @action(detail=False, methods=["get"])
    def history(self, request):
        employee = getattr(request.user, "employee_profile", None)
        queryset = (
            AttendanceRecord.objects.filter(employee=employee).select_related(
                "employee__user", "employee__department", "site", "shift"
            )
            if employee
            else AttendanceRecord.objects.none()
        )
        page = self.paginate_queryset(queryset)
        serializer = AttendanceRecordSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def _punch(self, request, action_name):
        serializer = PunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            employee = self._employee()
            record, replayed = process_punch(employee, action_name, serializer.validated_data)
        except PunchError as error:
            return Response({"code": error.code, "detail": error.detail}, status=error.status_code)
        data = AttendanceRecordSerializer(record).data
        data["idempotent_replay"] = replayed
        return Response(
            data,
            status=status.HTTP_200_OK
            if replayed or action_name == AttendanceAttempt.Action.CLOCK_OUT
            else status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="clock-in",
        permission_classes=[permissions.IsAuthenticated, PasswordChanged],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="punch",
    )
    def clock_in(self, request):
        return self._punch(request, AttendanceAttempt.Action.CLOCK_IN)

    @action(
        detail=False,
        methods=["post"],
        url_path="clock-out",
        permission_classes=[permissions.IsAuthenticated, PasswordChanged],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="punch",
    )
    def clock_out(self, request):
        return self._punch(request, AttendanceAttempt.Action.CLOCK_OUT)


class AttendanceManagementViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAdminWriteManagerRead, PasswordChanged]

    def get_queryset(self):
        queryset = AttendanceRecord.objects.select_related(
            "employee__user", "employee__department", "site", "shift"
        )
        return apply_record_filters(
            scoped_records(queryset, self.request.user), self.request.query_params
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.get_queryset()
        if not request.query_params.get("from") and not request.query_params.get("to"):
            queryset = queryset.filter(work_date=timezone.localdate())
        counts = {
            row["state"]: row["count"]
            for row in queryset.values("state").annotate(count=Count("id"))
        }
        present = counts.get(AttendanceRecord.State.PRESENT, 0)
        late = counts.get(AttendanceRecord.State.LATE, 0)
        absent = counts.get(AttendanceRecord.State.ABSENT, 0)
        denominator = present + late + absent
        rejected = scoped_records(
            AttendanceAttempt.objects.filter(accepted=False), request.user
        ).count()
        return Response(
            {
                "present": present,
                "late": late,
                "absent": absent,
                "excused": counts.get(AttendanceRecord.State.EXCUSED, 0),
                "attendance_rate": round(((present + late) / denominator * 100), 1)
                if denominator
                else 0,
                "missing_clock_out": queryset.filter(missing_clock_out=True).count(),
                "rejected_attempts": rejected,
            }
        )

    @action(detail=False, methods=["get"], url_path="export.csv")
    def export_csv(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="attendance.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Work date",
                "Employee number",
                "Employee",
                "Department",
                "Site",
                "State",
                "Clock in",
                "Clock out",
                "Worked minutes",
                "Missing clock-out",
            ]
        )
        for record in self.get_queryset().iterator():
            writer.writerow(
                [
                    record.work_date,
                    record.employee.employee_number,
                    record.employee.full_name,
                    record.employee.department.name,
                    record.site.name,
                    record.state,
                    record.clock_in.isoformat() if record.clock_in else "",
                    record.clock_out.isoformat() if record.clock_out else "",
                    record.worked_minutes if record.worked_minutes is not None else "",
                    "yes" if record.missing_clock_out else "no",
                ]
            )
        return response


class AttemptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AttendanceAttempt.objects.all()
    serializer_class = AttendanceAttemptSerializer
    permission_classes = [IsAdminWriteManagerRead, PasswordChanged]

    def get_queryset(self):
        queryset = AttendanceAttempt.objects.select_related(
            "employee__user", "employee__department", "site", "kiosk", "record"
        )
        queryset = scoped_records(queryset, self.request.user)
        if self.request.query_params.get("accepted") in {"true", "false"}:
            queryset = queryset.filter(accepted=self.request.query_params["accepted"] == "true")
        return queryset


class AdminExceptionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AdminException.objects.select_related("employee__user", "approved_by")
    serializer_class = AdminExceptionSerializer
    permission_classes = [IsAdministrator, PasswordChanged]


class CorrectionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AttendanceCorrection.objects.select_related(
        "record__employee__user",
        "record__employee__department",
        "record__site",
        "record__shift",
        "corrected_by",
    )
    permission_classes = [IsAdministrator, PasswordChanged]

    def get_serializer_class(self):
        return (
            AttendanceCorrectionWriteSerializer
            if self.action == "create"
            else AttendanceCorrectionSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correction = serializer.save()
        return Response(
            AttendanceCorrectionSerializer(correction).data, status=status.HTTP_201_CREATED
        )


class KioskQRView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "kiosk"

    @extend_schema(
        responses=inline_serializer(
            name="KioskQRResponse",
            fields={
                "qr_token": drf_serializers.CharField(),
                "expires_in_seconds": drf_serializers.IntegerField(),
                "site": inline_serializer(
                    name="KioskQRSite",
                    fields={
                        "id": drf_serializers.IntegerField(),
                        "name": drf_serializers.CharField(),
                    },
                ),
            },
        ),
        auth=[],
    )
    def get(self, request, device_id):
        kiosk = KioskDevice.objects.select_related("site").filter(pk=device_id).first()
        credential = request.headers.get("X-Kiosk-Credential", "")
        if not kiosk or not kiosk.credential_is_valid(credential) or not kiosk.site.is_active:
            return Response(
                {"detail": "Kiosk credential is invalid or revoked."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token = AccessToken()
        token.set_exp(lifetime=timedelta(seconds=settings.QR_LIFETIME_SECONDS))
        token["kind"] = "attendance_qr"
        token["kiosk_id"] = str(kiosk.pk)
        token["site_id"] = kiosk.site_id
        token["pairing_id"] = kiosk.paired_at.isoformat()
        kiosk.last_seen_at = timezone.now()
        kiosk.save(update_fields=["last_seen_at"])
        return Response(
            {
                "qr_token": str(token),
                "expires_in_seconds": settings.QR_LIFETIME_SECONDS,
                "site": {"id": kiosk.site_id, "name": kiosk.site.name},
            }
        )

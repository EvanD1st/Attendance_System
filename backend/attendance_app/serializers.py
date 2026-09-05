from datetime import timezone as dt_timezone

from core.models import Employee
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import AdminException, AttendanceAttempt, AttendanceCorrection, AttendanceRecord
from .services import holiday_for, is_scheduled, record_state, scheduled_bounds


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    department_name = serializers.CharField(source="employee.department.name", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    shift_name = serializers.CharField(source="shift.name", read_only=True)
    worked_hours = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "employee",
            "employee_number",
            "employee_name",
            "department_name",
            "work_date",
            "site",
            "site_name",
            "shift",
            "shift_name",
            "scheduled_start",
            "scheduled_end",
            "grace_minutes",
            "clock_in",
            "clock_out",
            "state",
            "worked_minutes",
            "worked_hours",
            "missing_clock_out",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_worked_hours(self, obj) -> float | None:
        return round(obj.worked_minutes / 60, 2) if obj.worked_minutes is not None else None


class TodaySerializer(serializers.Serializer):
    work_date = serializers.DateField()
    day_state = serializers.CharField()
    holiday_name = serializers.CharField(allow_null=True)
    assignment = serializers.DictField()
    attendance = AttendanceRecordSerializer(allow_null=True)
    is_checked_in = serializers.BooleanField()
    is_checked_out = serializers.BooleanField()


class AttendanceSummarySerializer(serializers.Serializer):
    present = serializers.IntegerField()
    late = serializers.IntegerField()
    absent = serializers.IntegerField()
    excused = serializers.IntegerField()
    attendance_rate = serializers.FloatField()
    missing_clock_out = serializers.IntegerField()
    rejected_attempts = serializers.IntegerField()


class PunchSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    qr_token = serializers.CharField(trim_whitespace=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, min_value=-180, max_value=180
    )
    accuracy_meters = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    captured_at = serializers.DateTimeField()


class AttendanceAttemptSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    kiosk_name = serializers.CharField(source="kiosk.name", read_only=True)

    class Meta:
        model = AttendanceAttempt
        exclude = []
        read_only_fields = [field.name for field in AttendanceAttempt._meta.fields]


class AdminExceptionSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    approved_by_email = serializers.EmailField(source="approved_by.email", read_only=True)

    class Meta:
        model = AdminException
        fields = [
            "id",
            "employee",
            "employee_number",
            "employee_name",
            "date",
            "reason",
            "approved_by",
            "approved_by_email",
            "created_at",
        ]
        read_only_fields = ["approved_by", "created_at"]

    def validate(self, attrs):
        employee = attrs["employee"]
        work_date = attrs["date"]
        if not is_scheduled(employee, work_date):
            raise serializers.ValidationError(
                {"date": "The employee is not scheduled on this date."}
            )
        if holiday_for(employee, work_date):
            raise serializers.ValidationError({"date": "The selected date is already a holiday."})
        record = AttendanceRecord.objects.filter(employee=employee, work_date=work_date).first()
        if record and record.clock_in:
            raise serializers.ValidationError(
                {"date": "An exception cannot replace an accepted punch; use a correction."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        approved_by = self.context["request"].user
        Employee.objects.select_for_update().get(pk=validated_data["employee"].pk)
        self.validate(validated_data)
        exception = AdminException.objects.create(approved_by=approved_by, **validated_data)
        employee = exception.employee
        start, end = scheduled_bounds(employee, exception.date)
        record, _ = AttendanceRecord.objects.get_or_create(
            employee=employee,
            work_date=exception.date,
            defaults={
                "site": employee.work_site,
                "shift": employee.shift,
                "scheduled_start": start,
                "scheduled_end": end,
                "grace_minutes": employee.shift.grace_minutes,
                "state": AttendanceRecord.State.EXCUSED,
            },
        )
        if not record.clock_in:
            record.state = AttendanceRecord.State.EXCUSED
            record.missing_clock_out = False
            record.save(update_fields=["state", "missing_clock_out", "updated_at"])
        return exception


def record_snapshot(record):
    if not record:
        return {}
    return {
        "state": record.state,
        "clock_in": record.clock_in.astimezone(dt_timezone.utc).isoformat()
        if record.clock_in
        else None,
        "clock_out": record.clock_out.astimezone(dt_timezone.utc).isoformat()
        if record.clock_out
        else None,
        "worked_minutes": record.worked_minutes,
        "missing_clock_out": record.missing_clock_out,
    }


class AttendanceCorrectionWriteSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.filter(is_active=True))
    work_date = serializers.DateField()
    clock_in = serializers.DateTimeField(required=False, allow_null=True)
    clock_out = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(min_length=5)

    def validate(self, attrs):
        employee = attrs["employee"]
        work_date = attrs["work_date"]
        if not is_scheduled(employee, work_date):
            raise serializers.ValidationError(
                {"work_date": "The employee is not scheduled on this date."}
            )
        if holiday_for(employee, work_date):
            raise serializers.ValidationError(
                {"work_date": "Holiday records do not need attendance corrections."}
            )
        if AdminException.objects.filter(employee=employee, date=work_date).exists():
            raise serializers.ValidationError(
                {"work_date": "Remove the exception before creating an attendance correction."}
            )
        existing = AttendanceRecord.objects.filter(employee=employee, work_date=work_date).first()
        clock_in = attrs.get("clock_in", existing.clock_in if existing else None)
        clock_out = attrs.get("clock_out", existing.clock_out if existing else None)
        if clock_out and not clock_in:
            raise serializers.ValidationError({"clock_out": "Clock-out requires a clock-in."})
        if clock_in and clock_out and clock_out < clock_in:
            raise serializers.ValidationError({"clock_out": "Clock-out cannot be before clock-in."})
        attrs["existing"] = existing
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        employee = validated_data["employee"]
        Employee.objects.select_for_update().get(pk=employee.pk)
        self.validate(validated_data)
        work_date = validated_data["work_date"]
        reason = validated_data["reason"]
        existing = validated_data.pop("existing", None)
        start, end = scheduled_bounds(employee, work_date)
        record = existing or AttendanceRecord(
            employee=employee,
            work_date=work_date,
            site=employee.work_site,
            shift=employee.shift,
            scheduled_start=start,
            scheduled_end=end,
            grace_minutes=employee.shift.grace_minutes,
        )
        before = record_snapshot(existing)
        if "clock_in" in validated_data:
            record.clock_in = validated_data["clock_in"]
        if "clock_out" in validated_data:
            record.clock_out = validated_data["clock_out"]
        record.state = record_state(record.clock_in, record.scheduled_start, record.grace_minutes)
        record.worked_minutes = (
            max(0, int((record.clock_out - record.clock_in).total_seconds() // 60))
            if record.clock_in and record.clock_out
            else None
        )
        record.missing_clock_out = bool(
            record.clock_in and not record.clock_out and timezone.now() > record.scheduled_end
        )
        record.save()
        return AttendanceCorrection.objects.create(
            record=record,
            corrected_by=self.context["request"].user,
            reason=reason,
            before_data=before,
            after_data=record_snapshot(record),
        )


class AttendanceCorrectionSerializer(serializers.ModelSerializer):
    record_details = AttendanceRecordSerializer(source="record", read_only=True)
    corrected_by_email = serializers.EmailField(source="corrected_by.email", read_only=True)

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "record",
            "record_details",
            "corrected_by",
            "corrected_by_email",
            "reason",
            "before_data",
            "after_data",
            "created_at",
        ]
        read_only_fields = fields

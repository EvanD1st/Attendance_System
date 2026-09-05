import uuid

from core.models import Employee, KioskDevice, Shift, WorkSite
from django.conf import settings
from django.db import models


class AttendanceRecord(models.Model):
    class State(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"
        ABSENT = "ABSENT", "Absent"
        EXCUSED = "EXCUSED", "Excused"

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="attendance_records"
    )
    work_date = models.DateField()
    site = models.ForeignKey(WorkSite, on_delete=models.PROTECT, related_name="attendance_records")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="attendance_records")
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    grace_minutes = models.PositiveSmallIntegerField(default=0)
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=State.choices)
    worked_minutes = models.PositiveIntegerField(null=True, blank=True)
    missing_clock_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "employee__employee_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "work_date"], name="unique_employee_work_date"
            )
        ]
        indexes = [
            models.Index(fields=["work_date", "site", "state"], name="idx_attendance_report"),
            models.Index(fields=["employee", "work_date"], name="idx_attendance_employee"),
        ]

    def __str__(self):
        return f"{self.employee} / {self.work_date} / {self.state}"


class AdminException(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="admin_exceptions"
    )
    date = models.DateField()
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approved_exceptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "employee__employee_number"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="unique_employee_exception")
        ]
        indexes = [models.Index(fields=["date", "employee"], name="idx_exception_date_employee")]


class AttendanceAttempt(models.Model):
    class Action(models.TextChoices):
        CLOCK_IN = "CLOCK_IN", "Clock in"
        CLOCK_OUT = "CLOCK_OUT", "Clock out"

    request_id = models.UUIDField(default=uuid.uuid4, unique=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="attendance_attempts"
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    site = models.ForeignKey(
        WorkSite,
        on_delete=models.PROTECT,
        related_name="attendance_attempts",
        null=True,
        blank=True,
    )
    kiosk = models.ForeignKey(
        KioskDevice,
        on_delete=models.SET_NULL,
        related_name="attendance_attempts",
        null=True,
        blank=True,
    )
    record = models.ForeignKey(
        AttendanceRecord, on_delete=models.SET_NULL, related_name="attempts", null=True, blank=True
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.DecimalField(max_digits=8, decimal_places=2)
    captured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    distance_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    accepted = models.BooleanField(default=False)
    reason_code = models.CharField(max_length=40, blank=True)
    reason_detail = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["received_at", "accepted"], name="idx_attempt_review"),
            models.Index(fields=["employee", "received_at"], name="idx_attempt_employee"),
        ]


class AttendanceCorrection(models.Model):
    record = models.ForeignKey(
        AttendanceRecord, on_delete=models.PROTECT, related_name="corrections"
    )
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_corrections"
    )
    reason = models.TextField()
    before_data = models.JSONField()
    after_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

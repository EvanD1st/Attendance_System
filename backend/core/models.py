import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EMPLOYEE)
    must_change_password = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class WorkSite(models.Model):
    name = models.CharField(max_length=150, unique=True)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    geofence_radius_meters = models.PositiveIntegerField(default=200)
    timezone = models.CharField(max_length=64, default="Africa/Lagos")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def default_working_weekdays():
    return [0, 1, 2, 3, 4]


class Shift(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    working_weekdays = models.JSONField(default=default_working_weekdays)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="employee_profile")
    employee_number = models.CharField(max_length=40, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    work_site = models.ForeignKey(WorkSite, on_delete=models.PROTECT, related_name="employees")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name="employees")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_number"]
        indexes = [
            models.Index(fields=["work_site", "department", "is_active"], name="idx_employee_scope")
        ]

    @property
    def full_name(self):
        return self.user.get_full_name().strip() or self.user.email

    def __str__(self):
        return f"{self.employee_number} - {self.full_name}"


class ManagerScope(models.Model):
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name="manager_scopes")
    site = models.ForeignKey(WorkSite, on_delete=models.CASCADE, related_name="manager_scopes")
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="manager_scopes", null=True, blank=True
    )

    class Meta:
        ordering = ["manager__email", "site__name", "department__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["manager", "site", "department"],
                condition=Q(department__isnull=False),
                name="unique_manager_department_scope",
            ),
            models.UniqueConstraint(
                fields=["manager", "site"],
                condition=Q(department__isnull=True),
                name="unique_manager_site_scope",
            ),
        ]

    def __str__(self):
        suffix = f" / {self.department}" if self.department else ""
        return f"{self.manager.email}: {self.site}{suffix}"


class Holiday(models.Model):
    name = models.CharField(max_length=150)
    date = models.DateField()
    site = models.ForeignKey(
        WorkSite, on_delete=models.CASCADE, related_name="holidays", null=True, blank=True
    )

    class Meta:
        ordering = ["-date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["date", "site"], name="unique_site_holiday"),
            models.UniqueConstraint(
                fields=["date"], condition=Q(site__isnull=True), name="unique_company_holiday"
            ),
        ]
        indexes = [models.Index(fields=["date", "site"], name="idx_holiday_date_site")]

    def __str__(self):
        return f"{self.name} ({self.date})"


class KioskDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    site = models.ForeignKey(WorkSite, on_delete=models.PROTECT, related_name="kiosks")
    is_active = models.BooleanField(default=True)
    credential_hash = models.CharField(max_length=256, blank=True)
    pairing_code_hash = models.CharField(max_length=256, blank=True)
    pairing_expires_at = models.DateTimeField(null=True, blank=True)
    paired_at = models.DateTimeField(null=True, blank=True)
    pairing_id = models.UUIDField(null=True, blank=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["site__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["site", "name"], name="unique_kiosk_name_per_site")
        ]

    def set_pairing_code(self, code: str, expires_at):
        self.pairing_code_hash = make_password(code)
        self.pairing_expires_at = expires_at

    def pairing_code_is_valid(self, code: str) -> bool:
        return bool(
            self.is_active
            and self.pairing_code_hash
            and self.pairing_expires_at
            and self.pairing_expires_at >= timezone.now()
            and check_password(code, self.pairing_code_hash)
        )

    def set_credential(self, credential: str):
        self.credential_hash = make_password(credential)
        self.paired_at = timezone.now()
        self.pairing_id = uuid.uuid4()
        self.pairing_code_hash = ""
        self.pairing_expires_at = None

    def credential_is_valid(self, credential: str) -> bool:
        return bool(
            self.is_active
            and self.credential_hash
            and self.pairing_id
            and check_password(credential, self.credential_hash)
        )

    def __str__(self):
        return f"{self.name} ({self.site})"

import uuid
from datetime import date, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import (
    Department,
    Employee,
    Holiday,
    KioskDevice,
    ManagerScope,
    Shift,
    User,
    WorkSite,
)


class Command(BaseCommand):
    help = "Create deterministic local demo users, configuration, and a kiosk pairing code."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Explicitly reset existing demo accounts to documented passwords.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is disabled when DEBUG=False.")
        self.reset_passwords = options["reset_passwords"]
        hq, _ = WorkSite.objects.update_or_create(
            name="Lagos HQ",
            defaults={
                "address": "1 Marina Road, Lagos",
                "latitude": "6.454100",
                "longitude": "3.394700",
                "geofence_radius_meters": 200,
                "timezone": "Africa/Lagos",
                "is_active": True,
            },
        )
        annex, _ = WorkSite.objects.update_or_create(
            name="Ikeja Annex",
            defaults={
                "address": "Allen Avenue, Ikeja",
                "latitude": "6.601800",
                "longitude": "3.351500",
                "geofence_radius_meters": 180,
                "timezone": "Africa/Lagos",
                "is_active": True,
            },
        )
        operations, _ = Department.objects.update_or_create(
            name="Operations", defaults={"is_active": True}
        )
        engineering, _ = Department.objects.update_or_create(
            name="Engineering", defaults={"is_active": True}
        )
        day, _ = Shift.objects.update_or_create(
            name="Weekday 09:00–17:00",
            defaults={
                "start_time": time(9),
                "end_time": time(17),
                "grace_minutes": 15,
                "working_weekdays": [0, 1, 2, 3, 4],
                "is_active": True,
            },
        )
        night, _ = Shift.objects.update_or_create(
            name="Night 22:00–06:00",
            defaults={
                "start_time": time(22),
                "end_time": time(6),
                "grace_minutes": 10,
                "working_weekdays": [0, 1, 2, 3, 4],
                "is_active": True,
            },
        )

        self._user(
            "admin@attendance.local", "DemoAdmin!2026", "Ada", "Admin", User.Role.ADMIN, False
        )
        manager_user = self._user(
            "manager@attendance.local",
            "DemoManager!2026",
            "Musa",
            "Manager",
            User.Role.MANAGER,
            False,
        )
        employee_user = self._user(
            "employee@attendance.local",
            "DemoEmployee!2026",
            "Amara",
            "Okafor",
            User.Role.EMPLOYEE,
            True,
        )
        night_user = self._user(
            "night@attendance.local", "DemoNight!2026", "Tunde", "Bello", User.Role.EMPLOYEE, True
        )

        manager, _ = Employee.objects.update_or_create(
            user=manager_user,
            defaults={
                "employee_number": "MGR-001",
                "department": operations,
                "work_site": hq,
                "shift": day,
                "is_active": True,
            },
        )
        employee, _ = Employee.objects.update_or_create(
            user=employee_user,
            defaults={
                "employee_number": "EMP-001",
                "department": engineering,
                "work_site": hq,
                "shift": day,
                "is_active": True,
            },
        )
        Employee.objects.update_or_create(
            user=night_user,
            defaults={
                "employee_number": "EMP-002",
                "department": operations,
                "work_site": annex,
                "shift": night,
                "is_active": True,
            },
        )
        ManagerScope.objects.get_or_create(manager=manager_user, site=hq, department=None)
        Holiday.objects.update_or_create(
            date=date(2030, 1, 1), site=None, defaults={"name": "Demo Company Holiday"}
        )
        kiosk, _ = KioskDevice.objects.get_or_create(
            name="HQ Entrance",
            site=hq,
            defaults={"id": uuid.UUID("11111111-1111-4111-8111-111111111111"), "is_active": True},
        )
        kiosk.is_active = True
        kiosk.set_pairing_code("123456", timezone.now() + timedelta(days=1))
        kiosk.save(update_fields=["is_active", "pairing_code_hash", "pairing_expires_at"])

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready. Existing passwords are preserved unless --reset-passwords was supplied."
            )
        )
        self.stdout.write("Admin: admin@attendance.local / DemoAdmin!2026")
        self.stdout.write("Manager: manager@attendance.local / DemoManager!2026")
        self.stdout.write(
            "Employee: employee@attendance.local / DemoEmployee!2026 (must change password)"
        )
        self.stdout.write(f"Kiosk device: {kiosk.pk} / pairing code 123456")

    def _user(self, email, password, first_name, last_name, role, must_change):
        user, created = User.objects.get_or_create(username=email, defaults={"email": email})
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        if created or self.reset_passwords:
            user.must_change_password = must_change
        user.is_active = True
        if created or self.reset_passwords:
            user.set_password(password)
        user.save()
        return user

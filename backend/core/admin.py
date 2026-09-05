from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Department, Employee, Holiday, KioskDevice, ManagerScope, Shift, User, WorkSite


@admin.register(User)
class AttendanceUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Attendance", {"fields": ("role", "must_change_password")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Attendance", {"fields": ("email", "role", "must_change_password")}),
    )
    list_display = ("username", "email", "role", "is_active", "must_change_password")


admin.site.register([Department, Employee, Holiday, KioskDevice, ManagerScope, Shift, WorkSite])

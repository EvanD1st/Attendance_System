from django.contrib import admin

from .models import AdminException, AttendanceAttempt, AttendanceCorrection, AttendanceRecord


class ImmutableAuditAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AttendanceAttempt)
class AttendanceAttemptAdmin(ImmutableAuditAdmin):
    list_display = ("received_at", "employee", "action", "accepted", "reason_code", "site", "kiosk")
    list_filter = ("accepted", "action", "reason_code", "site")


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(ImmutableAuditAdmin):
    list_display = ("created_at", "record", "corrected_by", "reason")


admin.site.register([AdminException, AttendanceRecord], ImmutableAuditAdmin)

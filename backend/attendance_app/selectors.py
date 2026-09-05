from core.models import User
from django.db.models import Q
from rest_framework import serializers

from .models import AttendanceRecord


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


class RecordFilters(serializers.Serializer):
    site = serializers.IntegerField(min_value=1, required=False)
    department = serializers.IntegerField(min_value=1, required=False)
    employee = serializers.IntegerField(min_value=1, required=False)
    state = serializers.ChoiceField(choices=AttendanceRecord.State.values, required=False)
    missing_clock_out = serializers.BooleanField(required=False)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = serializers.DateField(required=False)
        fields["to"] = serializers.DateField(required=False)
        return fields

    def validate(self, attrs):
        if attrs.get("from") and attrs.get("to") and attrs["from"] > attrs["to"]:
            raise serializers.ValidationError({"to": "End date cannot precede start date."})
        return attrs


def apply_record_filters(queryset, params):
    data = {key: value for key, value in params.items() if value != ""}
    if isinstance(data.get("state"), str):
        data["state"] = data["state"].upper()
    serializer = RecordFilters(data=data)
    serializer.is_valid(raise_exception=True)
    mappings = {
        "from": "work_date__gte",
        "to": "work_date__lte",
        "site": "site_id",
        "department": "employee__department_id",
        "employee": "employee_id",
        "state": "state",
        "missing_clock_out": "missing_clock_out",
    }
    return queryset.filter(
        **{mappings[key]: value for key, value in serializer.validated_data.items()}
    )

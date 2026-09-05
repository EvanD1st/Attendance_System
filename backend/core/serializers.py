from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import Department, Employee, Holiday, KioskDevice, ManagerScope, Shift, User, WorkSite


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "must_change_password"]


class WorkSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSite
        fields = "__all__"

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                "Use a valid IANA timezone, for example Africa/Lagos."
            ) from exc
        return value

    def validate_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = "__all__"

    def validate_working_weekdays(self, value):
        if (
            not isinstance(value, list)
            or not value
            or any(type(day) is not int or day < 0 or day > 6 for day in value)
        ):
            raise serializers.ValidationError(
                "Provide a non-empty list of weekday numbers from 0 (Monday) to 6 (Sunday)."
            )
        return sorted(set(value))

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and start == end:
            raise serializers.ValidationError(
                {"end_time": "Start and end time cannot be identical."}
            )
        return attrs


class EmployeeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    site_name = serializers.CharField(source="work_site.name", read_only=True)
    shift_name = serializers.CharField(source="shift.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "employee_number",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "department",
            "department_name",
            "work_site",
            "site_name",
            "shift",
            "shift_name",
            "is_active",
            "created_at",
        ]


class EmployeeWriteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    temporary_password = serializers.CharField(write_only=True, min_length=8, required=False)
    role = serializers.ChoiceField(
        choices=[User.Role.EMPLOYEE, User.Role.MANAGER], default=User.Role.EMPLOYEE
    )
    employee_number = serializers.CharField(max_length=40)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True)
    )
    work_site = serializers.PrimaryKeyRelatedField(queryset=WorkSite.objects.filter(is_active=True))
    shift = serializers.PrimaryKeyRelatedField(queryset=Shift.objects.filter(is_active=True))
    is_active = serializers.BooleanField(default=True)

    def validate_email(self, value):
        normalized = value.strip().lower()
        queryset = User.objects.filter(Q(email__iexact=normalized) | Q(username__iexact=normalized))
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.user_id)
        if queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate_employee_number(self, value):
        queryset = Employee.objects.filter(employee_number__iexact=value.strip())
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Employee number is already in use.")
        return value.strip().upper()

    def validate_temporary_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get("temporary_password"):
            raise serializers.ValidationError(
                {"temporary_password": "A temporary password is required."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("temporary_password")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")
        username = email
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
            must_change_password=True,
            is_active=validated_data.get("is_active", True),
        )
        return Employee.objects.create(user=user, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("temporary_password", None)
        user_fields = {
            key: validated_data.pop(key)
            for key in ["email", "first_name", "last_name", "role"]
            if key in validated_data
        }
        for key, value in user_fields.items():
            setattr(instance.user, key, value)
        if "email" in user_fields:
            instance.user.username = user_fields["email"]
        if password:
            instance.user.set_password(password)
            instance.user.must_change_password = True
        instance.user.is_active = validated_data.get("is_active", instance.is_active)
        instance.user.save()
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        return EmployeeSerializer(instance, context=self.context).data


class ManagerScopeSerializer(serializers.ModelSerializer):
    manager_email = serializers.EmailField(source="manager.email", read_only=True)
    site_name = serializers.CharField(source="site.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = ManagerScope
        fields = [
            "id",
            "manager",
            "manager_email",
            "site",
            "site_name",
            "department",
            "department_name",
        ]

    def validate_manager(self, value):
        if value.role != User.Role.MANAGER:
            raise serializers.ValidationError("Scopes can only be assigned to manager accounts.")
        return value


class HolidaySerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)

    class Meta:
        model = Holiday
        fields = ["id", "name", "date", "site", "site_name"]


class KioskDeviceSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    is_paired = serializers.SerializerMethodField()

    class Meta:
        model = KioskDevice
        fields = [
            "id",
            "name",
            "site",
            "site_name",
            "is_active",
            "is_paired",
            "paired_at",
            "last_seen_at",
            "created_at",
        ]
        read_only_fields = ["paired_at", "last_seen_at", "created_at"]

    def get_is_paired(self, obj) -> bool:
        return bool(obj.credential_hash and obj.pairing_id)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class KioskPairSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    pairing_code = serializers.CharField(min_length=6, max_length=12)

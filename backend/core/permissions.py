from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.role == "admin")
        )


class IsAdminWriteManagerRead(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.is_superuser or request.user.role in {"admin", "manager"}
        return request.user.is_superuser or request.user.role == "admin"


class PasswordChanged(BasePermission):
    message = "Change your temporary password before recording attendance."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and not request.user.must_change_password
        )

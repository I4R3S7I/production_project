from rest_framework import permissions

from users.models import User


class ResumePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        role = request.user.role
        action = view.action

        if role == User.Role.ADMIN:
            return True

        if action in ('list', 'retrieve'):
            return role in (User.Role.CANDIDATE, User.Role.HR)

        if action == 'create':
            return role == User.Role.CANDIDATE

        if action in ('update', 'partial_update'):
            return role == User.Role.CANDIDATE

        if action == 'destroy':
            return role == User.Role.ADMIN

        return False

    def has_object_permission(self, request, view, obj):
        role = request.user.role
        action = view.action

        if role == User.Role.ADMIN:
            return True

        if action in ('retrieve', 'list'):
            if role == User.Role.HR:
                return True
            return obj.user == request.user

        if action in ('update', 'partial_update'):
            return role == User.Role.CANDIDATE and obj.user == request.user

        if action == 'destroy':
            return role == User.Role.ADMIN

        return False
from rest_framework import permissions

class IsMessageOwner(permissions.BasePermission):
    """
    Custom permission to only allow the sender of a message to edit or delete it.
    """
    def has_object_permission(self, request, view, obj):
        return obj.sender == request.user


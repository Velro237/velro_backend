from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeviceViewSet, notify_user

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("", include(router.urls)),
    path("notify/", notify_user, name="notify-user"),
]

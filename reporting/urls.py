from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminMetricsViewSet

router = DefaultRouter()
router.register(r'metrics', AdminMetricsViewSet, basename='admin-metrics')

urlpatterns = [
    path('', include(router.urls)),
] 
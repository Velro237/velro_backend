from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TravelListingViewSet, PackageRequestViewSet, AlertViewSet,
    CountryViewSet, RegionViewSet
)

router = DefaultRouter()
router.register(r'travel', TravelListingViewSet)
router.register(r'packages', PackageRequestViewSet)
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'countries', CountryViewSet)
router.register(r'regions', RegionViewSet)

urlpatterns = [
    path('', include(router.urls)),
] 
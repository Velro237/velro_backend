from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from datetime import datetime
from .models import TravelListing, PackageRequest, Alert, Country, Region
from .serializers import TravelListingSerializer, PackageRequestSerializer, AlertSerializer, CountrySerializer, RegionSerializer
from config.views import StandardResponseViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework import status

# Create your views here.

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        return obj.user == request.user

class IsPackageRequestOwnerOrTravelListingOwner(permissions.BasePermission):
    """
    Custom permission to only allow:
    - Package request owner to edit their request
    - Travel listing owner to change the status of the request
    - Both package request owner and travel listing owner to view the request
    """
    def has_object_permission(self, request, view, obj):
        # Allow read access if user is either the package request owner or the travel listing owner
        if request.method in permissions.SAFE_METHODS:
            return obj.user == request.user or obj.travel_listing.user == request.user

        # For status-changing actions, allow travel listing owner
        if view.action in ['accept', 'reject', 'complete']:
            return obj.travel_listing.user == request.user

        # For other write operations, only allow package request owner
        return obj.user == request.user

class TravelListingViewSet(StandardResponseViewSet):
    """
    API endpoint for travel listings
    """
    queryset = TravelListing.objects.all()
    serializer_class = TravelListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        """
        This view returns a list of travel listings with the following visibility rules:
        - Published listings are visible to all authenticated users
        - Drafted, completed, and canceled listings are only visible to their owners
        Can be filtered by pickup location, destination, date, and status.
        """
        # Start with all listings
        queryset = TravelListing.objects.all()
        
        # Get query parameters
        pickup_country = self.request.query_params.get('pickup_country', None)
        pickup_region = self.request.query_params.get('pickup_region', None)
        destination_country = self.request.query_params.get('destination_country', None)
        destination_region = self.request.query_params.get('destination_region', None)
        travel_date = self.request.query_params.get('travel_date', None)
        status = self.request.query_params.get('status', None)

        # Apply visibility rules
        if status:
            # If status is specified, only show if user is owner or status is published
            queryset = queryset.filter(
                Q(user=self.request.user, status=status)
            )
        else:
            # If no status specified, show all published listings and user's own non-published listings
            queryset = queryset.filter(
                Q(status='published') | 
                Q(user=self.request.user, status__in=['drafted', 'completed', 'canceled'])
            )

        # Apply additional filters
        if pickup_country:
            queryset = queryset.filter(pickup_country__icontains=pickup_country)
        if pickup_region:
            queryset = queryset.filter(pickup_region__icontains=pickup_region)
        if destination_country:
            queryset = queryset.filter(destination_country__icontains=destination_country)
        if destination_region:
            queryset = queryset.filter(destination_region__icontains=destination_region)
        if travel_date:
            try:
                # Convert string date to datetime object
                date_obj = datetime.strptime(travel_date, '%Y-%m-%d').date()
                queryset = queryset.filter(travel_date=date_obj)
            except ValueError:
                # If date format is invalid, return empty queryset
                return TravelListing.objects.none()

        return queryset

    @action(detail=False, methods=['get'])
    def my_listings(self, request):
        """
        Get all travel listings created by the current user.
        """
        listings = TravelListing.objects.filter(user=request.user)
        serializer = self.get_serializer(listings, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark a travel listing as completed. Only the owner can complete their listing.
        """
        listing = self.get_object()
        if listing.user != request.user:
            return self._standardize_response(
                Response(
                    {"detail": "You do not have permission to complete this listing."},
                    status=403
                )
            )
        
        listing.status = 'completed'
        listing.save()
        serializer = self.get_serializer(listing)
        return self._standardize_response(Response(serializer.data))

class PackageRequestViewSet(StandardResponseViewSet):
    """
    API endpoint for package requests
    """
    queryset = PackageRequest.objects.all()
    serializer_class = PackageRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsPackageRequestOwnerOrTravelListingOwner]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        """
        This view returns a list of package requests where the user is either:
        - The creator of the package request
        - The owner of the travel listing being requested
        """
        return PackageRequest.objects.filter(
            Q(user=self.request.user) |  # User is the package request creator
            Q(travel_listing__user=self.request.user)  # User is the travel listing owner
        )

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """
        Get all package requests created by the current user.
        """
        requests = PackageRequest.objects.filter(user=request.user)
        serializer = self.get_serializer(requests, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=False, methods=['get'])
    def received_requests(self, request):
        """
        Get all package requests for travel listings owned by the current user.
        """
        requests = PackageRequest.objects.filter(travel_listing__user=request.user)
        serializer = self.get_serializer(requests, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept a package request. Only the travel listing owner can accept the request.
        """
        package_request = self.get_object()
        
        # Check if user is the travel listing owner
        if package_request.travel_listing.user != request.user:
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "error": ["Only the travel listing owner can accept the request."]
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if request is in pending status
        if package_request.status != 'pending':
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "error": [f"Cannot accept request in '{package_request.status}' status."]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        package_request.status = 'accepted'
        package_request.save()
        serializer = self.get_serializer(package_request)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a package request. Only the travel listing owner can reject the request.
        """
        package_request = self.get_object()
        
        # Check if user is the travel listing owner
        if package_request.travel_listing.user != request.user:
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "error": ["Only the travel listing owner can reject the request."]
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if request is in pending status
        if package_request.status != 'pending':
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "error": [f"Cannot reject request in '{package_request.status}' status."]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        package_request.status = 'rejected'
        package_request.save()
        serializer = self.get_serializer(package_request)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark a package request as completed. Only the travel listing owner can complete the request.
        """
        package_request = self.get_object()
        
        # Check if user is the travel listing owner
        if package_request.travel_listing.user != request.user:
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "error": ["Only the travel listing owner can complete the request."]
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if request is in accepted status
        if package_request.status != 'accepted':
            return Response(
                {
                    "status": "FAILED",
                    "data": {},
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "error": [f"Cannot complete request in '{package_request.status}' status. Request must be accepted first."]
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        package_request.status = 'completed'
        package_request.save()
        serializer = self.get_serializer(package_request)
        return self._standardize_response(Response(serializer.data))

class AlertViewSet(StandardResponseViewSet):
    """
    API endpoint for travel alerts
    """
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view returns a list of all alerts for the authenticated user.
        """
        return Alert.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_alerts(self, request):
        """
        Get all alerts created by the current user.
        """
        alerts = Alert.objects.filter(user=request.user)
        serializer = self.get_serializer(alerts, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """
        Toggle the active status of an alert. Only the owner can toggle their alert.
        """
        alert = self.get_object()
        if alert.user != request.user:
            return self._standardize_response(
                Response(
                    {"detail": "You do not have permission to toggle this alert."},
                    status=403
                )
            )
        
        alert.is_active = not alert.is_active
        alert.save()
        serializer = self.get_serializer(alert)
        return self._standardize_response(Response(serializer.data))

class CountryViewSet(StandardResponseViewSet):
    """
    API endpoint for countries
    """
    queryset = Country.objects.all()
    serializer_class = CountrySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

class RegionViewSet(StandardResponseViewSet):
    """
    API endpoint for regions
    """
    queryset = Region.objects.all()
    serializer_class = RegionSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Region.objects.all()
        country_id = self.request.query_params.get('country', None)
        if country_id is not None:
            queryset = queryset.filter(country_id=country_id)
        return queryset

    @action(detail=False, methods=['get'], url_path='by-country/(?P<country_id>[^/.]+)')
    def by_country(self, request, country_id=None):
        """
        Get all regions for a specific country.
        """
        try:
            regions = Region.objects.filter(country_id=country_id)
            serializer = self.get_serializer(regions, many=True)
            return self._standardize_response(Response(serializer.data))
        except Region.DoesNotExist:
            return self._standardize_response(
                Response(
                    {"error": "No regions found for this country"},
                    status=status.HTTP_404_NOT_FOUND
                )
            )

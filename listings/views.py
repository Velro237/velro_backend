from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from datetime import datetime
from .models import TravelListing, PackageRequest, Alert, Country, Region, Review
from .serializers import TravelListingSerializer, PackageRequestSerializer, AlertSerializer, CountrySerializer, RegionSerializer, ReviewSerializer, TransportTypeSerializer, PackageTypeSerializer
from config.views import StandardResponseViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework import status
from messaging.models import Conversation, Message, Notification
from decimal import Decimal
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from messaging.serializers import NotificationSerializer
from messaging.utils import send_notification_to_user
from listings.models import TransportType, PackageType
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

class IsIdentityVerified(permissions.BasePermission):
    """
    Custom permission to only allow identity verified users to create travel listings.
    """
    def has_permission(self, request, view):
        # Allow read operations for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # For write operations, check if user is verified
        return request.user.is_authenticated and request.user.is_identity_verified == 'completed'

class TravelListingViewSet(StandardResponseViewSet):
    """
    API endpoint for travel listings
    """
    queryset = TravelListing.objects.all()
    serializer_class = TravelListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly, IsIdentityVerified]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        """
        This view returns a list of travel listings with the following visibility rules:
        - Published listings are visible to all authenticated users
        - Drafted, completed, and canceled listings are only visible to their owners
        Can be filtered by pickup location, destination, date (from and above), and status.
        Query params:
        - pickup_country: ID of the pickup country
        - pickup_region: ID of the pickup region
        - destination_country: ID of the destination country
        - destination_region: ID of the destination region
        - travel_date: listings with travel_date >= this date (YYYY-MM-DD)
        - status: filter by status
        """
        queryset = TravelListing.objects.all()
        pickup_country = self.request.query_params.get('pickup_country', None)
        pickup_region = self.request.query_params.get('pickup_region', None)
        destination_country = self.request.query_params.get('destination_country', None)
        destination_region = self.request.query_params.get('destination_region', None)
        travel_date = self.request.query_params.get('travel_date', None)
        status = self.request.query_params.get('status', None)

        # Apply visibility rules
        if status:
            queryset = queryset.filter(
                Q(user=self.request.user, status=status)
            )
        else:
            queryset = queryset.filter(
                Q(status='published') |
                Q(user=self.request.user, status__in=['drafted', 'completed', 'canceled'])
            )

        # Apply additional filters using IDs
        if pickup_country:
            queryset = queryset.filter(pickup_country_id=pickup_country)
        if pickup_region:
            queryset = queryset.filter(pickup_region_id=pickup_region)
        if destination_country:
            queryset = queryset.filter(destination_country_id=destination_country)
        if destination_region:
            queryset = queryset.filter(destination_region_id=destination_region)
        if travel_date:
            try:
                date_obj = datetime.strptime(travel_date, '%Y-%m-%d').date()
                queryset = queryset.filter(travel_date__gte=date_obj)
            except ValueError:
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
        # Update travel listing's available weight and status
        travel_listing = package_request.travel_listing
        travel_listing.maximum_weight_in_kg = Decimal(travel_listing.maximum_weight_in_kg) - Decimal(package_request.weight)
        if travel_listing.maximum_weight_in_kg <= 0:
            travel_listing.maximum_weight_in_kg = 0
            travel_listing.status = 'fully-booked'
        travel_listing.save()
        serializer = self.get_serializer(package_request)
        # Send notification to package request owner
        notification = Notification.objects.create(
            user=package_request.user,
            travel_listing=package_request.travel_listing,
            message=f"Your package request has been accepted."
        )
        notification_serializer = NotificationSerializer(notification)
        send_notification_to_user(package_request.user.id, notification_serializer.data)
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
        # Send notification to package request owner
        notification = Notification.objects.create(
            user=package_request.user,
            travel_listing=package_request.travel_listing,
            message=f"Your package request has been rejected."
        )
        notification_serializer = NotificationSerializer(notification)
        send_notification_to_user(package_request.user.id, notification_serializer.data)
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
        # Send notification to package request owner
        notification = Notification.objects.create(
            user=package_request.user,
            travel_listing=package_request.travel_listing,
            message=f"Your package request has been marked as completed."
        )
        notification_serializer = NotificationSerializer(notification)
        send_notification_to_user(package_request.user.id, notification_serializer.data)
        return self._standardize_response(Response(serializer.data))

    @action(detail=True, methods=['post'], url_path='send-request-message')
    def send_request_in_message(self, request, pk=None):
        """
        Sends the package request details as a message to the traveler.
        Creates a new conversation if one does not already exist.
        Also sends the message in real time via Django Channels.
        """
        package_request = self.get_object()

        # 1. Permission Check: Only the request owner can send the message.
        if request.user != package_request.user:
            return self._standardize_response(
                Response(
                    {"error": "You do not have permission to perform this action."},
                    status=status.HTTP_403_FORBIDDEN
                ),
                status_code=status.HTTP_403_FORBIDDEN
            )

        travel_listing = package_request.travel_listing
        traveler = travel_listing.user

        # 2. Get or create the conversation.
        conversation, created = Conversation.objects.get_or_create(
            package_request=package_request,
            defaults={'travel_listing': travel_listing}
        )
        if created:
            conversation.participants.set([request.user, traveler])

        # 3. Format the message content.
        message_lines = ["Hi! I'd like to send the following items:"]
        items = {
            'phone': package_request.number_of_phone,
            'PC': package_request.number_of_pc,
            'tablet': package_request.number_of_tablet,
            'document': package_request.number_of_document,
            'full suitcase': package_request.number_of_full_suitcase
        }

        has_items = False
        for item, count in items.items():
            if count > 0:
                has_items = True
                plural = 's' if count > 1 and 'suitcase' not in item else ''
                message_lines.append(f"- {count} x {item}{plural}")

        if package_request.weight and Decimal(package_request.weight) > 0:
            has_items = True
            message_lines.append(f"- {package_request.weight}kg of other items ({package_request.package_description or 'not specified'}).")
        
        if not has_items:
            return self._standardize_response(
                Response(
                    {"error": "Cannot send an empty request. Please specify items or weight."},
                    status=status.HTTP_400_BAD_REQUEST
                ),
                status_code=status.HTTP_400_BAD_REQUEST
            )

        message_lines.append(f"\nTotal price: {package_request.total_price} {travel_listing.currency}")
        message_content = "\n".join(message_lines)

        # 4. Create and send the message (DB).
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=message_content
        )

        # 5. Send the message in real time via Channels.
        channel_layer = get_channel_layer()
        message_dict = {
            'id': message.id,
            'content': message.content,
            'sender': {
                'id': message.sender.id,
                'username': message.sender.username,
                'email': message.sender.email
            },
            'created_at': message.created_at.isoformat(),
            'attachments': []
        }
        async_to_sync(channel_layer.group_send)(
            f'chat_{conversation.id}',
            {
                'type': 'chat_message',
                'message': message_dict
            }
        )

        return self._standardize_response(Response({"detail": "Request message sent successfully."}))

class AlertViewSet(StandardResponseViewSet):
    """
    API endpoint for travel alerts
    """
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Alert.objects.all()
        pickup_country = self.request.query_params.get('pickup_country')
        pickup_region = self.request.query_params.get('pickup_region')
        destination_country = self.request.query_params.get('destination_country')
        destination_region = self.request.query_params.get('destination_region')
        from_travel_date = self.request.query_params.get('from_travel_date')
        to_travel_date = self.request.query_params.get('to_travel_date')
        notify_for_any_pickup_city = self.request.query_params.get('notify_for_any_pickup_city')
        notify_for_any_destination_city = self.request.query_params.get('notify_for_any_destination_city')
        if pickup_country:
            queryset = queryset.filter(pickup_country_id=pickup_country)
        if pickup_region:
            queryset = queryset.filter(pickup_region_id=pickup_region)
        if destination_country:
            queryset = queryset.filter(destination_country_id=destination_country)
        if destination_region:
            queryset = queryset.filter(destination_region_id=destination_region)
        if from_travel_date:
            queryset = queryset.filter(from_travel_date__gte=from_travel_date)
        if to_travel_date:
            queryset = queryset.filter(to_travel_date__lte=to_travel_date)
        if notify_for_any_pickup_city is not None:
            queryset = queryset.filter(notify_for_any_pickup_city=notify_for_any_pickup_city.lower() in ['true', '1'])
        if notify_for_any_destination_city is not None:
            queryset = queryset.filter(notify_for_any_destination_city=notify_for_any_destination_city.lower() in ['true', '1'])
        return queryset

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

class ReviewViewSet(StandardResponseViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Only the reviewer can create, update, partial_update, or delete
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsReviewerOnly()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

    @action(detail=False, methods=['get'], url_path='by-travel-listing-owner/(?P<owner_id>[^/.]+)')
    def by_travel_listing_owner(self, request, owner_id=None):
        reviews = Review.objects.filter(travel_listing__user_id=owner_id)
        serializer = self.get_serializer(reviews, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=False, methods=['get'], url_path='by-package-request-owner/(?P<owner_id>[^/.]+)')
    def by_package_request_owner(self, request, owner_id=None):
        reviews = Review.objects.filter(package_request__user_id=owner_id)
        serializer = self.get_serializer(reviews, many=True)
        return self._standardize_response(Response(serializer.data))

class IsReviewerOnly(IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        return obj.reviewer == request.user


class TransportTypeViewset(StandardResponseViewSet):
    """
    API endpoint for transport types
    """
    queryset = TransportType.objects.all()
    serializer_class = TransportTypeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

class PackageTypeViewSet(StandardResponseViewSet):
    """
    API endpoint for package types
    """
    queryset = PackageType.objects.all()
    serializer_class = PackageTypeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]
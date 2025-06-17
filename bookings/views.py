from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Booking, BookingMessage, BookingStatusUpdate
from .serializers import (
    BookingSerializer, BookingCreateSerializer, BookingMessageSerializer,
    BookingStatusUpdateSerializer
)
from config.views import StandardResponseViewSet

# Create your views here.

class BookingViewSet(StandardResponseViewSet):
    """
    API endpoint for bookings
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()

    def get_queryset(self):
        return Booking.objects.filter(
            Q(traveler=self.request.user) | Q(sender=self.request.user)
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        return BookingSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        booking = self.get_object()
        serializer = BookingStatusUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self._standardize_response(
                Response(
                    {"detail": "Validation failed", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            )

        new_status = serializer.validated_data['status']
        reason = serializer.validated_data.get('reason', '')

        # Check if user has permission to update status
        if request.user not in [booking.traveler, booking.sender]:
            return self._standardize_response(
                Response(
                    {"detail": "You do not have permission to update this booking"},
                    status=status.HTTP_403_FORBIDDEN
                )
            )

        # Create status update record
        BookingStatusUpdate.objects.create(
            booking=booking,
            updated_by=request.user,
            old_status=booking.status,
            new_status=new_status,
            reason=reason
        )

        # Update booking status
        booking.status = new_status
        booking.save()

        return self._standardize_response(Response(BookingSerializer(booking).data))

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        booking = self.get_object()
        serializer = BookingMessageSerializer(data=request.data)
        
        if not serializer.is_valid():
            return self._standardize_response(
                Response(
                    {"detail": "Validation failed", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            )

        # Check if user is part of the booking
        if request.user not in [booking.traveler, booking.sender]:
            return self._standardize_response(
                Response(
                    {"detail": "You do not have permission to send messages for this booking"},
                    status=status.HTTP_403_FORBIDDEN
                )
            )

        message = BookingMessage.objects.create(
            booking=booking,
            sender=request.user,
            message=serializer.validated_data['message']
        )

        return self._standardize_response(Response(BookingMessageSerializer(message).data))

    @action(detail=False, methods=['get'])
    def my_bookings(self, request):
        user = request.user
        bookings = Booking.objects.filter(
            Q(traveler=user) | Q(sender=user)
        ).order_by('-created_at')
        
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self._standardize_response(Response(self.get_paginated_response(serializer.data).data))

        serializer = self.get_serializer(bookings, many=True)
        return self._standardize_response(Response(serializer.data))

    @action(detail=False, methods=['get'])
    def active_bookings(self, request):
        user = request.user
        bookings = Booking.objects.filter(
            (Q(traveler=user) | Q(sender=user)) &
            ~Q(status__in=['completed', 'cancelled', 'rejected'])
        ).order_by('-created_at')
        
        page = self.paginate_queryset(bookings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self._standardize_response(Response(self.get_paginated_response(serializer.data).data))

        serializer = self.get_serializer(bookings, many=True)
        return self._standardize_response(Response(serializer.data))

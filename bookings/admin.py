from django.contrib import admin
from .models import Booking, BookingMessage, BookingStatusUpdate

class BookingMessageInline(admin.TabularInline):
    model = BookingMessage
    extra = 0
    readonly_fields = ('created_at',)

class BookingStatusUpdateInline(admin.TabularInline):
    model = BookingStatusUpdate
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'traveler', 'sender', 'status', 'package_weight',
                   'price_per_kg', 'total_price', 'currency', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('traveler__email', 'sender__email', 'notes')
    ordering = ('-created_at',)
    inlines = [BookingMessageInline, BookingStatusUpdateInline]

@admin.register(BookingMessage)
class BookingMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'sender', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('booking__id', 'sender__email', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

@admin.register(BookingStatusUpdate)
class BookingStatusUpdateAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'updated_by', 'old_status', 'new_status', 'created_at')
    list_filter = ('old_status', 'new_status', 'created_at')
    search_fields = ('booking__id', 'updated_by__email', 'reason')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

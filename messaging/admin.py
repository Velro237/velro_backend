from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['created_at', 'sender', 'is_read']
    fields = ['sender', 'content', 'is_read', 'created_at']
    can_delete = False

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'participants_display', 'travel_listing_link', 'package_request_link', 'message_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at', 'travel_listing', 'package_request']
    search_fields = ['participants__username', 'participants__email']
    readonly_fields = ['created_at', 'updated_at', 'message_count_display']
    filter_horizontal = ['participants']
    inlines = [MessageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('participants', 'created_at', 'updated_at')
        }),
        ('Related Items', {
            'fields': ('travel_listing', 'package_request'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('message_count_display',),
            'classes': ('collapse',)
        }),
    )

    def participants_display(self, obj):
        participants = obj.participants.all()
        if participants:
            return ", ".join([p.username for p in participants])
        return "No participants"
    participants_display.short_description = "Participants"

    def travel_listing_link(self, obj):
        if obj.travel_listing:
            url = reverse('admin:listings_travellisting_change', args=[obj.travel_listing.id])
            return format_html('<a href="{}">Travel Listing {}</a>', url, obj.travel_listing.id)
        return "None"
    travel_listing_link.short_description = "Travel Listing"

    def package_request_link(self, obj):
        if obj.package_request:
            url = reverse('admin:listings_packagerequest_change', args=[obj.package_request.id])
            return format_html('<a href="{}">Package Request {}</a>', url, obj.package_request.id)
        return "None"
    package_request_link.short_description = "Package Request"

    def message_count(self, obj):
        
        return obj.messages.count()
    message_count.short_description = "Messages"

    def message_count_display(self, obj):
        count = obj.messages.count()
        return f"{count} message{'s' if count != 1 else ''}"
    message_count_display.short_description = "Total Messages"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'conversation_link', 'content_preview', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at', 'sender', 'conversation']
    search_fields = ['content', 'sender__username', 'sender__email', 'conversation__id']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Message Details', {
            'fields': ('conversation', 'sender', 'content', 'is_read')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),

    )

    def conversation_link(self, obj):
        url = reverse('admin:messaging_conversation_change', args=[obj.conversation.id])
        return format_html('<a href="{}">Conversation {}</a>', url, obj.conversation.id)
    conversation_link.short_description = "Conversation"

    def content_preview(self, obj):
        content = obj.content[:100]
        if len(obj.content) > 100:
            content += "..."
        return content
    content_preview.short_description = "Content Preview"


# Customize admin site
admin.site.site_header = "Verlo Admin"
admin.site.site_title = "Verlo Admin Portal"
admin.site.index_title = "Welcome to Verlo Administration"

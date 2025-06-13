from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile, OTP

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('profile_picture', 'contact_info', 'languages', 'travel_history', 
              'preferences', 'identity_card', 'selfie_photo', 'phone_number', 
              'address', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('id', 'email', 'username', 'first_name', 'last_name', 'is_staff',
                   'is_email_verified', 'is_phone_verified', 'is_identity_verified',
                   'is_profile_completed', 'privacy_policy_accepted', 'date_privacy_accepted')
    list_filter = ('is_staff', 'is_superuser', 'is_email_verified', 'is_phone_verified',
                  'is_identity_verified', 'is_profile_completed', 'privacy_policy_accepted')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Verification Status', {'fields': ('is_email_verified', 'is_phone_verified', 
                                          'is_identity_verified', 'is_profile_completed')}),
        ('Privacy Policy', {'fields': ('privacy_policy_accepted', 'date_privacy_accepted')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                  'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'phone_number'),
        }),
    )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone_number', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'phone_number', 'contact_info', 'address')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Contact Information', {'fields': ('phone_number', 'contact_info', 'address')}),
        ('Profile Details', {'fields': ('profile_picture', 'languages', 'travel_history', 'preferences')}),
        ('Verification Documents', {'fields': ('identity_card', 'selfie_photo')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone_number', 'code', 'purpose', 'created_at', 'is_used')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('user__email', 'user__username', 'code', 'user__phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    def phone_number(self, obj):
        return obj.user.phone_number
    phone_number.short_description = 'Phone Number'

admin.site.register(CustomUser, CustomUserAdmin)

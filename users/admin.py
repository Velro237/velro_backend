from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile, OTP

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff',
                   'is_email_verified', 'is_phone_verified', 'is_identity_verified',
                   'is_profile_completed')
    list_filter = ('is_staff', 'is_superuser', 'is_email_verified', 'is_phone_verified',
                  'is_identity_verified', 'is_profile_completed')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)

admin.site.register(User, CustomUserAdmin)

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'purpose', 'created_at', 'is_used')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('user__email', 'user__username', 'code')
    ordering = ('-created_at',)

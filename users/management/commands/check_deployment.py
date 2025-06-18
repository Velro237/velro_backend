from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Check deployment settings and environment variables'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Deployment Settings Check ==='))
        
        # Check critical settings
        self.stdout.write(f"DEBUG: {settings.DEBUG}")
        self.stdout.write(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        self.stdout.write(f"SECRET_KEY: {'Set' if settings.SECRET_KEY else 'Not Set'}")
        
        # Check session settings
        self.stdout.write(f"SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
        self.stdout.write(f"CSRF_COOKIE_SECURE: {settings.CSRF_COOKIE_SECURE}")
        self.stdout.write(f"SESSION_COOKIE_DOMAIN: {settings.SESSION_COOKIE_DOMAIN}")
        self.stdout.write(f"CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")
        
        # Check database
        self.stdout.write(f"Database Engine: {settings.DATABASES['default']['ENGINE']}")
        
        # Check static files
        self.stdout.write(f"STATIC_ROOT: {settings.STATIC_ROOT}")
        self.stdout.write(f"STATIC_URL: {settings.STATIC_URL}")
        
        # Check environment variables
        self.stdout.write('\n=== Environment Variables ===')
        env_vars = [
            'SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
            'SESSION_COOKIE_DOMAIN', 'DATABASE_URL', 'CORS_ALLOWED_ORIGINS'
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                if 'SECRET_KEY' in var:
                    self.stdout.write(f"{var}: {'Set' if value else 'Not Set'}")
                else:
                    self.stdout.write(f"{var}: {value}")
            else:
                self.stdout.write(f"{var}: Not Set")
        
        self.stdout.write(self.style.SUCCESS('\n=== Check Complete ===')) 
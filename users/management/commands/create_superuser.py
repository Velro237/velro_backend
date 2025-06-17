from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser if none exists'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS('Superuser already exists'))
            return

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@gmail.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
        phone_number = os.environ.get('DJANGO_SUPERUSER_PHONE', '+251912345678')

        try:
            superuser = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                phone_number=phone_number
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser {username} created successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating superuser: {str(e)}')) 
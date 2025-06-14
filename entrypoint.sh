#!/bin/sh

# Run migrations
echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Daphne
echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application 
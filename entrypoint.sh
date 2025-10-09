#!/bin/sh

# # Wait for Postgres to be ready
# echo "Waiting for db to be ready..."
# until nc -z db 5432; do
#   sleep 1
# done
# echo "Database is ready!"

# Run migrations
echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser
echo "Creating superuser..."
python manage.py create_super_user

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Start Uvicorn
# echo "Starting Uvicorn ..."
# exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --ws-max-size 2097152 
echo "Starting Daphne ..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application

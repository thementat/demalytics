#!/bin/bash
# Database initialization script
# This script runs migrations and initializes baseline data

set -e

echo "Running database migrations..."
python manage.py migrate

echo ""
echo "Initializing baseline data..."
python manage.py init_data

echo ""
echo "Database initialization complete!"
echo ""
echo "You can now:"
echo "  - Access Django admin at http://localhost:8000/admin"
echo "  - Create a superuser: docker compose exec web python manage.py createsuperuser"

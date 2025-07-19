#!/bin/bash
set -e

echo "Waiting for MySQL to be ready..."
until mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1;" &>/dev/null; do
  sleep 1
done

# Run migrations if they haven't been initialized
if [ ! -d "migrations" ]; then
    echo "Initializing migrations directory..."
    flask db init
fi

# Always generate migration files (safe even if no changes)
echo "Generating migration files..."
flask db migrate -m "Auto migration" || true  # Don't fail if no changes detected

echo "Applying migrations..."
flask db upgrade

echo "Starting Flask app..."
exec gunicorn -w 1 -b 0.0.0.0:5000 server:app
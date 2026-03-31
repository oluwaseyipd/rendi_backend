#!/usr/bin/env bash
set -o errexit

echo "==> Upgrading pip..."
python -m pip install --upgrade pip

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate

echo "==> Build complete!"

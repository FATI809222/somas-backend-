# D:\Stage SOMAS\somas_backend\start.sh
#!/bin/bash

# ⭐ Attendre que la base de données soit prête
echo "⏳ Waiting for database..."
sleep 5

# ⭐ Exécuter les migrations
echo "🔄 Running migrations..."
python manage.py migrate

# ⭐ Collecter les fichiers statiques
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

# ⭐ Lancer Gunicorn (production)
echo "🚀 Starting Gunicorn..."
gunicorn somas_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 300
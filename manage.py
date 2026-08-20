#!/usr/bin/env python
# manage.py
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv

def main():
    """Run administrative tasks."""
    # ⭐ Charger .env AVANT de lancer Django
    load_dotenv()
    print("="*60)
    print("🔍 MANAGE.PY - VÉRIFICATION .env")
    print("="*60)
    print(f"📌 GEMINI_API_KEY: {os.getenv('GEMINI_API_KEY', 'NON TROUVÉE')[:10]}...")
    print(f"📌 GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'NON TROUVÉ')}")
    print("="*60)
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'somas_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
    
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'somas_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

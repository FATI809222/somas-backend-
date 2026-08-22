# somas_backend/settings.py
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

# ═══════════════════════════════════════════════════════════════
# 1. CHARGER LES VARIABLES D'ENVIRONNEMENT
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent.parent

# Charger .env depuis la racine
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Fichier .env chargé depuis: {env_path}")
else:
    print(f"⚠️ Fichier .env non trouvé à: {env_path}")

# ═══════════════════════════════════════════════════════════════
# 2. CONFIGURATION GÉNÉRALE
# ═══════════════════════════════════════════════════════════════

# ✅ UTILISER UNE VARIABLE D'ENVIRONNEMENT
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY non définie dans .env")

# ✅ UTILISER .env
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# ✅ DÉFINIR LES HÔTES AUTORISÉS
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# ═══════════════════════════════════════════════════════════════
# 3. APPLICATIONS INSTALLÉES
# ═══════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # ⭐ Packages tiers
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # ⭐ AJOUTER CETTE LIGNE
    'corsheaders',
    
    # ⭐ Applications du projet
    'api',
    'core',
]

# ═══════════════════════════════════════════════════════════════
# 4. MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # ⭐ DOIT être en premier
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'somas_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'somas_backend.wsgi.application'

# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# 5. BASE DE DONNÉES - SUPABASE (PRODUCTION) / SQLite (DEV)
# ═══════════════════════════════════════════════════════════════

# Récupérer DATABASE_URL depuis .env
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # ⭐ Utiliser Supabase (PostgreSQL)
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
    print("✅ Base de données: Supabase PostgreSQL")
else:
    # ⭐ Fallback SQLite (développement)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("⚠️ Base de données: SQLite (développement)")

# ═══════════════════════════════════════════════════════════════
# 6. VALIDATION DES MOTS DE PASSE
# ═══════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ═══════════════════════════════════════════════════════════════
# 7. INTERNATIONALISATION
# ═══════════════════════════════════════════════════════════════

LANGUAGE_CODE = 'fr-fr'  # ⭐ Changé en français
TIME_ZONE = 'Europe/Paris'  # ⭐ Changé pour Paris
USE_I18N = True
USE_TZ = True

# ═══════════════════════════════════════════════════════════════
# 8. FICHIERS STATIQUES ET MÉDIAS
# ═══════════════════════════════════════════════════════════════

STATIC_URL = 'static/'
MEDIA_URL = '/uploads/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'uploads')
 
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ═══════════════════════════════════════════════════════════════
# 9. CORS
# ═══════════════════════════════════════════════════════════════

# ✅ LISTE RESTREINTE
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOWED_ORIGINS = [url.strip() for url in CORS_ALLOWED_ORIGINS if url.strip()]# Pour la production, utilisez plutôt :
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://localhost:5173",
# ]

# ═══════════════════════════════════════════════════════════════
# 10. REST FRAMEWORK
# ═══════════════════════════════════════════════════════════════

# somas_backend/settings.py

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',  # ✅ Changé en AllowAny
    ),
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# ✅ SÉCURITÉ POUR LA PRODUCTION
if not DEBUG:
    # HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Protection XSS
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    # HSTS
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Session
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True

# ═══════════════════════════════════════════════════════════════
# 11. JWT
# ═══════════════════════════════════════════════════════════════

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ═══════════════════════════════════════════════════════════════
# 12. GEMINI API - Clé depuis .env
# ═══════════════════════════════════════════════════════════════

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')

# Vérification au démarrage
if GEMINI_API_KEY:
    print(f"✅ Gemini API Key chargée: {GEMINI_API_KEY[:10]}...")
    print(f"✅ Gemini Model: {GEMINI_MODEL}")
else:
    print("⚠️ ATTENTION: GEMINI_API_KEY non trouvée dans .env")
    print("   Veuillez créer un fichier .env avec GEMINI_API_KEY=...")

# ═══════════════════════════════════════════════════════════════
# 13. POPPLER (pour l'OCR)
# ═══════════════════════════════════════════════════════════════

POPPLER_PATH = r"C:\Program Files\poppler\poppler-26.02.0\Library\bin"

# ═══════════════════════════════════════════════════════════════
# 14. LOGGING (optionnel - pour le débogage)
# ═══════════════════════════════════════════════════════════════

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
} 
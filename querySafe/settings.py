from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

# File storage path dynamic
if ENVIRONMENT == "production":
    DATA_DIR = "/data"  # Mounted Google Storage bucket path
else:
    DATA_DIR = BASE_DIR  # Local storage fallback


SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
PROJECT_NAME = os.getenv('PROJECT_NAME', 'QuerySafe')

# Allow specific hosts
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,console.querysafe.in,.querysafe.ai,.run.app,0.0.0.0').split(',')

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'https://console.querysafe.in,https://*.querysafe.ai,https://*.run.app,http://localhost,https://localhost,http://127.0.0.1,https://127.0.0.1,http://0.0.0.0,https://0.0.0.0').split(',')

# Security settings for Cloud Run
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Cloud Run handles SSL redirect
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# Website URL for widget code
WEBSITE_URL = os.getenv('WEBSITE_URL')

# Razorpay keys (read from .env)
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')

# Google OAuth 2.0 settings
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')

# Vertex AI settings
PROJECT_ID = os.getenv('PROJECT_ID')
REGION = os.getenv('REGION')
# Gemini API location — can differ from Cloud Run region if models aren't available locally
GEMINI_LOCATION = os.getenv('GEMINI_LOCATION', 'us-central1')

# Gemini model names (change here to upgrade models globally)
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.0-flash')
GEMINI_VISION_MODEL = os.getenv('GEMINI_VISION_MODEL', 'gemini-2.0-flash')

# Paths for FAISS indices and metadata
INDEX_DIR = os.path.join(DATA_DIR, "documents", "vector_index")
META_DIR = os.path.join(DATA_DIR, "documents", "chunk-metadata")

# Create directories if they don't exist
os.makedirs(INDEX_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

# Email Settings
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.hostinger.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 465))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True') == 'True'
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'no-reply@metricvibes.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@metricvibes.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'contactmedipanshu@gmail.com')  # Add this if missing

# Note: For Hostinger, we use SSL instead of TLS

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'user_querySafe',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # WhiteNoise for static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'querySafe.urls'

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
                'user_querySafe.context_processors.project_name',
            ],
        },
    },
]

WSGI_APPLICATION = 'querySafe.wsgi.application'

# Database
# Production uses Cloud SQL PostgreSQL; local dev uses SQLite

if ENVIRONMENT == "production":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'querysafe'),
            'USER': os.getenv('DB_USER', 'querysafe'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '/cloudsql/querysafe-dev:asia-south1:querysafe-db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(DATA_DIR, os.getenv("DATABASE_NAME", "db.sqlite3")),
        }
    }

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

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en-us')

TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "user_querySafe" / "static",
]

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(DATA_DIR, "media")

# Ensure directories exist
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "static"), exist_ok=True)


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FILE_UPLOAD_PERMISSIONS = None
FILE_UPLOAD_DIRECTORY_PERMISSIONS = None
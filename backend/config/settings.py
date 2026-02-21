"""
Django settings for SmartExpense project.
"""
import os
import dj_database_url
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# ================================================
#            ENVIRONMENT VARIABLES
# ================================================

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR.parent, ".env"))

DEBUG = env('DEBUG', default=False, cast=bool)
# --------------------------
#       VARIABLES
# --------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
TELEGRAM_TOKEN = env("TELEGRAM_BOT_TOKEN")
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')



# ----------------------------
#   DataBase configuration
# ----------------------------
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "django_extensions",
    "corsheaders",
    # Local apps
    "apps.core",
    "apps.api",
    "apps.bot",
]

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



# ======================================================
#  
#       PRODUCTION/DEVELOPMENT CONFIGURATION
#
# ======================================================

# --------------------------
#     DATABASE AND CORS
# --------------------------
if DEBUG:
    DATABASES['default']['OPTIONS'] = {'sslmode': 'disable'}
    CORS_ALLOW_ALL_ORIGINS = True
else:
    DATABASES['default']['CONN_MAX_AGE'] = 600
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
    CORS_ALLOW_ALL_ORIGINS = False



# -------------
#    RAILWAY
# -------------
IS_PRODUCTION = env.bool('RAILWAY_ENVIRONMENT_NAME', default=False)

if IS_PRODUCTION:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]



# -------------
#     CORS
# -------------
CORS_ALLOWED_ORIGINS = [FRONTEND_URL,]



# -------------
#    CELERY
# -------------
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

# GLOBAL
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
# Serializacion
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
# Timezone
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
# Task Tracking
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 20 * 60  # CALCULANDO EN MINUTOS (20 MINUTOS MAX)
CELERY_TASK_SOFT_TIME_LIMIT = 15 * 60  # Warning a los 15 minutos


if DEBUG:
    CELERY_WORKER_POOL = 'solo'
else:
    CELERY_WORKER_POOL = 'prefork'
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True



# --------------------------
#   Logging configuration
# --------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
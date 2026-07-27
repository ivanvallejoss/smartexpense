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

_env_file = os.path.join(BASE_DIR.parent, ".env")
if os.path.exists(_env_file):
    environ.Env.read_env(_env_file)

DEBUG = env('DEBUG', default=False, cast=bool)

# --------------------------
#       VARIABLES
# --------------------------
SECRET_KEY = env("SECRET_KEY")

JWT_SECRET_KEY = env("JWT_SECRET_KEY")

TELEGRAM_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_TOKEN = env('TELEGRAM_WEBHOOK_TOKEN')

FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

FRONTEND_TEST = env('FRONTEND_TEST', default='http://localhost:5173')

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
# La politica de TLS (sslmode) NO vive aca: viaja como query param en
# DATABASE_URL. Depende de donde corre el Postgres, no de si DEBUG esta
# prendido — y ademas sslmode es un parametro de libpq que SQLite no acepta,
# por lo que aplicarlo incondicionalmente rompia el fallback a sqlite.
# Ver .env.example.
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    DATABASES['default']['CONN_MAX_AGE'] = 600
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    CORS_ALLOW_ALL_ORIGINS = False



# -------------
#    ENTORNO
# -------------
# Nombre explicito del entorno donde corre el proceso. No se deriva de DEBUG:
# DEBUG es un flag de comportamiento de Django, no una descripcion de la
# infraestructura. Tampoco se deriva de variables del proveedor de hosting.
ENVIRONMENT = env("ENVIRONMENT", default="dev")

# El default abierto aplica solo en desarrollo real (dev + DEBUG). En cualquier
# otro caso la lista vacia es intencional: Django rechaza los requests hasta
# que ALLOWED_HOSTS se configure explicitamente. Fallar ruidosamente es
# preferible a aceptar cualquier Host header en silencio.
_hosts_abiertos = DEBUG and ENVIRONMENT == "dev"
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"] if _hosts_abiertos else [])



# -------------
#     CORS
# -------------
CORS_ALLOWED_ORIGINS = [FRONTEND_URL, FRONTEND_TEST]



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
"""
Django settings for adom project.
"""

import os
import tempfile
from pathlib import Path
from decouple import config
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def csv_config(name, default=''):
    return [value.strip() for value in config(name, default=default).split(',') if value.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_INSECURE_SECRET_KEY = 'django-insecure-d0%ed(=dcva)nn18s1n9)vom8hr84$ztty3cbo&9@#+3sa+b!8'
SECRET_KEY = config('SECRET_KEY', default=DEFAULT_INSECURE_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = csv_config('ALLOWED_HOSTS', default='localhost,127.0.0.1')
if DEBUG and 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')

if not DEBUG and SECRET_KEY == DEFAULT_INSECURE_SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be configured when DEBUG=False.')

if not DEBUG:
    unsafe_hosts = {'*', 'localhost', '127.0.0.1', 'testserver'}
    if not ALLOWED_HOSTS or any(host in unsafe_hosts for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured(
            'ALLOWED_HOSTS must contain only production hostnames when DEBUG=False.'
        )

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'channels',
    'drf_yasg',
    'django_extensions',
    
    # Local apps
    'accounts',
    'students',
    'teachers',
    'academics',
    'fees',
    'attendance',
    'communication',
    'timetable',
    'library',
    'analytics',
    'adom_institute',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'adom.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.role_ui',
            ],
            'builtins': [
                'accounts.templatetags.adom_filters',
            ],
        },
    },
]

WSGI_APPLICATION = 'adom.wsgi.application'
ASGI_APPLICATION = 'adom.asgi.application'

# Database
DB_ENGINE = config('DB_ENGINE', default='sqlite')
if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        }
    }
else:
    sqlite_name = config('SQLITE_DB_NAME', default='adom.sqlite3')
    sqlite_path = config('SQLITE_DB_PATH', default=str(Path(tempfile.gettempdir()) / sqlite_name))
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
        }
    }

if not DEBUG and DB_ENGINE != 'postgresql':
    raise ImproperlyConfigured('DB_ENGINE=postgresql is required when DEBUG=False.')

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Learning-material policy.
# MATERIALS_READ_ONLY: only administrators and teachers may upload, edit or
# delete learning material; everyone else gets view-only access.
# ALLOW_MATERIAL_DOWNLOADS: when false, material is streamed inline to
# authenticated users and no endpoint will send it as an attachment.
MATERIALS_READ_ONLY = config('MATERIALS_READ_ONLY', default=True, cast=bool)
ALLOW_MATERIAL_DOWNLOADS = config('ALLOW_MATERIAL_DOWNLOADS', default=False, cast=bool)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Site ID for django.contrib.sites
SITE_ID = 1

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'adom.pagination.DefaultOrderedPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('DRF_ANON_THROTTLE_RATE', default='100/hour'),
        'user': config('DRF_USER_THROTTLE_RATE', default='1000/hour'),
    },
}

# Django Allauth Configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[ADOM Institute] '
# allauth 0.57 equivalents required for the username-less custom User model
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True

# Email Configuration (Development - Console Backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@adominstitute.com'

# Channels Configuration (WebSockets)
# Uses a dedicated Redis DB (2) so the channel layer never collides with the
# cache or the Celery broker/result backend.
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [config('REDIS_CHANNEL_URL', default='redis://127.0.0.1:6379/2')],
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Redis-backed caching + sessions.
# Enabled only when REDIS_URL is explicitly set (production/compose).
# Falls back to local-memory/db sessions so local development keeps working
# with zero configuration.
_redis_url = os.environ.get('REDIS_URL', config('REDIS_URL', default=''))
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
        },
        'session': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'TIMEOUT': 60 * 60 * 24,
        },
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'adom-default-cache',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ADOM Institute AI Configuration
# Open-source-first runtime defaults. Production can point these to Ollama,
# vLLM, llama.cpp server, Hugging Face TGI, or internally hosted endpoints.
ADOM_INSTITUTE_AI_ENABLED = config('ADOM_INSTITUTE_AI_ENABLED', default=False, cast=bool)
ADOM_INSTITUTE_AI_PROVIDER = config('ADOM_INSTITUTE_AI_PROVIDER', default='ollama')
ADOM_INSTITUTE_AI_CHAT_MODEL = config('ADOM_INSTITUTE_AI_CHAT_MODEL', default='qwen2.5:7b-instruct')
ADOM_INSTITUTE_AI_REASONING_MODEL = config('ADOM_INSTITUTE_AI_REASONING_MODEL', default='deepseek-r1:8b')
ADOM_INSTITUTE_AI_EMBEDDING_MODEL = config('ADOM_INSTITUTE_AI_EMBEDDING_MODEL', default='BAAI/bge-m3')
ADOM_INSTITUTE_AI_RERANKER_MODEL = config('ADOM_INSTITUTE_AI_RERANKER_MODEL', default='BAAI/bge-reranker-v2-m3')
ADOM_INSTITUTE_AI_VECTOR_STORE = config('ADOM_INSTITUTE_AI_VECTOR_STORE', default='pgvector')
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434')

# File Storage (S3-compatible object storage, e.g. OCI Object Storage or AWS S3)
if config('USE_S3', default=False, cast=bool):
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-ashburn-1')
    # OCI Object Storage exposes an S3-compatible endpoint. Leave unset for AWS S3.
    AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default=None)
    AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default=None)
    AWS_S3_ADDRESSING_STYLE = config('AWS_S3_ADDRESSING_STYLE', default='virtual')
    AWS_S3_OBJECT_PARAMETERS = {
        # Material is streamed through Django with its own no-store headers, so
        # the objects themselves must never sit in a shared/intermediary cache.
        'CacheControl': 'no-store',
    }
    AWS_QUERYSTRING_AUTH = config('AWS_QUERYSTRING_AUTH', default=True, cast=bool)
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_EXPIRE = 3600
    if not AWS_QUERYSTRING_AUTH:
        # A public bucket would make every material file fetchable by URL,
        # bypassing the authenticated inline viewer entirely.
        raise ImproperlyConfigured(
            'AWS_QUERYSTRING_AUTH must be True: learning material is only served '
            'through the authenticated read-only viewer, so public object URLs '
            'would defeat that control.'
        )
    # Static and media live in separate prefixes inside the same bucket.
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {'location': 'media'},
        },
        'staticfiles': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
            'OPTIONS': {'location': 'static'},
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# WhiteNoise cache headers for local static serving (falls back when not on object storage).
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0
WHITENOISE_USE_FINDERS = DEBUG

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if not DEBUG:
    # Trust the X-Forwarded-Proto header set by nginx (single node) or the
    # OCI Load Balancer (scaled) when terminating TLS.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
# Platform health probes (Railway, Docker, k8s) may hit /health/ over plain HTTP
# from inside the network. A 301 there makes the container look unhealthy, so the
# probe path is exempt from the HTTPS redirect. Everything else still redirects.
SECURE_REDIRECT_EXEMPT = [r'^health/$']
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=not DEBUG, cast=bool)

# CORS Settings
CORS_ALLOWED_ORIGINS = csv_config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000' if DEBUG else '',
)

# Debug Toolbar
INTERNAL_IPS = [
    '127.0.0.1',
]

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        # Unhandled 500s are logged to 'django.request' with a traceback. Without
        # this handler they only reach logs/django.log, which in the compose stack
        # lives in the `logsdata` volume, so `docker compose logs` shows nothing and
        # a failing endpoint is undiagnosable from outside the container.
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

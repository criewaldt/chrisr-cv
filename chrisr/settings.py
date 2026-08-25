import os
import dj_database_url
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# Load the .env file if it exists
ENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_PATH):
    import dotenv
    dotenv.load_dotenv(ENV_PATH)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', config('DJANGO_SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['chrisr-resume-1f6a2601c7fd.herokuapp.com', 'chrisriewaldt.com', '127.0.0.1', 'www.chrisriewaldt.com', 'localhost']

CSRF_TRUSTED_ORIGINS = [
    'https://chrisriewaldt.com',
    'https://www.chrisriewaldt.com',
    'https://chrisr-resume-1f6a2601c7fd.herokuapp.com',
]

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'chrisr',
    'resume',
    'bonnaroo',
    'reimbursable',
    'jobs',
    'studio',

    'rest_framework',
    'django_celery_results',
    'social_django',
]

AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('GOOGLE_CLIENT_ID', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['email', 'profile']
SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = ['picture']
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = os.environ.get(
    'GOOGLE_OAUTH2_REDIRECT_URI',
    'http://localhost:8000/social/complete/google-oauth2/',
)

LOGIN_URL = '/bonnaroo/'
LOGIN_REDIRECT_URL = '/bonnaroo/map/'
LOGOUT_REDIRECT_URL = '/bonnaroo/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'chrisr.urls'

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
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'chrisr.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
        ssl_require=True,
        engine='django_cockroachdb',
    )
}

_REDIS_URL = os.environ.get('REDIS_URL')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _REDIS_URL,
    } if _REDIS_URL else {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from chrisr.settings import TIME_ZONE

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get('GMAIL_USER', None)
EMAIL_HOST_PASSWORD = os.environ.get('GMAIL_PW', None)

#CELERY/REDIS
CELERY_BROKER_URL = os.environ.get('REDIS_URL', None)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_CONTENT_ENCODING = 'utf-8'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
# --- jobs app -------------------------------------------------------------
# Tier 1 triage is high-volume classification; tier 2 tailoring produces the
# document Chris actually submits. Spend accordingly. Both are overridable by
# env var so either stage can be re-pointed without a code change.
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
JOBS_TRIAGE_MODEL = os.environ.get('JOBS_TRIAGE_MODEL', 'claude-haiku-4-5')
JOBS_TAILOR_MODEL = os.environ.get('JOBS_TAILOR_MODEL', 'claude-opus-5')
JOBS_TRIAGE_CONCURRENCY = int(os.environ.get('JOBS_TRIAGE_CONCURRENCY', '6'))
JOBS_TAILOR_EFFORT = os.environ.get('JOBS_TAILOR_EFFORT', 'medium')

# Where digests go, and the base URL their deep links point at. Falls back to the
# Gmail sender so a missing config var still reaches an inbox rather than nowhere.
JOBS_DIGEST_TO = os.environ.get('JOBS_DIGEST_TO', '') or EMAIL_HOST_USER
JOBS_SITE_URL = os.environ.get('JOBS_SITE_URL', 'https://chrisriewaldt.com').rstrip('/')

# --- studio (services page) ----------------------------------------------
# The "Book a call" button renders only when a scheduling URL is configured, so
# the page never ships a button pointing at nothing.
STUDIO_CALENDAR_URL = os.environ.get('STUDIO_CALENDAR_URL', '')
STUDIO_NOTIFY_TO = os.environ.get('STUDIO_NOTIFY_TO', '') or EMAIL_HOST_USER

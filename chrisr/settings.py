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

    # Heroku terminates TLS and forwards over HTTP, so Django sees an insecure
    # request unless this header is trusted.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # OFF by default, deliberately. Cloudflare sits in front of this site, and when
    # its SSL/TLS mode is "Flexible" it fetches the origin over plain HTTP. Django
    # then sees X-Forwarded-Proto: http, redirects to HTTPS, Cloudflare fetches over
    # HTTP again -- an infinite loop that takes the whole site down. Cloudflare's
    # "Always Use HTTPS" already performs this redirect at the edge, which is the
    # right place for it. Only turn this on if Cloudflare is set to Full/Full-strict
    # and you want defence in depth.
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False') == 'True'

    # HSTS is deliberately short to start with. A long max-age is effectively
    # irreversible -- browsers refuse plain HTTP for the full duration, so a broken
    # certificate takes the site down until it expires. Verify HTTPS is solid, then
    # raise this to 31536000 (1 year) and only then consider preload.
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
        'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'False') == 'True'
    SECURE_HSTS_PRELOAD = False

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# Cap request bodies. The contact form needs a few KB; the default 2.5MB just gives
# an abusive client a bigger lever.
DATA_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200


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
    'jobs',
    'studio',

    'anymail',

    'rest_framework',
    'django_celery_results',
]

# The admin is the only thing that logs anyone in now, so its own login page is
# where a login_required redirect should land.
LOGIN_URL = '/admin/login/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'chrisr.middleware.SecurityHeadersMiddleware',
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

# --- email -----------------------------------------------------------------
# Postmark when a server token is present, Gmail SMTP otherwise, console in local
# development. Postmark is preferred for anything transactional: Gmail throttles
# around 500 messages a day and will restrict the account past that, and an SMTP
# timeout fails silently -- which for a contact form means a lost sales lead with
# no trace. Anymail raises a real exception instead.
# POSTMARK_API_KEY is accepted as an alias: the token is stored under that name
# in .env, and reading only POSTMARK_SERVER_TOKEN silently fell through to the
# console backend -- contact-form mail was printed to stdout, never delivered.
POSTMARK_SERVER_TOKEN = (os.environ.get('POSTMARK_SERVER_TOKEN', '')
                         or os.environ.get('POSTMARK_API_KEY', ''))

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = os.environ.get('GMAIL_USER', None)
EMAIL_HOST_PASSWORD = os.environ.get('GMAIL_PW', None)

if POSTMARK_SERVER_TOKEN:
    EMAIL_BACKEND = 'anymail.backends.postmark.EmailBackend'
    ANYMAIL = {
        'POSTMARK_SERVER_TOKEN': POSTMARK_SERVER_TOKEN,
        # Fail loudly on a bad recipient rather than reporting success.
        'IGNORE_UNSUPPORTED_FEATURES': False,
    }
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = os.environ.get(
        'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

# The From address must be one Postmark has verified -- a Sender Signature or, far
# better, an address on a domain you have verified with DKIM. Sending as
# @gmail.com through a third party fails DMARC alignment and lands in spam.
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@chrisriewaldt.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

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
# Where enquiries and digests land, independent of who sends them.
CONTACT_INBOX = os.environ.get('CONTACT_INBOX', 'criewaldt@gmail.com')

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
JOBS_TRIAGE_MODEL = os.environ.get('JOBS_TRIAGE_MODEL', 'claude-haiku-4-5')
JOBS_TAILOR_MODEL = os.environ.get('JOBS_TAILOR_MODEL', 'claude-opus-5')
JOBS_TRIAGE_CONCURRENCY = int(os.environ.get('JOBS_TRIAGE_CONCURRENCY', '6'))
JOBS_TAILOR_EFFORT = os.environ.get('JOBS_TAILOR_EFFORT', 'medium')

# Where digests go, and the base URL their deep links point at. Falls back to the
# Gmail sender so a missing config var still reaches an inbox rather than nowhere.
JOBS_DIGEST_TO = os.environ.get('JOBS_DIGEST_TO', '') or CONTACT_INBOX
JOBS_SITE_URL = os.environ.get('JOBS_SITE_URL', 'https://chrisriewaldt.com').rstrip('/')

# --- studio (services page) ----------------------------------------------
# The "Book a call" button renders only when a scheduling URL is configured, so
# the page never ships a button pointing at nothing.
STUDIO_CALENDAR_URL = os.environ.get('STUDIO_CALENDAR_URL', '')
STUDIO_NOTIFY_TO = os.environ.get('STUDIO_NOTIFY_TO', '') or CONTACT_INBOX

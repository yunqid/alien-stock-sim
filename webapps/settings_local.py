# Local development overrides.
# Run with: DJANGO_SETTINGS_MODULE=webapps.settings_local
from .settings import *  # noqa: F401,F403

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "alienstocksim_cache",
    }
}

# Configure the Google provider from .env so no SocialApp DB row is needed.
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),  # noqa: F405
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),  # noqa: F405
        },
    }
}

ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http'
SECURE_PROXY_SSL_HEADER = None
CSRF_TRUSTED_ORIGINS = []

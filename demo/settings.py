from pathlib import Path

DEBUG = True
SECRET_KEY = "formidant-demo-not-for-production"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ROOT_URLCONF = "demo.urls"
INSTALLED_APPS = ["formidant.django"]
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(__file__).parent / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]
USE_TZ = True

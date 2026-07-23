from pathlib import Path

SECRET_KEY = "formidant-test-suite"
USE_TZ = True
ALLOWED_HOSTS = ["testserver"]
ROOT_URLCONF = "tests.django.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(__file__).parent / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {},
    }
]

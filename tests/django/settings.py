from pathlib import Path

SECRET_KEY = "formidant-test-suite"
USE_TZ = True
ALLOWED_HOSTS = ["testserver"]
ROOT_URLCONF = "tests.django.urls"
INSTALLED_APPS = ["formidant.django"]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            Path(__file__).parent / "templates",
            Path(__file__).parent.parent.parent / "demo" / "templates",
        ],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DJ_INERTIAJS = {
    "LAYOUT": "layout.html",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "dj_inertiajs.middleware.InertiaMiddleware",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "dj_inertiajs",
    "tests.testapp.apps.TestAppConfig",
]

ROOT_URLCONF = "tests.testapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "tests/testapp",
        ],
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

# only in place to silence an error
SECRET_KEY = "django-insecure-3p_!uve+em7f45+74jh16)y)h00ve@9d2edh=cuebdsrbco%vb"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "unused"}}

# silence a warning
USE_TZ = False

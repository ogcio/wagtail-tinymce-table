"""
Pytest configuration.

Django must be fully configured before any wagtail/tinymce modules are
imported, so we use ``pytest_configure`` (the earliest hook) rather than a
module-level ``django.setup()`` call.
"""

import sys
import os

# Make the parent directory importable so ``wagtailtinymce`` is on sys.path
# when running pytest from inside the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def pytest_configure(config):
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                # django.contrib.staticfiles is required so that
                # staticfiles_storage.url() (called by Wagtail 7's
                # WidgetAdapter.media via versioned_static) resolves correctly.
                "django.contrib.staticfiles",
                "wagtail",
                # wagtail.admin must be present for wagtail.admin.telepath to
                # initialise its app registry entry (Wagtail 7+).
                "wagtail.admin",
                "tinymce",
                "wagtailtinymce",
            ],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            TINYMCE_DEFAULT_CONFIG={},
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            STATIC_URL="/static/",
            STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
            SECRET_KEY="test-secret-key-not-for-production",
        )

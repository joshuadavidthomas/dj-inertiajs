set dotenv-load := true
set unstable := true

[private]
default:
    @just --list --list-submodules

[private]
fmt:
    @just --fmt

bootstrap: lock
    uv sync --locked

# run pre-commit on all files
lint:
    uv run --with pre-commit-uv pre-commit run --all-files

lock:
    uv lock

# Run a Django management command
manage *COMMAND:
    #!/usr/bin/env python
    import sys

    try:
        from django.conf import settings
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    settings.configure(INSTALLED_APPS=["dj_inertiajs"])
    execute_from_command_line(sys.argv + "{{ COMMAND }}".split(" "))

test *ARGS:
    uv run pytest {{ ARGS }}

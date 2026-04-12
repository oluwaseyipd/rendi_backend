#!/usr/bin/env python
import os
import sys


def main():
    # Ensure the project root is always on sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "rendi_backend.settings.development"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and "
            "available on your PYTHONPATH environment variable."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

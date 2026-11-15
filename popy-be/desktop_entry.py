"""Start the local POS server used by the Windows installer.

Migrations run first. The shop owner is created later through /api/setup,
not by seed_pos (that command resets a built-in password).
"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")
    import django

    django.setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False)
    call_command("collectstatic", interactive=False, verbosity=0)

    from waitress import serve

    from config.wsgi import application

    host = os.environ.get("POPY_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("POPY_BIND_PORT", "18765"))
    serve(application, host=host, port=port, threads=8)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Popy server failed: {exc}", file=sys.stderr)
        raise

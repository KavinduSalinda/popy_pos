"""Start the local POS server used by the Windows installer.

Migrations run first. The shop owner is created later through /api/setup,
not by seed_pos (that command resets a built-in password).
"""

import os
import sys

# Embeddable Python's python312._pth resolves "." to the Python install
# folder and ignores the script directory and PYTHONPATH. The Django
# project lives next to this file, so put that folder on the path.
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _agent_log(hypothesis_id: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        import json
        import time

        with open(r"c:\Users\USER\Desktop\popy\.cursor\debug-cbaa89.log", "a", encoding="utf-8") as _log:
            _log.write(
                json.dumps(
                    {
                        "sessionId": "cbaa89",
                        "runId": "post-fix",
                        "hypothesisId": hypothesis_id,
                        "location": "desktop_entry.py",
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


def main() -> None:
    import importlib.util

    spec = importlib.util.find_spec("cryptography")
    import_error = ""
    if spec is not None:
        try:
            import cryptography  # noqa: F401
        except Exception as exc:
            import_error = f"{type(exc).__name__}: {exc}"
    # #region agent log
    _agent_log(
        "A",
        "cryptography availability before django setup",
        {
            "cryptographyFound": spec is not None,
            "cryptographyOrigin": getattr(spec, "origin", None) if spec else None,
            "importError": import_error,
            "executable": sys.executable,
        },
    )
    # #endregion
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")
    import django

    django.setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False)
    from apps.core.desktop_setup import promote_desktop_shops_to_pro

    promote_desktop_shops_to_pro()
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
        # #region agent log
        _agent_log(
            "B",
            "desktop server failed",
            {"errorType": type(exc).__name__, "error": str(exc)},
        )
        # #endregion
        print(f"Popy server failed: {exc}", file=sys.stderr)
        raise

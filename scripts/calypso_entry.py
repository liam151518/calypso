"""calypso_entry.py. Entry point used by PyInstaller.

Boots the Flask app as a sidecar. The Tauri shell spawns this binary on
Ready and kills it on Exit. Listens on 127.0.0.1 by default. Set
CALYPSO_HOST / CALYPSO_PORT env vars to override.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Make `app.*` importable regardless of CWD.
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    host = os.environ.get("CALYPSO_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("CALYPSO_PORT", "51730"))
    except ValueError:
        port = 51730

    from app.server import create_app

    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

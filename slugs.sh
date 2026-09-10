#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="$(command -v python3 || true)"
    if [[ -z "$PYTHON" ]]; then
        echo "Error: Python 3 is required." >&2
        exit 1
    fi

    if ! "$PYTHON" -c 'import dotenv, requests' >/dev/null 2>&1; then
        echo "Error: Plex TV Station dependencies are not installed." >&2
        echo "Run: python3 -m venv '$SCRIPT_DIR/.venv'" >&2
        echo "Then: '$SCRIPT_DIR/.venv/bin/python' -m pip install -r '$SCRIPT_DIR/requirements.txt'" >&2
        exit 1
    fi
fi

exec "$PYTHON" "$SCRIPT_DIR/src/main.py" slugs "$@"

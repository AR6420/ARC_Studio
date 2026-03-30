#!/usr/bin/env bash
# Start TRIBE v2 scorer using the Python 3.11 venv
# Usage: bash tribe_scorer/start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/Scripts/python.exe"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Python 3.11 venv not found at $SCRIPT_DIR/.venv"
    echo "Create it with: py -3.11 -m venv tribe_scorer/.venv"
    exit 1
fi

echo "Starting TRIBE v2 scorer (Python 3.11 venv)..."
cd "$SCRIPT_DIR" && "$VENV_PYTHON" main.py "$@"

#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
if [ ! -x "venv/bin/python" ]; then
    echo "Missing venv. Complete the one-time macOS setup in README.md first."
    read -r -p "Press Return to close..."
    exit 1
fi
venv/bin/python scripts/run.py app "$@"
result=$?
if [ "$result" -ne 0 ]; then
    read -r -p "Press Return to close..."
fi
exit "$result"

#!/bin/sh
# macOS Finder/Terminal entry point for the existing production launcher.
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
    printf '%s\n' 'Missing .venv/bin/python. Complete the Mac setup in README.md first.' >&2
    exit 1
fi

exec ".venv/bin/python" "scripts/run.py" app "$@"

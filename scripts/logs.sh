#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' 'Set up .venv using README.md first.' >&2
    exit 1
fi
exec .venv/bin/python -B -m shared.live_logs "$@"

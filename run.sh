#!/usr/bin/env bash
# Запуск саундпада на Linux. Нужен root: keyboard читает /dev/input напрямую.
set -e
cd "$(dirname "$0")"

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E "$PY" main.py "$@"
fi
exec "$PY" main.py "$@"

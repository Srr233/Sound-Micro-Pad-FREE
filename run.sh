#!/usr/bin/env bash
# Запуск саундпада на Linux. Нужен root: keyboard читает /dev/input напрямую.
set -e
cd "$(dirname "$0")"

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

if [ "$(id -u)" -eq 0 ]; then
    exec "$PY" main.py "$@"
fi

# В группе input? Тогда root не нужен — окно откроется в своей же сессии.
if id -nG | tr ' ' '\n' | grep -qx input; then
    exec "$PY" main.py "$@"
fi

# Иначе sudo. Под X11 root по умолчанию не имеет доступа к дисплею — выдаём его
# на время запуска. Под Wayland проброс невозможен, нужен XWayland или группа input.
if [ -n "${DISPLAY:-}" ] && command -v xhost >/dev/null; then
    xhost +SI:localuser:root >/dev/null
    trap 'xhost -SI:localuser:root >/dev/null 2>&1 || true' EXIT
elif [ "${XDG_SESSION_TYPE:-}" = wayland ]; then
    echo "Wayland без XWayland: окно из-под sudo не откроется." >&2
    echo "Добавь себя в группу input и перелогинься:" >&2
    echo "    sudo usermod -aG input \$USER" >&2
    echo "После этого run.sh запустится без sudo." >&2
fi

sudo -E "$PY" main.py "$@"

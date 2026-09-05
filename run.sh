#!/usr/bin/env bash
# Запуск саундпада на Linux. Нужен root: keyboard читает /dev/input напрямую.
set -e
cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
    PY="$PWD/.venv/bin/python"
else
    PY="$(command -v python3)"
fi

# Уже root, либо есть доступ к /dev/input через группу — запускаемся напрямую.
if [ "$(id -u)" -eq 0 ] || id -nG | tr ' ' '\n' | grep -qx input; then
    exec "$PY" main.py "$@"
fi

# Дальше нужен sudo. Под X11 root не имеет доступа к дисплею — выдаём на время.
if [ -n "${DISPLAY:-}" ] && command -v xhost >/dev/null; then
    xhost +SI:localuser:root >/dev/null 2>&1 || true
    trap 'xhost -SI:localuser:root >/dev/null 2>&1 || true' EXIT
fi

# Запуск из файлового менеджера: терминала нет, sudo спросить пароль негде.
# pkexec рисует графическое окно пароля; env пробрасываем руками, он чистит окружение.
if [ ! -t 0 ] && command -v pkexec >/dev/null; then
    exec pkexec env \
        DISPLAY="${DISPLAY:-}" \
        XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
        WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
        XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" \
        PULSE_SERVER="${PULSE_SERVER:-unix:${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/pulse/native}" \
        "$PY" "$PWD/main.py" "$@"
fi

if [ ! -t 0 ]; then
    echo "Нет терминала и нет pkexec. Запусти из терминала: ./run.sh" >&2
    exit 1
fi

exec sudo -E "$PY" main.py "$@"

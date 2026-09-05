# Саундпад

Звуки лежат в папке `sounds/`. Жмёшь горячую клавишу — звук уходит **в микрофон** (через виртуальный аудиокабель) и одновременно тебе в наушники. Работает поверх игры, окно можно свернуть.

Разделы 1–3 — про **Windows**. Если у тебя Linux — сразу к разделу [Linux](#linux).

## 1. Поставить виртуальный микрофон

Windows не умеет отдавать звук в микрофон сам по себе — нужен виртуальный кабель.

1. Скачай **VB-CABLE Virtual Audio Device**: https://vb-audio.com/Cable/ (бесплатно).
2. Распакуй, запусти `VBCABLE_Setup_x64.exe` **от администратора**, нажми `Install Driver`, перезагрузись.
3. Появятся два устройства: `CABLE Input` (выход) и `CABLE Output` (вход/микрофон).

## 2. Настроить

- В игре / Discord / Steam выбери микрофоном **`CABLE Output (VB-Audio Virtual Cable)`**.
- **Lethal Company и другие игры на Dissonance** выбора микрофона в настройках не имеют — они берут устройство записи **по умолчанию**. Поэтому: Win+R → `mmsys.cpl` → вкладка **Запись** → `CABLE Output` → **По умолчанию**.
- Чтобы тебя было слышно вместе со звуками — Windows → «Параметры звука» → «Дополнительные параметры звука» → вкладка **Запись** → твой реальный микрофон → **Свойства** → **Прослушать** → галочка «Прослушивать с данного устройства» → устройство `CABLE Input`. Теперь в кабель идёт и твой голос, и саундпад.

## 3. Запуск

```
pip install -r requirements.txt
python main.py
```
Или двойным кликом по `run.bat`.

В окне:
- **В микрофон** — выбери `CABLE Input (VB-Audio Virtual Cable)`.
- **Себе в наушники** — свои колонки/наушники (можно выключить).
- Ползунки справа — громкость каждого выхода.
- Выдели файл → **Назначить клавишу** → нажми сочетание (например `ctrl+1`, `f9`, `num 5`). Esc — отмена.
- **Стоп** или `ctrl+alt+s` — оборвать всё, что играет.
- Двойной клик по файлу — проиграть.

Настройки пишутся в `config.json` рядом с программой.

## Linux

Тут вместо VB-CABLE — виртуальный источник PulseAudio/PipeWire. Всё то же самое, только называется иначе:
`CABLE Input` → **null-sink** (туда пишем), `CABLE Output` → **его monitor** (оттуда игра читает как с микрофона).

### 1. Зависимости

```bash
# Debian / Ubuntu
sudo apt install python3-tk python3-pip libportaudio2 pulseaudio-utils
# Fedora
sudo dnf install python3-tkinter python3-pip portaudio pulseaudio-utils
# Arch
sudo pacman -S tk python-pip portaudio libpulse
```

```bash
pip install -r requirements.txt
```

### 2. Создать виртуальный микрофон

```bash
pactl load-module module-null-sink sink_name=soundpad sink_properties=device.description=Soundpad
pactl load-module module-remap-source master=soundpad.monitor source_name=soundpad_mic source_properties=device.description=Soundpad_Mic
```

Появятся: выход **Soundpad** (в него шлёт саундпад) и микрофон **Soundpad_Mic** (его выбираешь в игре/Discord).

Команды живут до перезагрузки. Чтобы навсегда — допиши те же две строки без `pactl` в `~/.config/pipewire/pipewire-pulse.conf.d/soundpad.conf`:

```
context.exec = [
    { path = "pactl" args = "load-module module-null-sink sink_name=soundpad sink_properties=device.description=Soundpad" }
    { path = "pactl" args = "load-module module-remap-source master=soundpad.monitor source_name=soundpad_mic source_properties=device.description=Soundpad_Mic" }
]
```
(на чистом PulseAudio — те же две строки с `load-module ...` в `~/.config/pulse/default.pa`, первой строкой `.include /etc/pulse/default.pa`).

Снести на лету: `pactl unload-module module-remap-source && pactl unload-module module-null-sink`.

### 3. Подмешать свой голос

Чтобы тебя было слышно вместе со звуками — заведи петлю с реального микрофона в тот же sink:

```bash
pactl load-module module-loopback source=@DEFAULT_SOURCE@ sink=soundpad latency_msec=20
```

Если из-за петли ты слышишь сам себя — приглуши этот loopback в `pavucontrol` → вкладка **Воспроизведение**.

### 4. Запуск

`keyboard` на Linux читает `/dev/input` напрямую, поэтому **нужен root**:

```bash
sudo -E python3 main.py
```

`-E` обязателен: без него потеряются `DISPLAY`/`XDG_RUNTIME_DIR`, и не откроется ни окно, ни звук.

Без sudo можно, если дать себе доступ к устройствам ввода (разово):

```bash
sudo usermod -aG input $USER   # перелогиниться после
```

В окне:
- **В микрофон** — `Soundpad` (или `pulse` / `default`, если в списке нет отдельного sink).
- **Себе в наушники** — свои колонки/наушники.
- Дальше как в Windows: назначаешь клавиши, `ctrl+alt+s` — стоп.

В игре / Discord микрофоном выбери **Soundpad_Mic**.

### Если не работает

- **Пустой список устройств / ошибка PortAudio** — не поставлен `libportaudio2` (или `portaudio`). Проверь: `python3 -c "import sounddevice; print(sounddevice.query_devices())"`.
- **Клавиши не ловятся** — запущено без root и юзер не в группе `input`. Под Wayland глобальные хуки работают только через `/dev/input`, то есть тоже требуют этих прав.
- **`ImportError: No module named tkinter`** — поставь `python3-tk` (`python3-tkinter` на Fedora).
- **Игра не видит Soundpad_Mic** — Steam/Discord во Flatpak: дай доступ через `flatpak override --user --socket=pulseaudio <app>` и выбери источник в `pavucontrol` → **Запись**.
- **Хрипит/трещит** — снизь громкость выхода ниже 1.0 или подними `latency_msec` у loopback.

## Форматы

`.wav`, `.mp3`, `.ogg`, `.flac`, `.opus`, `.aiff` — кидай в `sounds/` и жми «Обновить список».

## Если не работает

- **Клавиши не срабатывают в игре** — запусти саундпад от администратора (игра запущена с повышенными правами, обычный процесс до неё не достучится). Часть игр с анти-читом может блокировать глобальные хуки.
- **Ошибка при выборе устройства** — устройство занято в монопольном режиме: «Параметры звука» → свойства устройства → сними «Разрешить приложениям использовать устройство в монопольном режиме».
- **Тебя слышно, а звуков нет** — микрофоном в игре выбран реальный микрофон, а не `CABLE Output`.
- **Хрипит/трещит** — снизь громкость выхода ниже 1.0 (клиппинг) или выбери версию устройства `(Windows WASAPI)`.

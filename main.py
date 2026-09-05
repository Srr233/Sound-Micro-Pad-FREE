"""Саундпад: горячие клавиши -> звук в виртуальный микрофон + в наушники."""

from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import keyboard

from audio import Player

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
NO_DEVICE = "— выключено —"
EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif", ".opus")

DEFAULT_CONFIG = {
    "mic_device": None,
    "monitor_device": None,
    "mic_volume": 1.0,
    "monitor_volume": 0.6,
    "stop_hotkey": "ctrl+alt+s",
    "hotkeys": {},
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            config.update(json.load(fh))
    return config


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)


def list_sounds() -> list[str]:
    if not os.path.isdir(SOUNDS_DIR):
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        return []
    return sorted(
        name for name in os.listdir(SOUNDS_DIR) if name.lower().endswith(EXTENSIONS)
    )


class SoundpadApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = load_config()
        self.player = Player()
        self.devices = Player.output_devices()
        self.capturing = False
        self._hotkey_handlers = []

        root.title("Саундпад")
        root.geometry("780x540")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_devices()
        self._build_list()
        self._build_buttons()

        self.refresh_sounds()
        self.apply_devices()
        self.register_hotkeys()

    # --- интерфейс ------------------------------------------------------

    def _device_labels(self) -> list[str]:
        return [NO_DEVICE] + [label for _, label, _ in self.devices]

    def _label_for(self, stored):
        """Ищет устройство по сохранённому ключу «имя (host api)»."""
        if stored:
            # старые конфиги хранили подпись с индексом — отбрасываем его
            key = stored.split("] ", 1)[-1] if stored.startswith("[") else stored
            for _, label, dev_key in self.devices:
                if dev_key == key:
                    return label
        return NO_DEVICE

    def _device_index(self, label: str):
        for idx, name, _ in self.devices:
            if name == label:
                return idx
        return None

    def _device_key(self, label: str):
        for _, name, dev_key in self.devices:
            if name == label:
                return dev_key
        return None

    def _build_devices(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Устройства вывода")
        frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame, text="В микрофон (VB-CABLE Input):").grid(
            row=0, column=0, sticky="w", padx=4, pady=3
        )
        self.mic_var = tk.StringVar(value=self._label_for(self.config["mic_device"]))
        mic_box = ttk.Combobox(
            frame,
            textvariable=self.mic_var,
            values=self._device_labels(),
            state="readonly",
            width=58,
        )
        mic_box.grid(row=0, column=1, padx=4, pady=3)
        mic_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_devices())

        ttk.Label(frame, text="Себе в наушники:").grid(
            row=1, column=0, sticky="w", padx=4, pady=3
        )
        self.mon_var = tk.StringVar(value=self._label_for(self.config["monitor_device"]))
        mon_box = ttk.Combobox(
            frame,
            textvariable=self.mon_var,
            values=self._device_labels(),
            state="readonly",
            width=58,
        )
        mon_box.grid(row=1, column=1, padx=4, pady=3)
        mon_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_devices())

        self.mic_vol = tk.DoubleVar(value=self.config["mic_volume"])
        self.mon_vol = tk.DoubleVar(value=self.config["monitor_volume"])
        ttk.Scale(
            frame,
            from_=0.0,
            to=1.5,
            variable=self.mic_vol,
            length=140,
            command=lambda _v: self.player.set_volume("mic", self.mic_vol.get()),
        ).grid(row=0, column=2, padx=6)
        ttk.Scale(
            frame,
            from_=0.0,
            to=1.5,
            variable=self.mon_vol,
            length=140,
            command=lambda _v: self.player.set_volume("monitor", self.mon_vol.get()),
        ).grid(row=1, column=2, padx=6)

    def _build_list(self) -> None:
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.tree = ttk.Treeview(
            frame, columns=("file", "hotkey"), show="headings", selectmode="browse"
        )
        self.tree.heading("file", text="Файл")
        self.tree.heading("hotkey", text="Горячая клавиша")
        self.tree.column("file", width=540)
        self.tree.column("hotkey", width=180, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.play_selected())

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

    def _build_buttons(self) -> None:
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", padx=8, pady=6)

        buttons = (
            ("Назначить клавишу", self.capture_hotkey),
            ("Убрать клавишу", self.clear_hotkey),
            ("Проиграть", self.play_selected),
            ("Стоп", self.player.stop_all),
            ("Открыть папку", self.open_folder),
            ("Обновить список", self.refresh_sounds),
        )
        for text, command in buttons:
            ttk.Button(frame, text=text, command=command).pack(side="left", padx=3)

        self.status = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status).pack(
            fill="x", padx=10, pady=(0, 6)
        )
        self.status.set("Стоп-клавиша: " + str(self.config.get("stop_hotkey")))

    # --- данные ---------------------------------------------------------

    def refresh_sounds(self) -> None:
        self.tree.delete(*self.tree.get_children())
        files = list_sounds()
        for name in files:
            self.tree.insert(
                "", "end", iid=name, values=(name, self.config["hotkeys"].get(name, ""))
            )
        if not files:
            self.status.set(
                "Положи звуки в " + SOUNDS_DIR + " и нажми «Обновить список»"
            )

    def selected_file(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def apply_devices(self) -> None:
        mic_label = self.mic_var.get()
        mon_label = self.mon_var.get()
        mic_idx = self._device_index(mic_label)
        mon_idx = self._device_index(mon_label)
        try:
            self.player.set_output("mic", mic_idx, self.mic_vol.get())
            self.player.set_output("monitor", mon_idx, self.mon_vol.get())
        except Exception as exc:  # устройство занято или не тянет формат
            messagebox.showerror("Ошибка устройства", str(exc))
            return
        self.config["mic_device"] = self._device_key(mic_label)
        self.config["monitor_device"] = self._device_key(mon_label)
        self.persist()

    def persist(self) -> None:
        self.config["mic_volume"] = round(self.mic_vol.get(), 3)
        self.config["monitor_volume"] = round(self.mon_vol.get(), 3)
        save_config(self.config)

    # --- горячие клавиши -------------------------------------------------

    def unregister_hotkeys(self) -> None:
        # keyboard.unhook_all_hotkeys() падает, пока слушатель не запущен,
        # поэтому снимаем только свои обработчики.
        for handler in self._hotkey_handlers:
            try:
                keyboard.remove_hotkey(handler)
            except (KeyError, ValueError):
                pass
        self._hotkey_handlers.clear()

    def register_hotkeys(self) -> None:
        self.unregister_hotkeys()
        for name, hotkey in self.config["hotkeys"].items():
            path = os.path.join(SOUNDS_DIR, name)
            if not hotkey or not os.path.exists(path):
                continue
            try:
                self._hotkey_handlers.append(
                    keyboard.add_hotkey(hotkey, self._play_path, args=(path,), suppress=False)
                )
            except ValueError:
                continue
        stop = self.config.get("stop_hotkey")
        if stop:
            try:
                self._hotkey_handlers.append(
                    keyboard.add_hotkey(stop, self.player.stop_all, suppress=False)
                )
            except ValueError:
                pass

    def _play_path(self, path: str) -> None:
        try:
            self.player.play(path)
        except Exception as exc:
            message = "Ошибка воспроизведения: " + str(exc)
            self.root.after(0, lambda: self.status.set(message))

    def capture_hotkey(self) -> None:
        name = self.selected_file()
        if not name or self.capturing:
            return
        self.capturing = True
        self.status.set("Нажми сочетание клавиш… (Esc — отмена)")
        threading.Thread(target=self._capture_thread, args=(name,), daemon=True).start()

    def _capture_thread(self, name: str) -> None:
        hotkey = keyboard.read_hotkey(suppress=False)
        self.root.after(0, self._capture_done, name, hotkey)

    def _capture_done(self, name: str, hotkey: str) -> None:
        self.capturing = False
        if hotkey == "esc":
            self.status.set("Отменено")
            return
        for other, existing in list(self.config["hotkeys"].items()):
            if existing == hotkey and other != name:
                del self.config["hotkeys"][other]
                if self.tree.exists(other):
                    self.tree.set(other, "hotkey", "")
        self.config["hotkeys"][name] = hotkey
        self.tree.set(name, "hotkey", hotkey)
        self.persist()
        self.register_hotkeys()
        self.status.set(name + " -> " + hotkey)

    def clear_hotkey(self) -> None:
        name = self.selected_file()
        if not name:
            return
        self.config["hotkeys"].pop(name, None)
        self.tree.set(name, "hotkey", "")
        self.persist()
        self.register_hotkeys()

    # --- прочее ---------------------------------------------------------

    def play_selected(self) -> None:
        name = self.selected_file()
        if name:
            self._play_path(os.path.join(SOUNDS_DIR, name))

    def open_folder(self) -> None:
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        os.startfile(SOUNDS_DIR)

    def on_close(self) -> None:
        self.persist()
        self.unregister_hotkeys()
        self.player.close()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    try:
        SoundpadApp(root)
    except Exception as exc:
        messagebox.showerror("Не удалось запустить", str(exc))
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

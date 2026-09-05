"""Диагностика цепочки саундпад -> VB-CABLE -> игра.

Запуск: python diagnose.py
"""

import time

import numpy as np
import sounddevice as sd


def find(needle, kind, api="WASAPI"):
    for idx, dev in enumerate(sd.query_devices()):
        chans = dev["max_output_channels"] if kind == "out" else dev["max_input_channels"]
        hostapi = sd.query_hostapis(dev["hostapi"])["name"]
        if chans > 0 and dev["name"].lower().startswith(needle) and api in hostapi:
            return idx, dev
    return None, None


print("=" * 60)
default_in = sd.query_devices(kind="input")
print("Микрофон по умолчанию :", default_in["name"])
ok_default = "cable output" in default_in["name"].lower()
print("  ->", "ОК" if ok_default else "!! игра будет слушать НЕ кабель")

in_idx, in_dev = find("cable input", "out")
out_idx, out_dev = find("cable output", "in")
if in_dev is None or out_dev is None:
    raise SystemExit("VB-CABLE не найден")

sr_in = int(in_dev["default_samplerate"])
sr_out = int(out_dev["default_samplerate"])
print("\nCABLE Input  (куда пишем): %d Гц, до %d кан." % (sr_in, in_dev["max_output_channels"]))
print("CABLE Output (что слышит игра): %d Гц, до %d кан." % (sr_out, out_dev["max_input_channels"]))
if sr_in != sr_out:
    print("  !! ЧАСТОТЫ НЕ СОВПАДАЮТ — VB-CABLE не пропустит звук.")
    print("     mmsys.cpl -> Воспроизведение -> CABLE Input -> Свойства -> Дополнительно")
    print("     и Запись -> CABLE Output -> Свойства -> Дополнительно: выставь ОДИНАКОВО,")
    print("     например «2 канала, 16 бит, 48000 Гц».")
else:
    print("  -> формат согласован, ОК")

print("\nПрогоняю тон через кабель…")
dur = 1.5
rec = sd.rec(int(sr_out * dur), samplerate=sr_out, channels=1, device=out_idx, dtype="float32")
t = np.linspace(0, dur, int(sr_in * dur), endpoint=False)
tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32")
tone = np.stack([tone, tone], axis=1)
sd.play(tone, samplerate=sr_in, device=in_idx)
sd.wait()
peak = float(np.abs(rec).max())
print("  пик на выходе кабеля: %.4f -> %s" % (peak, "СИГНАЛ ИДЁТ" if peak > 0.01 else "!! ТИШИНА"))

print("\nТеперь 4 секунды ГОВОРИ В МИКРОФОН (проверяю прослушку голоса в кабель)…")
time.sleep(0.5)
voice = sd.rec(int(sr_out * 4), samplerate=sr_out, channels=1, device=out_idx, dtype="float32")
sd.wait()
vpeak = float(np.abs(voice).max())
print("  пик голоса в кабеле: %.4f -> %s" % (vpeak, "ГОЛОС ИДЁТ" if vpeak > 0.01 else
      "!! голоса нет: включи «Прослушать» у своего микрофона -> CABLE Input"))
print("=" * 60)

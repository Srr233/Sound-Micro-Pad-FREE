"""Показывает уровень сигнала на CABLE Output — ровно то, что слышит игра.

Запуск: python monitor_cable.py
"""

import sys

import numpy as np
import sounddevice as sd


def find_cable_output():
    for idx, dev in enumerate(sd.query_devices()):
        api = sd.query_hostapis(dev["hostapi"])["name"]
        if dev["max_input_channels"] > 0 and "cable output" in dev["name"].lower():
            if "WASAPI" in api:
                return idx, dev["name"], api
    return None


found = find_cable_output()
if not found:
    print("CABLE Output не найден. VB-CABLE не установлен?")
    sys.exit(1)

idx, name, api = found
print("Слушаю:", name, "|", api)
print("Говори в микрофон и жми хоткеи саундпада. Ctrl+C — выход.\n")

sr = int(sd.query_devices(idx)["default_samplerate"])


def callback(indata, frames, time_info, status):
    peak = float(np.abs(indata).max())
    bars = int(peak * 50)
    print("\r[%-50s] %.3f" % ("#" * bars, peak), end="", flush=True)


try:
    with sd.InputStream(device=idx, samplerate=sr, channels=1, callback=callback,
                        blocksize=2048):
        while True:
            sd.sleep(200)
except KeyboardInterrupt:
    print("\nвыход")

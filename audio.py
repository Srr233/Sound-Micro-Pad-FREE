"""Аудиодвижок саундпада: декодирование файлов и микширование в несколько устройств."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd
import soundfile as sf

BLOCKSIZE = 512


def load_clip(path: str, samplerate: int, channels: int) -> np.ndarray:
    """Читает файл и приводит его к нужной частоте/числу каналов (float32)."""
    data, sr_in = sf.read(path, dtype="float32", always_2d=True)

    if data.shape[1] >= channels:
        data = data[:, :channels] if channels > 1 else data.mean(axis=1, keepdims=True)
    else:
        data = np.repeat(data[:, :1], channels, axis=1)

    if sr_in != samplerate:
        n_out = max(1, int(round(data.shape[0] * samplerate / sr_in)))
        x_old = np.arange(data.shape[0], dtype=np.float64)
        x_new = np.linspace(0, data.shape[0] - 1, n_out)
        data = np.stack(
            [np.interp(x_new, x_old, data[:, c]) for c in range(data.shape[1])], axis=1
        )

    return np.ascontiguousarray(data, dtype=np.float32)


@dataclass
class _Voice:
    data: np.ndarray
    pos: int = 0


@dataclass
class _Output:
    """Один выходной поток: своё устройство, громкость и набор играющих звуков."""

    device: int
    samplerate: int
    channels: int
    volume: float = 1.0
    stream: sd.OutputStream | None = None
    voices: list[_Voice] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def _callback(self, outdata, frames, time_info, status):  # noqa: ARG002
        outdata.fill(0)
        vol = self.volume
        with self.lock:
            for voice in list(self.voices):
                chunk = voice.data[voice.pos : voice.pos + frames]
                n = chunk.shape[0]
                if n:
                    outdata[:n] += chunk * vol
                voice.pos += n
                if voice.pos >= voice.data.shape[0]:
                    self.voices.remove(voice)
        np.clip(outdata, -1.0, 1.0, out=outdata)

    def start(self) -> None:
        self.stream = sd.OutputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
            blocksize=BLOCKSIZE,
            latency="low",
            callback=self._callback,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        with self.lock:
            self.voices.clear()


class Player:
    """Играет один и тот же клип одновременно в микрофон-кабель и в наушники."""

    MAX_VOICES = 8

    def __init__(self) -> None:
        self._outputs: dict[str, _Output] = {}
        self._cache: dict[tuple[str, int, int], np.ndarray] = {}
        self._lock = threading.Lock()

    # --- устройства -----------------------------------------------------

    @staticmethod
    def output_devices() -> list[tuple[int, str, str]]:
        """(индекс, подпись для UI, стабильный ключ для config.json).

        Индексы PortAudio съезжают при установке/отключении устройств,
        поэтому в конфиге храним имя + host API, а не номер.
        """
        result = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                api = sd.query_hostapis(dev["hostapi"])["name"]
                result.append((idx, f"[{idx}] {dev['name']} ({api})", f"{dev['name']} ({api})"))
        return result

    def set_output(self, key: str, device: int | None, volume: float = 1.0) -> None:
        """Переключает выход `key` на устройство (None — выключить)."""
        with self._lock:
            old = self._outputs.pop(key, None)
        if old is not None:
            old.stop()
        if device is None:
            return

        info = sd.query_devices(device)
        out = _Output(
            device=device,
            samplerate=int(info["default_samplerate"]),
            channels=min(2, int(info["max_output_channels"])),
            volume=volume,
        )
        out.start()
        with self._lock:
            self._outputs[key] = out

    def set_volume(self, key: str, volume: float) -> None:
        out = self._outputs.get(key)
        if out is not None:
            out.volume = volume

    # --- воспроизведение ------------------------------------------------

    def play(self, path: str) -> None:
        with self._lock:
            outputs = list(self._outputs.values())
        for out in outputs:
            key = (path, out.samplerate, out.channels)
            clip = self._cache.get(key)
            if clip is None:
                clip = load_clip(path, out.samplerate, out.channels)
                self._cache[key] = clip
            with out.lock:
                if len(out.voices) >= self.MAX_VOICES:
                    del out.voices[0]
                out.voices.append(_Voice(clip))

    def stop_all(self) -> None:
        with self._lock:
            outputs = list(self._outputs.values())
        for out in outputs:
            with out.lock:
                out.voices.clear()

    def close(self) -> None:
        with self._lock:
            outputs = list(self._outputs.values())
            self._outputs.clear()
        for out in outputs:
            out.stop()

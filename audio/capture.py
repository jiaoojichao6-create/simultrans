"""Audio capture from soundcard using sounddevice (WASAPI on Windows)."""
import sounddevice as sd
import numpy as np
import threading
from queue import Queue
import time

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1600  # 100ms @ 16kHz
DTYPE = "float32"

class AudioCapture:
    def __init__(self, callback=None):
        self.callback = callback  # fn(audio_chunk: np.ndarray)
        self.stream = None
        self.running = False
        self._level = 0.0

    @staticmethod
    def list_devices():
        return sd.query_devices()

    @staticmethod
    def get_input_devices():
        devices = sd.query_devices()
        return [(i, d["name"]) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

    def start(self, device_id=None):
        if self.running:
            return
        self.running = True
        try:
            self.stream = sd.InputStream(
                device=device_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._audio_callback,
                latency="low",
            )
            self.stream.start()
        except Exception as e:
            self.running = False
            raise e

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        chunk = indata.copy().flatten()
        self._level = float(np.sqrt(np.mean(chunk ** 2)))
        if self.callback:
            self.callback(chunk)

    @property
    def level(self):
        return self._level

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

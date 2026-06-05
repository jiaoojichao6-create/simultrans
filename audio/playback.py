"""Audio playback through headphone jack using sounddevice."""
import sounddevice as sd
import numpy as np
from collections import deque
import threading

SAMPLE_RATE = 24000  # TTS typically outputs 24kHz
CHANNELS = 1
BLOCK_SIZE = 2400   # 100ms @ 24kHz

class AudioPlayback:
    def __init__(self):
        self.stream = None
        self.buffer = deque()
        self.running = False
        self._lock = threading.Lock()
        self._level = 0.0

    @staticmethod
    def get_output_devices():
        """Return all devices that can be used for output."""
        devices = sd.query_devices()
        return [(i, d["name"]) for i, d in enumerate(devices) if d["max_output_channels"] > 0]

    def enqueue(self, audio: np.ndarray):
        with self._lock:
            self.buffer.append(audio)

    def clear(self):
        with self._lock:
            self.buffer.clear()

    def start(self, device_id=None):
        if self.running:
            return
        self.running = True
        try:
            self.stream = sd.OutputStream(
                device=device_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                callback=self._play_callback,
                latency="low",
            )
            self.stream.start()
        except Exception as e:
            self.running = False
            raise e

    def _play_callback(self, outdata, frames, time_info, status):
        if not self.running:
            outdata.fill(0)
            return
        with self._lock:
            if self.buffer:
                chunk = self.buffer.popleft()
            else:
                chunk = None
        if chunk is not None:
            n = min(len(chunk), frames)
            outdata[:n, 0] = chunk[:n]
            if n < frames:
                outdata[n:, 0] = 0
            self._level = float(np.sqrt(np.mean(chunk ** 2)))
        else:
            outdata.fill(0)
            self._level = 0.0

    @property
    def level(self):
        return self._level

    def stop(self):
        self.running = False
        self.clear()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

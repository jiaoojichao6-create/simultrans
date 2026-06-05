"""Audio capture from any input device (mic, line-in, virtual, loopback)."""
import sounddevice as sd
import numpy as np
import threading

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1600  # 100ms @ 16kHz
DTYPE = "float32"

class AudioCapture:
    def __init__(self, callback=None):
        self.callback = callback
        self.stream = None
        self.running = False
        self._level = 0.0
        self._current_device = None

    @staticmethod
    def get_all_input_devices():
        """Return all devices that can be used as input."""
        devices = sd.query_devices()
        result = []
        for i, d in enumerate(devices):
            name = d["name"]
            if d["max_input_channels"] > 0:
                result.append((i, name, "input", d))
            # Also check loopback capability (WASAPI)
            if "WASAPI" in name and d["max_output_channels"] > 0:
                result.append((i, f"{name} [回环监听]", "loopback", d))
        return result

    def get_device_list_for_ui(self):
        """Return list of (device_id, display_name) for UI dropdown."""
        devices = self.get_all_input_devices()
        items = []
        for i, name, dtype, _ in devices:
            prefix = "🔴" if dtype == "loopback" else "🎤"
            items.append((i, f"{prefix} {name}"))
        return items

    def start(self, device_id=None, loopback=False):
        if self.running:
            return
        self._current_device = device_id
        self.running = True
        try:
            extra = None
            if loopback:
                try:
                    extra = sd.WasapiSettings(loopback=True)
                except AttributeError:
                    pass  # Fallback: loopback not supported

            self.stream = sd.InputStream(
                device=device_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._audio_callback,
                latency="low",
                extra_settings=extra,
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

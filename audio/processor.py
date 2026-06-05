"""Audio processing module - noise gate, AGC, high-pass filter.
Inspired by OBS/WebRTC/vMix professional audio processing pipeline."""
import numpy as np

SAMPLE_RATE = 16000

class AudioProcessor:
    """
    Lightweight audio processing pipeline:
    Input → High-pass filter → Noise Gate → AGC → Output
    """
    def __init__(self):
        self._highpass_state = 0.0
        # Noise gate: energy threshold (tune based on environment)
        self.noise_gate_threshold = 0.008
        # AGC target RMS level
        self._agc_target = 0.15
        self._agc_gain = 1.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        if len(audio) == 0:
            return audio

        # 1. High-pass filter (remove low rumble < 80Hz)
        audio = self._highpass(audio)

        # 2. Noise gate (zero out silence/noise)
        audio = self._noise_gate(audio)

        # 3. AGC (normalize volume)
        audio = self._agc(audio)

        return audio

    def _highpass(self, audio: np.ndarray) -> np.ndarray:
        """Simple single-pole high-pass filter ~80Hz cutoff."""
        rc = 1.0 / (2 * np.pi * 80)
        dt = 1.0 / SAMPLE_RATE
        alpha = rc / (rc + dt)
        out = np.zeros_like(audio)
        state = self._highpass_state
        for i in range(len(audio)):
            state = alpha * (state + audio[i] - (audio[i-1] if i > 0 else 0))
            out[i] = audio[i] - state
        self._highpass_state = state
        return out

    def _noise_gate(self, audio: np.ndarray) -> np.ndarray:
        """Zero out frames below energy threshold."""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < self.noise_gate_threshold:
            return np.zeros_like(audio)
        return audio

    def _agc(self, audio: np.ndarray) -> np.ndarray:
        """Automatic gain control - normalize to target RMS."""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 0.001:  # Don't boost silence
            return audio

        # Smooth gain changes to avoid pumping
        target_gain = self._agc_target / rms
        target_gain = np.clip(target_gain, 0.5, 5.0)  # Limit gain range
        self._agc_gain = self._agc_gain * 0.9 + target_gain * 0.1  # Smooth

        out = audio * self._agc_gain
        # Hard limit to prevent clipping
        return np.clip(out, -1.0, 1.0)

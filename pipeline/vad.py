"""Voice Activity Detection using Silero VAD."""
import numpy as np
import torch
import torchaudio
import threading
from collections import deque

SAMPLE_RATE = 16000
SPEECH_THRESHOLD = 0.5
MIN_SILENCE_MS = 500   # ms of silence to end an utterance
MIN_SPEECH_MS = 300    # ms of speech to start an utterance
PADDING_MS = 300       # extra audio before/after utterance

class VADProcessor:
    def __init__(self, on_speech=None, on_utterance=None):
        """
        on_speech(speech_chunk: np.ndarray) - called for each speech segment
        on_utterance(full_utterance: np.ndarray) - called when utterance ends
        """
        self.on_speech = on_speech
        self.on_utterance = on_utterance
        self.model = None
        self._load_model()
        self._buffer = deque()
        self._speech_buffer = []
        self._is_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
        self._lock = threading.Lock()

    def _load_model(self):
        try:
            self.model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self.model.eval()
        except Exception as e:
            print(f"[VAD] Model load failed: {e}")
            self.model = None

    def process(self, audio_chunk: np.ndarray):
        if self.model is None:
            return
        with self._lock:
            # Convert to tensor
            audio_tensor = torch.from_numpy(audio_chunk).float()
            # Get speech probability
            speech_prob = self.model(audio_tensor, SAMPLE_RATE).item()
            is_speech = speech_prob > SPEECH_THRESHOLD
            window_ms = len(audio_chunk) / SAMPLE_RATE * 1000

            if is_speech:
                self._silence_frames = 0
                self._speech_frames += 1
                self._speech_buffer.append(audio_chunk)
                if not self._is_speech and self._speech_frames * window_ms >= MIN_SPEECH_MS:
                    self._is_speech = True
                    if self.on_speech:
                        self.on_speech(np.concatenate(self._speech_buffer))
            else:
                self._speech_frames = 0
                if self._is_speech:
                    self._silence_frames += 1
                    self._speech_buffer.append(audio_chunk)
                    silence_ms = self._silence_frames * window_ms
                    if silence_ms >= MIN_SILENCE_MS:
                        # Utterance complete
                        utterance = np.concatenate(self._speech_buffer)
                        self._is_speech = False
                        self._speech_buffer = []
                        self._silence_frames = 0
                        if self.on_utterance:
                            self.on_utterance(utterance)
                else:
                    self._speech_buffer = []
                    self._silence_frames = 0

    def reset(self):
        with self._lock:
            self._speech_buffer = []
            self._is_speech = False
            self._silence_frames = 0
            self._speech_frames = 0

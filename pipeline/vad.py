"""Voice Activity Detection using WebRTC VAD (no PyTorch dependency)."""
import webrtcvad
import numpy as np
import struct
import threading

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 samples @ 16kHz
MIN_SPEECH_MS = 400     # ms of continuous speech to start utterance
MIN_SILENCE_MS = 500    # ms of silence to end utterance

class VADProcessor:
    def __init__(self, on_speech=None, on_utterance=None):
        """
        on_speech(chunk) - called for each speech segment
        on_utterance(audio) - called when utterance ends
        """
        self.on_speech = on_speech
        self.on_utterance = on_utterance
        self._vad = webrtcvad.Vad(2)  # Aggressiveness: 0-3, 2 is default
        self._buffer = b""
        self._speech_buffer = []
        self._silence_frames = 0
        self._speech_frames = 0
        self._is_speech = False
        self._frame_count = 0
        self._lock = threading.Lock()

    def process(self, audio_chunk: np.ndarray):
        with self._lock:
            # Convert float32 PCM to int16 PCM
            int16_chunk = (audio_chunk * 32767).astype(np.int16)
            self._buffer += int16_chunk.tobytes()

            # Process in 30ms frames
            while len(self._buffer) >= FRAME_SIZE * 2:  # 2 bytes per int16 sample
                frame = self._buffer[:FRAME_SIZE * 2]
                self._buffer = self._buffer[FRAME_SIZE * 2:]

                is_speech = False
                try:
                    is_speech = self._vad.is_speech(frame, SAMPLE_RATE)
                except:
                    pass

                frame_audio = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32767.0

                if is_speech:
                    self._silence_frames = 0
                    self._speech_frames += 1
                    self._speech_buffer.append(frame_audio)
                    if not self._is_speech and self._speech_frames * FRAME_MS >= MIN_SPEECH_MS:
                        self._is_speech = True
                        if self.on_speech:
                            self.on_speech(frame_audio)
                else:
                    self._speech_frames = 0
                    if self._is_speech:
                        self._silence_frames += 1
                        self._speech_buffer.append(frame_audio)
                        if self._silence_frames * FRAME_MS >= MIN_SILENCE_MS:
                            utterance = np.concatenate(self._speech_buffer)
                            self._is_speech = False
                            self._speech_buffer = []
                            self._silence_frames = 0
                            self._speech_frames = 0
                            if self.on_utterance:
                                self.on_utterance(utterance)
                    else:
                        self._speech_buffer = []
                        self._silence_frames = 0

    def reset(self):
        with self._lock:
            self._buffer = b""
            self._speech_buffer = []
            self._is_speech = False
            self._silence_frames = 0
            self._speech_frames = 0

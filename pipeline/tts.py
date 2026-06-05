"""Text-to-speech engine - Edge-TTS (free) or cloud APIs."""
import numpy as np
import asyncio
import threading
import io
import json
import requests
import time

class TTSEngine:
    def __init__(self, engine="edge", appkey="", secret=""):
        self.engine = engine
        self.appkey = appkey
        self.secret = secret
        self._edge_voice = "zh-CN-XiaoxiaoNeural"  # Default Chinese female
        self._en_voice = "en-US-AriaNeural"

    def _get_voice(self, lang="zh"):
        return self._zh_voice if lang == "zh" else self._en_voice

    def synthesize(self, text: str, lang="zh") -> np.ndarray:
        if not text.strip():
            return np.array([], dtype=np.float32)

        if self.engine == "edge":
            return self._synthesize_edge(text, lang)
        elif self.engine == "volc":
            return self._synthesize_volc(text, lang)
        elif self.engine == "aliyun":
            return self._synthesize_aliyun(text, lang)
        return np.array([], dtype=np.float32)

    def _synthesize_edge(self, text, lang):
        """Use edge-tts library (free, local)."""
        try:
            import edge_tts
            voice = self._en_voice if lang == "en" else self._edge_voice
            # edge-tts is async, need to run in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""
            async def _run():
                nonlocal audio_data
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
            loop.run_until_complete(_run())
            loop.close()
            if audio_data:
                # Decode MP3 to PCM float32
                import io as io_module
                buf = io_module.BytesIO(audio_data)
                import soundfile as sf
                data, sr = sf.read(buf)
                if sr != 24000:
                    import scipy.signal
                    ratio = 24000 / sr
                    new_len = int(len(data) * ratio)
                    data = np.interp(np.linspace(0, len(data)-1, new_len), np.arange(len(data)), data)
                return data.astype(np.float32)
            return np.array([], dtype=np.float32)
        except ImportError:
            return np.array([], dtype=np.float32)
        except Exception as e:
            print(f"[TTS] Edge error: {e}")
            return np.array([], dtype=np.float32)

    def _synthesize_volc(self, text, lang):
        """Volcano Engine TTS (抖音同款)."""
        if not self.appkey or not self.secret:
            return np.array([], dtype=np.float32)
        try:
            url = "https://openspeech.bytedance.com/api/v1/tts"
            voice_type = "BV001_streaming" if lang == "zh" else "BV002_streaming"
            resp = requests.post(url, json={
                "app": {
                    "appid": self.appkey,
                    "token": self.secret,
                    "cluster": "volcano_tts"
                },
                "user": {"uid": "simultrans"},
                "audio": {
                    "voice_type": voice_type,
                    "encoding": "wav",
                    "speed_ratio": 1.0,
                    "volume_ratio": 1.0,
                    "pitch_ratio": 1.0,
                },
                "request": {
                    "reqid": str(int(time.time() * 1000)),
                    "text": text,
                    "text_type": "plain",
                    "operation": "query"
                }
            }, timeout=10)
            if resp.ok:
                data = resp.json()
                if data.get("code") == 3000:
                    import base64
                    wav_bytes = base64.b64decode(data["data"])
                    import soundfile as sf
                    buf = io.BytesIO(wav_bytes)
                    audio_data, sr = sf.read(buf)
                    return audio_data.astype(np.float32)
            return np.array([], dtype=np.float32)
        except Exception as e:
            print(f"[TTS] Volcano error: {e}")
            return np.array([], dtype=np.float32)

    def _synthesize_aliyun(self, text, lang):
        """Aliyun TTS."""
        if not self.appkey:
            return np.array([], dtype=np.float32)
        try:
            voice = "Aixia" if lang == "zh" else "Emily"
            url = "https://nls-gateway.cn-shanghai.aliyuncs.com/rest/v1/tts/async"
            resp = requests.post(url, json={
                "appkey": self.appkey,
                "text": text,
                "format": "wav",
                "sample_rate": 24000,
                "voice": voice,
                "volume": 50,
                "speech_rate": 0,
                "pitch_rate": 0,
            }, timeout=10)
            return np.array([], dtype=np.float32)  # Async task, needs polling
        except:
            return np.array([], dtype=np.float32)

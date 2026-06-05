"""Speech recognition engine - local whisper or cloud API."""
import numpy as np
import threading
import json
import requests
import time

SAMPLE_RATE = 16000

class ASREngine:
    def __init__(self, engine="local", appkey="", secret=""):
        self.engine = engine
        self.appkey = appkey
        self.secret = secret
        self._whisper_model = None
        self._lock = threading.Lock()
        self._context = ""

    def load(self):
        if self.engine == "local":
            self._load_whisper()
        # Cloud engines loaded on demand

    def _load_whisper(self):
        try:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel("tiny", device="auto", compute_type="int8")
            print("[ASR] Local Whisper loaded (tiny)")
        except Exception as e:
            print(f"[ASR] Whisper load failed: {e}")
            self._whisper_model = None

    def transcribe(self, audio: np.ndarray) -> str:
        with self._lock:
            if self.engine == "local":
                return self._transcribe_local(audio)
            elif self.engine == "aliyun":
                return self._transcribe_aliyun(audio)
            elif self.engine == "tencent":
                return self._transcribe_tencent(audio)
            return ""

    def _transcribe_local(self, audio: np.ndarray) -> str:
        if self._whisper_model is None:
            return ""
        try:
            segments, _ = self._whisper_model.transcribe(audio, beam_size=1, language="zh")
            text = " ".join(seg.text for seg in segments)
            return text.strip()
        except Exception as e:
            print(f"[ASR] Whisper error: {e}")
            return ""

    def _transcribe_aliyun(self, audio: np.ndarray) -> str:
        """Aliyun real-time ASR via websocket. Simplified REST fallback."""
        if not self.appkey:
            return "[配置阿里云ASR Key]"
        # For full implementation, use Aliyun NLS WebSocket SDK
        # Simplified demo using REST API:
        try:
            url = "https://nls-gateway.cn-shanghai.aliyuncs.com/rest/v1/asr"
            audio_data = (audio * 32767).astype(np.int16).tobytes()
            import base64
            b64 = base64.b64encode(audio_data).decode()
            resp = requests.post(url, json={
                "appkey": self.appkey,
                "format": "pcm",
                "sample_rate": SAMPLE_RATE,
                "enable_punctuation_prediction": True,
                "enable_inverse_text_normalization": True,
                "audio_data": b64,
            }, timeout=10)
            if resp.ok:
                data = resp.json()
                return data.get("result", "")
            return ""
        except Exception as e:
            print(f"[ASR] Aliyun error: {e}")
            return ""

    def _transcribe_tencent(self, audio: np.ndarray) -> str:
        if not self.secret:
            return "[配置腾讯云ASR Key]"
        try:
            from tencentcloud.common import credential
            from tencentcloud.asr.v20190614 import asr_client, models
            cred = credential.Credential(self.secret.split("#")[0], self.secret.split("#")[1] if "#" in self.secret else "")
            client = asr_client.AsrClient(cred, "ap-guangzhou")
            import base64
            b64 = base64.b64encode((audio * 32767).astype(np.int16).tobytes()).decode()
            req = models.SentenceRecognitionRequest()
            req.ProjectId = 0
            req.SubServiceType = 2
            req.EngSerViceType = "16k_zh"
            req.SourceType = 1
            req.VoiceFormat = "pcm"
            req.Data = b64
            resp = client.SentenceRecognition(req)
            return resp.Result
        except:
            return ""

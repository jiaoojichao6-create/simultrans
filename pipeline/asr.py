"""Speech recognition engine - supports language auto-detection."""
import numpy as np
import threading
import requests
import time

SAMPLE_RATE = 16000

# Language code mapping for Whisper → our UI codes
WHISPER_LANG_MAP = {
    "zh": "zh", "yue": "zh", "wuu": "zh",
    "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es",
    "ru": "ru", "pt": "pt", "it": "it",
    "th": "th", "vi": "vi", "id": "id",
}

class ASRResult:
    def __init__(self, text: str, language: str = ""):
        self.text = text
        self.language = language  # detected language code

class ASREngine:
    def __init__(self, engine="local", appkey="", secret=""):
        self.engine = engine
        self.appkey = appkey
        self.secret = secret
        self._whisper_model = None
        self._lock = threading.Lock()

    def load(self):
        if self.engine == "local":
            self._load_whisper()

    def _load_whisper(self):
        try:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel("tiny", device="auto", compute_type="int8")
            print("[ASR] Local Whisper loaded (tiny) - auto language detection supported")
        except Exception as e:
            print(f"[ASR] Whisper load failed: {e}")
            self._whisper_model = None

    def transcribe(self, audio: np.ndarray, auto_detect: bool = False) -> ASRResult:
        with self._lock:
            if self.engine == "local":
                return self._transcribe_local(audio, auto_detect)
            elif self.engine == "aliyun":
                return self._transcribe_aliyun(audio)
            elif self.engine == "tencent":
                return self._transcribe_tencent(audio)
            return ASRResult("")

    def _transcribe_local(self, audio: np.ndarray, auto_detect: bool) -> ASRResult:
        if self._whisper_model is None:
            return ASRResult("")
        try:
            lang = None if auto_detect else "zh"
            segments, info = self._whisper_model.transcribe(
                audio, beam_size=1, language=lang
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            detected = ""
            if auto_detect and info:
                detected = WHISPER_LANG_MAP.get(info.language, info.language)
            return ASRResult(text, detected)
        except Exception as e:
            print(f"[ASR] Whisper error: {e}")
            return ASRResult("")

    def _transcribe_aliyun(self, audio: np.ndarray) -> ASRResult:
        if not self.appkey:
            return ASRResult("[配置阿里云ASR Key]")
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
                return ASRResult(data.get("result", ""))
            return ASRResult("")
        except Exception as e:
            print(f"[ASR] Aliyun error: {e}")
            return ASRResult("")

    def _transcribe_tencent(self, audio: np.ndarray) -> ASRResult:
        if not self.secret:
            return ASRResult("[配置腾讯云ASR Key]")
        try:
            from tencentcloud.common import credential
            from tencentcloud.asr.v20190614 import asr_client, models
            parts = self.secret.split("#")
            cred = credential.Credential(parts[0], parts[1] if len(parts) > 1 else "")
            client = asr_client.AsrClient(cred, "ap-guangzhou")
            b64 = base64.b64encode((audio * 32767).astype(np.int16).tobytes()).decode()
            req = models.SentenceRecognitionRequest()
            req.ProjectId = 0
            req.SubServiceType = 2
            req.EngSerViceType = "16k_zh"
            req.SourceType = 1
            req.VoiceFormat = "pcm"
            req.Data = b64
            resp = client.SentenceRecognition(req)
            return ASRResult(resp.Result)
        except:
            return ASRResult("")

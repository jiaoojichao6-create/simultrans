"""Pipeline controller - VAD → ASR → Translate → TTS with auto language detection."""
import threading
import time
import numpy as np
from .vad import VADProcessor
from .asr import ASREngine
from .translator import TranslationEngine
from .tts import TTSEngine

# Language codes used in the app
LANG_CODE = {"中文": "zh", "英文": "en", "日文": "ja", "韩文": "ko", "法文": "fr"}

class PipelineController:
    def __init__(self, config, on_status=None, on_original_text=None,
                 on_translated_text=None, on_level=None, on_lang_detected=None):
        self.config = config
        self.on_status = on_status
        self.on_original_text = on_original_text
        self.on_translated_text = on_translated_text
        self.on_level = on_level
        self.on_lang_detected = on_lang_detected  # callback when auto-detect identifies language

        self.vad = VADProcessor(
            on_speech=self._on_speech,
            on_utterance=self._on_utterance
        )
        self.asr = ASREngine(
            engine=config.get("asr_engine", "local"),
            appkey=config.get("asr_appkey", ""),
            secret=config.get("asr_secret", "")
        )
        self.translator = TranslationEngine(
            api_key=config.get("deepseek_key", ""),
            engine=config.get("translate_engine", "deepseek")
        )
        self.tts = TTSEngine(
            engine=config.get("tts_engine", "edge"),
            appkey=config.get("tts_appkey", ""),
            secret=config.get("tts_secret", "")
        )

        self.running = False
        self._playback_queue = []
        self._thread = None
        self._asr_loaded = False
        self._source_lang = "auto"  # "auto" = auto-detect
        self._target_lang = "en"    # default target is English
        self._detected_lang = ""    # last detected source language

    def set_languages(self, source, target):
        """source: "auto" | language, target: language."""
        self._source_lang = source
        self._target_lang = target
        if source != "auto":
            self._detected_lang = LANG_CODE.get(source, source)

    def get_current_source_lang(self):
        if self._source_lang == "auto":
            return self._detected_lang if self._detected_lang else "zh"
        return LANG_CODE.get(self._source_lang, self._source_lang)

    def start(self):
        if self.running:
            return
        self.running = True
        self._set_status("加载ASR模型...")
        threading.Thread(target=self._load_asr, daemon=True).start()
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        self._set_status("🎤 等待语音输入...")

    def _load_asr(self):
        self.asr.load()
        self._asr_loaded = True

    def stop(self):
        self.running = False
        self.vad.reset()
        self._playback_queue.clear()
        self._set_status("⏹ 已停止")

    def feed_audio(self, chunk: np.ndarray):
        if self.running:
            self.vad.process(chunk)

    def get_playback_audio(self):
        if self._playback_queue:
            return self._playback_queue.pop(0)
        return None

    def _on_speech(self, chunk):
        self._set_status("🎤 说话中...")

    def _on_utterance(self, utterance):
        if not self._asr_loaded:
            self._set_status("⏳ ASR模型加载中...")
            return

        self._set_status("📝 识别中...")

        # ASR with or without auto language detection
        auto_detect = (self._source_lang == "auto")
        result = self.asr.transcribe(utterance, auto_detect=auto_detect)
        text = result.text
        if not text:
            return

        # Update language if auto-detected
        if auto_detect and result.language:
            self._detected_lang = result.language
            if self.on_lang_detected:
                self.on_lang_detected(result.language)

        # Build display prefix with detected language
        detected_label = ""
        if auto_detect and result.language:
            rev_map = {v: k for k, v in LANG_CODE.items()}
            detected_label = f"[{rev_map.get(result.language, result.language)}] "

        if self.on_original_text:
            self.on_original_text(f"{detected_label}{text}")

        self._set_status("🔄 翻译中...")

        # Translate: use detected language as source
        source = result.language if auto_detect and result.language else self.get_current_source_lang()
        translated = self.translator.translate(text, source, self._target_lang)

        if self.on_translated_text:
            self.on_translated_text(translated)

        self._set_status("🔊 合成语音...")
        audio = self.tts.synthesize(translated, lang=self._target_lang)
        if len(audio) > 0:
            self._playback_queue.append(audio)
        self._set_status("🎤 等待语音输入...")

    def _process_loop(self):
        while self.running:
            time.sleep(0.05)

    def _set_status(self, status):
        if self.on_status:
            self.on_status(status)

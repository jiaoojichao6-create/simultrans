"""Pipeline controller - ties VAD → ASR → Translate → TTS together."""
import threading
import time
import numpy as np
from queue import Queue, Empty
from .vad import VADProcessor
from .asr import ASREngine
from .translator import TranslationEngine
from .tts import TTSEngine

class PipelineController:
    def __init__(self, config, on_status=None, on_original_text=None,
                 on_translated_text=None, on_level=None):
        self.config = config
        self.on_status = on_status          # status string
        self.on_original_text = on_original_text    # original text
        self.on_translated_text = on_translated_text  # translated text
        self.on_level = on_level            # audio level (0-1)

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
        self._audio_queue = Queue()
        self._playback_queue = Queue()
        self._thread = None
        self._asr_loaded = False
        self._source_lang = config.get("source_lang", "zh")
        self._target_lang = config.get("target_lang", "en")

    def set_languages(self, source, target):
        self._source_lang = source
        self._target_lang = target

    def start(self):
        if self.running:
            return
        self.running = True
        self._set_status("加载ASR模型...")
        # Load ASR in background
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
        # Clear queues
        while not self._audio_queue.empty():
            try: self._audio_queue.get_nowait()
            except: break
        self._set_status("⏹ 已停止")

    def feed_audio(self, chunk: np.ndarray):
        if self.running:
            self.vad.process(chunk)

    def get_playback_audio(self):
        """Called by AudioPlayback to get TTS output."""
        try:
            return self._playback_queue.get_nowait()
        except Empty:
            return None

    def _on_speech(self, chunk):
        self._set_status("🎤 说话中...")

    def _on_utterance(self, utterance):
        self._set_status("📝 识别中...")
        # Transcribe
        if not self._asr_loaded:
            self._set_status("⏳ ASR模型加载中...")
            return
        text = self.asr.transcribe(utterance)
        if not text:
            return
        if self.on_original_text:
            self.on_original_text(text)
        self._set_status("🔄 翻译中...")
        # Translate
        translated = self.translator.translate(text, self._source_lang, self._target_lang)
        if self.on_translated_text:
            self.on_translated_text(translated)
        self._set_status("🔊 合成语音...")
        # TTS
        audio = self.tts.synthesize(translated, lang=self._target_lang)
        if len(audio) > 0:
            self._playback_queue.put(audio)
        self._set_status("🎤 等待语音输入...")

    def _process_loop(self):
        while self.running:
            time.sleep(0.05)

    def _set_status(self, status):
        if self.on_status:
            self.on_status(status)

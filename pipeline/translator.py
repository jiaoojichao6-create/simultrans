"""Translation engine with glossary injection for professional terminology."""
import requests
import threading
from .glossary import GlossaryManager

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"

LANG_MAP = {
    ("zh", "en"): "将以下中文翻译成英文，保持专业性和流畅性，不要添加解释：",
    ("en", "zh"): "Translate the following English to Chinese, keep it professional and natural:",
    ("zh", "ja"): "将以下中文翻译成日文：",
    ("ja", "zh"): "将以下日文翻译成中文：",
    ("zh", "ko"): "将以下中文翻译成韩文：",
    ("ko", "zh"): "将以下韩文翻译成中文：",
    ("zh", "fr"): "将以下中文翻译成法文：",
    ("fr", "zh"): "将以下法文翻译成中文：",
    ("en", "ja"): "Translate English to Japanese:",
    ("ja", "en"): "Translate Japanese to English:",
}

class TranslationEngine:
    def __init__(self, api_key="", engine="deepseek"):
        self.api_key = api_key
        self.engine = engine
        self.glossary = GlossaryManager()
        self._context = []
        self._lock = threading.Lock()
        self._max_context = 10

    def set_api_key(self, key):
        self.api_key = key

    def translate(self, text: str, source_lang: str = "zh", target_lang: str = "en") -> str:
        if not text.strip():
            return ""
        if not self.api_key:
            return "[请在设置中填入DeepSeek API Key]"
        return self._translate_deepseek(text, source_lang, target_lang)

    def _translate_deepseek(self, text, source_lang, target_lang):
        prompt_prefix = LANG_MAP.get(
            (source_lang, target_lang),
            f"Translate from {source_lang} to {target_lang}: "
        )

        # Build system prompt with glossary
        glossary_suffix = self.glossary.build_prompt_suffix()
        system_prompt = "You are a professional simultaneous interpreter. Translate accurately and naturally."
        if glossary_suffix:
            system_prompt += glossary_suffix

        messages = [{"role": "system", "content": system_prompt}]

        # Add context for consistency
        with self._lock:
            for ctx in self._context[-self._max_context:]:
                messages.append({"role": "assistant", "content": ctx})

        messages.append({"role": "user", "content": f"{prompt_prefix}{text}"})

        try:
            resp = requests.post(DEEPSEEK_API, json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 512,
                "stream": False,
            }, headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }, timeout=15)

            if resp.ok:
                result = resp.json()["choices"][0]["message"]["content"].strip()
                with self._lock:
                    self._context.append(f"原文: {text}")
                    self._context.append(f"译文: {result}")
                    if len(self._context) > self._max_context * 2:
                        self._context = self._context[-self._max_context * 2:]
                return result
            else:
                return f"[翻译API错误: {resp.status_code}]"
        except Exception as e:
            return f"[翻译异常: {str(e)[:50]}]"

    def clear_context(self):
        with self._lock:
            self._context = []

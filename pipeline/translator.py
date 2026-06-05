"""Translation engine with glossary injection for professional terminology."""
import requests
import threading
from .glossary import GlossaryManager

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"

# Comprehensive language support
LANG_MAP = {
    ("zh", "en"): "将以下中文翻译成英文，保持专业性和流畅性，不要添加解释：",
    ("zh", "ja"): "将以下中文翻译成日文：",
    ("zh", "ko"): "将以下中文翻译成韩文：",
    ("zh", "fr"): "将以下中文翻译成法文：",
    ("zh", "de"): "将以下中文翻译成德文：",
    ("zh", "es"): "将以下中文翻译成西班牙文：",
    ("zh", "pt"): "将以下中文翻译成葡萄牙文：",
    ("zh", "ru"): "将以下中文翻译成俄文：",
    ("zh", "ar"): "将以下中文翻译成阿拉伯文：",
    ("zh", "it"): "将以下中文翻译成意大利文：",
    ("zh", "th"): "将以下中文翻译成泰文：",
    ("zh", "vi"): "将以下中文翻译成越南文：",
    ("zh", "id"): "将以下中文翻译成印尼文：",
    ("zh", "ms"): "将以下中文翻译成马来文：",
    ("zh", "hi"): "将以下中文翻译成印地文：",
    ("en", "zh"): "Translate the following English to Chinese, keep it professional and natural:",
    ("en", "ja"): "Translate English to Japanese:",
    ("en", "ko"): "Translate English to Korean:",
    ("en", "fr"): "Translate English to French:",
    ("en", "de"): "Translate English to German:",
    ("en", "es"): "Translate English to Spanish:",
    ("en", "pt"): "Translate English to Portuguese:",
    ("en", "ru"): "Translate English to Russian:",
    ("en", "ar"): "Translate English to Arabic:",
    ("en", "it"): "Translate English to Italian:",
    ("en", "th"): "Translate English to Thai:",
    ("en", "vi"): "Translate English to Vietnamese:",
    ("en", "id"): "Translate English to Indonesian:",
    ("ja", "zh"): "将以下日文翻译成中文：",
    ("ja", "en"): "Translate Japanese to English:",
    ("ja", "ko"): "Translate Japanese to Korean:",
    ("ko", "zh"): "将以下韩文翻译成中文：",
    ("ko", "en"): "Translate Korean to English:",
    ("fr", "zh"): "将以下法文翻译成中文：",
    ("fr", "en"): "Translate French to English:",
    ("de", "zh"): "将以下德文翻译成中文：",
    ("de", "en"): "Translate German to English:",
    ("es", "zh"): "将以下西班牙文翻译成中文：",
    ("es", "en"): "Translate Spanish to English:",
    ("pt", "zh"): "将以下葡萄牙文翻译成中文：",
    ("ru", "zh"): "将以下俄文翻译成中文：",
    ("ru", "en"): "Translate Russian to English:",
    ("ar", "zh"): "将以下阿拉伯文翻译成中文：",
    ("it", "zh"): "将以下意大利文翻译成中文：",
    ("th", "zh"): "将以下泰文翻译成中文：",
    ("th", "en"): "Translate Thai to English:",
    ("vi", "zh"): "将以下越南文翻译成中文：",
    ("vi", "en"): "Translate Vietnamese to English:",
    ("id", "zh"): "将以下印尼文翻译成中文：",
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

    def translate(self, text: str, source_lang: str = "zh", target_lang: str = "zh") -> str:
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

        glossary_suffix = self.glossary.build_prompt_suffix()
        system_prompt = "You are a professional simultaneous interpreter. Translate accurately and naturally."
        if glossary_suffix:
            system_prompt += glossary_suffix

        messages = [{"role": "system", "content": system_prompt}]

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

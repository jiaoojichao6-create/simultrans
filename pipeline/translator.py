"""Translation engine using DeepSeek API (or other LLMs)."""
import requests
import json
import threading

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"

class TranslationEngine:
    def __init__(self, api_key="", engine="deepseek"):
        self.api_key = api_key
        self.engine = engine
        self._context = []  # Recent translation history for consistency
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
        lang_map = {
            ("zh", "en"): "将以下中文翻译成英文，保持专业性和流畅性，不要添加解释：",
            ("en", "zh"): "Translate the following English to Chinese, keep it professional and natural:",
            ("zh", "ja"): "将以下中文翻译成日文：",
            ("ja", "zh"): "将以下日文翻译成中文：",
        }
        prompt = lang_map.get((source_lang, target_lang),
                              f"Translate from {source_lang} to {target_lang}: ")

        messages = [{"role": "system", "content": "You are a professional simultaneous interpreter."}]

        # Add context for consistency
        with self._lock:
            for ctx in self._context[-self._max_context:]:
                messages.append({"role": "assistant", "content": ctx})

        messages.append({"role": "user", "content": f"{prompt}{text}"})

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

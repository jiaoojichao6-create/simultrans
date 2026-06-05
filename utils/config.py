"""Configuration management and password hashing."""
import json
import hashlib
import os
import base64
import secrets

CONFIG_FILE = "simultrans_config.json"

def _get_config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", CONFIG_FILE)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def check_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return hashlib.sha256(password.encode()).hexdigest() == stored
    salt, h = stored.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h

DEFAULT_CONFIG = {
    "password": hash_password("jiaojichao"),
    "asr_engine": "local",       # local / aliyun / tencent
    "asr_appkey": "",
    "asr_secret": "",
    "translate_engine": "deepseek",
    "deepseek_key": "",
    "tts_engine": "edge",        # edge / volc / aliyun
    "tts_appkey": "",
    "tts_secret": "",
    "source_lang": "zh",
    "target_lang": "en",
    "source_volume": 80,
    "output_volume": 80,
    "monitor_original": True,
}

def load_config():
    path = _get_config_path()
    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except:
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    path = _get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def change_password(old_pw, new_pw):
    cfg = load_config()
    if not check_password(old_pw, cfg["password"]):
        return False, "原密码错误"
    cfg["password"] = hash_password(new_pw)
    save_config(cfg)
    return True, "密码修改成功"

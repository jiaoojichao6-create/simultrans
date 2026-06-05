"""Main application window with inline configuration."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QSlider,
                             QTextEdit, QGroupBox, QProgressBar, QCheckBox,
                             QMessageBox, QLineEdit, QInputDialog, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont
import os
import sounddevice as sd
from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from pipeline.controller import PipelineController
from utils.config import load_config, save_config, change_password

class SignalBridge(QObject):
    status = pyqtSignal(str)
    original_text = pyqtSignal(str)
    translated_text = pyqtSignal(str)
    capture_level = pyqtSignal(float)
    playback_level = pyqtSignal(float)
    lang_detected = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.setWindowTitle("同传翻译系统 v1.0")
        self.setMinimumSize(750, 680)
        self._input_device_id = None
        self._loopback_mode = False
        self._output_device_id = None
        self._config_visible = False
        self._setup_ui()
        self._setup_audio()
        self._setup_pipeline()
        self._setup_timers()
        self._refresh_devices()
        self._running = False

    def _setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # ===== Title bar =====
        title_layout = QHBoxLayout()
        title = QLabel("🎧 同传翻译系统")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        self._config_btn = QPushButton("🔧 配置")
        self._config_btn.setFont(QFont("Microsoft YaHei", 10))
        self._config_btn.setCheckable(True)
        self._config_btn.clicked.connect(self._toggle_config)
        title_layout.addWidget(self._config_btn)

        self._pw_btn = QPushButton("🔑 改密码")
        self._pw_btn.setFont(QFont("Microsoft YaHei", 10))
        self._pw_btn.clicked.connect(self._change_password)
        title_layout.addWidget(self._pw_btn)

        layout.addLayout(title_layout)

        # ===== Inline config panel (collapsible) =====
        self._config_panel = QWidget()
        self._config_panel.setVisible(False)
        config_layout = QVBoxLayout()
        config_layout.setContentsMargins(10, 5, 10, 5)
        config_layout.setSpacing(6)

        # DeepSeek API Key
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("🌐 DeepSeek API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setPlaceholderText("输入 DeepSeek API Key")
        self._api_key_input.setText(self.cfg.get("deepseek_key", ""))
        key_row.addWidget(self._api_key_input, 1)
        config_layout.addLayout(key_row)

        # ASR engine
        asr_row = QHBoxLayout()
        asr_row.addWidget(QLabel("🎤 ASR引擎:"))
        self._asr_combo = QComboBox()
        self._asr_combo.addItems(["local (本地Whisper)", "aliyun (阿里云)", "tencent (腾讯云)"])
        idx_map = {"local": 0, "aliyun": 1, "tencent": 2}
        self._asr_combo.setCurrentIndex(idx_map.get(self.cfg.get("asr_engine", "local"), 0))
        asr_row.addWidget(self._asr_combo)
        asr_row.addWidget(QLabel("AppKey:"))
        self._asr_appkey = QLineEdit(self.cfg.get("asr_appkey", ""))
        asr_row.addWidget(self._asr_appkey, 1)
        asr_row.addWidget(QLabel("Secret:"))
        self._asr_secret = QLineEdit(self.cfg.get("asr_secret", ""))
        self._asr_secret.setEchoMode(QLineEdit.Password)
        asr_row.addWidget(self._asr_secret, 1)
        config_layout.addLayout(asr_row)

        # TTS engine
        tts_row = QHBoxLayout()
        tts_row.addWidget(QLabel("🔊 TTS引擎:"))
        self._tts_combo = QComboBox()
        self._tts_combo.addItems(["edge (免费)", "volc (火山引擎)", "aliyun (阿里云)"])
        idx_map2 = {"edge": 0, "volc": 1, "aliyun": 2}
        self._tts_combo.setCurrentIndex(idx_map2.get(self.cfg.get("tts_engine", "edge"), 0))
        tts_row.addWidget(self._tts_combo)
        tts_row.addWidget(QLabel("AppKey:"))
        self._tts_appkey = QLineEdit(self.cfg.get("tts_appkey", ""))
        tts_row.addWidget(self._tts_appkey, 1)
        tts_row.addWidget(QLabel("Secret:"))
        self._tts_secret = QLineEdit(self.cfg.get("tts_secret", ""))
        self._tts_secret.setEchoMode(QLineEdit.Password)
        tts_row.addWidget(self._tts_secret, 1)
        config_layout.addLayout(tts_row)

        # Save config button
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("💾 保存配置")
        save_btn.clicked.connect(self._save_inline_config)
        save_btn.setFont(QFont("Microsoft YaHei", 10))
        save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px 20px; border-radius: 4px;")
        save_row.addWidget(save_btn)
        config_layout.addLayout(save_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        config_layout.addWidget(sep)

        self._config_panel.setLayout(config_layout)
        layout.addWidget(self._config_panel)

        # ===== Audio device selection (OBS/Zoom style) =====
        audio_group = QGroupBox("音频设备")
        audio_group.setFont(QFont("Microsoft YaHei", 10))
        audio_layout = QVBoxLayout()
        audio_layout.setSpacing(6)

        # Input section
        in_section = QHBoxLayout()
        in_section.addWidget(QLabel("🎤 输入:"))
        self._in_dev_combo = QComboBox()
        self._in_dev_combo.setMinimumWidth(400)
        self._in_dev_combo.currentIndexChanged.connect(self._on_input_device_changed)
        in_section.addWidget(self._in_dev_combo, 1)
        self._in_test_btn = QPushButton("▶ 测试")
        self._in_test_btn.setFixedWidth(50)
        self._in_test_btn.setToolTip("对着麦克风说话，观察电平变化")
        self._in_test_btn.clicked.connect(self._test_input)
        in_section.addWidget(self._in_test_btn)
        audio_layout.addLayout(in_section)

        # Output section
        out_section = QHBoxLayout()
        out_section.addWidget(QLabel("🔊 输出:"))
        self._out_dev_combo = QComboBox()
        self._out_dev_combo.setMinimumWidth(400)
        out_section.addWidget(self._out_dev_combo, 1)
        self._out_test_btn = QPushButton("🔔")
        self._out_test_btn.setFixedWidth(50)
        self._out_test_btn.setToolTip("播放测试音，检查输出设备")
        self._out_test_btn.clicked.connect(self._test_output)
        out_section.addWidget(self._out_test_btn)
        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.setFixedWidth(60)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        out_section.addWidget(self._refresh_btn)
        self._mute_btn = QPushButton("🔊")
        self._mute_btn.setFixedWidth(35)
        self._mute_btn.setCheckable(True)
        self._mute_btn.setToolTip("静音输出")
        self._mute_btn.clicked.connect(self._toggle_mute)
        out_section.addWidget(self._mute_btn)
        audio_layout.addLayout(out_section)

        # Device info + level meters (like OBS)
        meter_section = QHBoxLayout()
        # Input meter
        meter_section.addWidget(QLabel("输入电平:", styleSheet="font-size: 11px;"))
        self._in_meter = QProgressBar()
        self._in_meter.setFixedWidth(200)
        self._in_meter.setMaximum(100)
        self._in_meter.setTextVisible(False)
        self._in_meter.setStyleSheet("""
            QProgressBar { border: 1px solid #ccc; border-radius: 3px; background: #eee; height: 14px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4CAF50, stop:0.6 #8BC34A, stop:0.8 #FFEB3B, stop:1 #f44336); }
        """)
        meter_section.addWidget(self._in_meter)
        # Input level number
        self._in_level_num = QLabel("0")
        self._in_level_num.setFixedWidth(30)
        self._in_level_num.setStyleSheet("font-size: 11px; color: #666;")
        meter_section.addWidget(self._in_level_num)

        meter_section.addSpacing(15)

        # Output meter
        meter_section.addWidget(QLabel("输出电平:", styleSheet="font-size: 11px;"))
        self._out_meter = QProgressBar()
        self._out_meter.setFixedWidth(200)
        self._out_meter.setMaximum(100)
        self._out_meter.setTextVisible(False)
        self._out_meter.setStyleSheet("""
            QProgressBar { border: 1px solid #ccc; border-radius: 3px; background: #eee; height: 14px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2196F3, stop:0.6 #03A9F4, stop:0.8 #FF9800, stop:1 #f44336); }
        """)
        meter_section.addWidget(self._out_meter)
        self._out_level_num = QLabel("0")
        self._out_level_num.setFixedWidth(30)
        self._out_level_num.setStyleSheet("font-size: 11px; color: #666;")
        meter_section.addWidget(self._out_level_num)

        meter_section.addStretch()
        audio_layout.addLayout(meter_section)

        # Device status label
        self._dev_info_label = QLabel("")
        self._dev_info_label.setStyleSheet("color: #999; font-size: 10px;")
        audio_layout.addWidget(self._dev_info_label)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # ===== Language controls =====
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("源语言:"))
        self._src_lang = QComboBox()
        self._src_lang.addItems(["自动检测", "中文", "英文", "日文", "韩文", "法文",
                                 "德文", "西班牙文", "葡萄牙文", "俄文", "阿拉伯文",
                                 "意大利文", "泰文", "越南文", "印尼文", "马来文", "印地文"])
        self._src_lang.setCurrentIndex(0)
        self._src_lang.currentIndexChanged.connect(self._on_source_lang_changed)
        self._src_lang.setFixedWidth(100)
        ctrl_layout.addWidget(self._src_lang)
        ctrl_layout.addWidget(QLabel("→"))
        self._tgt_lang = QComboBox()
        self._tgt_lang.addItems(["中文", "英文", "日文", "韩文", "法文",
                                 "德文", "西班牙文", "葡萄牙文", "俄文", "阿拉伯文",
                                 "意大利文", "泰文", "越南文", "印尼文", "马来文", "印地文"])
        self._tgt_lang.setCurrentIndex(0)
        self._tgt_lang.setFixedWidth(80)
        ctrl_layout.addWidget(self._tgt_lang)
        self._lang_indicator = QLabel("")
        self._lang_indicator.setStyleSheet("color: #666; font-size: 11px;")
        ctrl_layout.addWidget(self._lang_indicator)
        ctrl_layout.addSpacing(15)
        self._start_btn = QPushButton("▶ 开始同传")
        self._start_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px; border-radius: 5px;")
        self._start_btn.clicked.connect(self._toggle_pipeline)
        ctrl_layout.addWidget(self._start_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # ===== Status =====
        self._status_label = QLabel("⏹ 就绪, 选择设备后点击开始同传")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status_label)

        # ===== Text display =====
        text_layout = QHBoxLayout()
        orig_group = QGroupBox("原文")
        orig_layout = QVBoxLayout()
        self._orig_text = QTextEdit()
        self._orig_text.setReadOnly(True)
        self._orig_text.setFont(QFont("Microsoft YaHei", 12))
        self._orig_text.setStyleSheet("background-color: #f5f5f5;")
        orig_layout.addWidget(self._orig_text)
        orig_group.setLayout(orig_layout)
        text_layout.addWidget(orig_group)

        trans_group = QGroupBox("译文")
        trans_layout = QVBoxLayout()
        self._trans_text = QTextEdit()
        self._trans_text.setReadOnly(True)
        self._trans_text.setFont(QFont("Microsoft YaHei", 12))
        self._trans_text.setStyleSheet("background-color: #e8f5e9;")
        trans_layout.addWidget(self._trans_text)
        trans_group.setLayout(trans_layout)
        text_layout.addWidget(trans_group)
        layout.addLayout(text_layout, 1)

        central.setLayout(layout)
        self.setCentralWidget(central)

        # Signals
        self._signals = SignalBridge()
        self._signals.status.connect(self._update_status)
        self._signals.original_text.connect(lambda t: self._orig_text.append(t))
        self._signals.translated_text.connect(lambda t: self._trans_text.append(t))
        self._signals.capture_level.connect(self._update_input_meter)
        self._signals.playback_level.connect(self._update_output_meter)
        self._signals.lang_detected.connect(self._on_lang_detected)

    def _update_input_meter(self, level):
        val = int(min(level * 250, 100))
        self._in_meter.setValue(val)
        self._in_level_num.setText(str(val))

    def _update_output_meter(self, level):
        val = int(min(level * 250, 100))
        self._out_meter.setValue(val)
        self._out_level_num.setText(str(val))

    def _toggle_config(self):
        self._config_visible = not self._config_visible
        self._config_panel.setVisible(self._config_visible)
        self._config_btn.setText("🔧 配置 ▼" if self._config_visible else "🔧 配置 ▶")

    def _save_inline_config(self):
        self.cfg["deepseek_key"] = self._api_key_input.text().strip()
        self.cfg["asr_engine"] = ["local", "aliyun", "tencent"][self._asr_combo.currentIndex()]
        self.cfg["asr_appkey"] = self._asr_appkey.text().strip()
        self.cfg["asr_secret"] = self._asr_secret.text().strip()
        self.cfg["tts_engine"] = ["edge", "volc", "aliyun"][self._tts_combo.currentIndex()]
        self.cfg["tts_appkey"] = self._tts_appkey.text().strip()
        self.cfg["tts_secret"] = self._tts_secret.text().strip()
        save_config(self.cfg)
        QMessageBox.information(self, "成功", "配置已保存")
        self._toggle_config()

    def _change_password(self):
        old_pw, ok1 = QInputDialog.getText(self, "修改密码", "当前密码:", QLineEdit.Password)
        if not ok1:
            return
        new_pw, ok2 = QInputDialog.getText(self, "修改密码", "新密码:", QLineEdit.Password)
        if not ok2:
            return
        ok, msg = change_password(old_pw, new_pw)
        if ok:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "错误", msg)

    def _on_lang_detected(self, lang_code):
        rev = {"zh": "中文", "en": "英文", "ja": "日文", "ko": "韩文",
                "fr": "法文", "de": "德文", "es": "西班牙文", "pt": "葡萄牙文",
                "ru": "俄文", "ar": "阿拉伯文", "it": "意大利文",
                "th": "泰文", "vi": "越南文", "id": "印尼文",
                "ms": "马来文", "hi": "印地文"}
        label = rev.get(lang_code, lang_code)
        self._lang_indicator.setText(f"检测到: {label}")

    def _on_source_lang_changed(self):
        text = self._src_lang.currentText()
        self._lang_indicator.setText("🔄 自动检测中..." if text == "自动检测" else "")

    def _refresh_devices(self):
        self._in_dev_combo.clear()
        capture = AudioCapture()
        in_devices = capture.get_all_input_devices()
        self._device_map = []
        self._in_dev_info = []
        last_input = None
        for i, name, dtype, info in in_devices:
            sr = info.get("default_samplerate", "?")
            ch = info.get("max_input_channels", "?")
            label = name
            if len(label) > 55:
                label = label[:52] + "..."
            self._in_dev_combo.addItem(f"{'🔴' if dtype == 'loopback' else '🎤'} {label}")
            self._device_map.append((i, dtype == "loopback"))
            self._in_dev_info.append(f"{sr}Hz / {ch}ch")
            if dtype == "input":
                last_input = len(self._device_map) - 1
        if last_input is not None:
            self._in_dev_combo.setCurrentIndex(last_input)
        self._on_input_device_changed()

        self._out_dev_combo.clear()
        out_devices = AudioPlayback.get_output_devices()
        self._out_dev_map = []
        self._out_dev_info = []
        for dev_id, name in out_devices:
            info = sd.query_devices(dev_id)
            sr = info.get("default_samplerate", "?") if info else "?"
            ch = info.get("max_output_channels", "?") if info else "?"
            label = name
            if len(label) > 55:
                label = label[:52] + "..."
            self._out_dev_combo.addItem(f"🔊 {label}")
            self._out_dev_map.append(dev_id)
            self._out_dev_info.append(f"{sr}Hz / {ch}ch")
        self._status_label.setText(
            f"检测到 {self._in_dev_combo.count()} 输入设备, {self._out_dev_combo.count()} 输出设备"
        )

    def _on_input_device_changed(self):
        idx = self._in_dev_combo.currentIndex()
        if 0 <= idx < len(self._device_map):
            self._input_device_id, self._loopback_mode = self._device_map[idx]
            if idx < len(self._in_dev_info):
                self._dev_info_label.setText(f"输入: {self._in_dev_info[idx]}")

    def _setup_audio(self):
        from audio.processor import AudioProcessor
        self._audio_processor = AudioProcessor()
        self._capture = AudioCapture(callback=self._on_audio_chunk)
        self._capture.set_processor(self._audio_processor)
        self._playback = AudioPlayback()
        self._muted = False

    def _toggle_mute(self):
        self._muted = self._mute_btn.isChecked()
        self._mute_btn.setText("🔇" if self._muted else "🔊")

    def _test_output(self):
        """Play a short test tone."""
        import numpy as np
        import time
        sr = 24000
        t = np.linspace(0, 0.3, int(sr * 0.3))
        tone = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        try:
            out_idx = self._out_dev_combo.currentIndex()
            out_dev_id = self._out_dev_map[out_idx] if 0 <= out_idx < len(self._out_dev_map) else None
            with sd.OutputStream(device=out_dev_id, samplerate=sr, channels=1,
                                 dtype="float32", latency="low") as stream:
                stream.write(tone)
        except Exception as e:
            QMessageBox.warning(self, "测试失败", f"输出设备测试失败: {str(e)}")

    def _test_input(self):
        """Show input level for 3 seconds to test microphone."""
        QMessageBox.information(self, "输入测试", "对着麦克风说话，观察电平表跳动\n3秒后自动结束测试")
        try:
            in_id = self._input_device_id
            if in_id is None:
                return
            import time
            t_end = time.time() + 3
            def test_cb(indata, frames, time_info, status):
                if time.time() > t_end:
                    raise sd.CallbackStop()
                chunk = indata.copy().flatten()
                if self._audio_processor:
                    chunk = self._audio_processor.process(chunk)
                level = float(np.sqrt(np.mean(chunk ** 2)))
                self._signals.capture_level.emit(level)
            with sd.InputStream(device=in_id, samplerate=16000, channels=1,
                                 dtype="float32", latency="low", callback=test_cb):
                while time.time() < t_end:
                    QApplication.processEvents()
        except:
            pass

    def _setup_pipeline(self):
        self._pipeline = PipelineController(
            self.cfg,
            on_status=lambda s: self._signals.status.emit(s),
            on_original_text=lambda t: self._signals.original_text.emit(t),
            on_translated_text=lambda t: self._signals.translated_text.emit(t),
            on_level=lambda v: self._signals.capture_level.emit(v),
            on_lang_detected=lambda l: self._signals.lang_detected.emit(l),
        )

    def _setup_timers(self):
        self._t = QTimer()
        self._t.timeout.connect(self._update_levels)
        self._t.start(100)

    def _update_levels(self):
        self._signals.capture_level.emit(self._capture.level)
        self._signals.playback_level.emit(self._playback.level)

    def _on_audio_chunk(self, chunk):
        self._pipeline.feed_audio(chunk)

    def _toggle_pipeline(self):
        (self._start_pipeline if not self._running else self._stop_pipeline)()

    def _start_pipeline(self):
        if self._input_device_id is None or self._out_dev_combo.count() == 0:
            QMessageBox.warning(self, "提示", "请选择音频输入和输出设备")
            return

        out_idx = self._out_dev_combo.currentIndex()
        out_dev_id = self._out_dev_map[out_idx] if 0 <= out_idx < len(self._out_dev_map) else None
        src = self._src_lang.currentText()
        tgt = self._tgt_lang.currentText()
        self._pipeline.set_languages(src, tgt)

        try:
            self._capture.start(device_id=self._input_device_id, loopback=self._loopback_mode)
            self._playback.start(device_id=out_dev_id)
            self._pipeline.start()
            self._running = True
            self._start_btn.setText("⏹ 停止同传")
            self._start_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px 20px; border-radius: 5px;")
            self._status_label.setText(f"同传中: {self._in_dev_combo.currentText()} → {self._out_dev_combo.currentText()}")
        except Exception as e:
            # Log full error to file
            import traceback
            err_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
            try:
                with open(err_path, "w", encoding="gbk") as f:
                    traceback.print_exc(file=f)
            except:
                pass
            QMessageBox.critical(self, "启动失败",
                f"错误: {str(e)}\n\n详细错误已保存到 error.log，请用记事本打开查看")
            self._stop_pipeline()

    def _stop_pipeline(self):
        self._pipeline.stop()
        self._capture.stop()
        self._playback.stop()
        self._running = False
        self._start_btn.setText("▶ 开始同传")
        self._start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 20px; border-radius: 5px;")
        self._status_label.setText("⏹ 已停止")

    def _update_status(self, status):
        self._status_label.setText(status)

    def closeEvent(self, event):
        self._stop_pipeline()
        event.accept()

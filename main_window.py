"""Main application window."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QSlider,
                             QTextEdit, QGroupBox, QProgressBar, QCheckBox,
                             QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QPalette, QColor
from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from pipeline.controller import PipelineController
from utils.config import load_config
from settings_window import SettingsWindow

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
        self.setMinimumSize(700, 620)
        self._input_device_id = None
        self._loopback_mode = False
        self._output_device_id = None
        self._setup_ui()
        self._setup_audio()
        self._setup_pipeline()
        self._setup_timers()
        self._refresh_devices()
        self._running = False

    def _setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Title bar
        title_layout = QHBoxLayout()
        title = QLabel("🎧 同传翻译系统")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        self._settings_btn = QPushButton("⚙ 设置")
        self._settings_btn.setFont(QFont("Microsoft YaHei", 10))
        self._settings_btn.clicked.connect(self._open_settings)
        title_layout.addWidget(self._settings_btn)

        layout.addLayout(title_layout)

        # Audio input device selection
        dev_layout = QVBoxLayout()
        dev_layout.setSpacing(4)
        # Input row
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("音频输入:"))
        self._in_dev_combo = QComboBox()
        self._in_dev_combo.setMinimumWidth(350)
        self._in_dev_combo.currentIndexChanged.connect(self._on_input_device_changed)
        in_row.addWidget(self._in_dev_combo)
        in_row.addStretch()
        dev_layout.addLayout(in_row)
        # Output row
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("音频输出:"))
        self._out_dev_combo = QComboBox()
        self._out_dev_combo.setMinimumWidth(350)
        out_row.addWidget(self._out_dev_combo)
        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.setFixedWidth(60)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        out_row.addWidget(self._refresh_btn)
        out_row.addStretch()
        dev_layout.addLayout(out_row)
        layout.addLayout(dev_layout)

        # Controls row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("源语言:"))
        self._src_lang = QComboBox()
        self._src_lang.addItems(["自动检测", "中文", "英文", "日文", "韩文", "法文"])
        self._src_lang.setCurrentIndex(0)
        self._src_lang.currentIndexChanged.connect(self._on_source_lang_changed)
        self._src_lang.setFixedWidth(100)
        ctrl_layout.addWidget(self._src_lang)
        ctrl_layout.addWidget(QLabel("→"))
        self._tgt_lang = QComboBox()
        self._tgt_lang.addItems(["英文", "中文", "日文", "韩文", "法文"])
        self._tgt_lang.setCurrentIndex(0)
        self._tgt_lang.setFixedWidth(80)
        ctrl_layout.addWidget(self._tgt_lang)

        # Auto-detect indicator
        self._lang_indicator = QLabel("")
        self._lang_indicator.setStyleSheet("color: #666; font-size: 11px;")
        ctrl_layout.addWidget(self._lang_indicator)
        ctrl_layout.addSpacing(20)

        self._start_btn = QPushButton("▶ 开始同传")
        self._start_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self._start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white;
                         padding: 8px 20px; border-radius: 5px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self._start_btn.clicked.connect(self._toggle_pipeline)
        ctrl_layout.addWidget(self._start_btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Volume controls
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("源音量:"))
        self._src_vol = QSlider(Qt.Horizontal)
        self._src_vol.setRange(0, 100)
        self._src_vol.setValue(self.cfg.get("source_volume", 80))
        self._src_vol.setFixedWidth(100)
        vol_layout.addWidget(self._src_vol)
        vol_layout.addSpacing(10)
        vol_layout.addWidget(QLabel("输出音量:"))
        self._out_vol = QSlider(Qt.Horizontal)
        self._out_vol.setRange(0, 100)
        self._out_vol.setValue(self.cfg.get("output_volume", 80))
        self._out_vol.setFixedWidth(100)
        vol_layout.addWidget(self._out_vol)
        vol_layout.addSpacing(10)
        self._monitor_cb = QCheckBox("同步监听原声")
        self._monitor_cb.setChecked(self.cfg.get("monitor_original", True))
        vol_layout.addWidget(self._monitor_cb)
        vol_layout.addStretch()
        layout.addLayout(vol_layout)

        # Audio level indicators
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("输入电平:"))
        self._in_level = QProgressBar()
        self._in_level.setFixedWidth(150)
        self._in_level.setMaximum(100)
        self._in_level.setTextVisible(False)
        self._in_level.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        level_layout.addWidget(self._in_level)
        level_layout.addSpacing(20)
        level_layout.addWidget(QLabel("输出电平:"))
        self._out_level = QProgressBar()
        self._out_level.setFixedWidth(150)
        self._out_level.setMaximum(100)
        self._out_level.setTextVisible(False)
        self._out_level.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")
        level_layout.addWidget(self._out_level)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # Status
        self._status_label = QLabel("⏹ 就绪，选择输入源后点击「开始同传」")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status_label)

        # Text display
        text_layout = QHBoxLayout()
        # Original text
        orig_group = QGroupBox("原文")
        orig_layout = QVBoxLayout()
        self._orig_text = QTextEdit()
        self._orig_text.setReadOnly(True)
        self._orig_text.setFont(QFont("Microsoft YaHei", 12))
        self._orig_text.setStyleSheet("background-color: #f5f5f5;")
        orig_layout.addWidget(self._orig_text)
        orig_group.setLayout(orig_layout)
        text_layout.addWidget(orig_group)
        # Translated text
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

        # Signal bridge
        self._signals = SignalBridge()
        self._signals.status.connect(self._update_status)
        self._signals.original_text.connect(lambda t: self._orig_text.append(t))
        self._signals.translated_text.connect(lambda t: self._trans_text.append(t))
        self._signals.capture_level.connect(lambda v: self._in_level.setValue(int(min(v * 200, 100))))
        self._signals.playback_level.connect(lambda v: self._out_level.setValue(int(min(v * 200, 100))))
        self._signals.lang_detected.connect(self._on_lang_detected)

    def _on_lang_detected(self, lang_code):
        rev = {"zh": "中文", "en": "英文", "ja": "日文", "ko": "韩文", "fr": "法文"}
        label = rev.get(lang_code, lang_code)
        self._lang_indicator.setText(f"检测到: {label} → 翻译中")

    def _on_source_lang_changed(self):
        text = self._src_lang.currentText()
        if text == "自动检测":
            self._lang_indicator.setText("🔄 自动检测中...")
        else:
            self._lang_indicator.setText("")

    def _refresh_devices(self):
        """Scan and populate audio device dropdowns."""
        # --- Input devices ---
        self._in_dev_combo.clear()
        capture = AudioCapture()
        in_devices = capture.get_all_input_devices()

        self._device_map = []  # (device_id, is_loopback)
        last_input = None
        for i, name, dtype, info in in_devices:
            display = f"{'🔴' if dtype == 'loopback' else '🎤'} {name}"
            self._in_dev_combo.addItem(display)
            self._device_map.append((i, dtype == "loopback"))
            if dtype == "input":
                last_input = len(self._device_map) - 1

        if last_input is not None:
            self._in_dev_combo.setCurrentIndex(last_input)
        self._on_input_device_changed()

        # --- Output devices ---
        self._out_dev_combo.clear()
        out_devices = AudioPlayback.get_output_devices()
        self._out_dev_map = []
        default_idx = 0
        for i, (dev_id, name) in enumerate(out_devices):
            display = f"🔊 {name}"
            self._out_dev_combo.addItem(display)
            self._out_dev_map.append(dev_id)
            if "耳机" in name or "headphone" in name.lower() or "speaker" in name.lower():
                default_idx = i
        # Try to select headphones/speakers by default
        if out_devices:
            self._out_dev_combo.setCurrentIndex(default_idx)

        in_count = self._in_dev_combo.count()
        out_count = self._out_dev_combo.count()
        self._status_label.setText(f"检测到 {in_count} 个输入设备，{out_count} 个输出设备")

    def _on_input_device_changed(self):
        idx = self._in_dev_combo.currentIndex()
        if 0 <= idx < len(self._device_map):
            self._input_device_id, self._loopback_mode = self._device_map[idx]

    def _setup_audio(self):
        self._capture = AudioCapture(callback=self._on_audio_chunk)
        self._playback = AudioPlayback()

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
        self._level_timer = QTimer()
        self._level_timer.timeout.connect(self._update_levels)
        self._level_timer.start(100)

    def _update_levels(self):
        self._signals.capture_level.emit(self._capture.level)
        self._signals.playback_level.emit(self._playback.level)

    def _on_audio_chunk(self, chunk):
        self._pipeline.feed_audio(chunk)

    def _toggle_pipeline(self):
        if not self._running:
            self._start_pipeline()
        else:
            self._stop_pipeline()

    def _start_pipeline(self):
        if self._input_device_id is None or self._out_dev_combo.count() == 0:
            QMessageBox.warning(self, "提示", "请先选择音频输入和输出设备")
            return
        out_idx = self._out_dev_combo.currentIndex()
        out_dev_id = self._out_dev_map[out_idx] if 0 <= out_idx < len(self._out_dev_map) else None
        # Set languages before starting
        source = self._src_lang.currentText()
        target = self._tgt_lang.currentText()
        if source == "自动检测":
            self._lang_indicator.setText("🔄 自动检测中...")
        else:
            self._lang_indicator.setText("")
        self._pipeline.set_languages(source, target)
        try:
            self._capture.start(device_id=self._input_device_id, loopback=self._loopback_mode)
            self._playback.start(device_id=out_dev_id)
            self._pipeline.start()
            self._running = True
            self._start_btn.setText("⏹ 停止同传")
            self._start_btn.setStyleSheet("""
                QPushButton { background-color: #f44336; color: white;
                             padding: 8px 20px; border-radius: 5px; }
                QPushButton:hover { background-color: #da190b; }
            """)
            in_name = self._in_dev_combo.currentText()
            out_name = self._out_dev_combo.currentText()
            self._status_label.setText(f"🎧 输入「{in_name}」→ 输出「{out_name}」开始同传...")
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"音频设备启动失败:\n{str(e)}")

    def _stop_pipeline(self):
        self._pipeline.stop()
        self._capture.stop()
        self._playback.stop()
        self._running = False
        self._start_btn.setText("▶ 开始同传")
        self._start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white;
                         padding: 8px 20px; border-radius: 5px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self._status_label.setText("⏹ 已停止")

    def _update_status(self, status):
        self._status_label.setText(status)

    def _open_settings(self):
        dialog = SettingsWindow(self)
        if dialog.exec_():
            self.cfg = load_config()
            self._pipeline = PipelineController(
                self.cfg,
                on_status=lambda s: self._signals.status.emit(s),
                on_original_text=lambda t: self._signals.original_text.emit(t),
                on_translated_text=lambda t: self._signals.translated_text.emit(t),
            )
            self._setup_audio()

    def closeEvent(self, event):
        self._stop_pipeline()
        event.accept()

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.setWindowTitle("同传翻译系统 v1.0")
        self.setMinimumSize(700, 550)
        self._setup_ui()
        self._setup_audio()
        self._setup_pipeline()
        self._setup_timers()
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

        # Controls row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("源语言:"))
        self._src_lang = QComboBox()
        self._src_lang.addItems(["中文", "英文", "日文"])
        self._src_lang.setFixedWidth(80)
        ctrl_layout.addWidget(self._src_lang)
        ctrl_layout.addWidget(QLabel("→"))
        self._tgt_lang = QComboBox()
        self._tgt_lang.addItems(["英文", "中文", "日文"])
        self._tgt_lang.setCurrentIndex(0)
        self._tgt_lang.setFixedWidth(80)
        ctrl_layout.addWidget(self._tgt_lang)
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
        level_layout.addWidget(self._in_level)
        level_layout.addSpacing(20)
        level_layout.addWidget(QLabel("输出电平:"))
        self._out_level = QProgressBar()
        self._out_level.setFixedWidth(150)
        self._out_level.setMaximum(100)
        self._out_level.setTextVisible(False)
        level_layout.addWidget(self._out_level)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # Status
        self._status_label = QLabel("⏹ 就绪，点击「开始同传」启动")
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
        try:
            self._caption.start()
            self._playback.start()
            self._pipeline.start()
            self._running = True
            self._start_btn.setText("⏹ 停止同传")
            self._start_btn.setStyleSheet("""
                QPushButton { background-color: #f44336; color: white;
                             padding: 8px 20px; border-radius: 5px; }
                QPushButton:hover { background-color: #da190b; }
            """)
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"音频设备启动失败:\n{str(e)}")

    def _stop_pipeline(self):
        self._pipeline.stop()
        self._caption.stop()
        self._playback.stop()
        self._running = False
        self._start_btn.setText("▶ 开始同传")
        self._start_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white;
                         padding: 8px 20px; border-radius: 5px; }
            QPushButton:hover { background-color: #45a049; }
        """)

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

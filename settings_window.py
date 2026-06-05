"""Settings window."""
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTabWidget, QWidget,
                             QFormLayout, QComboBox, QMessageBox, QGroupBox,
                             QListWidget, QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from utils.config import load_config, save_config, change_password
from pipeline.glossary import GlossaryManager


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(520, 480)
        self.cfg = load_config()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        tabs = QTabWidget()

        # --- Password tab ---
        pw_tab = QWidget()
        pw_layout = QFormLayout()
        self._old_pw = QLineEdit()
        self._old_pw.setEchoMode(QLineEdit.Password)
        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.Password)
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.Password)
        pw_layout.addRow("当前密码:", self._old_pw)
        pw_layout.addRow("新密码:", self._new_pw)
        pw_layout.addRow("确认新密码:", self._confirm_pw)
        change_btn = QPushButton("修改密码")
        change_btn.clicked.connect(self._on_change_password)
        pw_layout.addRow("", change_btn)
        pw_tab.setLayout(pw_layout)
        tabs.addTab(pw_tab, "🔑 修改密码")

        # --- ASR tab ---
        asr_tab = QWidget()
        asr_layout = QFormLayout()
        self._asr_engine = QComboBox()
        self._asr_engine.addItems(["local (本地Whisper)", "aliyun (阿里云)", "tencent (腾讯云)"])
        idx = ["local", "aliyun", "tencent"].index(self.cfg.get("asr_engine", "local"))
        self._asr_engine.setCurrentIndex(idx)
        self._asr_appkey = QLineEdit(self.cfg.get("asr_appkey", ""))
        self._asr_secret = QLineEdit(self.cfg.get("asr_secret", ""))
        self._asr_secret.setEchoMode(QLineEdit.Password)
        asr_layout.addRow("引擎:", self._asr_engine)
        asr_layout.addRow("AppKey:", self._asr_appkey)
        asr_layout.addRow("Secret:", self._asr_secret)
        asr_hint = QLabel('本地Whisper不需要填Key，但首次运行会下载模型(~75MB)')
        asr_hint.setStyleSheet("color: gray; font-size: 11px;")
        asr_layout.addRow("", asr_hint)
        asr_tab.setLayout(asr_layout)
        tabs.addTab(asr_tab, "🎤 语音识别")

        # --- Translation tab ---
        trans_tab = QWidget()
        trans_layout = QFormLayout()
        self._deepseek_key = QLineEdit(self.cfg.get("deepseek_key", ""))
        self._deepseek_key.setEchoMode(QLineEdit.Password)
        trans_layout.addRow("DeepSeek API Key:", self._deepseek_key)
        trans_hint = QLabel('从 platform.deepseek.com 获取API Key\n用于翻译，质量高且便宜')
        trans_hint.setStyleSheet("color: gray; font-size: 11px;")
        trans_layout.addRow("", trans_hint)
        trans_tab.setLayout(trans_layout)
        tabs.addTab(trans_tab, "🌐 翻译引擎")

        # --- TTS tab ---
        tts_tab = QWidget()
        tts_layout = QFormLayout()
        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["edge (Edge-TTS 免费)", "volc (火山引擎)", "aliyun (阿里云)"])
        idx2 = ["edge", "volc", "aliyun"].index(self.cfg.get("tts_engine", "edge"))
        self._tts_engine.setCurrentIndex(idx2)
        self._tts_appkey = QLineEdit(self.cfg.get("tts_appkey", ""))
        self._tts_secret = QLineEdit(self.cfg.get("tts_secret", ""))
        self._tts_secret.setEchoMode(QLineEdit.Password)
        tts_layout.addRow("引擎:", self._tts_engine)
        tts_layout.addRow("AppKey:", self._tts_appkey)
        tts_layout.addRow("Secret:", self._tts_secret)
        tts_hint = QLabel('Edge-TTS免费无需Key，火山引擎效果最佳需注册')
        tts_hint.setStyleSheet("color: gray; font-size: 11px;")
        tts_layout.addRow("", tts_hint)
        tts_tab.setLayout(tts_layout)
        tabs.addTab(tts_tab, "🔊 语音合成")

        # --- Glossary tab ---
        gloss_tab = QWidget()
        gloss_layout = QVBoxLayout()

        # Import section
        import_layout = QHBoxLayout()
        import_layout.addWidget(QLabel("导入专业文档:"))
        self._import_btn = QPushButton("📂 选择文件")
        self._import_btn.clicked.connect(self._on_import_glossary)
        import_layout.addWidget(self._import_btn)
        import_layout.addStretch()
        gloss_layout.addLayout(import_layout)

        import_hint = QLabel("支持 txt / csv / tsv / pdf / docx，系统自动提取术语")
        import_hint.setStyleSheet("color: gray; font-size: 11px;")
        gloss_layout.addWidget(import_hint)

        # Imported files
        self._gloss_files = QListWidget()
        self._gloss_files.setMaximumHeight(80)
        gloss_layout.addWidget(QLabel("已导入的文件:"))
        gloss_layout.addWidget(self._gloss_files)

        # Manual term entry
        add_term_layout = QHBoxLayout()
        self._term_source = QLineEdit()
        self._term_source.setPlaceholderText("原文术语")
        add_term_layout.addWidget(self._term_source)
        add_term_layout.addWidget(QLabel("→"))
        self._term_target = QLineEdit()
        self._term_target.setPlaceholderText("翻译")
        add_term_layout.addWidget(self._term_target)
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add_term)
        add_term_layout.addWidget(add_btn)
        gloss_layout.addLayout(add_term_layout)

        # Term list
        gloss_layout.addWidget(QLabel("术语表:"))
        self._gloss_list = QListWidget()
        gloss_layout.addWidget(self._gloss_list)

        # Action buttons
        gloss_btn_layout = QHBoxLayout()
        clear_btn = QPushButton("🗑 清空术语表")
        clear_btn.clicked.connect(self._on_clear_glossary)
        gloss_btn_layout.addWidget(clear_btn)
        gloss_btn_layout.addStretch()
        refresh_btn = QPushButton("🔄 刷新显示")
        refresh_btn.clicked.connect(self._refresh_glossary_ui)
        gloss_btn_layout.addWidget(refresh_btn)
        gloss_layout.addLayout(gloss_btn_layout)

        gloss_tab.setLayout(gloss_layout)
        tabs.addTab(gloss_tab, "📖 术语库")

        # Initialize glossary
        self._glossary_mgr = GlossaryManager()
        self._refresh_glossary_ui()

        # Save/Cancel buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    # === Glossary methods ===
    def _refresh_glossary_ui(self):
        self._gloss_list.clear()
        self._gloss_files.clear()
        terms = self._glossary_mgr.get_terms()
        for src, tgt in sorted(terms.items()):
            self._gloss_list.addItem(f"{src}  →  {tgt}")
        for fname in self._glossary_mgr.get_imported_files():
            self._gloss_files.addItem(fname)
        self._gloss_list.addItem(f"━━━ 共 {len(terms)} 条术语 ━━━")

    def _on_import_glossary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入专业文档", "",
            "文档文件 (*.txt *.csv *.tsv *.pdf *.docx);;所有文件 (*)"
        )
        if not path:
            return
        result = self._glossary_mgr.import_document(path)
        if "error" in result:
            QMessageBox.warning(self, "导入失败", result["error"])
        else:
            count = result.get("count", 0)
            QMessageBox.information(
                self, "导入成功",
                f"从文档中提取了 {count} 条术语\n"
                f"文件名: {os.path.basename(path)}\n"
                f"术语已加入翻译系统，下次翻译自动生效"
            )
            self._refresh_glossary_ui()

    def _on_add_term(self):
        src = self._term_source.text().strip()
        tgt = self._term_target.text().strip()
        if not src or not tgt:
            QMessageBox.warning(self, "提示", "请填写原文术语和翻译")
            return
        self._glossary_mgr.add_term(src, tgt)
        self._term_source.clear()
        self._term_target.clear()
        self._refresh_glossary_ui()

    def _on_clear_glossary(self):
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有术语吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._glossary_mgr.clear_all()
            self._refresh_glossary_ui()
            QMessageBox.information(self, "已清空", "术语表已清空")

    def _on_change_password(self):
        old = self._old_pw.text()
        new = self._new_pw.text()
        confirm = self._confirm_pw.text()
        if not old or not new:
            QMessageBox.warning(self, "错误", "请填写完整")
            return
        if new != confirm:
            QMessageBox.warning(self, "错误", "两次密码不一致")
            return
        if len(new) < 4:
            QMessageBox.warning(self, "错误", "密码至少4位")
            return
        ok, msg = change_password(old, new)
        if ok:
            QMessageBox.information(self, "成功", "密码修改成功！")
            self._old_pw.clear()
            self._new_pw.clear()
            self._confirm_pw.clear()
        else:
            QMessageBox.warning(self, "错误", msg)

    def _on_save(self):
        self.cfg["asr_engine"] = ["local", "aliyun", "tencent"][self._asr_engine.currentIndex()]
        self.cfg["asr_appkey"] = self._asr_appkey.text().strip()
        self.cfg["asr_secret"] = self._asr_secret.text().strip()
        self.cfg["deepseek_key"] = self._deepseek_key.text().strip()
        self.cfg["tts_engine"] = ["edge", "volc", "aliyun"][self._tts_engine.currentIndex()]
        self.cfg["tts_appkey"] = self._tts_appkey.text().strip()
        self.cfg["tts_secret"] = self._tts_secret.text().strip()
        save_config(self.cfg)
        QMessageBox.information(self, "成功", "设置已保存")
        self.accept()

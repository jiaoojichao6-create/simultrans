"""Password login dialog."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from utils.config import load_config, check_password

LOGIN_ATTEMPTS = 5
LOCK_TIME = 30  # seconds

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._attempts = 0
        self._locked_until = 0
        self.setWindowTitle("同传翻译 - 登录")
        self.setFixedSize(360, 200)
        self.setWindowFlags(Qt.WindowCloseButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        title = QLabel("🔐 同传翻译系统")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(10)

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.Password)
        self._pw_input.setPlaceholderText("请输入密码")
        self._pw_input.setFont(QFont("Microsoft YaHei", 11))
        self._pw_input.returnPressed.connect(self._on_login)
        layout.addWidget(self._pw_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red; font-size: 12px;")
        self._error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._error_label)

        btn_layout = QHBoxLayout()
        self._login_btn = QPushButton("登录")
        self._login_btn.setFont(QFont("Microsoft YaHei", 11))
        self._login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self._login_btn)

        cancel_btn = QPushButton("退出")
        cancel_btn.setFont(QFont("Microsoft YaHei", 11))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self._pw_input.setFocus()

    def _on_login(self):
        import time
        now = time.time()
        if now < self._locked_until:
            remain = int(self._locked_until - now)
            self._error_label.setText(f"登录锁定，请在{remain}秒后重试")
            return

        cfg = load_config()
        pw = self._pw_input.text()
        if check_password(pw, cfg["password"]):
            self.accept()
        else:
            self._attempts += 1
            remaining = LOGIN_ATTEMPTS - self._attempts
            if remaining <= 0:
                self._locked_until = now + LOCK_TIME
                self._error_label.setText(f"密码错误次数过多，锁定{LOCK_TIME}秒")
                self._attempts = 0
            else:
                self._error_label.setText(f"密码错误，还剩{remaining}次机会")
            self._pw_input.clear()
            self._pw_input.setFocus()

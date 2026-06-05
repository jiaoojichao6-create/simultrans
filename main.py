#!/usr/bin/env python3
"""Simultaneous Translation System - Entry Point."""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Explicit imports for PyInstaller - forces all modules to be included
import audio.capture
import audio.playback
import pipeline.controller
import pipeline.vad
import pipeline.asr
import pipeline.translator
import pipeline.tts
import pipeline.glossary
import utils.config
import settings_window

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from login import LoginDialog
from main_window import MainWindow

def main():
    # High DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("同传翻译系统")
    app.setApplicationDisplayName("同传翻译系统 v1.0")

    # Login
    login = LoginDialog()
    if login.exec_() != LoginDialog.Accepted:
        return

    # Main window
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

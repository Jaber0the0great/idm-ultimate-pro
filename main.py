import sys
import os

# Prepends AppData updates to sys.path to dynamically override/load updated yt-dlp package
APP_NAME = "IDM ULTIMATE PRO"
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
updates_dir = os.path.join(CONFIG_DIR, "updates")
if os.path.exists(updates_dir):
    sys.path.insert(0, updates_dir)

from PyQt6.QtWidgets import QApplication
from main_window import ProDownloader

def main():
    app = QApplication(sys.argv)
    window = ProDownloader()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

# IDM Ultimate Pro (v1.0)

A modern, high-performance, and fully accessible download manager built with Python and PyQt6. This application is optimized for speed, reliability, and screen readers (such as NVDA and JAWS), providing a seamless downloading experience for all users.

## Features

- **High-Speed Downloads**: Multi-threaded segmented downloading to maximize bandwidth utilization.
- **Bulk URLs Input**: Add multiple direct, YouTube, or Google Drive download links simultaneously by separating them with commas (`,`).
- **Accessibility-First Design**: Consolidated single-field read-only details dialog (`QReadOnlyTextEdit`) optimized for line-by-line reading and text selection by screen readers.
- **No Emojis in UI**: Purely clean text interface designed for optimal speech output on assistive technologies.
- **Standalone Engine (No FFmpeg dependency)**: Specialized for direct, YouTube, and Google Drive downloading out of the box.
- **Hot-Reloadable Engine Update**: Bypasses compiled executable environment limitations by downloading, extracting, and loading pure Python `yt-dlp` updates directly from `%APPDATA%/IDM ULTIMATE PRO/updates`.
- **Multi-language Support**: Full support for English and Arabic.
- **Settings & Proxy Manager**: Custom speed limits, concurrent download settings, window close behaviors (tray vs exit), and proxies list manager.
- **Local History Database**: Relational SQLite-backed database (`history.db`) to log downloads, progress, speed, and completed duration.

## Project Structure

```text
idm_ultimate_pro/
│
├── main.py              # Application entrypoint (injects AppData updates into sys.path)
├── main_window.py       # Main PyQt6 interface, tabs (Direct, YouTube, Drive), list tables, and application logic
├── dialogs.py           # Custom dialogs (Settings, Proxy list, and accessible Task Info Dialog)
├── workers.py           # QRunnable background threads for downloading, speed metrics, and engine updating
├── config.py            # Local settings (config.json), SQLite database setup, and Arabic/English translations
└── .gitignore           # Git ignore configurations (ignores cache, DBs, and virtual environments)
```

## System Requirements

- Windows 10/11
- Python 3.8 or higher
- Dependency packages (see `requirements.txt`)

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/idm-ultimate-pro.git
   cd idm-ultimate-pro
   ```

2. **Create a virtual environment (Optional but recommended)**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install PyQt6
   ```
   *(Note: The core downloading logic is built on Python's built-in libraries and dynamic source loading of `yt-dlp` during updates, keeping standard dependencies minimal).*

4. **Run the application**:
   ```bash
   python main.py
   ```

## Creating a Windows Executable (Installer / Standalone EXE)

To compile this project into a standalone executable:

1. **Install PyInstaller**:
   ```bash
   pip install pyinstaller
   ```

2. **Generate the executable**:
   Run the following command in your terminal:
   ```bash
   pyinstaller --noconsole --onefile --name="IDM_Ultimate_Pro" --clean main.py
   ```
   This will generate a portable `IDM_Ultimate_Pro.exe` file in the `dist/` directory.

## How the Translations System Works

All application texts and translation dictionaries are managed dynamically:
- **Default translations** are stored embedded in the [config.py](file:///d:/PYTHON/idm_ultimate_pro/config.py) source code under the `ensure_translations()` method.
- **Local cache file**: When the application runs for the first time, it automatically creates/updates a translation file at:
  `%APPDATA%\IDM ULTIMATE PRO\translations.json` (typically `C:\Users\<Username>\AppData\Roaming\IDM ULTIMATE PRO\translations.json`).
- If you wish to customize translations, add more languages, or alter default phrases, you can edit that `translations.json` file. The application reads directly from this JSON cache upon startup.

## License

This project is open-source and available under the MIT License.

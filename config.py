import os
import json
import re
import sqlite3

APP_NAME = "IDM ULTIMATE PRO"
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DB_FILE = os.path.join(CONFIG_DIR, "history.db")

def load_config():
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = {
        "save_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "speed_limit": 0,
        "max_connections": 8,
        "language": "en",
        "minimize_to_tray_on_close": None
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except: pass
    
    # Ensure proxy fields are initialized
    if "proxy_enabled" not in cfg:
        cfg["proxy_enabled"] = False
    if "proxy_list" not in cfg:
        cfg["proxy_list"] = [
            "http://51.79.50.22:3128",
            "http://80.66.81.188:8080",
            "http://185.162.229.156:7497",
            "http://45.8.106.10:80"
        ]
    if "active_proxy" not in cfg:
        cfg["active_proxy"] = cfg["proxy_list"][0] if cfg["proxy_list"] else ""
        
    return cfg

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', str(text))

def init_db():
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            task_id TEXT PRIMARY KEY,
            url TEXT,
            filename TEXT,
            size TEXT,
            progress INTEGER,
            speed TEXT,
            status TEXT,
            path TEXT
        )
    ''')
    try:
        cursor.execute("ALTER TABLE downloads ADD COLUMN yt_opts TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE downloads ADD COLUMN max_connections INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE downloads ADD COLUMN added_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE downloads ADD COLUMN duration INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE downloads ADD COLUMN average_speed TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def migrate_json_to_sqlite():
    json_path = os.path.join(CONFIG_DIR, "history.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                history = json.load(f)
            init_db()
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            for tid, task in history.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO downloads (task_id, url, filename, size, progress, speed, status, path, yt_opts, max_connections, added_at, duration, average_speed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tid,
                    task.get("url", ""),
                    task.get("filename", ""),
                    task.get("size", ""),
                    task.get("progress", 0),
                    task.get("speed", ""),
                    task.get("status", ""),
                    task.get("path", ""),
                    json.dumps(task.get("yt_opts", {})),
                    task.get("max_connections", 8),
                    task.get("added_at", ""),
                    task.get("duration", 0),
                    task.get("average_speed", "0.00 MB/s")
                ))
            conn.commit()
            conn.close()
            os.remove(json_path)
        except Exception as e:
            print(f"Migration error: {e}")

def load_history():
    init_db()
    migrate_json_to_sqlite()
    
    history = {}
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, url, filename, size, progress, speed, status, path, yt_opts, max_connections, added_at, duration, average_speed FROM downloads")
        rows = cursor.fetchall()
        for row in rows:
            yt_opts_val = {}
            if len(row) > 8 and row[8]:
                try:
                    yt_opts_val = json.loads(row[8])
                except:
                    pass
            max_conn_val = 8
            if len(row) > 9 and row[9] is not None:
                try:
                    max_conn_val = int(row[9])
                except:
                    pass
            history[row[0]] = {
                "url": row[1],
                "filename": row[2],
                "size": row[3],
                "progress": row[4],
                "speed": row[5],
                "status": row[6],
                "path": row[7],
                "yt_opts": yt_opts_val,
                "max_connections": max_conn_val,
                "added_at": row[10] if len(row) > 10 else None,
                "duration": row[11] if len(row) > 11 else 0,
                "average_speed": row[12] if len(row) > 12 else "0.00 MB/s"
            }
        conn.close()
    except Exception as e:
        print(f"Load history error: {e}")
    return history

def save_history(history):
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for tid, task in history.items():
            yt_opts_str = json.dumps(task.get("yt_opts", {}))
            cursor.execute('''
                INSERT OR REPLACE INTO downloads (task_id, url, filename, size, progress, speed, status, path, yt_opts, max_connections, added_at, duration, average_speed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tid,
                task.get("url", ""),
                task.get("filename", ""),
                task.get("size", ""),
                task.get("progress", 0),
                task.get("speed", ""),
                task.get("status", ""),
                task.get("path", ""),
                yt_opts_str,
                task.get("max_connections", 8),
                task.get("added_at", ""),
                task.get("duration", 0),
                task.get("average_speed", "0.00 MB/s")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save history error: {e}")

def delete_history_task(task_id):
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM downloads WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Delete history task error: {e}")

TRANSLATIONS_FILE = os.path.join(CONFIG_DIR, "translations.json")

def ensure_translations():
    if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR, exist_ok=True)
    
    default_translations = {
        "en": {
            "title": "IDM ULTIMATE PRO v1.3",
            "subtitle": "STANDALONE ELITE ENGINE (NO FFMPEG)",
            "settings": "SETTINGS",
            "update_engine": "UPDATE ENGINE",
            "show_history": "SHOW HISTORY",
            "hide_history": "HIDE HISTORY",
            "youtube": "YOUTUBE",
            "direct": "DIRECT",
            "drive": "DRIVE",
            "url_placeholder": "Paste Link...",
            "direct_placeholder": "URL...",
            "drive_placeholder": "Link...",
            "start_downloading": "START DOWNLOADING",
            "col_filename": "File Name",
            "col_status": "Status",
            "col_size": "Size",
            "col_progress": "Progress",
            "col_speed": "Speed",
            "col_url": "URL",
            "status_ready": "STATUS: READY",
            "status_label": "STATUS",
            "speed_label": "SPEED",
            "shutdown_cb": "SHUTDOWN WHEN COMPLETE",
            "btn_pause": "PAUSE",
            "btn_resume": "RESUME",
            "btn_cancel": "CANCEL",
            "menu_pause": "Pause Download",
            "menu_resume": "Resume Download",
            "menu_info": "Information",
            "menu_copy_link": "Copy Download Link",
            "menu_open_file": "Open File",
            "menu_open_folder": "Open Folder",
            "menu_restart": "Restart Download",
            "menu_remove": "Remove from List",
            "menu_delete": "Delete Task & File",
            "Starting...": "Starting...",
            "Downloading...": "Downloading...",
            "Paused": "Paused",
            "Queue": "Queue",
            "Completed": "Completed",
            "Error": "Error",
            "Cancelled": "Cancelled",
            "Merging segments...": "Merging segments...",
            "Status: Merging segments...": "Merging segments...",
            "close_dialog_title": "CLOSE IDM ULTIMATE PRO",
            "close_dialog_text": "Do you want to minimize to the System Tray or exit the application completely?",
            "close_dialog_exit": "Exit Completely",
            "close_dialog_tray": "Minimize to Tray",
            "close_dialog_remember": "Remember my choice",
            "tray_restore": "Restore Window",
            "tray_exit": "Exit App",
            "tray_active": "Active Downloads:",
            "settings_title": "SETTINGS",
            "settings_dir": "DOWNLOAD DIRECTORY:",
            "settings_browse": "BROWSE",
            "settings_limit": "SPEED LIMIT (0 for Unlimited):",
            "settings_enable_limit": "Enable Speed Limit",
            "settings_max_conn": "MAX CONNECTIONS PER DOWNLOAD (Starting Point):",
            "settings_queue": "QUEUE / CONCURRENT DOWNLOADS:",
            "settings_limit_concurrent": "Limit Concurrent Downloads",
            "settings_proxy": "PROXY SETTINGS (Changes apply to future downloads):",
            "settings_enable_proxy": "Enable Proxy Server",
            "settings_proxy_list": "Proxy List Manager",
            "settings_add_proxy": "ADD PROXY",
            "settings_edit": "EDIT",
            "settings_delete": "DELETE",
            "settings_set_active": "SET ACTIVE",
            "settings_save": "SAVE",
            "settings_lang": "LANGUAGE / اللغة:",
            "update_app_btn": "Check App Update",
            "checking_updates": "Checking for updates...",
            "up_to_date": "Application is up to date!",
            "update_available_msg": "A new version ({}) of IDM Ultimate Pro is available.\nWould you like to download and install it now?",
            "updating_app_title": "Updating Application",
            "downloading_update": "Downloading update...",
            
            
            "settings_close_behavior_lbl": "ON WINDOW CLOSE:",
            "settings_close_behavior_prompt": "Always Ask Me",
            "settings_close_behavior_tray": "Minimize to System Tray",
            "settings_close_behavior_exit": "Exit Application",

            "close_confirm_title": "Confirm Exit",
            "close_confirm_text": "Warning: There are active downloads running. If you close the application, they will be paused.\n\nAre you sure you want to exit?",
            "btn_ok": "OK",
            "btn_cancel_action": "Cancel",

            "dialog_info_title": "DOWNLOAD DETAILS",
            "dialog_info_header": "DOWNLOAD DETAILS",
            "dialog_info_subtitle": "Detailed information for the selected task",
            "dialog_info_filename": "File Name:",
            "dialog_info_url": "Download URL:",
            "dialog_info_status": "Status:",
            "dialog_info_size": "Size:",
            "dialog_info_progress": "Progress:",
            "dialog_info_added": "Added At:",
            "dialog_info_time": "Download Time:",
            "dialog_info_conn": "Connection Level:",
            "dialog_info_avg_speed": "Avg Speed:",
            "dialog_info_save_path": "Save Path:",
            "dialog_info_open_folder": "OPEN FOLDER",
            "dialog_info_close": "CLOSE",
            "dialog_info_threads": "Threads",

            "link_copied_title": "Link Copied",
            "link_copied_msg": "Download link copied to clipboard!",

            "acc_title": "Application Title",
            "acc_subtitle": "Application Subtitle",
            "acc_settings_btn": "Settings Button",
            "acc_update_btn": "Update Engine Button",
            "acc_show_history_btn": "Show History Button",
            "acc_hide_history_btn": "Hide History Button",
            "acc_tabs": "Download Category Tabs",
            "acc_table": "Downloads Table List",
            "acc_status_indicator": "Task Status Indicator",
            "acc_progress_bar": "Download Progress Percentage",
            "acc_sizes": "File Sizes",
            "acc_percentage": "Percentage Complete Value",
            "acc_details_speed": "Download Details and speed",
            "acc_shutdown_cb": "Shutdown PC Checkbox",
            "acc_btn_pause": "Pause Selected Download Button",
            "acc_btn_resume": "Resume Selected Download Button",
            "acc_btn_cancel": "Cancel Selected Download Button",
            "acc_yt_url": "YouTube Video Link Input Field",
            "acc_yt_type": "Media Format Type Dropdown",
            "acc_yt_ext": "File Extension Dropdown",
            "acc_yt_qual": "Download Quality Dropdown",
            "acc_yt_start": "Start Downloading YouTube Video Button",
            "acc_direct_url": "Direct Link Input Field",
            "acc_direct_start": "Start Downloading Direct File Button",
            "acc_drive_url": "Google Drive Link Input Field",
            "acc_drive_start": "Start Downloading Google Drive File Button",
            "acc_lang_combo": "Language Selector Dropdown",
            "acc_path_edit": "Download Directory Path Field",
            "acc_bb": "Browse Folder Button",
            "acc_limit_checkbox": "Enable Speed Limit Checkbox",
            "acc_limit_spin": "Speed Limit Value Spinner",
            "acc_conn_combo": "Max Connections Dropdown",
            "acc_queue_checkbox": "Limit Concurrent Downloads Checkbox",
            "acc_queue_spin": "Max Concurrent Downloads Spinner",
            "acc_close_behavior_combo": "Window Close Action Dropdown",
            "acc_proxy_checkbox": "Enable Proxy Checkbox",
            "acc_proxy_list_widget": "Proxy List Manager List",
            "acc_btn_add_proxy": "Add Proxy Button",
            "acc_btn_edit_proxy": "Edit Selected Proxy Button",
            "acc_btn_del_proxy": "Delete Selected Proxy Button",
            "acc_btn_activate_proxy": "Set Selected Proxy Active Button",
            "acc_sb": "Save Settings Button",
            "acc_update_app_btn": "Check Application Update Button"
        },
        "ar": {
            "title": "IDM ULTIMATE PRO v1.3",
            "subtitle": "محرك النخبة المستقل (بدون FFMPEG)",
            "settings": "الإعدادات",
            "update_engine": "تحديث المحرك",
            "show_history": "عرض السجل",
            "hide_history": "إخفاء السجل",
            "youtube": "يوتيوب",
            "direct": "رابط مباشر",
            "drive": "جوجل درايف",
            "url_placeholder": "ضع الرابط هنا...",
            "direct_placeholder": "رابط الملف...",
            "drive_placeholder": "رابط الملف...",
            "start_downloading": "ابدأ التحميل",
            "col_filename": "اسم الملف",
            "col_status": "الحالة",
            "col_size": "الحجم",
            "col_progress": "نسبة التقدم",
            "col_speed": "السرعة",
            "col_url": "الرابط",
            "status_ready": "الحالة: جاهز",
            "status_label": "الحالة",
            "speed_label": "السرعة",
            "shutdown_cb": "إغلاق الكمبيوتر عند الاكتمال",
            "btn_pause": "إيقاف مؤقت",
            "btn_resume": "استئناف",
            "btn_cancel": "إلغاء",
            "menu_pause": "إيقاف مؤقت للتحميل",
            "menu_resume": "استئناف التحميل",
            "menu_info": "معلومات التحميل",
            "menu_copy_link": "نسخ رابط التحميل",
            "menu_open_file": "فتح الملف",
            "menu_open_folder": "فتح المجلد",
            "menu_restart": "إعادة التحميل من البداية",
            "menu_remove": "حذف من القائمة",
            "menu_delete": "حذف الملف والمهمة",
            "Starting...": "جاري البدء...",
            "Downloading...": "جاري التحميل...",
            "Paused": "موقوف مؤقتاً",
            "Queue": "في الانتظار",
            "Completed": "مكتمل",
            "Error": "خطأ",
            "Cancelled": "ملغى",
            "Merging segments...": "جاري دمج الأجزاء...",
            "Status: Merging segments...": "دمج الأجزاء...",
            "close_dialog_title": "إغلاق IDM ULTIMATE PRO",
            "close_dialog_text": "هل تريد إخفاء البرنامج في شريط النظام (System Tray) أم إغلاقه بالكامل؟",
            "close_dialog_exit": "إغلاق بالكامل",
            "close_dialog_tray": "إخفاء في شريط النظام",
            "close_dialog_remember": "تذكر خياري دائماً",
            "tray_restore": "استعادة النافذة",
            "tray_exit": "إغلاق بالكامل",
            "tray_active": "التحميلات الجارية:",
            "settings_title": "الإعدادات",
            "settings_dir": "مجلد حفظ التحميلات:",
            "settings_browse": "تصفح",
            "settings_limit": "الحد الأقصى للسرعة (0 لغير محدود):",
            "settings_enable_limit": "تفعيل حد السرعة",
            "settings_max_conn": "أقصى عدد اتصالات للتحميل الواحد (نقطة البداية):",
            "settings_queue": "جدولة التحميلات / التحميلات المتزامنة:",
            "settings_limit_concurrent": "تحديد عدد التحميلات المتزامنة",
            "settings_proxy": "إعدادات البروكسي (تطبق على التحميلات الجديدة):",
            "settings_enable_proxy": "تفعيل خادم البروكسي",
            "settings_proxy_list": "إدارة قائمة البروكسي",
            "settings_add_proxy": "إضافة بروكسي",
            "settings_edit": "تعديل",
            "settings_delete": "حذف",
            "settings_set_active": "تفعيل",
            "settings_save": "حفظ الإعدادات",
            "settings_lang": "اللغة / Language:",
            "update_app_btn": "التحقق من تحديث التطبيق",
            "checking_updates": "جاري التحقق من التحديثات...",
            "up_to_date": "التطبيق محدث إلى آخر إصدار!",
            "update_available_msg": "إصدار جديد متاح ({}) من برنامج IDM Ultimate Pro.\nهل تريد تحميل وتثبيت التحديث الآن؟",
            "updating_app_title": "تحديث التطبيق",
            "downloading_update": "جاري تحميل التحديث...",
            
            
            "settings_close_behavior_lbl": "عند إغلاق النافذة:",
            "settings_close_behavior_prompt": "اسألني دائماً",
            "settings_close_behavior_tray": "إخفاء في شريط النظام",
            "settings_close_behavior_exit": "إغلاق البرنامج بالكامل",

            "close_confirm_title": "تأكيد الخروج",
            "close_confirm_text": "تنبيه: هناك تحميلات نشطة جارية حالياً. إذا قمت بإغلاق البرنامج، فسيتم إيقافها مؤقتاً.\n\nهل أنت متأكد من رغبتك في الإغلاق؟",
            "btn_ok": "موافق",
            "btn_cancel_action": "إلغاء",

            "dialog_info_title": "تفاصيل التحميل",
            "dialog_info_header": "تفاصيل وبيانات التحميل",
            "dialog_info_subtitle": "معلومات وبيانات مهمة التحميل بالتفصيل",
            "dialog_info_filename": "اسم الملف:",
            "dialog_info_url": "رابط التحميل:",
            "dialog_info_status": "حالة الملف:",
            "dialog_info_size": "الحجم:",
            "dialog_info_progress": "نسبة التقدم:",
            "dialog_info_added": "تاريخ الإضافة:",
            "dialog_info_time": "الوقت المستغرق:",
            "dialog_info_conn": "طريقة التحميل:",
            "dialog_info_avg_speed": "متوسط السرعة:",
            "dialog_info_save_path": "مسار الحفظ:",
            "dialog_info_open_folder": "فتح المجلد",
            "dialog_info_close": "إغلاق",
            "dialog_info_threads": "خيوط (اتصالات)",

            "link_copied_title": "تم نسخ الرابط",
            "link_copied_msg": "تم نسخ رابط التحميل إلى الحافظة!",

            "acc_title": "عنوان التطبيق",
            "acc_subtitle": "العنوان الفرعي للتطبيق",
            "acc_settings_btn": "زر الإعدادات",
            "acc_update_btn": "زر تحديث المحرك",
            "acc_show_history_btn": "زر عرض السجل",
            "acc_hide_history_btn": "زر إخفاء السجل",
            "acc_tabs": "تبويبات فئات التحميل",
            "acc_table": "قائمة جدول التحميلات",
            "acc_status_indicator": "مؤشر حالة المهمة",
            "acc_progress_bar": "نسبة تقدم التحميل",
            "acc_sizes": "أحجام الملفات",
            "acc_percentage": "نسبة القيمة المكتملة",
            "acc_details_speed": "تفاصيل التحميل والسرعة",
            "acc_shutdown_cb": "صندوق اختيار إيقاف تشغيل الكمبيوتر",
            "acc_btn_pause": "زر إيقاف التحميل المحدد مؤقتاً",
            "acc_btn_resume": "زر استئناف التحميل المحدد",
            "acc_btn_cancel": "زر إلغاء التحميل المحدد",
            "acc_yt_url": "حقل إدخال رابط فيديو يوتيوب",
            "acc_yt_type": "قائمة اختيار نوع التنسيق",
            "acc_yt_ext": "قائمة اختيار امتداد الملف",
            "acc_yt_qual": "قائمة اختيار جودة التحميل",
            "acc_yt_start": "زر بدء تحميل فيديو يوتيوب",
            "acc_direct_url": "حقل إدخال رابط الملف المباشر",
            "acc_direct_start": "زر بدء تحميل الملف المباشر",
            "acc_drive_url": "حقل إدخال رابط جوجل درايف",
            "acc_drive_start": "زر بدء تحميل ملف جوجل درايف",
            "acc_lang_combo": "قائمة اختيار لغة البرنامج",
            "acc_path_edit": "حقل مسار مجلد التحميلات",
            "acc_bb": "زر تصفح المجلدات",
            "acc_limit_checkbox": "صندوق اختيار تفعيل حد السرعة",
            "acc_limit_spin": "محدد قيمة حد السرعة",
            "acc_conn_combo": "قائمة أقصى عدد اتصالات",
            "acc_queue_checkbox": "صندوق اختيار تحديد التحميلات المتزامنة",
            "acc_queue_spin": "محدد عدد التحميلات المتزامنة",
            "acc_close_behavior_combo": "قائمة إجراء إغلاق النافذة",
            "acc_proxy_checkbox": "صندوق اختيار تفعيل البروكسي",
            "acc_proxy_list_widget": "قائمة مدير خوادم البروكسي",
            "acc_btn_add_proxy": "زر إضافة بروكسي",
            "acc_btn_edit_proxy": "زر تعديل البروكسي المحدد",
            "acc_btn_del_proxy": "زر حذف البروكسي المحدد",
            "acc_btn_activate_proxy": "زر تفعيل البروكسي المحدد",
            "acc_sb": "زر حفظ الإعدادات",
            "acc_update_app_btn": "زر التحقق من تحديث التطبيق"
        }
    }
    
    try:
        with open(TRANSLATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_translations, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing default translations: {e}")

def load_translations():
    ensure_translations()
    try:
        with open(TRANSLATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading translations: {e}")
        return {"en": {}, "ar": {}}

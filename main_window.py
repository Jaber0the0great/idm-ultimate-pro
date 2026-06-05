import os
import sys
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QProgressBar, QLabel, QMessageBox, QTabWidget, QComboBox, QFrame,
    QFileDialog, QApplication, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QCheckBox,
    QMenu
)
from PyQt6.QtCore import Qt, QTimer, QEvent
from config import load_config, save_config, APP_NAME, load_history, save_history, delete_history_task, load_translations
from workers import UpdateWorker, UniversalWorker, FormatFetcher, AppUpdateCheckWorker
from dialogs import SettingsDialog, TaskInfoDialog

class AccessibleTableWidget(QTableWidget):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab:
            # Bypass QTableWidget cell-navigation and use standard QWidget focus change
            QWidget.focusNextPrevChild(self, True)
            return
        elif event.key() == Qt.Key.Key_Backtab:
            QWidget.focusNextPrevChild(self, False)
            return
        super().keyPressEvent(event)

class ProDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.translations = load_translations()
        self.lang = self.config.get("language", "en")
        self.setWindowTitle("IDM ULTIMATE PRO v1.0")
        self.setMinimumSize(1050, 780)
        self.update_save_dir(self.config.get("save_dir"))
        self.last_clipboard_url = ""
        
        # Load persistent history
        self.download_tasks = {}
        history = load_history()
        has_changes = False
        for task_id, task in history.items():
            status = task.get("status", "Paused")
            if status not in ["Completed", "Error", "Cancelled"]:
                status = "Paused"
                has_changes = True
            self.download_tasks[task_id] = {
                "worker": None,
                "url": task.get("url"),
                "filename": task.get("filename"),
                "size": task.get("size"),
                "progress": task.get("progress"),
                "speed": task.get("speed"),
                "status": status,
                "path": task.get("path", ""),
                "yt_opts": task.get("yt_opts", {}),
                "max_connections": task.get("max_connections", 8),
                "added_at": task.get("added_at", ""),
                "duration": task.get("duration", 0),
                "average_speed": task.get("average_speed", "0.00 MB/s")
            }
        if has_changes:
            save_history(self.download_tasks)
            
        self.init_ui()
        self.populate_table_from_history()
        
        # Hide history table by default on startup
        self.table.setVisible(False)
        
        # Shimmer and Glow Animations
        self.shimmer_step = 0
        self.shimmer_timer = QTimer(self)
        self.shimmer_timer.setInterval(80)
        self.shimmer_timer.timeout.connect(self.update_shimmer)
        self.shimmer_timer.start()
        
        self.update_style(0); self.tabs.currentChanged.connect(self.update_style)
        
        # Check for app updates automatically on startup after 3 seconds
        QTimer.singleShot(3000, lambda: self.check_app_updates(manual=False))

    def update_save_dir(self, p):
        self.save_dir = os.path.join(p, APP_NAME)
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir, exist_ok=True)

    def init_ui(self):
        c = QWidget(); self.setCentralWidget(c); l = QVBoxLayout(c); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        h = QFrame(); h.setObjectName("header"); hl = QHBoxLayout(h)
        tv = QVBoxLayout(); self.tl = QLabel("IDM ULTIMATE PRO"); self.tl.setObjectName("title")
        self.sl = QLabel("STANDALONE ELITE ENGINE (NO FFMPEG)"); self.sl.setObjectName("subtitle")
        tv.addWidget(self.tl); tv.addWidget(self.sl); hl.addLayout(tv); hl.addStretch()
        
        # Header Controls
        self.st_b = QPushButton("⚙️ SETTINGS"); self.st_b.clicked.connect(self.open_settings); self.st_b.setDefault(True); hl.addWidget(self.st_b)
        self.st_b.setAccessibleName("Settings Button")
        
        self.up_b = QPushButton("🔄 UPDATE ENGINE"); self.up_b.clicked.connect(self.update_lib); self.up_b.setDefault(True); hl.addWidget(self.up_b)
        self.up_b.setAccessibleName("Update Engine Button")
        
        self.app_up_b = QPushButton("CHECK APP UPDATE"); self.app_up_b.clicked.connect(lambda: self.check_app_updates(manual=True)); self.app_up_b.setDefault(True); hl.addWidget(self.app_up_b)
        self.app_up_b.setAccessibleName("Check App Update Button")
        
        # Toggle History Button
        self.hist_b = QPushButton("📋 SHOW HISTORY"); self.hist_b.clicked.connect(self.toggle_history); self.hist_b.setDefault(True); hl.addWidget(self.hist_b)
        self.hist_b.setAccessibleName("Show History Button")
        
        l.addWidget(h)
        
        self.tabs = QTabWidget(); self.tabs.setObjectName("tabs")
        self.tabs.setAccessibleName("Download Category Tabs")
        
        self.tabs.addTab(self.create_yt_tab(), "YOUTUBE")
        self.tabs.addTab(self.create_gen_tab("DIRECT LINK", "URL..."), "DIRECT")
        self.tabs.addTab(self.create_gen_tab("GOOGLE DRIVE", "Link..."), "DRIVE")
        l.addWidget(self.tabs)
        
        # Central Accessible Downloads Table with Context Menu
        self.table = AccessibleTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["File Name", "Status", "Size", "Progress", "Speed", "URL"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        
        self.table.setAccessibleName("Downloads Table List")
        self.table.setAccessibleDescription("Select a download task to view its progress or right-click to show action menu. Use Up and Down arrows to navigate rows.")
        
        # Enable Right-Click Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        l.addWidget(self.table)
        
        # Dashboard for Selected Task Details
        d = QFrame(); d.setObjectName("dash"); dl = QVBoxLayout(d)
        
        self.stat_l = QLabel("STATUS: READY"); self.stat_l.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.stat_l.setObjectName("stat_l")
        self.stat_l.setAccessibleName("Task Status Indicator")
        
        self.bar = QProgressBar(); self.bar.setFixedHeight(14); self.bar.setTextVisible(False); self.bar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.bar.setAccessibleName("Download Progress Percentage")
        
        dl.addWidget(self.stat_l); dl.addWidget(self.bar)
        
        il = QHBoxLayout()
        self.sz_l = QLabel("0.00 MB / 0.00 MB"); self.sz_l.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.sz_l.setAccessibleName("File Sizes")
        
        self.pc_l = QLabel("0%"); self.pc_l.setObjectName("perc"); 
        self.pc_l.setAccessibleName("Percentage Complete Value")
        
        il.addWidget(self.sz_l); il.addStretch(); il.addWidget(self.pc_l); dl.addLayout(il)
        
        self.sd = QLineEdit(); self.sd.setReadOnly(True); self.sd.setAlignment(Qt.AlignmentFlag.AlignCenter); self.sd.setObjectName("sd"); self.sd.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.sd.setAccessibleName("Download Details and speed")
        dl.addWidget(self.sd)
        
        bl = QHBoxLayout()
        self.shutdown_cb = QCheckBox("SHUTDOWN WHEN COMPLETE")
        self.shutdown_cb.setStyleSheet("color: #fff; font-weight: bold; margin-right: 15px;")
        self.shutdown_cb.setAccessibleName("Shutdown PC Checkbox")
        bl.addWidget(self.shutdown_cb)
        
        self.p_b = QPushButton("⏸️ PAUSE"); self.r_b = QPushButton("▶️ RESUME"); self.c_b = QPushButton("⏹️ CANCEL")
        
        self.p_b.setAccessibleName("Pause Selected Download")
        self.r_b.setAccessibleName("Resume Selected Download")
        self.c_b.setAccessibleName("Cancel Selected Download")
        
        for b in [self.p_b, self.r_b, self.c_b]: b.setEnabled(False); b.setDefault(True); bl.addWidget(b)
        self.p_b.clicked.connect(self.pause); self.r_b.clicked.connect(self.resume); self.c_b.clicked.connect(self.cancel)
        dl.addLayout(bl); l.addWidget(d)
        
        self.setup_tray_icon()
        self.retranslate_ui()

    def toggle_history(self):
        visible = self.table.isVisible()
        self.table.setVisible(not visible)
        if not visible:
            self.hist_b.setText(self.translate("hide_history"))
            self.hist_b.setAccessibleName("Hide History Button")
        else:
            self.hist_b.setText(self.translate("show_history"))
            self.hist_b.setAccessibleName("Show History Button")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        
        row = self.table.row(item)
        name_item = self.table.item(row, 0)
        if not name_item: return
        task_id = name_item.data(Qt.ItemDataRole.UserRole)
        task = self.download_tasks.get(task_id)
        if not task: return
        
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #111; color: #fff; border: 1px solid #333;")
        
        status = task.get("status", "")
        status_lower = status.lower()
        worker = task.get("worker")
        
        is_running = False
        is_paused = False
        if worker:
            try:
                is_running = worker.isRunning()
                is_paused = worker._is_paused
            except RuntimeError:
                task["worker"] = None
                worker = None
        
        action_pause = None
        action_resume = None
        
        if status_lower != "completed":
            action_pause = menu.addAction(self.translate("menu_pause"))
            action_resume = menu.addAction(self.translate("menu_resume"))
            if status_lower == "queue":
                action_pause.setEnabled(True)
                action_resume.setEnabled(False)
            else:
                action_pause.setEnabled(is_running and not is_paused)
                action_resume.setEnabled(
                    (not is_running and status_lower in ["paused", "cancelled", "error", "ready"]) or
                    (is_running and is_paused)
                )
            menu.addSeparator()
            
        action_info = menu.addAction(self.translate("menu_info"))
        menu.addSeparator()
        action_copy_link = menu.addAction(self.translate("menu_copy_link"))
        action_open_file = menu.addAction(self.translate("menu_open_file"))
        action_open_folder = menu.addAction(self.translate("menu_open_folder"))
        menu.addSeparator()
        action_restart = menu.addAction(self.translate("menu_restart"))
        action_remove = menu.addAction(self.translate("menu_remove"))
        action_delete = menu.addAction(self.translate("menu_delete"))
        
        action = menu.exec(self.table.mapToGlobal(pos))
        
        if action == action_info:
            self.show_task_info(task_id)
        elif action_pause and action == action_pause:
            self.pause_task(task_id)
        elif action_resume and action == action_resume:
            self.resume_task(task_id)
        elif action == action_copy_link:
            self.copy_task_link(task)
        elif action == action_open_file:
            self.open_task_file(task)
        elif action == action_open_folder:
            self.open_task_folder(task)
        elif action == action_restart:
            self.restart_task(task_id)
        elif action == action_remove:
            self.remove_task(task_id)
        elif action == action_delete:
            self.delete_task_file(task_id)

    def show_task_info(self, task_id):
        task = self.download_tasks.get(task_id)
        if not task: return
        dlg = TaskInfoDialog(self, task, current_lang=self.lang, translations=self.translations)
        dlg.exec()

    def copy_task_link(self, task):
        url = task.get("url", "")
        if url:
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "INFO", "Download link copied to clipboard!")

    def open_task_file(self, task):
        path = task.get("path", "")
        if path and os.path.exists(path):
            try: os.startfile(path)
            except Exception as e: QMessageBox.warning(self, "ERROR", f"Could not open file:\n{str(e)}")
        else:
            QMessageBox.warning(self, "ERROR", "File does not exist on disk!")

    def open_task_folder(self, task):
        path = task.get("path", "")
        if path:
            folder = os.path.dirname(path)
            if os.path.exists(folder):
                try: os.startfile(folder)
                except Exception as e: QMessageBox.warning(self, "ERROR", f"Could not open folder:\n{str(e)}")
                return
        QMessageBox.warning(self, "ERROR", "Download folder does not exist!")

    def restart_task(self, task_id):
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if worker and worker.isRunning():
                worker.cancel()
                worker.wait()
            
            path = task.get("path", "")
            if path and os.path.exists(path):
                try: os.remove(path)
                except: pass
            temp_dir = os.path.join(self.save_dir, ".temp", task_id)
            if os.path.exists(temp_dir):
                import shutil
                try: shutil.rmtree(temp_dir, ignore_errors=True)
                except: pass
            for i in range(8):
                part = os.path.join(self.save_dir, f"{task_id}.part{i}")
                if os.path.exists(part):
                    try: os.remove(part)
                    except: pass
            # Fallback part file cleanup
            fallback_part = os.path.join(self.save_dir, f"{task_id}.part")
            if os.path.exists(fallback_part):
                try: os.remove(fallback_part)
                except: pass
            # YouTube temp files cleanup
            for ext in ['.mp4', '.webm', '.m4a', '.mp3', '.part', '.ytdl', '.part-Frag0', '.part-Frag1', '.part-Frag2', '.part-Frag3']:
                yt_temp = os.path.join(self.save_dir, f"dl_temp_{task_id}{ext}")
                if os.path.exists(yt_temp):
                    try: os.remove(yt_temp)
                    except: pass
            
            # Check queue limit
            queue_enabled = self.config.get("queue_enabled", False)
            max_concurrent = self.config.get("max_concurrent", 1)
            active_count = self.get_active_downloads_count()
            
            status_str = "Downloading..."
            should_start = True
            
            if queue_enabled and active_count >= max_concurrent:
                status_str = "Queue"
                should_start = False
                
            row = self.find_row_by_task_id(task_id)
            if row != -1:
                self.table.setItem(row, 1, QTableWidgetItem(status_str))
                self.table.setItem(row, 2, QTableWidgetItem("0.00 MB / 0.00 MB"))
                self.table.setItem(row, 3, QTableWidgetItem("0%"))
                self.table.setItem(row, 4, QTableWidgetItem("0.00 MB/s"))
            
            url = task["url"]
            idx = 0 if "youtu" in url else (2 if "drive" in url else 1)
            mode = ["YouTube", "Direct", "Drive"][idx]
            yt_opts = task.get("yt_opts", {})
            if not yt_opts and idx == 0:
                yt_opts = {'type': self.type_c.currentText(), 'ext': self.ext_c.currentText(), 'quality': self.qual_c.currentText()}
            speed_limit = self.config.get("speed_limit", 0)
            max_conn = task.get("max_connections", self.config.get("max_connections", 8))
            proxy = self.config.get("active_proxy") if self.config.get("proxy_enabled", False) else None
            
            new_worker = UniversalWorker(task_id, url, self.save_dir, mode, yt_opts, speed_limit, max_conn, proxy)
            new_worker.finished.connect(lambda *args, w=new_worker: w.deleteLater())
            new_worker.progress_changed.connect(lambda p, tid=task_id: self.update_progress(tid, p))
            new_worker.stats_updated.connect(lambda s, tid=task_id: self.update_stats(tid, s))
            new_worker.size_info_changed.connect(lambda d, t, r, tid=task_id: self.update_size_info(tid, d, t))
            new_worker.status_changed.connect(lambda s, tid=task_id: self.update_status(tid, s))
            new_worker.finished.connect(lambda ok, path, msg, duration, avg_speed, tid=task_id: self.done(tid, ok, path, msg, duration, avg_speed))
            
            task["worker"] = new_worker
            task["status"] = status_str
            task["progress"] = 0
            task["duration"] = 0
            task["average_speed"] = "0.00 MB/s"
            save_history(self.download_tasks)
            
            if should_start:
                new_worker.start()
            self.update_dashboard_ui(task_id)

    def remove_task(self, task_id):
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if worker and worker.isRunning():
                worker.cancel()
                worker.wait()
            row = self.find_row_by_task_id(task_id)
            if row != -1: self.table.removeRow(row)
            del self.download_tasks[task_id]
            delete_history_task(task_id)
            self.on_row_selected()
            self.process_queue()

    def delete_task_file(self, task_id):
        res = QMessageBox.question(self, "DELETE", "Are you sure you want to delete this task and its files from disk?")
        if res == QMessageBox.StandardButton.Yes:
            task = self.download_tasks.get(task_id)
            if task:
                worker = task.get("worker")
                if worker and worker.isRunning():
                    worker.cancel()
                    worker.wait()
                
                path = task.get("path", "")
                if path and os.path.exists(path):
                    try: os.remove(path)
                    except: pass
                temp_dir = os.path.join(self.save_dir, ".temp", task_id)
                if os.path.exists(temp_dir):
                    import shutil
                    try: shutil.rmtree(temp_dir, ignore_errors=True)
                    except: pass
                for i in range(8):
                    part = os.path.join(self.save_dir, f"{task_id}.part{i}")
                    if os.path.exists(part):
                        try: os.remove(part)
                        except: pass
                # Fallback part file cleanup
                fallback_part = os.path.join(self.save_dir, f"{task_id}.part")
                if os.path.exists(fallback_part):
                    try: os.remove(fallback_part)
                    except: pass
                # YouTube temp files cleanup
                for ext in ['.mp4', '.webm', '.m4a', '.mp3', '.part', '.ytdl', '.part-Frag0', '.part-Frag1', '.part-Frag2', '.part-Frag3']:
                    yt_temp = os.path.join(self.save_dir, f"dl_temp_{task_id}{ext}")
                    if os.path.exists(yt_temp):
                        try: os.remove(yt_temp)
                        except: pass
                
                row = self.find_row_by_task_id(task_id)
                if row != -1: self.table.removeRow(row)
                del self.download_tasks[task_id]
                delete_history_task(task_id)
                self.on_row_selected()
                self.process_queue()

    def populate_table_from_history(self):
        for task_id, task in self.download_tasks.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            name_item = QTableWidgetItem(task.get("filename", "Unknown"))
            name_item.setData(Qt.ItemDataRole.UserRole, task_id)
            
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(task.get("status", "Paused")))
            self.table.setItem(row, 2, QTableWidgetItem(task.get("size", "0.00 MB / 0.00 MB")))
            self.table.setItem(row, 3, QTableWidgetItem(f"{task.get('progress', 0)}%"))
            self.table.setItem(row, 4, QTableWidgetItem(task.get("speed", "0.00 MB/s")))
            self.table.setItem(row, 5, QTableWidgetItem(task.get("url", "")))

    def translate(self, key):
        return self.translations.get(self.lang, {}).get(key, key)

    def retranslate_ui(self):
        # Header titles
        if hasattr(self, 'tl') and self.tl:
            self.tl.setText(self.translate("title"))
            self.tl.setAccessibleName(self.translate("acc_title"))
        if hasattr(self, 'sl') and self.sl:
            self.sl.setText(self.translate("subtitle"))
            self.sl.setAccessibleName(self.translate("acc_subtitle"))
            
        # Header buttons
        if hasattr(self, 'st_b') and self.st_b:
            self.st_b.setText(self.translate("settings"))
            self.st_b.setAccessibleName(self.translate("acc_settings_btn"))
        if hasattr(self, 'up_b') and self.up_b:
            self.up_b.setText(self.translate("update_engine"))
            self.up_b.setAccessibleName(self.translate("acc_update_btn"))
        if hasattr(self, 'app_up_b') and self.app_up_b:
            self.app_up_b.setText(self.translate("update_app_btn"))
            self.app_up_b.setAccessibleName(self.translate("acc_update_app_btn"))
        if hasattr(self, 'hist_b') and self.hist_b:
            visible = self.table.isVisible()
            self.hist_b.setText(self.translate("hide_history") if visible else self.translate("show_history"))
            self.hist_b.setAccessibleName(self.translate("acc_hide_history_btn") if visible else self.translate("acc_show_history_btn"))
            
        # Tab headers
        if hasattr(self, 'tabs') and self.tabs:
            self.tabs.setTabText(0, self.translate("youtube"))
            self.tabs.setTabText(1, self.translate("direct"))
            self.tabs.setTabText(2, self.translate("drive"))
            self.tabs.setAccessibleName(self.translate("acc_tabs"))
            
            # YouTube tab contents
            yt_tab = self.tabs.widget(0)
            if yt_tab:
                lbl_title = yt_tab.findChild(QLabel, "tabTitle")
                if lbl_title: lbl_title.setText(self.translate("youtube") + " ENGINE")
                if hasattr(self, 'yt_url_input') and self.yt_url_input:
                    self.yt_url_input.setPlaceholderText(self.translate("url_placeholder"))
                    self.yt_url_input.setAccessibleName(self.translate("acc_yt_url"))
                if hasattr(self, 'type_c') and self.type_c:
                    self.type_c.setAccessibleName(self.translate("acc_yt_type"))
                if hasattr(self, 'ext_c') and self.ext_c:
                    self.ext_c.setAccessibleName(self.translate("acc_yt_ext"))
                if hasattr(self, 'qual_c') and self.qual_c:
                    self.qual_c.setAccessibleName(self.translate("acc_yt_qual"))
                btn_start = yt_tab.findChild(QPushButton, "start_btn")
                if btn_start:
                    btn_start.setText(self.translate("start_downloading"))
                    btn_start.setAccessibleName(self.translate("acc_yt_start"))
                
            # Direct tab contents
            dir_tab = self.tabs.widget(1)
            if dir_tab:
                lbl_title = dir_tab.findChild(QLabel, "tabTitle")
                if lbl_title: lbl_title.setText(self.translate("direct") + " LINK")
                inp_url = dir_tab.findChild(QLineEdit, "url")
                if inp_url: 
                    inp_url.setPlaceholderText(self.translate("direct_placeholder"))
                    inp_url.setAccessibleName(self.translate("acc_direct_url"))
                btn_start = dir_tab.findChild(QPushButton, "start_btn")
                if btn_start:
                    btn_start.setText(self.translate("start_downloading"))
                    btn_start.setAccessibleName(self.translate("acc_direct_start"))
                
            # Drive tab contents
            drv_tab = self.tabs.widget(2)
            if drv_tab:
                lbl_title = drv_tab.findChild(QLabel, "tabTitle")
                if lbl_title: lbl_title.setText(self.translate("drive") + " DRIVE")
                inp_url = drv_tab.findChild(QLineEdit, "url")
                if inp_url:
                    inp_url.setPlaceholderText(self.translate("drive_placeholder"))
                    inp_url.setAccessibleName(self.translate("acc_drive_url"))
                btn_start = drv_tab.findChild(QPushButton, "start_btn")
                if btn_start:
                    btn_start.setText(self.translate("start_downloading"))
                    btn_start.setAccessibleName(self.translate("acc_drive_start"))
                
        # Table Headers
        if hasattr(self, 'table') and self.table:
            self.table.setAccessibleName(self.translate("acc_table"))
            self.table.setHorizontalHeaderLabels([
                self.translate("col_filename"),
                self.translate("col_status"),
                self.translate("col_size"),
                self.translate("col_progress"),
                self.translate("col_speed"),
                self.translate("col_url")
            ])
            
            # Retranslate statuses of all existing rows
            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                if name_item:
                    task_id = name_item.data(Qt.ItemDataRole.UserRole)
                    task = self.download_tasks.get(task_id)
                    if task:
                        status_item = self.table.item(row, 1)
                        if status_item:
                            status_item.setText(self.translate(task.get("status", "Paused")))
                            
        # Dashboard
        if hasattr(self, 'shutdown_cb') and self.shutdown_cb:
            self.shutdown_cb.setText(self.translate("shutdown_cb"))
            self.shutdown_cb.setAccessibleName(self.translate("acc_shutdown_cb"))
        if hasattr(self, 'p_b') and self.p_b:
            self.p_b.setText(self.translate("btn_pause"))
            self.p_b.setAccessibleName(self.translate("acc_btn_pause"))
        if hasattr(self, 'r_b') and self.r_b:
            self.r_b.setText(self.translate("btn_resume"))
            self.r_b.setAccessibleName(self.translate("acc_btn_resume"))
        if hasattr(self, 'c_b') and self.c_b:
            self.c_b.setText(self.translate("btn_cancel"))
            self.c_b.setAccessibleName(self.translate("acc_btn_cancel"))
            
        # Accessible names for sizes, progress value, details speed indicators
        if hasattr(self, 'stat_l') and self.stat_l:
            self.stat_l.setAccessibleName(self.translate("acc_status_indicator"))
        if hasattr(self, 'bar') and self.bar:
            self.bar.setAccessibleName(self.translate("acc_progress_bar"))
        if hasattr(self, 'sz_l') and self.sz_l:
            self.sz_l.setAccessibleName(self.translate("acc_sizes"))
        if hasattr(self, 'pc_l') and self.pc_l:
            self.pc_l.setAccessibleName(self.translate("acc_percentage"))
        if hasattr(self, 'sd') and self.sd:
            self.sd.setAccessibleName(self.translate("acc_details_speed"))
            
        # Retranslate system tray icon tooltip
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.setToolTip(self.translate("title"))
            
        # Update Dashboard text
        selected_id = self.get_selected_task_id()
        if selected_id:
            self.update_dashboard_ui(selected_id)
        else:
            if hasattr(self, 'stat_l') and self.stat_l:
                self.stat_l.setText(self.translate("status_ready"))

    def setup_tray_icon(self):
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
        
        self.tray_icon = QSystemTrayIcon(self)
        
        # Resilient icon loading
        icon_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico"),
            "icon.ico"
        ]
        icon = None
        for p in icon_paths:
            if os.path.exists(p):
                icon = QIcon(p)
                break
        if not icon:
            icon = self.windowIcon()
            
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(self.translate("title"))
        
        self.tray_menu = QMenu(self)
        self.tray_menu.setStyleSheet("background-color: #111; color: #fff; border: 1px solid #333;")
        self.tray_menu.aboutToShow.connect(self.populate_tray_menu)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        
    def on_tray_icon_activated(self, reason):
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason in [QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick]:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
                
    def populate_tray_menu(self):
        self.tray_menu.clear()
        
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu
        
        # Restore Action
        action_restore = QAction(self.translate("tray_restore"), self)
        action_restore.triggered.connect(lambda: (self.show(), self.raise_(), self.activateWindow()))
        self.tray_menu.addAction(action_restore)
        
        # Exit Action
        action_exit = QAction(self.translate("tray_exit"), self)
        action_exit.triggered.connect(self.exit_application)
        self.tray_menu.addAction(action_exit)
        
        self.tray_menu.addSeparator()
        
        # Active Downloads Header
        header_action = QAction(self.translate("tray_active"), self)
        header_action.setEnabled(False)
        self.tray_menu.addAction(header_action)
        
        # Add dynamic active tasks
        active_tasks_found = False
        for task_id, task in self.download_tasks.items():
            status = task.get("status", "").lower()
            if status in ["starting...", "downloading...", "queue", "paused", "merging segments...", "status: merging segments..."]:
                active_tasks_found = True
                
                filename = task.get("filename", "Unknown")
                progress = task.get("progress", 0)
                status_disp = self.translate(task.get("status"))
                label = f"• {filename} ({status_disp} - {progress}%)"
                
                sub_menu = QMenu(label, self)
                sub_menu.setStyleSheet("background-color: #111; color: #fff; border: 1px solid #333;")
                
                if status == "paused":
                    act_resume = QAction(self.translate("btn_resume"), self)
                    act_resume.triggered.connect(lambda checked, tid=task_id: self.resume_task(tid))
                    sub_menu.addAction(act_resume)
                else:
                    act_pause = QAction(self.translate("btn_pause"), self)
                    act_pause.triggered.connect(lambda checked, tid=task_id: self.pause_task(tid))
                    sub_menu.addAction(act_pause)
                    
                act_cancel = QAction(self.translate("btn_cancel"), self)
                act_cancel.triggered.connect(lambda checked, tid=task_id: self.cancel_task_by_id(tid))
                sub_menu.addAction(act_cancel)
                
                self.tray_menu.addMenu(sub_menu)
                
        if not active_tasks_found:
            no_active_action = QAction("  " + ("لا يوجد تحميلات نشطة" if self.lang == "ar" else "No active downloads"), self)
            no_active_action.setEnabled(False)
            self.tray_menu.addAction(no_active_action)
            
    def cancel_task_by_id(self, task_id):
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if worker and worker.isRunning():
                worker.cancel()
            task["status"] = "Cancelled"
            save_history(self.download_tasks)
            row = self.find_row_by_task_id(task_id)
            if row != -1:
                status_item = self.table.item(row, 1)
                if status_item:
                    status_item.setText(self.translate("Cancelled"))
                else:
                    self.table.setItem(row, 1, QTableWidgetItem(self.translate("Cancelled")))
            self.update_dashboard_ui(task_id)
            self.process_queue()

    def open_settings(self):
        current_base = os.path.dirname(self.save_dir) if self.save_dir.endswith(APP_NAME) else self.save_dir
        current_limit = self.config.get("speed_limit", 0)
        q_enabled = self.config.get("queue_enabled", False)
        q_max = self.config.get("max_concurrent", 1)
        max_conn = self.config.get("max_connections", 8)
        proxy_enabled = self.config.get("proxy_enabled", False)
        proxy_list = self.config.get("proxy_list", [])
        active_proxy = self.config.get("active_proxy", "")
        close_behavior = self.config.get("minimize_to_tray_on_close", None)
        
        dlg = SettingsDialog(self, current_base, current_limit, q_enabled, q_max, max_conn, proxy_enabled, proxy_list, active_proxy, self.lang, self.translations, close_behavior)
        if dlg.exec():
            new_base = dlg.get_path()
            new_limit = dlg.get_limit()
            new_q_enabled = dlg.get_queue_enabled()
            new_q_max = dlg.get_max_concurrent()
            new_max_conn = dlg.get_max_connections()
            new_proxy_enabled = dlg.get_proxy_enabled()
            new_proxy_list = dlg.get_proxy_list()
            new_active_proxy = dlg.get_active_proxy()
            new_lang = dlg.get_language()
            new_close_behavior = dlg.get_close_behavior()
            
            self.config["save_dir"] = new_base
            self.config["speed_limit"] = new_limit
            self.config["queue_enabled"] = new_q_enabled
            self.config["max_concurrent"] = new_q_max
            self.config["max_connections"] = new_max_conn
            self.config["proxy_enabled"] = new_proxy_enabled
            self.config["proxy_list"] = new_proxy_list
            self.config["active_proxy"] = new_active_proxy
            self.config["language"] = new_lang
            self.config["minimize_to_tray_on_close"] = new_close_behavior
            
            save_config(self.config)
            self.update_save_dir(new_base)
            self.process_queue()
            
            if new_lang != self.lang:
                self.lang = new_lang
                self.retranslate_ui()

    def update_style(self, idx):
        base = (
            "QMainWindow { background: #0d0e12; }"
            "#header { background: #161922; padding: 25px; border-bottom: 2px solid #2e3440; }"
            "#title { color: #fff; font-size: 38px; font-weight: 900; }"
            "#subtitle { color: #4c566a; font-size: 10px; letter-spacing: 5px; }"
            "#dash { background: #161922; padding: 25px; border-top: 1px solid #2e3440; }"
            "QTabWidget::pane { border-radius: 8px; border: 1px solid #2e3440; }"
            "QTabBar::tab { background: #161922; color: #d8dee9; padding: 15px 40px; font-weight: 900; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }"
            "QLineEdit, QComboBox { background: #161922; border: 1px solid #2e3440; color: #fff; padding: 10px; border-radius: 6px; }"
            "QPushButton { background: #1a1d26; color: #fff; border: 1px solid #2e3440; font-weight: 900; padding: 12px; border-radius: 6px; }"
            "QPushButton:hover { background: #2b303c; border: 1px solid #434c5e; }"
            "QProgressBar { background: #161922; border: 1px solid #2e3440; border-radius: 7px; height: 14px; }"
            "#sd { background: #0d0e12; border: none; color: #fff; border-radius: 4px; }"
            "#tabTitle { font-size: 24px; font-weight: 800; }"
            "QTableWidget { background: #0d0e12; border: 1px solid #2e3440; color: #fff; gridline-color: #1a1d26; border-radius: 8px; }"
            "QHeaderView::section { background: #161922; color: #d8dee9; padding: 8px; border: 1px solid #2e3440; font-weight: bold; }"
            "QTableWidget::item { padding: 10px; }"
            "QScrollBar:vertical { background: #161922; width: 12px; margin: 0px; }"
            "QScrollBar::handle:vertical { background: #2e3440; min-height: 20px; border-radius: 6px; }"
            "QScrollBar::handle:vertical:hover { background: #434c5e; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; height: 0px; }"
            "QScrollBar:horizontal { background: #161922; height: 12px; margin: 0px; }"
            "QScrollBar::handle:horizontal { background: #2e3440; min-width: 20px; border-radius: 6px; }"
            "QScrollBar::handle:horizontal:hover { background: #434c5e; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: none; width: 0px; }"
        )
        if idx == 0: 
            c = (
                "QTabBar::tab:selected { border-bottom: 4px solid #ff3b30; color: #ff3b30; }"
                "QLineEdit:focus, QComboBox:focus { border: 1px solid #ff3b30; }"
                "QProgressBar::chunk { background: #ff3b30; border-radius: 7px; }"
                "#perc, #sd, #tabTitle { color: #ff3b30; }"
                "QTabWidget::pane { background: #181010; border-top: 2px solid #ff3b30; }"
                "QTableWidget::item:selected { background: #1a1010; color: #ff3b30; border: 1px solid #ff3b30; }"
            )
        elif idx == 2: 
            c = (
                "QTabBar::tab:selected { border-bottom: 4px solid #2ecc71; color: #2ecc71; }"
                "QLineEdit:focus, QComboBox:focus { border: 1px solid #2ecc71; }"
                "QProgressBar::chunk { background: #2ecc71; border-radius: 7px; }"
                "#perc, #sd, #tabTitle { color: #2ecc71; }"
                "QTabWidget::pane { background: #0c1810; border-top: 2px solid #2ecc71; }"
                "QTableWidget::item:selected { background: #0c1410; color: #2ecc71; border: 1px solid #2ecc71; }"
            )
        else: 
            c = (
                "QTabBar::tab:selected { border-bottom: 4px solid #00d8ff; color: #00d8ff; }"
                "QLineEdit:focus, QComboBox:focus { border: 1px solid #00d8ff; }"
                "QProgressBar::chunk { background: #00d8ff; border-radius: 7px; }"
                "#perc, #sd, #tabTitle { color: #00d8ff; }"
                "QTabWidget::pane { background: #0c181a; border-top: 2px solid #00d8ff; }"
                "QTableWidget::item:selected { background: #0c141a; color: #00d8ff; border: 1px solid #00d8ff; }"
            )
        self.setStyleSheet(base + c)

    def create_yt_tab(self):
        tab = QWidget(); l = QVBoxLayout(tab); l.setContentsMargins(80, 50, 80, 50); l.setSpacing(20)
        lbl = QLabel("YOUTUBE ENGINE"); lbl.setObjectName("tabTitle"); l.addWidget(lbl)
        self.yt_url_input = QLineEdit(); self.yt_url_input.setPlaceholderText("Paste Link..."); self.yt_url_input.setObjectName("url"); self.yt_url_input.setFixedHeight(50); l.addWidget(self.yt_url_input)
        
        self.yt_url_input.setAccessibleName("YouTube Video Link Input")
        self.yt_url_input.editingFinished.connect(self.fetch_yt_formats)
        
        sel = QHBoxLayout(); self.type_c = QComboBox(); self.type_c.addItems(["Video", "Audio"]); self.type_c.currentTextChanged.connect(self.update_opts)
        self.type_c.setAccessibleName("Media Format Type Dropdown")
        
        self.ext_c = QComboBox(); self.qual_c = QComboBox()
        self.ext_c.setAccessibleName("File Extension Dropdown")
        self.qual_c.setAccessibleName("Download Quality Dropdown")
        
        sel.addWidget(self.type_c); sel.addWidget(self.ext_c); sel.addWidget(self.qual_c); l.addLayout(sel)
        self.update_opts("Video")
        
        btn = QPushButton("🚀 START DOWNLOADING"); btn.setFixedHeight(60); btn.clicked.connect(self.start); btn.setDefault(True); l.addWidget(btn)
        btn.setObjectName("start_btn")
        btn.setAccessibleName("Start Downloading YouTube Video Button")
        
        return tab

    def create_gen_tab(self, txt, hint):
        tab = QWidget(); l = QVBoxLayout(tab); l.setContentsMargins(80, 80, 80, 80); l.setSpacing(20)
        lbl = QLabel(txt); lbl.setObjectName("tabTitle"); l.addWidget(lbl)
        
        inp = QLineEdit(); inp.setPlaceholderText(hint); inp.setObjectName("url"); inp.setFixedHeight(50); l.addWidget(inp)
        inp.setAccessibleName(f"{txt} Link Input")
        
        btn = QPushButton("🚀 START DOWNLOADING"); btn.setFixedHeight(60); btn.clicked.connect(self.start); btn.setDefault(True); l.addWidget(btn)
        btn.setObjectName("start_btn")
        btn.setAccessibleName(f"Start Downloading {txt} Button")
        
        return tab

    def update_opts(self, t):
        self.ext_c.clear(); self.qual_c.clear()
        if t == "Video":
            self.ext_c.addItems(["mp4", "original"])
            if hasattr(self, 'fetched_video_res') and self.fetched_video_res:
                self.qual_c.addItems(self.fetched_video_res)
            else:
                self.qual_c.addItems(["1080p", "720p", "480p", "360p"])
        else:
            self.ext_c.addItems(["mp3", "m4a"])
            if hasattr(self, 'fetched_audio_kbps') and self.fetched_audio_kbps:
                self.qual_c.addItems(self.fetched_audio_kbps)
            else:
                self.qual_c.addItems(["320kbps", "192kbps", "128kbps"])

    def fetch_yt_formats(self):
        url = self.yt_url_input.text().strip()
        if not url or "youtu" not in url:
            return
        self.stat_l.setText("STATUS: Fetching YouTube qualities...")
        self.fetcher = FormatFetcher(url)
        self.fetcher.finished.connect(lambda *args: self.fetcher.deleteLater())
        self.fetcher.formats_fetched.connect(self.on_formats_fetched)
        self.fetcher.error_occurred.connect(self.on_formats_error)
        self.fetcher.start()

    def on_formats_fetched(self, video_res, audio_kbps):
        self.stat_l.setText("STATUS: READY")
        self.fetched_video_res = video_res
        self.fetched_audio_kbps = audio_kbps
        self.update_opts(self.type_c.currentText())

    def on_formats_error(self, err):
        self.stat_l.setText("STATUS: READY")
        print(f"Error fetching formats: {err}")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self.check_clipboard()
        super().changeEvent(event)

    def check_clipboard(self):
        c = QApplication.clipboard(); t = c.text().strip()
        if t.startswith("http") and t != self.last_clipboard_url:
            self.last_clipboard_url = t; res = QMessageBox.question(self, "LINK", "ADD DETECTED LINK?")
            if res == QMessageBox.StandardButton.Yes:
                idx = 0 if "youtu" in t else (2 if "drive" in t else 1)
                self.tabs.setCurrentIndex(idx)
                inp = self.tabs.widget(idx).findChild(QLineEdit, "url")
                if inp:
                    inp.setText(t)
                    if idx == 0:
                        self.fetch_yt_formats()

    def update_lib(self):
        self.up_b.setEnabled(False); self.worker_up = UpdateWorker()
        self.worker_up.finished.connect(lambda *args: self.worker_up.deleteLater())
        self.worker_up.finished.connect(self.update_lib_done); self.worker_up.start()

    def update_lib_done(self, success, message):
        self.up_b.setEnabled(True)
        if success:
            QMessageBox.information(self, "INFO", message)
        else:
            QMessageBox.warning(self, "ERROR", f"Failed to update engine:\n{message}")

    def check_app_updates(self, manual=False):
        if hasattr(self, 'worker_app_up') and self.worker_app_up and self.worker_app_up.isRunning():
            return
        
        if manual:
            self.app_up_b.setEnabled(False)
            
        self.worker_app_up = AppUpdateCheckWorker()
        self.worker_app_up.finished.connect(lambda *args: self.worker_app_up.deleteLater())
        self.worker_app_up.finished.connect(lambda success, tag_name, download_url, body: self.check_app_updates_done(success, tag_name, download_url, body, manual))
        self.worker_app_up.start()

    def check_app_updates_done(self, success, tag_name, download_url, body, manual):
        if hasattr(self, 'app_up_b') and self.app_up_b:
            self.app_up_b.setEnabled(True)
            
        if success:
            current_version = "v1.0"
            latest_version = tag_name.strip()
            
            if latest_version and latest_version.lower() != current_version.lower():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(self.translate("update_available_title"))
                msg_box.setText(self.translate("update_available_msg").format(latest_version))
                if body:
                    msg_box.setInformativeText(body)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                
                yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
                yes_btn.setText(self.translate("btn_ok") if self.lang == "ar" else "Yes")
                no_btn = msg_box.button(QMessageBox.StandardButton.No)
                no_btn.setText(self.translate("btn_cancel_action") if self.lang == "ar" else "No")
                
                if msg_box.exec() == QMessageBox.StandardButton.Yes:
                    import webbrowser
                    webbrowser.open(download_url)
            else:
                if manual:
                    QMessageBox.information(self, "INFO", self.translate("up_to_date"))
        else:
            if manual:
                QMessageBox.warning(self, "ERROR", f"Failed to check for updates:\n{body}")

    def start(self):
        idx = self.tabs.currentIndex()
        raw_text = self.tabs.widget(idx).findChild(QLineEdit, "url").text().strip()
        if not raw_text: return
        
        self.tabs.widget(idx).findChild(QLineEdit, "url").clear()
        
        # Split by comma to support bulk downloads
        urls = [u.strip() for u in raw_text.split(",") if u.strip()]
        if not urls: return
        
        import time
        import uuid
        import datetime
        
        for url in urls:
            task_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            temp_name = os.path.basename(url.split("?")[0]) or "Pending..."
            name_item = QTableWidgetItem(temp_name)
            name_item.setData(Qt.ItemDataRole.UserRole, task_id)
            
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem("Starting..."))
            self.table.setItem(row, 2, QTableWidgetItem("0.00 MB / 0.00 MB"))
            self.table.setItem(row, 3, QTableWidgetItem("0%"))
            self.table.setItem(row, 4, QTableWidgetItem("0.00 MB/s"))
            self.table.setItem(row, 5, QTableWidgetItem(url))
            
            mode = ["YouTube", "Direct", "Drive"][idx]
            yt_opts = {'type': self.type_c.currentText(), 'ext': self.ext_c.currentText(), 'quality': self.qual_c.currentText()} if idx == 0 else {}
            speed_limit = self.config.get("speed_limit", 0)
            
            # Check queue limit (count both running workers and starting tasks)
            queue_enabled = self.config.get("queue_enabled", False)
            max_concurrent = self.config.get("max_concurrent", 1)
            active_count = 0
            for t in self.download_tasks.values():
                s = t.get("status", "").lower()
                if s in ["starting...", "downloading...", "merging segments...", "status: merging segments..."]:
                    active_count += 1
            
            status_str = "Starting..."
            should_start = True
            
            if queue_enabled and active_count >= max_concurrent:
                status_str = "Queue"
                should_start = False
                
            self.table.setItem(row, 1, QTableWidgetItem(self.translate(status_str)))
            
            added_at_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            max_conn = self.config.get("max_connections", 8)
            proxy = self.config.get("active_proxy") if self.config.get("proxy_enabled", False) else None
            worker = UniversalWorker(task_id, url, self.save_dir, mode, yt_opts, speed_limit, max_conn, proxy)
            worker.finished.connect(lambda *args, w=worker: w.deleteLater())
            worker.progress_changed.connect(lambda p, tid=task_id: self.update_progress(tid, p))
            worker.stats_updated.connect(lambda s, tid=task_id: self.update_stats(tid, s))
            worker.size_info_changed.connect(lambda d, t, r, tid=task_id: self.update_size_info(tid, d, t))
            worker.status_changed.connect(lambda s, tid=task_id: self.update_status(tid, s))
            worker.finished.connect(lambda ok, path, msg, duration, avg_speed, tid=task_id: self.done(tid, ok, path, msg, duration, avg_speed))
            
            self.download_tasks[task_id] = {
                "worker": worker,
                "url": url,
                "filename": temp_name,
                "size": "0.00 MB / 0.00 MB",
                "progress": 0,
                "speed": "0.00 MB/s",
                "status": status_str,
                "path": "",
                "yt_opts": yt_opts,
                "max_connections": max_conn,
                "added_at": added_at_str,
                "duration": 0,
                "average_speed": "0.00 MB/s"
            }
            
            save_history(self.download_tasks)
            if should_start:
                worker.start()
            self.table.selectRow(row)

    def find_row_by_task_id(self, task_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == task_id:
                return row
        return -1

    def update_progress(self, task_id, progress):
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            item = self.table.item(row, 3)
            if item:
                item.setText(f"{progress}%")
            else:
                self.table.setItem(row, 3, QTableWidgetItem(f"{progress}%"))
            task = self.download_tasks.get(task_id)
            if task:
                task["progress"] = progress
            if self.get_selected_task_id() == task_id:
                self.bar.setValue(progress)
                self.pc_l.setText(f"{progress}%")

    def update_stats(self, task_id, stats):
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            speed_val = "0.00 MB/s"
            m = re.search(r"SPEED:\s*([^|]+)", stats)
            if m: speed_val = m.group(1).strip()
            item = self.table.item(row, 4)
            if item:
                item.setText(speed_val)
            else:
                self.table.setItem(row, 4, QTableWidgetItem(speed_val))
            task = self.download_tasks.get(task_id)
            if task:
                task["speed"] = speed_val
            if self.get_selected_task_id() == task_id:
                self.sd.setText(stats)

    def update_size_info(self, task_id, down_size, total_size):
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            item = self.table.item(row, 2)
            if item:
                item.setText(f"{down_size} / {total_size}")
            else:
                self.table.setItem(row, 2, QTableWidgetItem(f"{down_size} / {total_size}"))
            task = self.download_tasks.get(task_id)
            if task:
                task["size"] = f"{down_size} / {total_size}"
            if self.get_selected_task_id() == task_id:
                self.sz_l.setText(f"{down_size} / {total_size}")

    def update_status(self, task_id, status):
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            disp_status = status.replace("Status: ", "")
            item = self.table.item(row, 1)
            translated_status = self.translate(disp_status)
            if item:
                item.setText(translated_status)
            else:
                self.table.setItem(row, 1, QTableWidgetItem(translated_status))
            task = self.download_tasks.get(task_id)
            if task:
                task["status"] = disp_status
            if self.get_selected_task_id() == task_id:
                self.stat_l.setText(f"{self.translate('status_label')}: {translated_status.upper()}")

    def on_row_selected(self):
        task_id = self.get_selected_task_id()
        if not task_id:
            self.stat_l.setText(self.translate("status_ready"))
            self.bar.setValue(0)
            self.sz_l.setText("0.00 MB / 0.00 MB")
            self.pc_l.setText("0%")
            self.sd.clear()
            self.p_b.setVisible(True)
            self.r_b.setVisible(True)
            self.c_b.setVisible(True)
            self.p_b.setEnabled(False)
            self.r_b.setEnabled(False)
            self.c_b.setEnabled(False)
            return
        self.update_dashboard_ui(task_id)

    def get_selected_task_id(self):
        selected_indexes = self.table.selectedIndexes()
        if selected_indexes:
            row = selected_indexes[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def update_dashboard_ui(self, task_id):
        row = self.find_row_by_task_id(task_id)
        if row == -1: return
        task = self.download_tasks.get(task_id)
        if not task: return
        
        status = task.get("status", "Paused")
        status_lower = status.lower()
        size_info = task.get("size", "0.00 MB / 0.00 MB")
        progress = f"{task.get('progress', 0)}%"
        speed = task.get("speed", "0.00 MB/s")
        
        translated_status = self.translate(status)
        self.stat_l.setText(f"{self.translate('status_label')}: {translated_status.upper()}")
        try: self.bar.setValue(int(progress.replace("%", "")))
        except: self.bar.setValue(0)
        self.pc_l.setText(progress)
        self.sz_l.setText(size_info)
        self.sd.setText(f"{self.translate('speed_label')}: {speed} | {self.translate('status_label')}: {translated_status}")
        
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if status_lower == "completed":
                self.p_b.setVisible(False)
                self.r_b.setVisible(False)
                self.c_b.setVisible(False)
            else:
                self.p_b.setVisible(True)
                self.r_b.setVisible(True)
                self.c_b.setVisible(True)
                
                is_running = False
                is_paused = False
                if worker:
                    try:
                        is_running = worker.isRunning()
                        is_paused = worker._is_paused
                    except RuntimeError:
                        task["worker"] = None
                        worker = None
                        
                if worker and is_running:
                    if is_paused:
                        self.p_b.setEnabled(False)
                        self.r_b.setEnabled(True)
                    else:
                        self.p_b.setEnabled(True)
                        self.r_b.setEnabled(False)
                    self.c_b.setEnabled(True)
                else:
                    if status_lower in ["paused", "cancelled", "error", "ready"]:
                        self.p_b.setEnabled(False)
                        self.r_b.setEnabled(True)
                        self.c_b.setEnabled(False)
                    else:
                        self.p_b.setEnabled(False)
                        self.r_b.setEnabled(False)
                        self.c_b.setEnabled(False)

    def pause(self):
        task_id = self.get_selected_task_id()
        if task_id:
            self.pause_task(task_id)

    def resume(self):
        task_id = self.get_selected_task_id()
        if task_id:
            self.resume_task(task_id)

    def pause_task(self, task_id):
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if worker and worker.isRunning():
                worker.pause()
                worker.finalize_active_time()
                task["duration"] = task.get("duration", 0) + int(worker.total_active_time)
                worker.total_active_time = 0
            task["status"] = "Paused"
            save_history(self.download_tasks)
            row = self.find_row_by_task_id(task_id)
            if row != -1: self.table.setItem(row, 1, QTableWidgetItem("Paused"))
            selected_id = self.get_selected_task_id()
            if selected_id == task_id:
                self.update_dashboard_ui(task_id)
            self.process_queue()

    def resume_task(self, task_id):
        task = self.download_tasks.get(task_id)
        if task:
            worker = task.get("worker")
            if worker and worker.isRunning():
                worker.resume()
                task["status"] = "Downloading..."
                save_history(self.download_tasks)
                row = self.find_row_by_task_id(task_id)
                if row != -1: self.table.setItem(row, 1, QTableWidgetItem("Downloading..."))
                selected_id = self.get_selected_task_id()
                if selected_id == task_id:
                    self.update_dashboard_ui(task_id)
            elif not worker or not worker.isRunning():
                # Check queue limit
                queue_enabled = self.config.get("queue_enabled", False)
                max_concurrent = self.config.get("max_concurrent", 1)
                active_count = self.get_active_downloads_count()
                
                if queue_enabled and active_count >= max_concurrent:
                    task["status"] = "Queue"
                    save_history(self.download_tasks)
                    row = self.find_row_by_task_id(task_id)
                    if row != -1: self.table.setItem(row, 1, QTableWidgetItem("Queue"))
                    selected_id = self.get_selected_task_id()
                    if selected_id == task_id:
                        self.update_dashboard_ui(task_id)
                    return
                
                # Start immediately
                url = task["url"]
                idx = 0 if "youtu" in url else (2 if "drive" in url else 1)
                mode = ["YouTube", "Direct", "Drive"][idx]
                yt_opts = task.get("yt_opts", {})
                if not yt_opts and idx == 0:
                    yt_opts = {'type': self.type_c.currentText(), 'ext': self.ext_c.currentText(), 'quality': self.qual_c.currentText()}
                speed_limit = self.config.get("speed_limit", 0)
                max_conn = task.get("max_connections", self.config.get("max_connections", 8))
                proxy = self.config.get("active_proxy") if self.config.get("proxy_enabled", False) else None
                
                new_worker = UniversalWorker(task_id, url, self.save_dir, mode, yt_opts, speed_limit, max_conn, proxy)
                new_worker.finished.connect(lambda *args, w=new_worker: w.deleteLater())
                new_worker.progress_changed.connect(lambda p, tid=task_id: self.update_progress(tid, p))
                new_worker.stats_updated.connect(lambda s, tid=task_id: self.update_stats(tid, s))
                new_worker.size_info_changed.connect(lambda d, t, r, tid=task_id: self.update_size_info(tid, d, t))
                new_worker.status_changed.connect(lambda s, tid=task_id: self.update_status(tid, s))
                new_worker.finished.connect(lambda ok, path, msg, duration, avg_speed, tid=task_id: self.done(tid, ok, path, msg, duration, avg_speed))
                
                task["worker"] = new_worker
                task["status"] = "Downloading..."
                save_history(self.download_tasks)
                
                new_worker.start()
                row = self.find_row_by_task_id(task_id)
                if row != -1: self.table.setItem(row, 1, QTableWidgetItem("Downloading..."))
                selected_id = self.get_selected_task_id()
                if selected_id == task_id:
                    self.update_dashboard_ui(task_id)

    def cancel(self):
        task_id = self.get_selected_task_id()
        if task_id:
            self.cancel_task_by_id(task_id)

    def done(self, task_id, ok, path, msg, duration=0, avg_speed="0.00 MB/s"):
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            task = self.download_tasks.get(task_id)
            if ok:
                filename = os.path.basename(path)
            else:
                filename = task.get("filename", "Unknown") if task else "Unknown"
                
            name_item = QTableWidgetItem(filename)
            name_item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.table.setItem(row, 0, name_item)
            
            if not ok and (path == "Cancelled" or (task and task.get("status") == "Cancelled")):
                status_text = "Cancelled"
            else:
                status_text = "Completed" if ok else "Error"
            self.table.setItem(row, 1, QTableWidgetItem(self.translate(status_text)))
            
            if ok and path and os.path.exists(path):
                try:
                    sz_mb = os.path.getsize(path) / 1e6
                    size_text = f"{sz_mb:.2f}MB / {sz_mb:.2f}MB"
                except:
                    size_text = self.table.item(row, 2).text() if self.table.item(row, 2) else "Unknown"
            else:
                size_text = self.table.item(row, 2).text() if self.table.item(row, 2) else "0.00 MB / 0.00 MB"
                
            self.table.setItem(row, 2, QTableWidgetItem(size_text))
            
            progress_val = "100%" if ok else (f"{task.get('progress', 0)}%" if task else "0%")
            self.table.setItem(row, 3, QTableWidgetItem(progress_val))
            
            self.table.setItem(row, 4, QTableWidgetItem(avg_speed if ok else "0.00 MB/s"))
            
            if task:
                task["filename"] = filename
                task["status"] = status_text
                if ok:
                    task["path"] = path
                task["size"] = size_text
                task["progress"] = 100 if ok else task.get("progress", 0)
                task["speed"] = avg_speed if ok else "0.00 MB/s"
                task["worker"] = None
                task["duration"] = task.get("duration", 0) + duration
                if ok:
                    task["average_speed"] = avg_speed
            
            save_history(self.download_tasks)
            
            selected_task_id = self.get_selected_task_id()
            if selected_task_id == task_id:
                self.update_dashboard_ui(task_id)
                if ok: 
                    self.stat_l.setText(f"{self.translate('status_label')}: {self.translate('Completed')}")
                    QMessageBox.information(self, self.translate("Completed"), f"{self.translate('col_filename')}: {filename}\nSaved to:\n{path}")
                else: 
                    if status_text == "Cancelled":
                        self.stat_l.setText(f"{self.translate('status_label')}: {self.translate('Cancelled')}")
                    else:
                        self.stat_l.setText(f"{self.translate('status_label')}: {self.translate('Error')}")
                        friendly_msg = path
                        if "getaddrinfo failed" in path or "NameResolutionError" in path or "Failed to resolve" in path:
                            if self.lang == "ar":
                                friendly_msg = "خطأ في الاتصال:\nفشل في الوصول إلى عنوان الموقع (فشل DNS).\n\nالأسباب المحتملة:\n1. جهازك غير متصل بالإنترنت.\n2. إعدادات VPN أو البروكسي تمنع الوصول.\n3. اسم الموقع غير صحيح أو محجوب من قبل مزود الخدمة."
                            else:
                                friendly_msg = "CONNECTION ERROR:\nFailed to resolve the website address (DNS lookup failed).\n\nPossible reasons:\n1. Your internet connection is offline.\n2. Your VPN or Proxy settings are blocking DNS resolution.\n3. The domain name is incorrect or blocked by your network/ISP."
                        elif "ConnectTimeoutError" in path or "timed out" in path.lower() or "Timeout" in path:
                            if self.lang == "ar":
                                friendly_msg = "انتهت مهلة الاتصال:\nتعذر الوصول إلى الخادم (انتهت المهلة).\n\nالأسباب المحتملة:\n1. قام الخادم بحظر عنوان IP الخاص بك مؤقتاً/دائماً.\n2. الخادم متوقف عن العمل حالياً.\n3. اتصال الـ VPN/البروكيس بطيء أو متوقف."
                            else:
                                friendly_msg = "CONNECTION TIMEOUT:\nCould not reach the server (Timed out).\n\nPossible reasons:\n1. The server has blocked your IP address temporarily/permanently.\n2. The server is currently offline.\n3. Your VPN/Proxy connection is offline or slow."
                        elif "403" in path:
                            if self.lang == "ar":
                                friendly_msg = "غير مسموح (403):\nتم رفض الوصول من قبل الخادم.\n\n- الموقع يحظر التحميل التلقائي أو تم تقييد عنوان IP الخاص بك."
                            else:
                                friendly_msg = "FORBIDDEN (403):\nAccess denied by the server.\n\n- The website is blocking automated downloads or your IP address has been restricted."
                        elif "429" in path:
                            if self.lang == "ar":
                                friendly_msg = "طلبات كثيرة جداً (429):\nقام الخادم بحظر اتصالك بسبب كثرة الاتصالات النشطة.\n\n- قلل 'أقصى عدد اتصالات' من الإعدادات وحاول مجدداً."
                            else:
                                friendly_msg = "TOO MANY REQUESTS (429):\nThe server blocked your connection due to too many active segments.\n\n- Lower the 'Max Connections' in Settings and try again."
                        elif "404" in path:
                            if self.lang == "ar":
                                friendly_msg = "الملف غير موجود (404):\nرابط التحميل معطل أو تم حذف الملف من الخادم."
                            else:
                                friendly_msg = "FILE NOT FOUND (404):\nThe download link is broken or the file has been deleted from the server."
                        QMessageBox.warning(self, self.translate("Error"), friendly_msg)
            else:
                if ok: 
                    QMessageBox.information(self, self.translate("Completed"), f"{self.translate('col_filename')}: {filename}\nSaved to:\n{path}")
                elif status_text != "Cancelled":
                    friendly_msg = path
                    if "getaddrinfo failed" in path or "NameResolutionError" in path or "Failed to resolve" in path:
                        if self.lang == "ar":
                            friendly_msg = "خطأ في الاتصال:\nفشل في الوصول إلى عنوان الموقع (فشل DNS).\n\nالأسباب المحتملة:\n1. جهازك غير متصل بالإنترنت.\n2. إعدادات VPN أو البروكسي تمنع الوصول.\n3. اسم الموقع غير صحيح أو محجوب من قبل مزود الخدمة."
                        else:
                            friendly_msg = "CONNECTION ERROR:\nFailed to resolve the website address (DNS lookup failed).\n\nPossible reasons:\n1. Your internet connection is offline.\n2. Your VPN or Proxy settings are blocking DNS resolution.\n3. The domain name is incorrect or blocked by your network/ISP."
                    elif "ConnectTimeoutError" in path or "timed out" in path.lower() or "Timeout" in path:
                        if self.lang == "ar":
                            friendly_msg = "انتهت مهلة الاتصال:\nتعذر الوصول إلى الخادم (انتهت المهلة).\n\nالأسباب المحتملة:\n1. قام الخادم بحظر عنوان IP الخاص بك مؤقتاً/دائماً.\n2. الخادم متوقف عن العمل حالياً.\n3. اتصال الـ VPN/البروكيس بطيء أو متوقف."
                        else:
                            friendly_msg = "CONNECTION TIMEOUT:\nCould not reach the server (Timed out).\n\nPossible reasons:\n1. The server has blocked your IP address temporarily/permanently.\n2. The server is currently offline.\n3. Your VPN/Proxy connection is offline or slow."
                    elif "403" in path:
                        if self.lang == "ar":
                            friendly_msg = "غير مسموح (403):\nتم رفض الوصول من قبل الخادم.\n\n- الموقع يحظر التحميل التلقائي أو تم تقييد عنوان IP الخاص بك."
                        else:
                            friendly_msg = "FORBIDDEN (403):\nAccess denied by the server.\n\n- The website is blocking automated downloads or your IP address has been restricted."
                    elif "429" in path:
                        if self.lang == "ar":
                            friendly_msg = "طلبات كثيرة جداً (429):\nقام الخادم بحظر اتصالك بسبب كثرة الاتصالات النشطة.\n\n- قلل 'أقصى عدد اتصالات' من الإعدادات وحاول مجدداً."
                        else:
                            friendly_msg = "TOO MANY REQUESTS (429):\nThe server blocked your connection due to too many active segments.\n\n- Lower the 'Max Connections' in Settings and try again."
                    elif "404" in path:
                        if self.lang == "ar":
                            friendly_msg = "الملف غير موجود (404):\nرابط التحميل معطل أو تم حذف الملف من الخادم."
                        else:
                            friendly_msg = "FILE NOT FOUND (404):\nThe download link is broken or the file has been deleted from the server."
                    QMessageBox.warning(self, self.translate("Error"), friendly_msg)
 
            self.process_queue()
 
            # Auto Shutdown trigger
            if self.shutdown_cb.isChecked():
                running = False
                for tid, t in self.download_tasks.items():
                    w = t.get("worker")
                    if w and w.isRunning():
                        running = True
                        break
                if not running:
                    os.system("shutdown /s /t 60")
                    shutdown_title = "AUTO SHUTDOWN" if self.lang == "en" else "إغلاق تلقائي للكمبيوتر"
                    shutdown_msg = (
                        "All downloads completed! The computer will shut down in 60 seconds.\nTo cancel, run 'shutdown /a' in command prompt or close this app."
                        if self.lang == "en" else
                        "اكتملت جميع التحميلات! سيتم إغلاق الكمبيوتر خلال 60 ثانية.\nلإلغاء الإغلاق، اكتب الأمر 'shutdown /a' في موجه الأوامر (CMD) أو أغلق البرنامج."
                    )
                    QMessageBox.information(self, shutdown_title, shutdown_msg)
 
    def closeEvent(self, event):
        pref = self.config.get("minimize_to_tray_on_close")
        if pref is True:
            event.ignore()
            self.hide()
            return
        elif pref is False:
            if self.exit_application():
                event.accept()
            else:
                event.ignore()
            return
            
        # If pref is None, show prompt
        from PyQt6.QtWidgets import QMessageBox, QCheckBox, QSystemTrayIcon
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(self.translate("close_dialog_title"))
        msg_box.setText(self.translate("close_dialog_text"))
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStyleSheet("background-color: #0f111a; color: #fff; QLabel { color: #fff; } QPushButton { background-color: #1b1e2e; border: 1px solid #3b4252; color: #fff; padding: 6px 15px; border-radius: 4px; } QPushButton:hover { background-color: #2e3440; }")
        
        tray_btn = msg_box.addButton(self.translate("close_dialog_tray"), QMessageBox.ButtonRole.YesRole)
        exit_btn = msg_box.addButton(self.translate("close_dialog_exit"), QMessageBox.ButtonRole.NoRole)
        
        remember_cb = QCheckBox(self.translate("close_dialog_remember"), msg_box)
        remember_cb.setStyleSheet("color: #fff; margin-top: 10px;")
        msg_box.setCheckBox(remember_cb)
        
        msg_box.exec()
        
        remember = remember_cb.isChecked()
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == tray_btn:
            if remember:
                self.config["minimize_to_tray_on_close"] = True
                save_config(self.config)
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon') and self.tray_icon and self.tray_icon.isSystemTrayAvailable():
                notify_title = self.translate("title")
                notify_body = "تم إخفاء البرنامج في شريط النظام." if self.lang == "ar" else "Application minimized to system tray."
                self.tray_icon.showMessage(notify_title, notify_body, QSystemTrayIcon.MessageIcon.Information, 2000)
        else:
            if self.exit_application():
                if remember:
                    self.config["minimize_to_tray_on_close"] = False
                    save_config(self.config)
                event.accept()
            else:
                event.ignore()

    def exit_application(self):
        # Check if there are active downloads running
        active_count = self.get_active_downloads_count()
        if active_count > 0:
            from PyQt6.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(self.translate("close_confirm_title"))
            msg_box.setText(self.translate("close_confirm_text"))
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStyleSheet("background-color: #0f111a; color: #fff; QLabel { color: #fff; } QPushButton { background-color: #1b1e2e; border: 1px solid #3b4252; color: #fff; padding: 6px 15px; border-radius: 4px; } QPushButton:hover { background-color: #2e3440; }")
            
            ok_btn = msg_box.addButton(self.translate("btn_ok"), QMessageBox.ButtonRole.YesRole)
            cancel_btn = msg_box.addButton(self.translate("btn_cancel_action"), QMessageBox.ButtonRole.NoRole)
            
            msg_box.exec()
            if msg_box.clickedButton() == cancel_btn:
                return False
                
        try: os.system("shutdown /a")
        except: pass
        active_tasks_exist = False
        for tid, task in self.download_tasks.items():
            w = task.get("worker")
            if w:
                try:
                    if w.isRunning():
                        active_tasks_exist = True
                        w.cancel()
                        w.wait(1500)
                        w.finalize_active_time()
                        task["duration"] = task.get("duration", 0) + int(w.total_active_time)
                except RuntimeError:
                    pass
            if task.get("status") not in ["Completed", "Error", "Cancelled"]:
                task["status"] = "Paused"
        if active_tasks_exist or True:
            save_history(self.download_tasks)
            
        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.hide()
            
        QApplication.quit()
        return True

    def update_shimmer(self):
        # 1. Determine active color based on active tab
        idx = self.tabs.currentIndex()
        if idx == 0:
            color = "#ff3b30"
            r, g, b = 255, 59, 48
        elif idx == 2:
            color = "#2ecc71"
            r, g, b = 46, 204, 113
        else:
            color = "#00d8ff"
            r, g, b = 0, 216, 255
            
        # 2. Check if there are any active downloading tasks
        has_active = False
        for task in self.download_tasks.values():
            w = task.get("worker")
            if w:
                try:
                    if w.isRunning() and not w._is_paused:
                        has_active = True
                        break
                except RuntimeError:
                    task["worker"] = None
                
        if not has_active:
            # Apply static progress bar style
            style = (
                f"QProgressBar {{ background: #161922; border: 1px solid #2e3440; border-radius: 7px; height: 14px; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 7px; }}"
            )
            self.bar.setStyleSheet(style)
            # Reset status text style to standard color
            self.stat_l.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
            return
            
        # 3. Animate shimmer on progress bar
        self.shimmer_step = (self.shimmer_step + 1) % 20
        offset = (self.shimmer_step / 20.0)
        
        style = (
            f"QProgressBar {{ background: #161922; border: 1px solid #2e3440; border-radius: 7px; height: 14px; }}"
            f"QProgressBar::chunk {{ "
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"    stop:0 {color}, stop:{max(0.0, offset - 0.15):.2f} {color}, "
            f"    stop:{offset:.2f} #ffffff, "
            f"    stop:{min(1.0, offset + 0.15):.2f} {color}, stop:1 {color}); "
            f"  border-radius: 7px; "
            f"}}"
        )
        self.bar.setStyleSheet(style)
        
        # 4. Pulse the status label text color
        import math
        alpha = int(180 + 75 * math.sin(self.shimmer_step * math.pi / 10))
        self.stat_l.setStyleSheet(f"color: rgba({r}, {g}, {b}, {alpha}); font-weight: bold; font-size: 15px;")

    def get_active_downloads_count(self):
        count = 0
        for task in self.download_tasks.values():
            status = task.get("status", "").lower()
            if status in ["starting...", "downloading...", "merging segments...", "status: merging segments..."]:
                w = task.get("worker")
                if w:
                    try:
                        if w.isRunning() and not w._is_paused:
                            count += 1
                    except RuntimeError:
                        task["worker"] = None
        return count

    def process_queue(self):
        queue_enabled = self.config.get("queue_enabled", False)
        if not queue_enabled:
            return
            
        max_concurrent = self.config.get("max_concurrent", 1)
        active_count = self.get_active_downloads_count()
        
        if active_count >= max_concurrent:
            return
            
        slots_available = max_concurrent - active_count
        
        for task_id, task in self.download_tasks.items():
            if slots_available <= 0:
                break
                
            status = task.get("status", "").lower()
            if status == "queue":
                self.start_queued_task(task_id)
                slots_available -= 1

    def start_queued_task(self, task_id):
        task = self.download_tasks.get(task_id)
        if not task:
            return
            
        worker = task.get("worker")
        if not worker:
            url = task["url"]
            idx = 0 if "youtu" in url else (2 if "drive" in url else 1)
            mode = ["YouTube", "Direct", "Drive"][idx]
            yt_opts = task.get("yt_opts", {})
            if not yt_opts and idx == 0:
                yt_opts = {'type': self.type_c.currentText(), 'ext': self.ext_c.currentText(), 'quality': self.qual_c.currentText()}
            speed_limit = self.config.get("speed_limit", 0)
            max_conn = task.get("max_connections", self.config.get("max_connections", 8))
            proxy = self.config.get("active_proxy") if self.config.get("proxy_enabled", False) else None
            
            worker = UniversalWorker(task_id, url, self.save_dir, mode, yt_opts, speed_limit, max_conn, proxy)
            worker.finished.connect(lambda *args, w=worker: w.deleteLater())
            worker.progress_changed.connect(lambda p, tid=task_id: self.update_progress(tid, p))
            worker.stats_updated.connect(lambda s, tid=task_id: self.update_stats(tid, s))
            worker.size_info_changed.connect(lambda d, t, r, tid=task_id: self.update_size_info(tid, d, t))
            worker.status_changed.connect(lambda s, tid=task_id: self.update_status(tid, s))
            worker.finished.connect(lambda ok, path, msg, duration, avg_speed, tid=task_id: self.done(tid, ok, path, msg, duration, avg_speed))
            task["worker"] = worker
            
        task["status"] = "Starting..."
        save_history(self.download_tasks)
        
        row = self.find_row_by_task_id(task_id)
        if row != -1:
            self.table.setItem(row, 1, QTableWidgetItem("Starting..."))
            
        worker.start()
        
        selected_id = self.get_selected_task_id()
        if selected_id == task_id:
            self.update_dashboard_ui(task_id)

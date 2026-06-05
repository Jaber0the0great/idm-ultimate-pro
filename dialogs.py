from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QFileDialog, QCheckBox, QSpinBox, QComboBox, QListWidget, QListWidgetItem, 
    QInputDialog, QMenu, QGridLayout, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_path="", current_limit=0, queue_enabled=False, max_concurrent=1, max_connections=8, proxy_enabled=False, proxy_list=None, active_proxy="", current_lang="en", translations=None, close_behavior=None):
        super().__init__(parent)
        self.current_lang = current_lang
        self.translations = translations or {}
        
        self.setWindowTitle("SETTINGS")
        self.setFixedSize(600, 780)
        self.setStyleSheet(
            "QDialog { background: #0d0e12; color: #fff; }"
            "QLabel { color: #fff; font-weight: bold; font-size: 13px; }"
            "QLineEdit, QComboBox, QListWidget { background: #161922; border: 1px solid #2e3440; color: #fff; padding: 10px; border-radius: 6px; }"
            "QLineEdit:focus, QComboBox:focus, QListWidget:focus { border: 1px solid #00d8ff; }"
            "QPushButton { background: #1a1d26; color: #fff; border: 1px solid #2e3440; font-weight: bold; padding: 10px; border-radius: 6px; }"
            "QPushButton:hover { background: #2b303c; border: 1px solid #434c5e; }"
            "QCheckBox { color: #fff; font-weight: bold; padding: 5px; }"
            "QSpinBox { background: #161922; color: #fff; border: 1px solid #2e3440; padding: 8px; border-radius: 6px; }"
        )
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(12)
        
        # Language Selector
        self.lbl_lang = QLabel()
        l.addWidget(self.lbl_lang)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("العربية", "ar")
        idx = 0 if self.current_lang == "en" else 1
        self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self.on_lang_changed)
        self.lang_combo.setAccessibleName("Language Selector")
        l.addWidget(self.lang_combo)
        
        # Download Directory
        self.lbl_dir = QLabel()
        l.addWidget(self.lbl_dir)
        
        self.path_edit = QLineEdit(current_path); self.path_edit.setReadOnly(True)
        self.path_edit.setAccessibleName("Download Directory Path")
        
        bl_dir = QHBoxLayout()
        self.bb = QPushButton()
        self.bb.clicked.connect(self.browse)
        self.bb.setAccessibleName("Browse Folder Button")
        
        bl_dir.addWidget(self.path_edit)
        bl_dir.addWidget(self.bb)
        l.addLayout(bl_dir)
        
        # Speed Limit
        self.lbl_lim = QLabel()
        l.addWidget(self.lbl_lim)
        
        self.limit_checkbox = QCheckBox()
        self.limit_checkbox.setChecked(current_limit > 0)
        self.limit_checkbox.stateChanged.connect(self.toggle_limit_input)
        self.limit_checkbox.setAccessibleName("Enable Speed Limit Checkbox")
        l.addWidget(self.limit_checkbox)
        
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 100000)
        self.limit_spin.setValue(current_limit if current_limit > 0 else 1024)
        self.limit_spin.setSuffix(" KB/s")
        self.limit_spin.setEnabled(current_limit > 0)
        self.limit_spin.setAccessibleName("Speed Limit Value Spinner")
        l.addWidget(self.limit_spin)
        
        # Connections count configuration
        self.lbl_conn = QLabel()
        l.addWidget(self.lbl_conn)
        
        self.conn_combo = QComboBox()
        self.conn_combo.addItems(["4", "8", "16"])
        self.conn_combo.setCurrentText(str(max_connections))
        self.conn_combo.setAccessibleName("Max Connections Dropdown")
        l.addWidget(self.conn_combo)
        
        # Queue Configuration
        self.lbl_q = QLabel()
        l.addWidget(self.lbl_q)
        
        self.queue_checkbox = QCheckBox()
        self.queue_checkbox.setChecked(queue_enabled)
        self.queue_checkbox.stateChanged.connect(self.toggle_queue_input)
        self.queue_checkbox.setAccessibleName("Limit Concurrent Downloads Checkbox")
        l.addWidget(self.queue_checkbox)
        
        self.queue_spin = QSpinBox()
        self.queue_spin.setRange(1, 10)
        self.queue_spin.setValue(max_concurrent)
        self.queue_spin.setSuffix(" Download(s)")
        self.queue_spin.setEnabled(queue_enabled)
        self.queue_spin.setAccessibleName("Max Concurrent Downloads Spinner")
        l.addWidget(self.queue_spin)
        
        # Close Behavior Configuration
        self.close_behavior = close_behavior
        self.lbl_close_behavior = QLabel()
        l.addWidget(self.lbl_close_behavior)
        
        self.close_behavior_combo = QComboBox()
        self.close_behavior_combo.setAccessibleName("Window Close Action Dropdown")
        l.addWidget(self.close_behavior_combo)
        
        # Proxy Configuration
        self.proxy_list_data = proxy_list or []
        self.active_proxy_data = active_proxy
        
        self.lbl_proxy = QLabel()
        l.addWidget(self.lbl_proxy)
        
        self.proxy_checkbox = QCheckBox()
        self.proxy_checkbox.setChecked(proxy_enabled)
        self.proxy_checkbox.stateChanged.connect(self.toggle_proxy_input)
        self.proxy_checkbox.setAccessibleName("Enable Proxy Checkbox")
        l.addWidget(self.proxy_checkbox)
        
        self.proxy_layout = QHBoxLayout()
        self.proxy_list_widget = QListWidget()
        self.proxy_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.proxy_list_widget.customContextMenuRequested.connect(self.show_proxy_context_menu)
        self.proxy_list_widget.setAccessibleName("Proxy List Manager")
        self.proxy_layout.addWidget(self.proxy_list_widget)
        
        proxy_btn_layout = QVBoxLayout()
        self.btn_add_proxy = QPushButton()
        self.btn_add_proxy.clicked.connect(self.add_proxy_dialog)
        self.btn_add_proxy.setAccessibleName("Add Proxy Button")
        
        self.btn_edit_proxy = QPushButton()
        self.btn_edit_proxy.clicked.connect(self.edit_selected_proxy)
        self.btn_edit_proxy.setAccessibleName("Edit Selected Proxy")
        
        self.btn_del_proxy = QPushButton()
        self.btn_del_proxy.clicked.connect(self.delete_selected_proxy)
        self.btn_del_proxy.setAccessibleName("Delete Selected Proxy")
        
        self.btn_activate_proxy = QPushButton()
        self.btn_activate_proxy.clicked.connect(self.activate_selected_proxy)
        self.btn_activate_proxy.setAccessibleName("Set Selected Proxy Active")
        
        proxy_btn_layout.addWidget(self.btn_add_proxy)
        proxy_btn_layout.addWidget(self.btn_edit_proxy)
        proxy_btn_layout.addWidget(self.btn_del_proxy)
        proxy_btn_layout.addWidget(self.btn_activate_proxy)
        proxy_btn_layout.addStretch()
        
        self.proxy_layout.addLayout(proxy_btn_layout)
        l.addLayout(self.proxy_layout)
        
        self.populate_proxy_list()
        self.toggle_proxy_input(proxy_enabled)
        
        bl = QHBoxLayout()
        self.sb = QPushButton()
        self.sb.clicked.connect(self.accept)
        self.sb.setDefault(True)
        self.sb.setAccessibleName("Save Settings Button")
        bl.addStretch(); bl.addWidget(self.sb)
        l.addLayout(bl)
        
        self.retranslate_ui()
        
    def translate(self, key):
        return self.translations.get(self.current_lang, {}).get(key, key)
        
    def on_lang_changed(self):
        code = self.lang_combo.currentData()
        if code:
            self.current_lang = code
            self.retranslate_ui()
            
    def retranslate_ui(self):
        self.setWindowTitle(self.translate("settings_title"))
        self.lbl_lang.setText(self.translate("settings_lang"))
        self.lbl_dir.setText(self.translate("settings_dir"))
        self.bb.setText(self.translate("settings_browse"))
        self.lbl_lim.setText(self.translate("settings_limit"))
        self.limit_checkbox.setText(self.translate("settings_enable_limit"))
        self.lbl_conn.setText(self.translate("settings_max_conn"))
        self.lbl_q.setText(self.translate("settings_queue"))
        self.queue_checkbox.setText(self.translate("settings_limit_concurrent"))
        
        # Translate Close Behavior Label
        self.lbl_close_behavior.setText(self.translate("settings_close_behavior_lbl"))
        
        # Translate Close Behavior Combobox options dynamically
        current_data = self.close_behavior_combo.currentData() if self.close_behavior_combo.count() > 0 else self.close_behavior
        self.close_behavior_combo.clear()
        self.close_behavior_combo.addItem(self.translate("settings_close_behavior_prompt"), None)
        self.close_behavior_combo.addItem(self.translate("settings_close_behavior_tray"), True)
        self.close_behavior_combo.addItem(self.translate("settings_close_behavior_exit"), False)
        
        if current_data is True:
            self.close_behavior_combo.setCurrentIndex(1)
        elif current_data is False:
            self.close_behavior_combo.setCurrentIndex(2)
        else:
            self.close_behavior_combo.setCurrentIndex(0)
            
        self.lbl_proxy.setText(self.translate("settings_proxy"))
        self.proxy_checkbox.setText(self.translate("settings_enable_proxy"))
        self.btn_add_proxy.setText(self.translate("settings_add_proxy"))
        self.btn_edit_proxy.setText(self.translate("settings_edit"))
        self.btn_del_proxy.setText(self.translate("settings_delete"))
        self.btn_activate_proxy.setText(self.translate("settings_set_active"))
        self.sb.setText(self.translate("settings_save"))
        
        # Set accessibility names dynamically
        self.lang_combo.setAccessibleName(self.translate("acc_lang_combo"))
        self.path_edit.setAccessibleName(self.translate("acc_path_edit"))
        self.bb.setAccessibleName(self.translate("acc_bb"))
        self.limit_checkbox.setAccessibleName(self.translate("acc_limit_checkbox"))
        self.limit_spin.setAccessibleName(self.translate("acc_limit_spin"))
        self.conn_combo.setAccessibleName(self.translate("acc_conn_combo"))
        self.queue_checkbox.setAccessibleName(self.translate("acc_queue_checkbox"))
        self.queue_spin.setAccessibleName(self.translate("acc_queue_spin"))
        self.close_behavior_combo.setAccessibleName(self.translate("acc_close_behavior_combo"))
        self.proxy_checkbox.setAccessibleName(self.translate("acc_proxy_checkbox"))
        self.proxy_list_widget.setAccessibleName(self.translate("acc_proxy_list_widget"))
        self.btn_add_proxy.setAccessibleName(self.translate("acc_btn_add_proxy"))
        self.btn_edit_proxy.setAccessibleName(self.translate("acc_btn_edit_proxy"))
        self.btn_del_proxy.setAccessibleName(self.translate("acc_btn_del_proxy"))
        self.btn_activate_proxy.setAccessibleName(self.translate("acc_btn_activate_proxy"))
        self.sb.setAccessibleName(self.translate("acc_sb"))
        
    def get_language(self):
        return self.lang_combo.currentData()
        
    def toggle_limit_input(self, state):
        self.limit_spin.setEnabled(state == 2 or state == True)
        
    def toggle_queue_input(self, state):
        self.queue_spin.setEnabled(state == 2 or state == True)
        
    def toggle_proxy_input(self, state):
        enabled = (state == 2 or state == True)
        self.proxy_list_widget.setEnabled(enabled)
        self.btn_add_proxy.setEnabled(enabled)
        self.btn_edit_proxy.setEnabled(enabled)
        self.btn_del_proxy.setEnabled(enabled)
        self.btn_activate_proxy.setEnabled(enabled)
        
    def populate_proxy_list(self):
        self.proxy_list_widget.clear()
        for proxy in self.proxy_list_data:
            display_text = proxy
            if proxy == self.active_proxy_data:
                display_text = f"🟢 {proxy} (Active)"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, proxy)
            self.proxy_list_widget.addItem(item)
            
    def add_proxy_dialog(self):
        text, ok = QInputDialog.getText(self, "Add Custom Proxy", "Enter proxy address (e.g. http://ip:port or socks5://ip:port):")
        if ok and text.strip():
            proxy = text.strip()
            if proxy not in self.proxy_list_data:
                self.proxy_list_data.append(proxy)
                if not self.active_proxy_data:
                    self.active_proxy_data = proxy
                self.populate_proxy_list()
                
    def edit_selected_proxy(self):
        current_item = self.proxy_list_widget.currentItem()
        if current_item:
            old_proxy = current_item.data(Qt.ItemDataRole.UserRole)
            text, ok = QInputDialog.getText(self, "Edit Proxy", "Modify proxy address:", text=old_proxy)
            if ok and text.strip():
                new_proxy = text.strip()
                if old_proxy in self.proxy_list_data:
                    idx = self.proxy_list_data.index(old_proxy)
                    self.proxy_list_data[idx] = new_proxy
                    if self.active_proxy_data == old_proxy:
                        self.active_proxy_data = new_proxy
                    self.populate_proxy_list()
                    
    def delete_selected_proxy(self):
        current_item = self.proxy_list_widget.currentItem()
        if current_item:
            proxy = current_item.data(Qt.ItemDataRole.UserRole)
            if proxy in self.proxy_list_data:
                self.proxy_list_data.remove(proxy)
                if self.active_proxy_data == proxy:
                    self.active_proxy_data = self.proxy_list_data[0] if self.proxy_list_data else ""
                self.populate_proxy_list()
                
    def activate_selected_proxy(self):
        current_item = self.proxy_list_widget.currentItem()
        if current_item:
            proxy = current_item.data(Qt.ItemDataRole.UserRole)
            self.active_proxy_data = proxy
            self.populate_proxy_list()
            
    def show_proxy_context_menu(self, pos):
        if not self.proxy_checkbox.isChecked():
            return
        item = self.proxy_list_widget.itemAt(pos)
        if not item:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #111; color: #fff; border: 1px solid #333;")
        
        proxy = item.data(Qt.ItemDataRole.UserRole)
        action_activate = menu.addAction("🟢 Set as Active")
        action_edit = menu.addAction("✏️ Edit")
        action_delete = menu.addAction("❌ Delete")
        
        if proxy == self.active_proxy_data:
            action_activate.setEnabled(False)
            
        action = menu.exec(self.proxy_list_widget.mapToGlobal(pos))
        if action == action_activate:
            self.active_proxy_data = proxy
            self.populate_proxy_list()
        elif action == action_edit:
            self.edit_selected_proxy()
        elif action == action_delete:
            self.delete_selected_proxy()
            
    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d: self.path_edit.setText(d)
        
    def get_path(self): return self.path_edit.text()
    
    def get_limit(self):
        if self.limit_checkbox.isChecked():
            return self.limit_spin.value()
        return 0

    def get_max_connections(self):
        try: return int(self.conn_combo.currentText())
        except: return 8
        
    def get_proxy_enabled(self):
        return self.proxy_checkbox.isChecked()
        
    def get_proxy_list(self):
        return self.proxy_list_data
        
    def get_active_proxy(self):
        return self.active_proxy_data
        
    def get_queue_enabled(self):
        return self.queue_checkbox.isChecked()
        
    def get_max_concurrent(self):
        return self.queue_spin.value()

    def get_close_behavior(self):
        return self.close_behavior_combo.currentData()

class QReadOnlyTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setAcceptRichText(True)
        self.document().setDefaultCursorMoveStyle(Qt.CursorMoveStyle.VisualMoveStyle)
        
    def setText(self, text):
        if text:
            text = "\n".join([line if line.strip() else "\u200b" for line in text.split("\n")])
        super().setText(text)
        
    def setHtml(self, html):
        if html:
            html = "\n".join([line if line.strip() else "\u200b" for line in html.split("\n")])
        super().setHtml(html)

import os
class TaskInfoDialog(QDialog):
    def __init__(self, parent=None, task=None, current_lang="en", translations=None):
        super().__init__(parent)
        self.task = task or {}
        self.current_lang = current_lang
        self.translations = translations or {}
        
        self.setWindowTitle(self.translate("dialog_info_title"))
        self.setFixedSize(580, 620)
        self.setStyleSheet(
            "QDialog { background: #0d0e12; color: #fff; }"
            "QLabel { color: #d8dee9; font-size: 13px; }"
            "QLabel#title { color: #00d8ff; font-weight: 900; font-size: 18px; }"
            "QLabel#subtitle { color: #4c566a; font-size: 10px; letter-spacing: 2px; font-weight: bold; }"
            "QLabel#section_lbl { color: #88c0d0; font-weight: bold; font-size: 14px; margin-top: 10px; }"
            "QLabel#field_lbl { color: #abb2bf; font-weight: bold; font-size: 12px; }"
            "QLabel#value_lbl { color: #ffffff; font-size: 13px; }"
            "QLineEdit, QTextEdit, QReadOnlyTextEdit { background: #161922; border: 1px solid #2e3440; color: #fff; padding: 8px; border-radius: 6px; font-size: 12px; }"
            "QLineEdit:focus, QTextEdit:focus, QReadOnlyTextEdit:focus { border: 1px solid #00d8ff; }"
            "QPushButton { background: #1a1d26; color: #fff; border: 1px solid #2e3440; font-weight: bold; padding: 10px 20px; border-radius: 6px; font-size: 13px; }"
            "QPushButton:hover { background: #2b303c; border: 1px solid #434c5e; }"
            "QPushButton#open_folder_btn { background: #161922; border: 1px solid #2e3440; padding: 8px; border-radius: 6px; font-size: 12px; min-width: 100px; }"
            "QPushButton#open_folder_btn:hover { background: #2b303c; border: 1px solid #434c5e; }"
            "QFrame#line { background: #2e3440; min-height: 1px; max-height: 1px; }"
        )
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(15)
        
        # Title
        title_layout = QVBoxLayout()
        title_lbl = QLabel(self.translate("dialog_info_header"))
        title_lbl.setObjectName("title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sub_lbl = QLabel(self.translate("dialog_info_subtitle"))
        sub_lbl.setObjectName("subtitle")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_layout.addWidget(title_lbl)
        title_layout.addWidget(sub_lbl)
        main_layout.addLayout(title_layout)
        
        # Divider Line
        line = QFrame()
        line.setObjectName("line")
        main_layout.addWidget(line)
        
        # Grid Layout for task properties
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        
        row_idx = 0
        
        # URL
        url_lbl = QLabel(self.translate("dialog_info_url"))
        url_lbl.setObjectName("field_lbl")
        self.url_edit = QLineEdit(self.task.get("url", ""))
        self.url_edit.setReadOnly(True)
        self.url_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.url_edit.setAccessibleName(self.translate("col_url"))
        grid.addWidget(url_lbl, row_idx, 0)
        grid.addWidget(self.url_edit, row_idx, 1)
        row_idx += 1
        
        # Save Path
        path_lbl = QLabel(self.translate("dialog_info_save_path"))
        path_lbl.setObjectName("field_lbl")
        
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(self.task.get("path", "Pending..."))
        self.path_edit.setReadOnly(True)
        self.path_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.path_edit.setAccessibleName(self.translate("dialog_info_save_path"))
        path_layout.addWidget(self.path_edit)
        
        self.open_folder_btn = QPushButton(self.translate("dialog_info_open_folder"))
        self.open_folder_btn.setObjectName("open_folder_btn")
        self.open_folder_btn.setAccessibleName(self.translate("dialog_info_open_folder"))
        self.open_folder_btn.clicked.connect(self.open_folder)
        path_layout.addWidget(self.open_folder_btn)
        
        grid.addWidget(path_lbl, row_idx, 0)
        grid.addLayout(path_layout, row_idx, 1)
        row_idx += 1
        
        # Details Label and single QTextEdit
        details_lbl = QLabel(self.translate("dialog_info_header"))
        details_lbl.setObjectName("field_lbl")
        
        total_seconds = self.task.get("duration", 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        duration_str = ""
        if hours > 0:
            duration_str += f"{hours}h "
        if minutes > 0 or hours > 0:
            duration_str += f"{minutes}m "
        duration_str += f"{seconds}s"

        status_val = self.task.get("status", "Unknown")
        status_color = "#e5c07b"
        status_lower = status_val.lower()
        if "completed" in status_lower:
            status_color = "#2ecc71"
        elif "error" in status_lower:
            status_color = "#ff3b30"
        elif "downloading" in status_lower or "starting" in status_lower:
            status_color = "#00d8ff"

        html_content = f"""
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_filename')}</span> <span style="color: #ffffff;">{self.task.get('filename', 'Unknown')}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_status')}</span> <span style="color: {status_color}; font-weight: bold;">{self.translate(status_val)}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_size')}</span> <span style="color: #ffffff;">{self.task.get('size', '0.00 MB / 0.00 MB')}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_progress')}</span> <span style="color: #00d8ff; font-weight: bold;">{self.task.get('progress', 0)}%</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_added')}</span> <span style="color: #ffffff;">{self.task.get('added_at', 'Unknown')}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_time')}</span> <span style="color: #ffffff;">{duration_str}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_conn')}</span> <span style="color: #ffffff;">{self.task.get('max_connections', 8)}x {self.translate('dialog_info_threads')}</span></p>
        <p style="margin: 6px 0; font-family: sans-serif; font-size: 13px;"><span style="color: #abb2bf; font-weight: bold;">{self.translate('dialog_info_avg_speed')}</span> <span style="color: #2ecc71; font-weight: bold;">{self.task.get('average_speed', '0.00 MB/s')}</span></p>
        """
        
        self.details_edit = QReadOnlyTextEdit()
        self.details_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.details_edit.setAccessibleName(self.translate("dialog_info_header"))
        self.details_edit.setHtml(html_content)
        self.details_edit.setMinimumHeight(300)
        
        grid.addWidget(details_lbl, row_idx, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.details_edit, row_idx, 1)
        row_idx += 1
        
        main_layout.addLayout(grid)
        
        # Bottom Divider Line
        line2 = QFrame()
        line2.setObjectName("line")
        main_layout.addWidget(line2)
        
        # Footer Action Button
        footer_layout = QHBoxLayout()
        close_btn = QPushButton(self.translate("dialog_info_close"))
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        close_btn.setAccessibleName(self.translate("dialog_info_close"))
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)
        
    def translate(self, key):
        return self.translations.get(self.current_lang, {}).get(key, key)

    def open_folder(self):
        path = self.task.get("path", "")
        if path:
            folder = os.path.dirname(path)
            if os.path.exists(folder):
                try:
                    os.startfile(folder)
                except Exception as e:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, self.translate("Error"), f"Could not open folder:\n{str(e)}")
                    return
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, self.translate("Error"), "Download folder does not exist yet!")

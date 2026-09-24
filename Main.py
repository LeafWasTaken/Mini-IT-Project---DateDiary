import hashlib
import os
import shutil
import sqlite3
import sys
from PyQt6.QtCore import QDate, QSettings, Qt
from PyQt6.QtGui import QCloseEvent, QColor, QFont, QPixmap, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def get_app_dir() -> str:
    """Returns absolute path to app root directory (handles PyInstaller standalone builds)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


MOOD_COLORS = {
    "Neutral 😐": "#6B7280",  # Gray
    "Happy 😊": "#10B981",    # Green
    "Excited 🤩": "#F59E0B",  # Orange
    "Relaxed 😌": "#8B5CF6",  # Purple
    "Sad 😢": "#3B82F6",      # Blue
    "Angry 😡": "#EF4444",    # Red
}

LIGHT_STYLESHEET = """
    QMainWindow, QWidget, QDialog { background-color: #F8FAFC; color: #0F172A; }
    QCalendarWidget QAbstractItemView:enabled { background-color: #FFFFFF; color: #0F172A; selection-background-color: #E2E8F0; }
    QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #F1F5F9; }
    QTextEdit, QLineEdit { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px; }
    QComboBox { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 4px; padding: 4px; }
"""

DARK_STYLESHEET = """
    QMainWindow, QWidget, QDialog { background-color: #1E1E2E; color: #CDD6F4; }
    QCalendarWidget QAbstractItemView:enabled { background-color: #181825; color: #CDD6F4; selection-background-color: #45475A; }
    QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #313244; }
    QTextEdit, QLineEdit { background-color: #181825; color: #CDD6F4; border: 1px solid #45475A; border-radius: 6px; padding: 4px; }
    QComboBox { background-color: #313244; color: #CDD6F4; border: 1px solid #45475A; border-radius: 4px; padding: 4px; }
"""


class EntryPinDialog(QDialog):
    """Dialog for setting or verifying a password/PIN for a specific entry."""

    def __init__(self, mode="verify", parent=None):
        super().__init__(parent)
        self.mode = mode  # 'verify' or 'set'
        self.pin = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Unlock Entry" if self.mode == "verify" else "Lock Entry")
        self.setFixedSize(320, 150)
        layout = QVBoxLayout(self)

        lbl_text = (
            "Enter password to view this entry:"
            if self.mode == "verify"
            else "Set a password/PIN for this entry:"
        )
        layout.addWidget(QLabel(lbl_text))

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("Password / PIN...")
        layout.addWidget(self.pin_input)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_pin)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def accept_pin(self):
        self.pin = self.pin_input.text().strip()
        if not self.pin:
            QMessageBox.warning(self, "Error", "Password cannot be empty!")
            return
        self.accept()


class MoodAnalyticsDialog(QDialog):
    """Dialog displaying mood frequency breakdown and percentages."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("📊 Mood Analytics")
        self.setMinimumSize(380, 360)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Mood Frequency Summary")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        stats = self.db.get_mood_stats()
        total_entries = sum(stats.values())

        total_lbl = QLabel(f"Total Entries Recorded: {total_entries}")
        total_lbl.setStyleSheet("color: #888888; margin-bottom: 10px;")
        layout.addWidget(total_lbl)

        if total_entries == 0:
            layout.addWidget(QLabel("No entries recorded yet."))
        else:
            for mood, color in MOOD_COLORS.items():
                count = stats.get(mood, 0)
                percentage = int((count / total_entries) * 100) if total_entries > 0 else 0

                row_layout = QVBoxLayout()
                info_layout = QHBoxLayout()

                mood_lbl = QLabel(f"{mood}: {count} ({percentage}%)")
                info_layout.addWidget(mood_lbl)
                info_layout.addStretch()

                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(percentage)
                bar.setTextVisible(False)
                bar.setFixedHeight(12)
                bar.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }} "
                    f"QProgressBar {{ border: 1px solid #CBD5E1; border-radius: 4px; background: #E2E8F0; }}"
                )

                row_layout.addLayout(info_layout)
                row_layout.addWidget(bar)
                layout.addLayout(row_layout)

        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class DatabaseManager:
    """Handles all SQLite database operations for DateDiary."""

    def __init__(self, db_name="datediary.db"):
        if not os.path.isabs(db_name):
            self.db_name = os.path.join(get_app_dir(), db_name)
        else:
            self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Creates table and handles schema migration for mood, image, and date locking."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    content TEXT,
                    mood TEXT,
                    image_path TEXT,
                    is_locked INTEGER DEFAULT 0,
                    pin_hash TEXT DEFAULT ''
                )
            """)

            cursor.execute("PRAGMA table_info(entries)")
            columns = [column[1] for column in cursor.fetchall()]

            if "mood" not in columns:
                cursor.execute("ALTER TABLE entries ADD COLUMN mood TEXT DEFAULT 'Neutral 😐'")

            if "image_path" not in columns:
                try:
                    cursor.execute("ALTER TABLE entries ADD COLUMN image_path TEXT")
                except Exception:
                    pass

            if "is_locked" not in columns:
                try:
                    cursor.execute("ALTER TABLE entries ADD COLUMN is_locked INTEGER DEFAULT 0")
                except Exception:
                    pass

            if "pin_hash" not in columns:
                try:
                    cursor.execute("ALTER TABLE entries ADD COLUMN pin_hash TEXT DEFAULT ''")
                except Exception:
                    pass

            conn.commit()

    def get_entry(self, date_str: str) -> tuple[str, str, str, int, str]:
        """Retrieves content, mood, image_path, is_locked, and pin_hash for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, mood, image_path, is_locked, pin_hash FROM entries WHERE date = ?",
                (date_str,),
            )
            result = cursor.fetchone()
            if result:
                content, mood, image_path, is_locked, pin_hash = result
                return (
                    content if content else "",
                    mood if mood else "Neutral 😐",
                    image_path if image_path else "",
                    is_locked if is_locked else 0,
                    pin_hash if pin_hash else "",
                )
            return "", "Neutral 😐", "", 0, ""

    def save_entry(
        self,
        date_str: str,
        content: str,
        mood: str,
        image_path: str = "",
        is_locked: int = 0,
        pin_hash: str = "",
    ):
        """Saves or updates entry content, mood tag, image path, and lock status for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO entries (date, content, mood, image_path, is_locked, pin_hash) 
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET 
                    content = excluded.content,
                    mood = excluded.mood,
                    image_path = excluded.image_path,
                    is_locked = excluded.is_locked,
                    pin_hash = excluded.pin_hash
            """,
                (date_str, content, mood, image_path, is_locked, pin_hash),
            )
            conn.commit()

    def delete_entry(self, date_str: str):
        """Deletes a diary entry for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM entries WHERE date = ?", (date_str,))
            conn.commit()

    def get_all_dates_with_entries(self) -> list[tuple[str, str]]:
        """Returns a list of tuples containing (date, mood) for active entries."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, mood FROM entries WHERE content != '' OR mood != '' OR (image_path IS NOT NULL AND image_path != '')"
            )
            return cursor.fetchall()

    def get_mood_stats(self) -> dict[str, int]:
        """Returns total counts grouped by mood."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT mood, COUNT(*) FROM entries WHERE content != '' OR (image_path IS NOT NULL AND image_path != '') GROUP BY mood"
            )
            return dict(cursor.fetchall())


class DiaryWindow(QMainWindow):
    """The main graphical user interface for DateDiary."""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_date = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        self.current_image_path = ""
        self.current_is_locked = 0
        self.current_pin_hash = ""
        self.unlocked_session_dates = set()  # Dates unlocked during current session

        self.is_modified = False
        self.settings = QSettings("DateDiary", "ThemeSettings")
        self.is_dark_mode = self.settings.value("dark_mode", False, type=bool)

        self.init_ui()
        self.load_current_entry()
        self.highlight_saved_dates()

    def set_bold(self):
        """Toggles bold on selected text."""
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if fmt.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal
        )
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_italic(self):
        """Toggles italic on selected text."""
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_underline(self):
        """Toggles underline on selected text."""
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_text_color(self):
        """Opens color picker dialog to set font color."""
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = self.text_editor.currentCharFormat()
            fmt.setForeground(color)
            self.text_editor.mergeCurrentCharFormat(fmt)

    def set_font_size(self, size_str: str):
        """Changes font size of selected text."""
        if size_str.isdigit():
            fmt = self.text_editor.currentCharFormat()
            fmt.setFontPointSize(float(size_str))
            self.text_editor.mergeCurrentCharFormat(fmt)

    def init_ui(self):
        """Sets up the windows, widgets, and layouts."""
        self.setWindowTitle("DateDiary")
        self.resize(960, 640)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left panel (Calendar & Navigation) ---
        left_panel = QVBoxLayout()

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.on_date_changed)

        self.today_button = QPushButton("📅 Go to Today")
        self.today_button.setMinimumHeight(35)
        self.today_button.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.today_button.clicked.connect(self.go_to_today)

        left_panel.addWidget(self.calendar)
        left_panel.addWidget(self.today_button)
        left_panel.addStretch()

        # --- Right panel (Notes, Photos & Mood) ---
        right_panel = QVBoxLayout()

        # Header row
        header_layout = QHBoxLayout()

        self.date_label = QLabel("Loading date...")
        self.date_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        self.analytics_btn = QPushButton("📊 Analytics")
        self.analytics_btn.setMinimumHeight(30)
        self.analytics_btn.clicked.connect(self.open_analytics)

        self.lock_entry_btn = QPushButton("🔒 Lock Entry")
        self.lock_entry_btn.setMinimumHeight(30)
        self.lock_entry_btn.clicked.connect(self.handle_lock_button)

        self.theme_button = QPushButton("🌙 Dark Mode")
        self.theme_button.setMinimumHeight(30)
        self.theme_button.clicked.connect(self.toggle_theme)

        self.mood_combo = QComboBox()
        self.mood_combo.addItems(list(MOOD_COLORS.keys()))
        self.mood_combo.setMinimumHeight(30)
        self.mood_combo.currentIndexChanged.connect(self.mark_as_modified)

        header_layout.addWidget(self.date_label)
        header_layout.addStretch()
        header_layout.addWidget(self.analytics_btn)
        header_layout.addWidget(self.lock_entry_btn)
        header_layout.addWidget(self.theme_button)
        header_layout.addWidget(QLabel("Mood:"))
        header_layout.addWidget(self.mood_combo)

        # --- Formatting Toolbar ---
        self.format_widget = QWidget()
        format_layout = QHBoxLayout(self.format_widget)
        format_layout.setContentsMargins(0, 0, 0, 0)

        bold_btn = QPushButton("B")
        bold_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        bold_btn.setFixedWidth(32)
        bold_btn.clicked.connect(self.set_bold)

        italic_btn = QPushButton("I")
        italic_btn.setFont(QFont("Arial", 10, QFont.Weight.Normal, True))
        italic_btn.setFixedWidth(32)
        italic_btn.clicked.connect(self.set_italic)

        underline_btn = QPushButton("U")
        underline_btn.setFixedWidth(32)
        underline_btn.clicked.connect(self.set_underline)

        color_btn = QPushButton("🎨 Color")
        color_btn.clicked.connect(self.set_text_color)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["10", "12", "14", "16", "18", "20", "24"])
        self.size_combo.setCurrentText("12")
        self.size_combo.currentTextChanged.connect(self.set_font_size)

        format_layout.addWidget(bold_btn)
        format_layout.addWidget(italic_btn)
        format_layout.addWidget(underline_btn)
        format_layout.addWidget(color_btn)
        format_layout.addWidget(QLabel("Size:"))
        format_layout.addWidget(self.size_combo)
        format_layout.addStretch()

        # Text Editor
        self.text_editor = QTextEdit()
        self.text_editor.setFont(QFont("Arial", 11))
        self.text_editor.setPlaceholderText("Write your thoughts for this day here...")
        self.text_editor.textChanged.connect(self.on_text_changed)

        # Word Counter Label
        self.word_count_label = QLabel("Words: 0 | Characters: 0")
        self.word_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.word_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Photo Attachment Section ---
        self.image_label = QLabel("No photo attached")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedHeight(120)
        self.image_label.setStyleSheet("border: 1px dashed #CBD5E1; border-radius: 6px; color: #888888;")

        self.photo_widget = QWidget()
        photo_btn_layout = QHBoxLayout(self.photo_widget)
        photo_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.attach_img_btn = QPushButton("📷 Attach Photo")
        self.attach_img_btn.setMinimumHeight(32)
        self.attach_img_btn.clicked.connect(self.attach_image)

        self.remove_img_btn = QPushButton("❌ Remove Photo")
        self.remove_img_btn.setMinimumHeight(32)
        self.remove_img_btn.clicked.connect(self.remove_image)

        photo_btn_layout.addWidget(self.attach_img_btn)
        photo_btn_layout.addWidget(self.remove_img_btn)

        # --- Main Action Buttons Layout ---
        buttons_layout = QHBoxLayout()

        self.delete_button = QPushButton("Delete Entry")
        self.delete_button.setMinimumHeight(40)
        self.delete_button.setStyleSheet("background-color: #CD5C5C; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.delete_current_entry)

        self.export_button = QPushButton("Export Entry")
        self.export_button.setMinimumHeight(40)
        self.export_button.setStyleSheet("background-color: #4B5563; color: white; font-weight: bold;")
        self.export_button.clicked.connect(self.export_current_entry)

        self.save_button = QPushButton("Save Entry")
        self.save_button.setMinimumHeight(40)
        self.save_button.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.save_current_entry)

        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.save_button)

        # Assemble Right Panel
        right_panel.addLayout(header_layout)
        right_panel.addWidget(self.format_widget)
        right_panel.addWidget(self.text_editor)
        right_panel.addWidget(self.word_count_label)
        right_panel.addWidget(self.image_label)
        right_panel.addWidget(self.photo_widget)
        right_panel.addLayout(buttons_layout)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)

        self.apply_theme()

    def handle_lock_button(self):
        """Handles lock/unlock actions for the current entry date."""
        if self.current_is_locked and self.current_date not in self.unlocked_session_dates:
            # Entry is currently locked and hidden -> Prompt to unlock
            dialog = EntryPinDialog(mode="verify", parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                input_hash = hashlib.sha256(dialog.pin.encode()).hexdigest()
                if input_hash == self.current_pin_hash:
                    self.unlocked_session_dates.add(self.current_date)
                    self.load_current_entry()
                else:
                    QMessageBox.warning(self, "Access Denied", "Incorrect password!")
        elif self.current_is_locked and self.current_date in self.unlocked_session_dates:
            # Entry is locked but currently visible -> Option to remove lock or relock
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Entry Lock Options")
            msg_box.setText("This entry is currently password protected.")
            relock_btn = msg_box.addButton("🔒 Re-lock Now", QMessageBox.ButtonRole.ActionRole)
            remove_btn = msg_box.addButton("🔓 Remove Password Protection", QMessageBox.ButtonRole.DestructiveRole)
            msg_box.addButton(QMessageBox.StandardButton.Cancel)

            msg_box.exec()

            if msg_box.clickedButton() == relock_btn:
                self.unlocked_session_dates.discard(self.current_date)
                self.load_current_entry()
            elif msg_box.clickedButton() == remove_btn:
                self.current_is_locked = 0
                self.current_pin_hash = ""
                self.unlocked_session_dates.discard(self.current_date)
                self.save_current_entry(show_prompt=False)
                self.load_current_entry()
                QMessageBox.information(self, "Protection Removed", "Password protection removed for this entry.")
        else:
            # Entry is NOT locked -> Set a password
            dialog = EntryPinDialog(mode="set", parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.current_pin_hash = hashlib.sha256(dialog.pin.encode()).hexdigest()
                self.current_is_locked = 1
                self.unlocked_session_dates.add(self.current_date)
                self.save_current_entry(show_prompt=False)
                self.load_current_entry()
                QMessageBox.information(self, "Entry Locked", "Password protection enabled for this date!")

    def open_analytics(self):
        """Opens mood statistics dialog."""
        dialog = MoodAnalyticsDialog(self.db, parent=self)
        dialog.exec()

    def attach_image(self):
        """Selects an image, cleans up previous photos for date, copies to project storage, and updates UI."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            rel_photos_dir = os.path.join("assets", "photos")
            abs_photos_dir = os.path.join(get_app_dir(), rel_photos_dir)
            os.makedirs(abs_photos_dir, exist_ok=True)

            for existing_file in os.listdir(abs_photos_dir):
                if existing_file.startswith(self.current_date + "."):
                    try:
                        os.remove(os.path.join(abs_photos_dir, existing_file))
                    except Exception:
                        pass

            ext = os.path.splitext(file_path)[1].lower()
            rel_dest_path = os.path.join(rel_photos_dir, f"{self.current_date}{ext}")
            abs_dest_path = os.path.join(get_app_dir(), rel_dest_path)

            try:
                shutil.copy2(file_path, abs_dest_path)
                self.current_image_path = rel_dest_path
                self.display_image(rel_dest_path)
                self.mark_as_modified()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to attach image:\n{str(e)}")

    def remove_image(self):
        """Clears attached image from current entry."""
        self.current_image_path = ""
        self.image_label.setText("No photo attached")
        self.image_label.setPixmap(QPixmap())
        self.mark_as_modified()

    def display_image(self, path: str):
        """Displays image inside QLabel scaled properly, resolving relative paths dynamically."""
        full_path = os.path.join(get_app_dir(), path) if path and not os.path.isabs(path) else path
        if full_path and os.path.exists(full_path):
            pixmap = QPixmap(full_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    300, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                return
        self.image_label.setText("No photo attached")
        self.image_label.setPixmap(QPixmap())

    def toggle_theme(self):
        """Toggles between Light and Dark mode."""
        self.is_dark_mode = not self.is_dark_mode
        self.settings.setValue("dark_mode", self.is_dark_mode)
        self.apply_theme()

    def apply_theme(self):
        """Applies the current theme stylesheet."""
        if self.is_dark_mode:
            self.setStyleSheet(DARK_STYLESHEET)
            self.theme_button.setText("☀️ Light Mode")
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)
            self.theme_button.setText("🌙 Dark Mode")

    def go_to_today(self):
        """Snaps calendar back to current date."""
        today = QDate.currentDate()
        if self.calendar.selectedDate() != today:
            self.calendar.setSelectedDate(today)

    def export_current_entry(self):
        """Exports active entry to a file."""
        if self.current_is_locked and self.current_date not in self.unlocked_session_dates:
            QMessageBox.warning(self, "Export Failed", "Unlock this entry first before exporting!")
            return

        content = self.text_editor.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Export Failed", "There is no text to export!")
            return
        mood = self.mood_combo.currentText()
        default_filename = f"DateDiary_{self.current_date}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diary Entry",
            default_filename,
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"Date: {self.current_date}\n")
                    f.write(f"Mood: {mood}\n")
                    f.write(f"Image: {self.current_image_path if self.current_image_path else 'None'}\n")
                    f.write("=" * 35 + "\n\n")
                    f.write(content)

                QMessageBox.information(
                    self, "Export Successful", f"Entry exported to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error saving file:\n{str(e)}")

    def update_word_count(self):
        """Calculates and updates word/character counts."""
        text = self.text_editor.toPlainText().strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.word_count_label.setText(f"Words: {words} | Characters: {chars}")

    def on_text_changed(self):
        """Triggers when text changes to mark unsaved status."""
        self.mark_as_modified()
        self.update_word_count()

    def highlight_saved_dates(self):
        """Highlights calendar entries with saved entries."""
        qdate_current = QDate.fromString(self.current_date, Qt.DateFormat.ISODate)
        self.calendar.setDateTextFormat(qdate_current, QTextCharFormat())

        saved_entries = self.db.get_all_dates_with_entries()

        for date_str, mood in saved_entries:
            qdate = QDate.fromString(date_str, Qt.DateFormat.ISODate)
            if qdate.isValid():
                fmt = QTextCharFormat()
                bg_color = MOOD_COLORS.get(mood, "#3B82F6")
                fmt.setBackground(QColor(bg_color))
                fmt.setForeground(QColor("#FFFFFF"))
                self.calendar.setDateTextFormat(qdate, fmt)

    def mark_as_modified(self):
        """Flags current text/mood/image as having unsaved changes."""
        self.is_modified = True

    def on_date_changed(self):
        """Triggered when user clicks a new date on the calendar."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_entry(show_prompt=False)
            elif reply == QMessageBox.StandardButton.Cancel:
                self.calendar.blockSignals(True)
                self.calendar.setSelectedDate(
                    QDate.fromString(self.current_date, Qt.DateFormat.ISODate)
                )
                self.calendar.blockSignals(False)
                return

        selected_qdate = self.calendar.selectedDate()
        self.current_date = selected_qdate.toString(Qt.DateFormat.ISODate)
        self.load_current_entry()

    def load_current_entry(self):
        """Loads text, mood, photo, and lock state from database into editor UI."""
        self.date_label.setText(f"Entry for: {self.current_date}")

        self.text_editor.blockSignals(True)
        self.mood_combo.blockSignals(True)

        content, mood, image_path, is_locked, pin_hash = self.db.get_entry(self.current_date)
        self.current_image_path = image_path
        self.current_is_locked = is_locked
        self.current_pin_hash = pin_hash

        # Lock Verification Logic
        if is_locked and self.current_date not in self.unlocked_session_dates:
            # Mask entry content when locked
            self.text_editor.setHtml(
                "<h3 style='color: #EF4444;'>🔒 THIS ENTRY IS PASSWORD PROTECTED</h3>"
                "<p>Click the <b>🔓 Unlock Entry</b> button in the top bar to enter your password and view this note.</p>"
            )
            self.text_editor.setReadOnly(True)
            self.format_widget.setEnabled(False)
            self.photo_widget.setEnabled(False)
            self.image_label.setText("🔒 Photo hidden (Entry locked)")
            self.image_label.setPixmap(QPixmap())
            self.lock_entry_btn.setText("🔓 Unlock Entry")
            self.lock_entry_btn.setStyleSheet("background-color: #EF4444; color: white; font-weight: bold;")
        else:
            # Unlocked state
            self.text_editor.setReadOnly(False)
            self.format_widget.setEnabled(True)
            self.photo_widget.setEnabled(True)
            self.text_editor.setHtml(content)
            self.display_image(image_path)

            if is_locked:
                self.lock_entry_btn.setText("🔑 Lock Options")
                self.lock_entry_btn.setStyleSheet("background-color: #F59E0B; color: white; font-weight: bold;")
            else:
                self.lock_entry_btn.setText("🔒 Lock Entry")
                self.lock_entry_btn.setStyleSheet("")

        idx = self.mood_combo.findText(mood)
        if idx != -1:
            self.mood_combo.setCurrentIndex(idx)
        else:
            self.mood_combo.setCurrentIndex(0)

        self.text_editor.blockSignals(False)
        self.mood_combo.blockSignals(False)

        self.is_modified = False
        self.update_word_count()

    def save_current_entry(self, show_prompt=True):
        """Saves current text, mood tag, image path, and lock status to SQLite."""
        if self.current_is_locked and self.current_date not in self.unlocked_session_dates:
            return  # Prevent overwriting locked data with placeholder text

        content = self.text_editor.toHtml() if self.text_editor.toPlainText().strip() else ""
        mood = self.mood_combo.currentText()

        if content or self.current_image_path or self.current_is_locked:
            self.db.save_entry(
                self.current_date,
                content,
                mood,
                self.current_image_path,
                self.current_is_locked,
                self.current_pin_hash,
            )
        else:
            self.db.delete_entry(self.current_date)

        self.is_modified = False
        self.highlight_saved_dates()

        if show_prompt:
            QMessageBox.information(
                self, "Success", f"Entry saved for {self.current_date}!"
            )

    def delete_current_entry(self):
        """Deletes entry and clears editor."""
        if self.current_is_locked and self.current_date not in self.unlocked_session_dates:
            QMessageBox.warning(self, "Action Denied", "Unlock this entry first before deleting!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this entry?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_entry(self.current_date)
            self.load_current_entry()
            self.highlight_saved_dates()

    def closeEvent(self, event: QCloseEvent):
        """Intercepts window close event for unsaved changes."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Exit DateDiary",
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_entry(show_prompt=False)
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DiaryWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
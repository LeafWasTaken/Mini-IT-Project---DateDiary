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
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
    QMainWindow, QWidget { background-color: #F8FAFC; color: #0F172A; }
    QCalendarWidget QAbstractItemView:enabled { background-color: #FFFFFF; color: #0F172A; selection-background-color: #E2E8F0; }
    QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #F1F5F9; }
    QTextEdit { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px; }
    QComboBox { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 4px; padding: 4px; }
"""

DARK_STYLESHEET = """
    QMainWindow, QWidget { background-color: #1E1E2E; color: #CDD6F4; }
    QCalendarWidget QAbstractItemView:enabled { background-color: #181825; color: #CDD6F4; selection-background-color: #45475A; }
    QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #313244; }
    QTextEdit { background-color: #181825; color: #CDD6F4; border: 1px solid #45475A; border-radius: 6px; }
    QComboBox { background-color: #313244; color: #CDD6F4; border: 1px solid #45475A; border-radius: 4px; padding: 4px; }
"""


class DatabaseManager:
    """Handles all SQLite database operations for DateDiary."""

    def __init__(self, db_name="datediary.db"):
        if not os.path.isabs(db_name):
            self.db_name = os.path.join(get_app_dir(), db_name)
        else:
            self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Creates table and handles schema migration for mood and image support."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    content TEXT,
                    mood TEXT,
                    image_path TEXT
                )
            """)

            cursor.execute("PRAGMA table_info(entries)")
            columns = [column[1] for column in cursor.fetchall()]

            if "mood" not in columns:
                cursor.execute(
                    "ALTER TABLE entries ADD COLUMN mood TEXT DEFAULT 'Neutral 😐'"
                )

            if "image_path" not in columns:
                try:
                    cursor.execute("ALTER TABLE entries ADD COLUMN image_path TEXT")
                    print("Database updated: Added 'image_path' column.")
                except Exception:
                    pass

            conn.commit()

    def get_entry(self, date_str: str) -> tuple[str, str, str]:
        """Retrieves content, mood, and image_path for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, mood, image_path FROM entries WHERE date = ?", (date_str,)
            )
            result = cursor.fetchone()
            if result:
                content, mood, image_path = result
                return (
                    content if content else "",
                    mood if mood else "Neutral 😐",
                    image_path if image_path else "",
                )
            return "", "Neutral 😐", ""

    def save_entry(self, date_str: str, content: str, mood: str, image_path: str = ""):
        """Saves or updates entry content, mood tag, and image path for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO entries (date, content, mood, image_path) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET 
                    content = excluded.content,
                    mood = excluded.mood,
                    image_path = excluded.image_path
            """,
                (date_str, content, mood, image_path),
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


class DiaryWindow(QMainWindow):
    """The main graphical user interface for DateDiary."""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_date = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        self.current_image_path = ""
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
        self.resize(920, 640)

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

        # Header row (Date label + Mood Dropdown + Theme Switcher)
        header_layout = QHBoxLayout()

        self.date_label = QLabel("Loading date...")
        self.date_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        self.theme_button = QPushButton("🌙 Dark Mode")
        self.theme_button.setMinimumHeight(30)
        self.theme_button.clicked.connect(self.toggle_theme)

        self.mood_combo = QComboBox()
        self.mood_combo.addItems(list(MOOD_COLORS.keys()))
        self.mood_combo.setMinimumHeight(30)
        self.mood_combo.currentIndexChanged.connect(self.mark_as_modified)

        header_layout.addWidget(self.date_label)
        header_layout.addStretch()
        header_layout.addWidget(self.theme_button)
        header_layout.addWidget(QLabel("Mood:"))
        header_layout.addWidget(self.mood_combo)

        # --- Formatting Toolbar ---
        format_layout = QHBoxLayout()

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

        photo_btn_layout = QHBoxLayout()
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
        right_panel.addLayout(format_layout)
        right_panel.addWidget(self.text_editor)
        right_panel.addWidget(self.word_count_label)
        right_panel.addWidget(self.image_label)
        right_panel.addLayout(photo_btn_layout)
        right_panel.addLayout(buttons_layout)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)

        self.apply_theme()

    def attach_image(self):
        """Selects an image, cleans up previous photos for date, copies to project storage, and updates UI."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            rel_photos_dir = os.path.join("assets", "photos")
            abs_photos_dir = os.path.join(get_app_dir(), rel_photos_dir)
            os.makedirs(abs_photos_dir, exist_ok=True)

            # Clean up old image files matching the current date to prevent orphan extensions (.png vs .jpg)
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
        """Loads text, mood, and photo from database into editor UI."""
        self.date_label.setText(f"Entry for: {self.current_date}")

        self.text_editor.blockSignals(True)
        self.mood_combo.blockSignals(True)

        content, mood, image_path = self.db.get_entry(self.current_date)
        self.text_editor.setHtml(content)
        self.current_image_path = image_path
        self.display_image(image_path)

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
        """Saves current text, mood tag, and image path to SQLite."""
        content = self.text_editor.toHtml() if self.text_editor.toPlainText().strip() else ""
        mood = self.mood_combo.currentText()

        if content or self.current_image_path:
            self.db.save_entry(self.current_date, content, mood, self.current_image_path)
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
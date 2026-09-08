import sqlite3
import sys
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QCloseEvent, QColor, QFont, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

MOOD_COLORS = {
    "Neutral 😐": "#6B7280",  # Gray
    "Happy 😊": "#10B981",    # Green
    "Excited 🤩": "#F59E0B",  # Orange
    "Relaxed 😌": "#8B5CF6",  # Purple
    "Sad 😢": "#3B82F6",      # Blue
    "Angry 😡": "#EF4444",    # Red
}


class DatabaseManager:
    """Handles all SQLite database operations for DateDiary."""

    def __init__(self, db_name="datediary.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Creates the table and handles schema migration for mood support."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    content TEXT,
                    mood TEXT
                )
            """)

            cursor.execute("PRAGMA table_info(entries)")
            columns = [column[1] for column in cursor.fetchall()]
            if "mood" not in columns:
                cursor.execute(
                    "ALTER TABLE entries ADD COLUMN mood TEXT DEFAULT 'Neutral 😐'"
                )

            conn.commit()

    def get_entry(self, date_str: str) -> tuple[str, str]:
        """Retrieves content and mood for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, mood FROM entries WHERE date = ?", (date_str,)
            )
            result = cursor.fetchone()
            if result:
                content, mood = result
                return content if content else "", mood if mood else "Neutral 😐"
            return "", "Neutral 😐"

    def save_entry(self, date_str: str, content: str, mood: str):
        """Saves or updates entry content and mood tag for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO entries (date, content, mood) 
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET 
                    content = excluded.content,
                    mood = excluded.mood
            """,
                (date_str, content, mood),
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
            cursor.execute("SELECT date, mood FROM entries WHERE content != '' OR mood != ''")
            return cursor.fetchall()


class DiaryWindow(QMainWindow):
    """The main graphical user interface for DateDiary."""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_date = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        self.is_modified = False

        self.init_ui()
        self.load_current_entry()
        self.highlight_saved_dates()

    def init_ui(self):
        """Sets up the windows, widgets, and layouts."""
        self.setWindowTitle("DateDiary")
        self.resize(850, 550)

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

        # --- Right panel (Notes & Mood) ---
        right_panel = QVBoxLayout()

        # Header row (Date label + Mood Dropdown)
        header_layout = QHBoxLayout()

        self.date_label = QLabel("Loading date...")
        self.date_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        self.mood_combo = QComboBox()
        self.mood_combo.addItems(list(MOOD_COLORS.keys()))
        self.mood_combo.setMinimumHeight(30)
        self.mood_combo.currentIndexChanged.connect(self.mark_as_modified)

        header_layout.addWidget(self.date_label)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Mood:"))
        header_layout.addWidget(self.mood_combo)

        self.text_editor = QTextEdit()
        self.text_editor.setFont(QFont("Arial", 11))
        self.text_editor.setPlaceholderText(
            "Write your thoughts for this day here..."
        )
        self.text_editor.textChanged.connect(self.on_text_changed)

        # --- Word Counter Label ---
        self.word_count_label = QLabel("Words: 0 | Characters: 0")
        self.word_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.word_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Buttons Layout ---
        buttons_layout = QHBoxLayout()

        self.delete_button = QPushButton("Delete Entry")
        self.delete_button.setMinimumHeight(40)
        self.delete_button.setStyleSheet(
            "background-color: #CD5C5C; color: white; font-weight: bold;"
        )
        self.delete_button.clicked.connect(self.delete_current_entry)

        self.save_button = QPushButton("Save Entry")
        self.save_button.setMinimumHeight(40)
        self.save_button.setStyleSheet(
            "background-color: #2E8B57; color: white; font-weight: bold;"
        )
        self.save_button.clicked.connect(self.save_current_entry)

        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.save_button)

        right_panel.addLayout(header_layout)
        right_panel.addWidget(self.text_editor)
        right_panel.addWidget(self.word_count_label)
        right_panel.addLayout(buttons_layout)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)

    def go_to_today(self):
        """Snaps the calendar back to the current date."""
        today = QDate.currentDate()
        if self.calendar.selectedDate() != today:
            self.calendar.setSelectedDate(today)

    def update_word_count(self):
        """Calculates and updates word/character counts."""
        text = self.text_editor.toPlainText().strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.word_count_label.setText(f"Words: {words} | Characters: {chars}")

    def on_text_changed(self):
        """Triggers when text changes to mark unsaved status and update word count."""
        self.mark_as_modified()
        self.update_word_count()

    def highlight_saved_dates(self):
        """Fetches saved dates and highlights calendar entries based on mood."""
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
        """Flags the current text/mood as having unsaved changes."""
        self.is_modified = True

    def on_date_changed(self):
        """Triggered when the user clicks a new date on the calendar."""
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
        """Loads text and mood from the database into the editor UI."""
        self.date_label.setText(f"Entry for: {self.current_date}")

        self.text_editor.blockSignals(True)
        self.mood_combo.blockSignals(True)

        content, mood = self.db.get_entry(self.current_date)
        self.text_editor.setPlainText(content)

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
        """Saves current text and mood tag to SQLite."""
        content = self.text_editor.toPlainText().strip()
        mood = self.mood_combo.currentText()

        if content:
            self.db.save_entry(self.current_date, content, mood)
        else:
            self.db.delete_entry(self.current_date)

        self.is_modified = False
        self.highlight_saved_dates()

        if show_prompt:
            QMessageBox.information(
                self, "Success", f"Entry saved for {self.current_date}!"
            )

    def delete_current_entry(self):
        """Deletes entry and clears the editor."""
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
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QVBoxLayout, QCalendarWidget, QTextEdit, QPushButton, 
    QLabel, QMessageBox
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont, QCloseEvent

class DatabaseManager:
    """Handles all SQLite database operations for DateDiary."""
    
    def __init__(self, db_name="datediary.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Creates the diary table if it doesn't exist."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    content TEXT
                )
            ''')
            conn.commit()

    def get_entry(self, date_str: str) -> str:
        """Retrieves a diary entry for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM entries WHERE date = ?', (date_str,))
            result = cursor.fetchone()
            return result[0] if result else ""

    def save_entry(self, date_str: str, content: str):
        """Saves or updates a diary entry for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO entries (date, content) 
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET content = excluded.content
            ''', (date_str, content))
            conn.commit()
            
    def delete_entry(self, date_str: str):
        """Deletes a diary entry for a specific date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM entries WHERE date = ?', (date_str,))
            conn.commit()


class DiaryWindow(QMainWindow):
    """The main graphical user interface for DateDiary."""
    
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_date = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        self.is_modified = False  # Tracks if the current text has unsaved changes
        
        self.init_ui()
        self.load_current_entry()

    def init_ui(self):
        """Sets up the windows, widgets, and layouts."""
        self.setWindowTitle("DateDiary")
        self.resize(850, 550)

        # Central Widget and Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left panel (Calendar) ---
        left_panel = QVBoxLayout()
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.on_date_changed)
        
        left_panel.addWidget(self.calendar)
        left_panel.addStretch()
        
        # --- Right panel (Notes) ---
        right_panel = QVBoxLayout()
        
        self.date_label = QLabel("Loading date...")
        self.date_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        
        self.text_editor = QTextEdit()
        self.text_editor.setFont(QFont("Arial", 11))
        self.text_editor.setPlaceholderText("Write your thoughts for this day here...")
        self.text_editor.textChanged.connect(self.mark_as_modified)
        
        # --- Buttons Layout ---
        buttons_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("Delete Entry")
        self.delete_button.setMinimumHeight(40)
        self.delete_button.setStyleSheet("background-color: #CD5C5C; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.delete_current_entry)
        
        self.save_button = QPushButton("Save Entry")
        self.save_button.setMinimumHeight(40)
        self.save_button.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.save_current_entry)
        
        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.save_button)
        
        right_panel.addWidget(self.date_label)
        right_panel.addWidget(self.text_editor)
        right_panel.addLayout(buttons_layout)
        
        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)
        
    def mark_as_modified(self):
        """Flags the current text as having unsaved changes."""
        self.is_modified = True

    def on_date_changed(self):
        """Triggered when the user clicks a new date on the calendar."""
        # Check for unsaved changes before moving to the new date
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                "You have unsaved changes. Do you want to save them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_entry(show_prompt=False)
            elif reply == QMessageBox.StandardButton.Cancel:
                # Revert calendar visual selection back to the previous date
                self.calendar.blockSignals(True)
                self.calendar.setSelectedDate(QDate.fromString(self.current_date, Qt.DateFormat.ISODate))
                self.calendar.blockSignals(False)
                return

        # Proceed to load new date
        selected_qdate = self.calendar.selectedDate()
        self.current_date = selected_qdate.toString(Qt.DateFormat.ISODate)
        self.load_current_entry()

    def load_current_entry(self):
        """Loads the text from the database into the editor."""
        self.date_label.setText(f"Entry for: {self.current_date}")
        
        # Block signals temporarily so setting text doesn't trigger mark_as_modified
        self.text_editor.blockSignals(True)
        content = self.db.get_entry(self.current_date)
        self.text_editor.setPlainText(content)
        self.text_editor.blockSignals(False)
        
        self.is_modified = False

    def save_current_entry(self, show_prompt=True):
        """Saves the current text in the editor to the database."""
        content = self.text_editor.toPlainText().strip()
        
        if content:
            self.db.save_entry(self.current_date, content)
        else:
            self.db.delete_entry(self.current_date) # Treat empty save as delete
            
        self.is_modified = False
        
        if show_prompt:
            QMessageBox.information(self, "Success", f"Entry saved for {self.current_date}!")

    def delete_current_entry(self):
        """Deletes the current entry and clears the editor."""
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this entry?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_entry(self.current_date)
            self.load_current_entry() # Reloads (which will clear the box)

    def closeEvent(self, event: QCloseEvent):
        """Intercepts the window closing to check for unsaved changes."""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Exit DateDiary", 
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_entry(show_prompt=False)
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept() # Close without saving
            else:
                event.ignore() # Cancel the close event
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
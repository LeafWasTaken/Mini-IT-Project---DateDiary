# Main.py - Card 2: Rich-Text Formatting Only
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, 
    QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtGui import QFont

class DateDiary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DateDiary")
        self.setGeometry(100, 100, 600, 500)
        
        self.init_db()
        self.init_ui()

    def init_db(self):
        """Initialize SQLite database."""
        self.conn = sqlite3.connect("datediary.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def init_ui(self):
        """Set up UI with rich-text formatting controls."""
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # Formatting Toolbar
        toolbar_layout = QHBoxLayout()

        self.bold_btn = QPushButton("B")
        self.bold_btn.setFixedWidth(30)
        self.bold_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.bold_btn.clicked.connect(self.toggle_bold)

        self.italic_btn = QPushButton("I")
        self.italic_btn.setFixedWidth(30)
        font_italic = QFont("Arial", 10)
        font_italic.setItalic(True)
        self.italic_btn.setFont(font_italic)
        self.italic_btn.clicked.connect(self.toggle_italic)

        self.underline_btn = QPushButton("U")
        self.underline_btn.setFixedWidth(30)
        font_underline = QFont("Arial", 10)
        font_underline.setUnderline(True)
        self.underline_btn.setFont(font_underline)
        self.underline_btn.clicked.connect(self.toggle_underline)

        toolbar_layout.addWidget(self.bold_btn)
        toolbar_layout.addWidget(self.italic_btn)
        toolbar_layout.addWidget(self.underline_btn)
        toolbar_layout.addStretch()

        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Write your diary entry here...")

        # Save Button
        self.save_btn = QPushButton("Save Entry")
        self.save_btn.clicked.connect(self.save_entry)

        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.text_edit)
        main_layout.addWidget(self.save_btn)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def toggle_bold(self):
        fmt = self.text_edit.currentCharFormat()
        weight = QFont.Weight.Normal if self.text_edit.fontWeight() == QFont.Weight.Bold else QFont.Weight.Bold
        fmt.setFontWeight(weight)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def toggle_italic(self):
        fmt = self.text_edit.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.text_edit.mergeCurrentCharFormat(fmt)

    def toggle_underline(self):
        fmt = self.text_edit.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.text_edit.mergeCurrentCharFormat(fmt)

    def save_entry(self):
        content = self.text_edit.toHtml() if self.text_edit.toPlainText().strip() else ""
        if content:
            self.cursor.execute("INSERT INTO entries (content) VALUES (?)", (content,))
            self.conn.commit()
            QMessageBox.information(self, "Success", "Rich-text entry saved successfully!")
            self.text_edit.clear()
        else:
            QMessageBox.warning(self, "Warning", "Cannot save an empty entry.")

    def closeEvent(self, event):
        self.conn.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DateDiary()
    window.show()
    sys.exit(app.exec())
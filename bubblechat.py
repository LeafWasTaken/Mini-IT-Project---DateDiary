import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QDialog,
    QTextEdit,
    QPushButton,
    QComboBox,
    QFrame
)
from PyQt6.QtCore import Qt


class IOSEditorSheet(QDialog):
    """iOS-style modal sheet for editing notes."""
    def __init__(self, entry_date, mood, full_content, parent=None):
        super().__init__(parent)
        self.entry_date = entry_date
        self.setWindowTitle("Edit Note")
        self.resize(560, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #1C1C1E;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
            }
            /* Explicitly set transparent backgrounds to prevent black bleed-through */
            QLabel {
                background-color: transparent;
                border: none;
            }
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
                border: none;
                border-radius: 16px;
                padding: 16px;
                font-size: 15px;
                line-height: 1.45;
                selection-background-color: #0A84FF;
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.09);
                color: #0A84FF;
                border: none;
                border-radius: 14px;
                padding: 6px 14px 6px 14px;
                font-size: 13px;
                font-weight: 600;
                min-width: 110px;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #2C2C2E;
                color: #FFFFFF;
                border: none;
                selection-background-color: rgba(10, 132, 255, 0.35);
                outline: none;
                padding: 6px;
                border-radius: 10px;
            }
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton#CancelBtn {
                color: #8E8E93;
            }
            QPushButton#CancelBtn:hover {
                color: #EBEBF5;
            }
            QPushButton#SaveBtn {
                color: #0A84FF;
            }
            QPushButton#SaveBtn:hover {
                color: #409CFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)

        # iOS Grab Handle
        grab_handle_container = QHBoxLayout()
        grab_handle = QFrame()
        grab_handle.setFixedSize(36, 5)
        grab_handle.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.25);
            border-radius: 2.5px;
        """)
        grab_handle_container.addStretch()
        grab_handle_container.addWidget(grab_handle)
        grab_handle_container.addStretch()
        layout.addLayout(grab_handle_container)

        # Top Navigation Bar (Cancel / Title / Done)
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(0, 4, 0, 4)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("CancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        nav_bar.addWidget(cancel_btn)

        nav_bar.addStretch()

        title_lbl = QLabel(f"{entry_date}")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 600; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_bar.addWidget(title_lbl)

        nav_bar.addStretch()

        save_btn = QPushButton("Done")
        save_btn.setObjectName("SaveBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        nav_bar.addWidget(save_btn)
        layout.addLayout(nav_bar)

        # Mood Selector Row
        mood_row = QHBoxLayout()
        mood_row.setContentsMargins(4, 2, 4, 2)

        mood_lbl = QLabel("Mood")
        mood_lbl.setStyleSheet("color: #8E8E93; font-size: 14px; font-weight: 500; background: transparent;")
        mood_row.addWidget(mood_lbl)

        mood_row.addStretch()

        self.mood_combo = QComboBox()
        self.mood_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        mood_options = [
            "Happy 😊",
            "Excited 🤩",
            "Calm 😌",
            "Neutral 😐",
            "Tired 😴",
            "Sad 😢",
            "Stressed 🤯"
        ]
        if mood and mood not in mood_options:
            mood_options.insert(0, mood)
        self.mood_combo.addItems(mood_options)
        self.mood_combo.setCurrentText(mood if mood else "Neutral 😐")
        mood_row.addWidget(self.mood_combo)
        layout.addLayout(mood_row)

        # Main Editable Content
        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(full_content)
        layout.addWidget(self.content_edit)

    def get_data(self):
        return self.content_edit.toPlainText().strip(), self.mood_combo.currentText()


class IOSBubbleWidget(QWidget):
    """Minimal iOS-style message bubble card."""
    def __init__(self, entry_date, preview_text, mood_text):
        super().__init__()

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(4, 2, 4, 2)

        # iOS Card Bubble
        self.bubble_frame = QFrame()
        self.bubble_frame.setStyleSheet("""
            QFrame {
                background-color: #1C1C1E;
                border: none;
                border-radius: 16px;
            }
            QFrame:hover {
                background-color: #242426;
            }
        """)

        bubble_layout = QVBoxLayout(self.bubble_frame)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(6)

        # Header Row: Subtitle Date + Minimal Pill Badge
        header_row = QHBoxLayout()
        lbl_date = QLabel(entry_date)
        lbl_date.setStyleSheet("color: #8E8E93; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        header_row.addWidget(lbl_date)

        header_row.addStretch()

        self.lbl_mood = QLabel(f" {mood_text} ")
        self.lbl_mood.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.08);
            color: #EBEBF5;
            font-size: 11px;
            font-weight: 500;
            padding: 3px 8px;
            border-radius: 8px;
            border: none;
        """)
        header_row.addWidget(self.lbl_mood)
        bubble_layout.addLayout(header_row)

        # Note Preview Text
        self.lbl_preview = QLabel(preview_text)
        self.lbl_preview.setStyleSheet("""
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 400;
            background: transparent;
            border: none;
            line-height: 1.35;
        """)
        self.lbl_preview.setWordWrap(True)
        bubble_layout.addWidget(self.lbl_preview)

        outer_layout.addWidget(self.bubble_frame)

    def update_content(self, preview_text, mood_text):
        self.lbl_preview.setText(preview_text)
        self.lbl_mood.setText(f" {mood_text} ")


class NoteListWidget(QWidget):
    def __init__(self, db_name="datediary.db"):
        super().__init__()
        self.db_name = db_name
        self.setWindowTitle("DateDiary")
        self.resize(850, 600)

        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(14)

        # Big "Diary" Title Header
        self.title_lbl = QLabel("Diary")
        self.title_lbl.setStyleSheet("""
            color: #FFFFFF;
            font-size: 32px;
            font-weight: 700;
            padding-left: 2px;
            padding-bottom: 2px;
            background: transparent;
        """)
        self.layout.addWidget(self.title_lbl)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for past notes...")
        self.search_input.textChanged.connect(self.filter_notes)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1C1C1E;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #8E8E93;
            }
            QLineEdit:focus {
                background-color: #242426;
            }
        """)
        self.layout.addWidget(self.search_input)

        # List Widget for Cards
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(10)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: 0;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.list_widget.itemClicked.connect(self.edit_note)
        self.layout.addWidget(self.list_widget)

        self.load_notes_from_db()

    def load_notes_from_db(self):
        self.list_widget.clear()

        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            query = """
                SELECT rowid, date, content, mood 
                FROM entries 
                WHERE content IS NOT NULL AND content != '' 
                ORDER BY date DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for rowid, entry_date, full_content, mood in rows:
                preview = full_content[:110] + "..." if len(full_content) > 110 else full_content
                mood_text = mood if mood else "Neutral 😐"

                item = QListWidgetItem(self.list_widget)
                item.setData(Qt.ItemDataRole.UserRole, {
                    "rowid": rowid,
                    "date": str(entry_date),
                    "mood": str(mood_text),
                    "content": full_content,
                    "search_key": f"{entry_date} {full_content} {mood_text}".lower()
                })

                bubble = IOSBubbleWidget(str(entry_date), str(preview), str(mood_text))
                item.setSizeHint(bubble.sizeHint())
                self.list_widget.setItemWidget(item, bubble)

            conn.close()

        except sqlite3.OperationalError:
            pass

    def edit_note(self, item):
        note_data = item.data(Qt.ItemDataRole.UserRole)
        if not note_data:
            return

        dialog = IOSEditorSheet(
            entry_date=note_data["date"],
            mood=note_data["mood"],
            full_content=note_data["content"],
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_content, new_mood = dialog.get_data()

            try:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE entries SET content = ?, mood = ? WHERE rowid = ?",
                    (new_content, new_mood, note_data["rowid"])
                )
                conn.commit()
                conn.close()
            except sqlite3.Error as e:
                print(f"Error updating note: {e}")
                return

            note_data["content"] = new_content
            note_data["mood"] = new_mood
            note_data["search_key"] = f"{note_data['date']} {new_content} {new_mood}".lower()
            item.setData(Qt.ItemDataRole.UserRole, note_data)

            bubble = self.list_widget.itemWidget(item)
            if isinstance(bubble, IOSBubbleWidget):
                new_preview = new_content[:110] + "..." if len(new_content) > 110 else new_content
                bubble.update_content(new_preview, new_mood)
                item.setSizeHint(bubble.sizeHint())

    def filter_notes(self):
        query = self.search_input.text().strip().lower()

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            searchable_text = data.get("search_key", "")
            item.setHidden(query not in searchable_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NoteListWidget()
    window.show()
    sys.exit(app.exec())
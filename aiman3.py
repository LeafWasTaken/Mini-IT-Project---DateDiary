import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView
)

class NoteListWidget(QWidget):
    def __init__(self, db_name="datediary.db"):
        super().__init__()
        self.db_name = db_name
        self.setWindowTitle("DateDiary Note list")
        self.resize(850, 550)

        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for past notes ...")
        self.search_input.textChanged.connect(self.filter_notes)
        self.layout.addWidget(self.search_input)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Date", "Notes Preview", "Mood"])

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 130)
        self.layout.addWidget(self.table)

        self.load_notes_from_db()

        self.table.setSortingEnabled(True)

    def load_notes_from_db(self):
        """Pulls saved notes from datediary.db and maps them into table rows."""
        self.table.setSortingEnabled(False)

        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            query = """
                SELECT date, SUBSTR(content, 1, 50), mood 
                FROM entries 
                WHERE content != '' 
                ORDER BY date DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, (entry_date, preview, mood) in enumerate(rows):
                preview_text = (preview + "...") if len(preview) >= 50 else preview
                mood_text = mood if mood else "Neutral 😐"

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(entry_date)))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(preview_text)))
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(mood_text)))

            conn.close()

        except sqlite3.OperationalError:
            pass

        self.table.setSortingEnabled(True)

    def filter_notes(self):
        """Filters table rows based on the search input in real-time."""
        query = self.search_input.text().strip().lower()

        for row in range(self.table.rowCount()):
            date_item = self.table.item(row, 0)
            preview_item = self.table.item(row, 1)
            mood_item = self.table.item(row, 2)

            date_text = date_item.text().lower() if date_item else ""
            preview_text = preview_item.text().lower() if preview_item else ""
            mood_text = mood_item.text().lower() if mood_item else ""

            is_match = (
                query in date_text or 
                query in preview_text or 
                query in mood_text
            )

            self.table.setRowHidden(row, not is_match)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NoteListWidget()
    window.show()
    sys.exit(app.exec())
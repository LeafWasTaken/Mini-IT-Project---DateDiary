import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableWidget,
    QHeaderView,
    QAbstractItemView
)

class NoteListWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DateDiary Note list")
        self.resize(850, 550)

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # 1. Search Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for past notes ...")
        self.layout.addWidget(self.search_input)

        # 2. Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Date", "Notes Preview", "Reminder"])


        # Tables rules Behaviour                                                                                                                                              
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Column Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 100)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 150)
        self.layout.addWidget(self.table)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NoteListWidget()
    window.show()
    sys.exit(app.exec())

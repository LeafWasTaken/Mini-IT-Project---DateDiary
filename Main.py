import hashlib
import hmac
import os
import secrets
import shutil
import sqlite3
import sys
from string import Template

from PyQt6.QtCore import QDate, QSettings, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
    QTextCharFormat,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCalendarWidget,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def get_app_dir() -> str:
    """Returns absolute path to app root directory (handles PyInstaller standalone builds)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------------------
# Moods (union of both versions: Calm is treated as Relaxed, they shared the same emoji)
# --------------------------------------------------------------------------------------
MOOD_COLORS = {
    "Neutral 😐": "#8E8E93",
    "Happy 😊": "#30D158",
    "Excited 🤩": "#FF9F0A",
    "Relaxed 😌": "#BF5AF2",
    "Tired 😴": "#64D2FF",
    "Sad 😢": "#0A84FF",
    "Stressed 🤯": "#FF375F",
    "Angry 😡": "#FF453A",
}
MOOD_ALIASES = {"Calm 😌": "Relaxed 😌"}
DEFAULT_MOOD = "Neutral 😐"
LOCKED_CELL_COLOR = "#636366"  # calendar colour for locked dates while the vault is closed


def normalize_mood(mood) -> str:
    """Maps empty/legacy mood names onto the current mood list."""
    if not mood:
        return DEFAULT_MOOD
    return MOOD_ALIASES.get(mood, mood)


def is_rich_text(text: str) -> bool:
    """True for HTML written by QTextEdit.toHtml(); False for plain text."""
    return text.lstrip()[:15].lower().startswith(("<!doctype", "<html"))


def to_plain_text(text: str) -> str:
    """Converts a stored note (HTML or plain text) to plain text for previews and search."""
    if not text:
        return ""
    if is_rich_text(text):
        doc = QTextDocument()
        doc.setHtml(text)
        return doc.toPlainText().strip()
    return text.strip()


# --------------------------------------------------------------------------------------
# Theme (iOS look: black / white pages, rounded cards, blue accent)
# --------------------------------------------------------------------------------------
PALETTES = {
    "dark": {
        "bg": "#000000", "card": "#1C1C1E", "card_hover": "#242426",
        "fill": "#2C2C2E", "fill_hover": "#3A3A3C", "border": "#48484A",
        "text": "#FFFFFF", "muted": "#8E8E93", "accent": "#0A84FF",
        "accent_hover": "#409CFF", "danger": "#FF453A", "scroll": "#48484A",
    },
    "light": {
        "bg": "#F2F2F7", "card": "#FFFFFF", "card_hover": "#F7F7FA",
        "fill": "#E5E5EA", "fill_hover": "#D8D8DE", "border": "#C7C7CC",
        "text": "#000000", "muted": "#6C6C70", "accent": "#007AFF",
        "accent_hover": "#3395FF", "danger": "#FF3B30", "scroll": "#C7C7CC",
    },
}

STYLE_TEMPLATE = """
QMainWindow, QWidget#Page { background-color: $bg; }
QWidget {
    color: $text;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
}
QDialog, QMessageBox { background-color: $card; }

QLabel { background: transparent; border: none; }
QLabel#PageTitle { font-size: 32px; font-weight: 700; padding-bottom: 2px; }
QLabel#DateTitle { font-size: 18px; font-weight: 600; }
QLabel#Muted { color: $muted; font-size: 12px; }
QLabel#ImageBox { border: 1px dashed $border; border-radius: 12px; color: $muted; }

QPushButton {
    background-color: $fill; color: $accent; border: none; border-radius: 12px;
    padding: 7px 14px; font-size: 13px; font-weight: 600;
}
QPushButton:hover { background-color: $fill_hover; }
QPushButton:disabled { color: $muted; }
QPushButton#PrimaryBtn { background-color: $accent; color: #FFFFFF; font-size: 14px; padding: 10px 18px; }
QPushButton#PrimaryBtn:hover { background-color: $accent_hover; }
QPushButton#PrimaryBtn:disabled { background-color: $fill; color: $muted; }
QPushButton#DangerBtn { color: $danger; font-size: 14px; padding: 10px 18px; }
QPushButton#SecondaryBtn { color: $text; font-size: 14px; padding: 10px 18px; }
QPushButton#DangerBtn:disabled, QPushButton#SecondaryBtn:disabled { color: $muted; }
QPushButton#FmtBtn { color: $text; padding: 5px 0px; min-width: 34px; max-width: 34px; }
QPushButton#BackBtn { background-color: transparent; color: $accent; font-size: 16px; padding: 4px 0px; }
QPushButton#BackBtn:hover { color: $accent_hover; }

QTextEdit {
    background-color: $card; color: $text; border: none; border-radius: 16px;
    padding: 16px; font-size: 15px; selection-background-color: $accent; selection-color: #FFFFFF;
}
QLineEdit {
    background-color: $card; color: $text; border: none; border-radius: 10px;
    padding: 10px 14px; font-size: 14px; selection-background-color: $accent; selection-color: #FFFFFF;
}
QLineEdit:focus { background-color: $card_hover; }
QDialog QLineEdit { background-color: $fill; }
QComboBox {
    background-color: $fill; color: $accent; border: none; border-radius: 12px;
    padding: 6px 14px; font-size: 13px; font-weight: 600; min-width: 90px;
}
QComboBox::drop-down { border: none; width: 0px; }
QComboBox QAbstractItemView {
    background-color: $fill; color: $text; border: none; outline: none; padding: 6px;
    selection-background-color: $accent; selection-color: #FFFFFF;
}

QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: $card; padding: 4px; }
QCalendarWidget QToolButton {
    color: $text; background-color: transparent; border: none; border-radius: 8px;
    padding: 4px 8px; font-size: 15px; font-weight: 600;
}
QCalendarWidget QToolButton:hover { background-color: $fill; }
QCalendarWidget QToolButton::menu-indicator { image: none; }
QCalendarWidget QMenu { background-color: $fill; color: $text; }
QCalendarWidget QSpinBox { background-color: $fill; color: $text; border: none; border-radius: 6px; }
QCalendarWidget QAbstractItemView:enabled {
    background-color: $card; color: $text; font-size: 14px; outline: 0;
    selection-background-color: $accent; selection-color: #FFFFFF;
}
QCalendarWidget QAbstractItemView:disabled { color: $muted; }

QListWidget { background-color: transparent; border: none; outline: 0; }
QListWidget::item { background-color: transparent; border: none; padding: 0px; }
QListWidget::item:selected, QListWidget::item:hover { background-color: transparent; }

QFrame#Bubble { background-color: $card; border: none; border-radius: 16px; }
QFrame#Bubble:hover { background-color: $card_hover; }
QLabel#BubbleDate { color: $muted; font-size: 12px; font-weight: 500; }
QLabel#BubbleMood {
    background-color: $fill; color: $text; font-size: 11px; font-weight: 500;
    padding: 3px 8px; border-radius: 8px;
}
QLabel#BubblePreview { font-size: 14px; font-weight: 400; }

QProgressBar { border: none; background-color: $fill; border-radius: 5px; }
QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def build_stylesheet(palette: dict) -> str:
    return Template(STYLE_TEMPLATE).substitute(palette)


def glyph_icon(glyph: str, color: str, size: int = 24) -> QIcon:
    """Draws a single coloured character into an icon (used for the calendar arrows)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(QColor(color))
    font = QFont()
    font.setPixelSize(size)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter.value, glyph)
    painter.end()
    return QIcon(pixmap)


# --------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------
class DatabaseManager:
    """Handles all SQLite database operations for DateDiary."""

    PBKDF2_ROUNDS = 200_000

    def __init__(self, db_name="datediary.db"):
        if not os.path.isabs(db_name):
            self.db_name = os.path.join(get_app_dir(), db_name)
        else:
            self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Creates tables and migrates older databases (mood, image, lock columns)."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    content TEXT,
                    mood TEXT,
                    image_path TEXT,
                    is_locked INTEGER DEFAULT 0
                )
            """)
            cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

            cursor.execute("PRAGMA table_info(entries)")
            columns = [column[1] for column in cursor.fetchall()]
            for name, ddl in (
                ("mood", "TEXT DEFAULT 'Neutral 😐'"),
                ("image_path", "TEXT"),
                ("is_locked", "INTEGER DEFAULT 0"),
            ):
                if name not in columns:
                    cursor.execute(f"ALTER TABLE entries ADD COLUMN {name} {ddl}")
            conn.commit()

    # ----- entries -----
    def get_entry(self, date_str: str) -> tuple[str, str, str, int]:
        """Returns (content, mood, image_path, is_locked) for a date."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content, mood, image_path, is_locked FROM entries WHERE date = ?",
                (date_str,),
            )
            result = cursor.fetchone()
        if result:
            content, mood, image_path, is_locked = result
            return (
                content if content else "",
                normalize_mood(mood),
                image_path if image_path else "",
                1 if is_locked else 0,
            )
        return "", DEFAULT_MOOD, "", 0

    def save_entry(self, date_str, content, mood, image_path="", is_locked=0):
        """Saves or updates the entry for a date."""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute(
                """
                INSERT INTO entries (date, content, mood, image_path, is_locked)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    content = excluded.content,
                    mood = excluded.mood,
                    image_path = excluded.image_path,
                    is_locked = excluded.is_locked
                """,
                (date_str, content, mood, image_path, is_locked),
            )
            conn.commit()

    def delete_entry(self, date_str: str):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("DELETE FROM entries WHERE date = ?", (date_str,))
            conn.commit()

    def get_all_dates_with_entries(self) -> list[tuple[str, str, int]]:
        """Returns (date, mood, is_locked) for every saved entry."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, mood, COALESCE(is_locked, 0) FROM entries "
                "WHERE content != '' OR (image_path IS NOT NULL AND image_path != '') "
                "OR COALESCE(is_locked, 0) = 1"
            )
            return cursor.fetchall()

    def get_mood_stats(self, include_locked: bool = False) -> dict[str, int]:
        """Returns entry counts grouped by mood (locked notes only if include_locked)."""
        query = (
            "SELECT mood, COUNT(*) FROM entries "
            "WHERE (content != '' OR (image_path IS NOT NULL AND image_path != ''))"
        )
        if not include_locked:
            query += " AND COALESCE(is_locked, 0) = 0"
        query += " GROUP BY mood"
        with sqlite3.connect(self.db_name) as conn:
            rows = conn.execute(query).fetchall()
        stats: dict[str, int] = {}
        for mood, count in rows:
            key = normalize_mood(mood)
            stats[key] = stats.get(key, 0) + count
        return stats

    def count_locked_entries(self) -> int:
        with sqlite3.connect(self.db_name) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM entries WHERE COALESCE(is_locked, 0) = 1"
            ).fetchone()[0]

    def get_searchable_entries(self, include_locked: bool = False) -> list[tuple[str, str, str, int]]:
        """Returns (date, content, mood, is_locked) for notes that have text, newest first."""
        query = (
            "SELECT date, content, mood, COALESCE(is_locked, 0) FROM entries "
            "WHERE content IS NOT NULL AND content != ''"
        )
        if not include_locked:
            query += " AND COALESCE(is_locked, 0) = 0"
        query += " ORDER BY date DESC"
        with sqlite3.connect(self.db_name) as conn:
            return conn.execute(query).fetchall()

    # ----- vault password (one shared password for all locked notes) -----
    def _get_setting(self, key: str) -> str:
        with sqlite3.connect(self.db_name) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row and row[0] else ""

    def _set_setting(self, key: str, value: str):
        with sqlite3.connect(self.db_name) as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def _hash_password(self, password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.PBKDF2_ROUNDS
        ).hex()

    def has_vault_password(self) -> bool:
        return bool(self._get_setting("vault_hash"))

    def set_vault_password(self, password: str):
        salt = secrets.token_bytes(16)
        self._set_setting("vault_salt", salt.hex())
        self._set_setting("vault_hash", self._hash_password(password, salt))

    def verify_vault_password(self, password: str) -> bool:
        salt_hex = self._get_setting("vault_salt")
        stored = self._get_setting("vault_hash")
        if not salt_hex or not stored:
            return False
        candidate = self._hash_password(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(candidate, stored)


# --------------------------------------------------------------------------------------
# Dialogs
# --------------------------------------------------------------------------------------
class VaultPasswordDialog(QDialog):
    """Asks for the shared vault password ('unlock') or creates it ('create')."""

    def __init__(self, mode="unlock", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.password = ""
        self.confirm_input = None
        self.init_ui()

    def init_ui(self):
        creating = self.mode == "create"
        self.setWindowTitle("Create Vault Password" if creating else "Unlock Vault")
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading = QLabel(
            "Create a password for your locked notes:"
            if creating
            else "Enter your vault password to view locked notes:"
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("Password...")
        layout.addWidget(self.pin_input)

        if creating:
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setPlaceholderText("Confirm password...")
            layout.addWidget(self.confirm_input)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept_password)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def accept_password(self):
        password = self.pin_input.text().strip()
        if not password:
            QMessageBox.warning(self, "Error", "Password cannot be empty!")
            return
        if self.confirm_input is not None and self.confirm_input.text().strip() != password:
            QMessageBox.warning(self, "Error", "Passwords do not match!")
            return
        self.password = password
        self.accept()


class MoodAnalyticsDialog(QDialog):
    """Dialog displaying mood frequency breakdown and percentages."""

    def __init__(self, db_manager, include_locked=False, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.include_locked = include_locked
        self.setWindowTitle("📊 Mood Analytics")
        self.setMinimumSize(420, 540)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        title = QLabel("Mood Frequency")
        title.setObjectName("DateTitle")
        layout.addWidget(title)

        stats = self.db.get_mood_stats(self.include_locked)
        total_entries = sum(stats.values())

        total_lbl = QLabel(f"Total Entries Recorded: {total_entries}")
        total_lbl.setObjectName("Muted")
        layout.addWidget(total_lbl)

        if not self.include_locked and self.db.count_locked_entries() > 0:
            hint = QLabel("🔒 Locked notes are not counted until the vault is unlocked.")
            hint.setObjectName("Muted")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        if total_entries == 0:
            layout.addWidget(QLabel("No entries recorded yet."))
        else:
            for mood, color in MOOD_COLORS.items():
                count = stats.get(mood, 0)
                percentage = int((count / total_entries) * 100)

                row_layout = QVBoxLayout()
                row_layout.setSpacing(4)
                row_layout.addWidget(QLabel(f"{mood}: {count} ({percentage}%)"))

                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(percentage)
                bar.setTextVisible(False)
                bar.setFixedHeight(10)
                bar.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {color}; border-radius: 5px; }}"
                )
                row_layout.addWidget(bar)
                layout.addLayout(row_layout)

        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class CatalogDialog(QDialog):
    """Dialog displaying a list of all recorded diary entries."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.parent_window = parent
        self.setWindowTitle("📖 Entries Catalog")
        self.setMinimumSize(400, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("All Diary Entries")
        title.setObjectName("DateTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self.open_entry)
        self.list_widget.setStyleSheet(
            "QListWidget { font-size: 14px; padding: 5px; outline: none; }"
            "QListWidget::item { padding: 10px; border-bottom: 1px solid rgba(128, 128, 128, 0.2); }"
            "QListWidget::item:selected { background-color: #0A84FF; color: white; border-radius: 8px; }"
        )
        layout.addWidget(self.list_widget)

        self.populate_list()

        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Open Selected")
        open_btn.setObjectName("PrimaryBtn")
        open_btn.clicked.connect(self.open_selected_entry)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def populate_list(self):
        """Fetches entries from the database and populates the list."""
        raw_entries = self.db.get_all_dates_with_entries()
        entries = sorted(raw_entries, key=lambda x: x[0], reverse=True)

        for item_data in entries:
            date_str = item_data[0]
            mood = normalize_mood(item_data[1])
            is_locked = item_data[2] if len(item_data) > 2 else 0

            lock_prefix = "🔒 " if is_locked else "📅 "
            item_text = f"{lock_prefix}{date_str}   |   Mood: {mood}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, date_str)
            self.list_widget.addItem(item)

        if not entries:
            empty_item = QListWidgetItem("No entries found yet.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(empty_item)

    def open_selected_entry(self):
        """Triggered by the Open button."""
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            self.open_entry(selected_items[0])

    def open_entry(self, item):
        """Tells the main calendar to jump to the selected item's date."""
        date_str = item.data(Qt.ItemDataRole.UserRole)
        if date_str and self.parent_window:
            qdate = QDate.fromString(date_str, Qt.DateFormat.ISODate)
            if qdate.isValid():
                self.parent_window.calendar.setSelectedDate(qdate)
            self.accept()


# --------------------------------------------------------------------------------------
# Calendar with a small lock marker on locked dates
# --------------------------------------------------------------------------------------
class LockCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.locked_dates: set[str] = set()

    def set_locked_dates(self, dates: set):
        self.locked_dates = set(dates)
        self.updateCells()

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        if date.toString(Qt.DateFormat.ISODate) in self.locked_dates:
            painter.save()
            font = painter.font()
            font.setPointSize(7)
            painter.setFont(font)
            flags = (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop).value
            painter.drawText(rect.adjusted(0, 1, -3, 0), flags, "🔒")
            painter.restore()

    def apply_palette(self, palette: dict):
        """Colours the things a stylesheet can't reach (weekday text, header, arrow icons)."""
        day_fmt = QTextCharFormat()
        day_fmt.setForeground(QColor(palette["text"]))
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.setWeekdayTextFormat(day, day_fmt)

        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor(palette["muted"]))
        self.setHeaderTextFormat(header_fmt)

        for name, glyph in (("qt_calendar_prevmonth", "‹"), ("qt_calendar_nextmonth", "›")):
            button = self.findChild(QToolButton, name)
            if button is not None:
                button.setIcon(glyph_icon(glyph, palette["accent"]))


# --------------------------------------------------------------------------------------
# Search page ( iOS-style list, now theme-aware and database-shared)
# --------------------------------------------------------------------------------------
class IOSBubbleWidget(QWidget):
    """Minimal iOS-style note card."""

    def __init__(self, entry_date, preview_text, mood_text):
        super().__init__()

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(4, 2, 4, 2)

        self.bubble_frame = QFrame()
        self.bubble_frame.setObjectName("Bubble")

        bubble_layout = QVBoxLayout(self.bubble_frame)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        bubble_layout.setSpacing(6)

        header_row = QHBoxLayout()
        lbl_date = QLabel(entry_date)
        lbl_date.setObjectName("BubbleDate")
        header_row.addWidget(lbl_date)
        header_row.addStretch()

        self.lbl_mood = QLabel(f" {mood_text} ")
        self.lbl_mood.setObjectName("BubbleMood")
        header_row.addWidget(self.lbl_mood)
        bubble_layout.addLayout(header_row)

        self.lbl_preview = QLabel(preview_text)
        self.lbl_preview.setObjectName("BubblePreview")
        self.lbl_preview.setWordWrap(True)
        bubble_layout.addWidget(self.lbl_preview)

        outer_layout.addWidget(self.bubble_frame)

    def height_for_width(self, width: int) -> int:
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            return layout.totalHeightForWidth(width)
        return self.sizeHint().height()


class NoteListWidget(QWidget):
    """The 'All Notes' page: searchable list of saved notes."""

    back_requested = pyqtSignal()
    note_selected = pyqtSignal(str)  # emits the note's date (YYYY-MM-DD)

    def __init__(self, db, is_vault_open, parent=None):
        super().__init__(parent)
        self.db = db
        self.is_vault_open = is_vault_open  # callable -> bool
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        back_btn = QPushButton("‹ Diary")
        back_btn.setObjectName("BackBtn")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(lambda: self.back_requested.emit())
        top_row.addWidget(back_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        title_lbl = QLabel("All Notes")
        title_lbl.setObjectName("PageTitle")
        layout.addWidget(title_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for past notes...")
        self.search_input.textChanged.connect(self.filter_notes)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(10)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

        self.empty_lbl = QLabel("")
        self.empty_lbl.setObjectName("Muted")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.hide()
        layout.addWidget(self.empty_lbl)

    def refresh(self):
        """Reloads notes from the database (called every time the page is opened)."""
        self.list_widget.clear()

        for entry_date, content, mood, is_locked in self.db.get_searchable_entries(
            include_locked=bool(self.is_vault_open())
        ):
            plain = to_plain_text(content)
            if not plain:
                continue
            flat = " ".join(plain.split())
            preview = flat[:110] + "..." if len(flat) > 110 else flat
            mood_text = normalize_mood(mood)
            date_label = f"🔒 {entry_date}" if is_locked else str(entry_date)

            item = QListWidgetItem(self.list_widget)
            item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "date": str(entry_date),
                    "search_key": f"{entry_date} {plain} {mood_text}".lower(),
                },
            )
            bubble = IOSBubbleWidget(date_label, preview, mood_text)
            item.setSizeHint(bubble.sizeHint())
            self.list_widget.setItemWidget(item, bubble)

        self.filter_notes()
        self._fit_items()
        self.search_input.setFocus()

    def filter_notes(self):
        query = self.search_input.text().strip().lower()
        visible = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            hide = query not in data.get("search_key", "")
            item.setHidden(hide)
            if not hide:
                visible += 1

        if visible == 0:
            self.empty_lbl.setText(
                "No notes found." if self.list_widget.count() else "No notes yet."
            )
        self.empty_lbl.setVisible(visible == 0)

    def on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.note_selected.emit(data["date"])

    def _fit_items(self):
        """Gives every card the height it needs at the current width."""
        width = self.list_widget.viewport().width()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            bubble = self.list_widget.itemWidget(item)
            if isinstance(bubble, IOSBubbleWidget):
                item.setSizeHint(QSize(width, bubble.height_for_width(width)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_items()

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_items()
        QTimer.singleShot(0, self._fit_items)


# --------------------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------------------
class DiaryWindow(QMainWindow):
    """The main graphical user interface for DateDiary."""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.current_date = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        self.current_image_path = ""
        self.current_is_locked = 0
        self.vault_unlocked = False

        self.is_modified = False
        self.settings = QSettings("DateDiary", "ThemeSettings")
        self.is_dark_mode = self.settings.value("dark_mode", True, type=bool)

        self.init_ui()
        self.load_current_entry()
        self.highlight_saved_dates()

    # ----- text formatting -----
    def set_bold(self):
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Bold if fmt.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal
        )
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_italic(self):
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_underline(self):
        fmt = self.text_editor.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.text_editor.mergeCurrentCharFormat(fmt)

    def set_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = self.text_editor.currentCharFormat()
            fmt.setForeground(color)
            self.text_editor.mergeCurrentCharFormat(fmt)

    def set_font_size(self, size_str: str):
        if size_str.isdigit():
            fmt = self.text_editor.currentCharFormat()
            fmt.setFontPointSize(float(size_str))
            self.text_editor.mergeCurrentCharFormat(fmt)

    # ----- UI -----
    def init_ui(self):
        self.setWindowTitle("DateDiary")
        self.resize(1100, 740)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.diary_page = QWidget()
        self.diary_page.setObjectName("Page")
        self.diary_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QHBoxLayout(self.diary_page)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # --- Left panel (Calendar & Navigation) ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        self.calendar = LockCalendar()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.selectionChanged.connect(self.on_date_changed)

        self.today_button = QPushButton("📅 Go to Today")
        self.today_button.setMinimumHeight(38)
        self.today_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.today_button.clicked.connect(self.go_to_today)

        self.catalog_button = QPushButton("📖 View All Entries")
        self.catalog_button.setMinimumHeight(38)
        self.catalog_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.catalog_button.clicked.connect(self.open_catalog)

        left_panel.addWidget(self.calendar)
        left_panel.addWidget(self.today_button)
        left_panel.addWidget(self.catalog_button)
        left_panel.addStretch()

        # --- Right panel ---
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        # Top bar: big title + page buttons
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        page_title = QLabel("Diary")
        page_title.setObjectName("PageTitle")

        self.search_btn = QPushButton("All notes")
        self.search_btn.clicked.connect(self.open_search)
        self.analytics_btn = QPushButton("📊 Analytics")
        self.analytics_btn.clicked.connect(self.open_analytics)
        self.vault_btn = QPushButton("🔐 Unlock Vault")
        self.vault_btn.clicked.connect(self.toggle_vault)
        self.theme_button = QPushButton("🌙 Dark Mode")
        self.theme_button.clicked.connect(self.toggle_theme)

        top_bar.addWidget(page_title)
        top_bar.addStretch()
        for button in (self.search_btn, self.analytics_btn, self.vault_btn, self.theme_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            top_bar.addWidget(button)

        # Note header: date + lock + mood
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        self.date_label = QLabel("Loading date...")
        self.date_label.setObjectName("DateTitle")

        self.lock_entry_btn = QPushButton("🔒 Lock Note")
        self.lock_entry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_entry_btn.clicked.connect(self.toggle_note_lock)

        mood_lbl = QLabel("Mood")
        mood_lbl.setObjectName("Muted")
        self.mood_combo = QComboBox()
        self.mood_combo.addItems(list(MOOD_COLORS.keys()))
        self.mood_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mood_combo.currentIndexChanged.connect(self.mark_as_modified)

        header_layout.addWidget(self.date_label)
        header_layout.addStretch()
        header_layout.addWidget(self.lock_entry_btn)
        header_layout.addWidget(mood_lbl)
        header_layout.addWidget(self.mood_combo)

        # --- Formatting toolbar ---
        self.format_widget = QWidget()
        format_layout = QHBoxLayout(self.format_widget)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(8)

        bold_btn = QPushButton("B")
        bold_btn.setObjectName("FmtBtn")
        bold_btn.setStyleSheet("font-weight: 800;")
        bold_btn.clicked.connect(self.set_bold)

        italic_btn = QPushButton("I")
        italic_btn.setObjectName("FmtBtn")
        italic_btn.setStyleSheet("font-style: italic;")
        italic_btn.clicked.connect(self.set_italic)

        underline_btn = QPushButton("U")
        underline_btn.setObjectName("FmtBtn")
        underline_btn.setStyleSheet("text-decoration: underline;")
        underline_btn.clicked.connect(self.set_underline)

        color_btn = QPushButton("🎨 Color")
        color_btn.clicked.connect(self.set_text_color)

        size_lbl = QLabel("Size")
        size_lbl.setObjectName("Muted")
        self.size_combo = QComboBox()
        self.size_combo.addItems(["10", "12", "14", "16", "18", "20", "24"])
        self.size_combo.setCurrentText("12")
        self.size_combo.currentTextChanged.connect(self.set_font_size)

        format_layout.addWidget(bold_btn)
        format_layout.addWidget(italic_btn)
        format_layout.addWidget(underline_btn)
        format_layout.addWidget(color_btn)
        format_layout.addWidget(size_lbl)
        format_layout.addWidget(self.size_combo)
        format_layout.addStretch()

        # Text editor
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Write your thoughts for this day here...")
        self.text_editor.textChanged.connect(self.on_text_changed)

        self.word_count_label = QLabel("Words: 0 | Characters: 0")
        self.word_count_label.setObjectName("Muted")
        self.word_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Photo attachment ---
        self.image_label = QLabel("No photo attached")
        self.image_label.setObjectName("ImageBox")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedHeight(120)

        self.photo_widget = QWidget()
        photo_btn_layout = QHBoxLayout(self.photo_widget)
        photo_btn_layout.setContentsMargins(0, 0, 0, 0)
        photo_btn_layout.setSpacing(8)

        self.attach_img_btn = QPushButton("📷 Attach Photo")
        self.attach_img_btn.clicked.connect(self.attach_image)
        self.remove_img_btn = QPushButton("❌ Remove Photo")
        self.remove_img_btn.clicked.connect(self.remove_image)
        photo_btn_layout.addWidget(self.attach_img_btn)
        photo_btn_layout.addWidget(self.remove_img_btn)

        # --- Main action buttons ---
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        self.delete_button = QPushButton("Delete Entry")
        self.delete_button.setObjectName("DangerBtn")
        self.delete_button.clicked.connect(self.delete_current_entry)

        self.export_button = QPushButton("Export Entry")
        self.export_button.setObjectName("SecondaryBtn")
        self.export_button.clicked.connect(self.export_current_entry)

        self.save_button = QPushButton("Save Entry")
        self.save_button.setObjectName("PrimaryBtn")
        self.save_button.clicked.connect(lambda: self.save_current_entry())

        buttons_layout.addWidget(self.delete_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.save_button)

        right_panel.addLayout(top_bar)
        right_panel.addLayout(header_layout)
        right_panel.addWidget(self.format_widget)
        right_panel.addWidget(self.text_editor)
        right_panel.addWidget(self.word_count_label)
        right_panel.addWidget(self.image_label)
        right_panel.addWidget(self.photo_widget)
        right_panel.addLayout(buttons_layout)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)

        # --- Search page ---
        self.search_page = NoteListWidget(self.db, lambda: self.vault_unlocked)
        self.search_page.back_requested.connect(self.show_diary)
        self.search_page.note_selected.connect(self.open_note_from_search)

        self.stack.addWidget(self.diary_page)
        self.stack.addWidget(self.search_page)

        self.apply_theme()

    # ----- page navigation -----
    def open_search(self):
        """Switches to the search page (saving or discarding pending edits first)."""
        if not self.confirm_unsaved():
            return
        self.load_current_entry()
        self.search_page.refresh()
        self.stack.setCurrentWidget(self.search_page)

    def show_diary(self):
        self.stack.setCurrentWidget(self.diary_page)

    def open_note_from_search(self, date_str: str):
        """A card was clicked on the search page: jump to that day in the diary."""
        self.stack.setCurrentWidget(self.diary_page)
        qdate = QDate.fromString(date_str, Qt.DateFormat.ISODate)
        if qdate.isValid() and self.calendar.selectedDate() != qdate:
            self.calendar.setSelectedDate(qdate)

    # ----- lock system (one vault password for all locked notes) -----
    def entry_hidden(self) -> bool:
        """True when the current note is locked and the vault is closed."""
        return bool(self.current_is_locked) and not self.vault_unlocked

    def create_vault_password(self) -> bool:
        dialog = VaultPasswordDialog(mode="create", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.db.set_vault_password(dialog.password)
        self.vault_unlocked = True
        return True

    def toggle_vault(self):
        """Unlocks the vault (shows all locked notes) or locks it again (hides them)."""
        if self.vault_unlocked:
            if self.current_is_locked and not self.confirm_unsaved():
                return
            self.vault_unlocked = False
            self.on_vault_state_changed()
            return

        if not self.db.has_vault_password():
            if self.create_vault_password():
                self.on_vault_state_changed()
            return

        dialog = VaultPasswordDialog(mode="unlock", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self.db.verify_vault_password(dialog.password):
                self.vault_unlocked = True
                self.on_vault_state_changed()
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect password!")

    def toggle_note_lock(self):
        """Marks the current note as locked, or removes its lock (only while the vault is open)."""
        if self.entry_hidden():
            return

        if self.current_is_locked:
            reply = QMessageBox.question(
                self,
                "Remove Lock",
                "Remove the lock from this note?\nIt will be visible without the vault password.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.current_is_locked = 0
        else:
            if not self.db.has_vault_password() and not self.create_vault_password():
                return
            self.current_is_locked = 1

        self._write_entry()
        self.is_modified = False
        self.on_vault_state_changed()

        if self.current_is_locked and self.vault_unlocked:
            QMessageBox.information(
                self,
                "Note Locked",
                "This note is locked. It stays visible while the vault is unlocked - "
                "click 'Lock Vault' to hide all locked notes.",
            )

    def on_vault_state_changed(self):
        if self.current_is_locked:
            self.load_current_entry()
        else:
            self.update_lock_buttons()
        self.highlight_saved_dates()

    def update_lock_buttons(self):
        self.vault_btn.setText("🔓 Lock Vault" if self.vault_unlocked else "🔐 Unlock Vault")
        if self.current_is_locked and not self.vault_unlocked:
            self.lock_entry_btn.setText("🔒 Locked")
            self.lock_entry_btn.setEnabled(False)
        elif self.current_is_locked:
            self.lock_entry_btn.setText("🔓 Remove Lock")
            self.lock_entry_btn.setEnabled(True)
        else:
            self.lock_entry_btn.setText("🔒 Lock Note")
            self.lock_entry_btn.setEnabled(True)

    # ----- dialogs / theme -----
    def open_analytics(self):
        dialog = MoodAnalyticsDialog(self.db, self.vault_unlocked, parent=self)
        dialog.exec()

    def open_catalog(self):
        """Opens the catalog dialog to view all entries."""
        dialog = CatalogDialog(self.db, parent=self)
        dialog.exec()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.settings.setValue("dark_mode", self.is_dark_mode)
        self.apply_theme()

    def apply_theme(self):
        palette = PALETTES["dark" if self.is_dark_mode else "light"]
        self.setStyleSheet(build_stylesheet(palette))
        self.calendar.apply_palette(palette)
        self.theme_button.setText("☀️ Light Mode" if self.is_dark_mode else "🌙 Dark Mode")

    # ----- photos -----
    def attach_image(self):
        """Selects an image, replaces any old photo for the date, copies it to assets/photos."""
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
        self.current_image_path = ""
        self.image_label.setText("No photo attached")
        self.image_label.setPixmap(QPixmap())
        self.mark_as_modified()

    def display_image(self, path: str):
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

    # ----- misc actions -----
    def go_to_today(self):
        today = QDate.currentDate()
        if self.calendar.selectedDate() != today:
            self.calendar.setSelectedDate(today)

    def export_current_entry(self):
        if self.entry_hidden():
            QMessageBox.warning(self, "Export Failed", "Unlock the vault first before exporting!")
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
                QMessageBox.information(self, "Export Successful", f"Entry exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error saving file:\n{str(e)}")

    def update_word_count(self):
        if self.entry_hidden():
            self.word_count_label.setText("")
            return
        text = self.text_editor.toPlainText().strip()
        words = len(text.split()) if text else 0
        self.word_count_label.setText(f"Words: {words} | Characters: {len(text)}")

    def on_text_changed(self):
        self.mark_as_modified()
        self.update_word_count()

    def mark_as_modified(self):
        self.is_modified = True

    # ----- calendar -----
    def highlight_saved_dates(self):
        """Colours saved dates by mood; locked dates stay grey (no mood shown) until unlocked."""
        self.calendar.setDateTextFormat(QDate(), QTextCharFormat())

        locked_dates = set()
        for date_str, mood, is_locked in self.db.get_all_dates_with_entries():
            qdate = QDate.fromString(date_str, Qt.DateFormat.ISODate)
            if not qdate.isValid():
                continue
            if is_locked:
                locked_dates.add(date_str)
            if is_locked and not self.vault_unlocked:
                color = LOCKED_CELL_COLOR
            else:
                color = MOOD_COLORS.get(normalize_mood(mood), "#0A84FF")
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(color))
            fmt.setForeground(QColor("#FFFFFF"))
            self.calendar.setDateTextFormat(qdate, fmt)

        self.calendar.set_locked_dates(locked_dates)

    def confirm_unsaved(
        self,
        title="Unsaved Changes",
        text="You have unsaved changes. Do you want to save them?",
    ) -> bool:
        """Returns True when it is fine to continue (saved, discarded or nothing pending)."""
        if not self.is_modified:
            return True
        reply = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Yes:
            self.save_current_entry(show_prompt=False)
        return True

    def on_date_changed(self):
        """Triggered when the user picks another date on the calendar."""
        if not self.confirm_unsaved():
            self.calendar.blockSignals(True)
            self.calendar.setSelectedDate(QDate.fromString(self.current_date, Qt.DateFormat.ISODate))
            self.calendar.blockSignals(False)
            return

        self.current_date = self.calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        self.load_current_entry()

    # ----- load / save -----
    def load_current_entry(self):
        """Loads text, mood, photo and lock state for the current date into the editor."""
        self.date_label.setText(self.current_date)

        self.text_editor.blockSignals(True)
        self.mood_combo.blockSignals(True)

        content, mood, image_path, is_locked = self.db.get_entry(self.current_date)
        self.current_image_path = image_path
        self.current_is_locked = is_locked
        hidden = self.entry_hidden()

        if hidden:
            self.text_editor.setHtml(
                "<h3 style='color: #FF453A;'>🔒 This note is locked</h3>"
                "<p style='color: #8E8E93;'>Click <b>Unlock Vault</b> at the top and enter "
                "your password to view your locked notes.</p>"
            )
            self.text_editor.setReadOnly(True)
            self.image_label.setText("🔒 Photo hidden (note locked)")
            self.image_label.setPixmap(QPixmap())
            self.mood_combo.setCurrentIndex(0)
        else:
            self.text_editor.setReadOnly(False)
            if is_rich_text(content):
                self.text_editor.setHtml(content)
            else:
                self.text_editor.setPlainText(content)
            self.display_image(image_path)
            idx = self.mood_combo.findText(mood)
            self.mood_combo.setCurrentIndex(idx if idx != -1 else 0)

        for widget in (
            self.format_widget,
            self.photo_widget,
            self.mood_combo,
            self.save_button,
            self.export_button,
            self.delete_button,
        ):
            widget.setEnabled(not hidden)
        self.update_lock_buttons()

        self.text_editor.blockSignals(False)
        self.mood_combo.blockSignals(False)

        self.is_modified = False
        self.update_word_count()

    def _write_entry(self):
        """Writes the editor state for the current date to the database."""
        content = self.text_editor.toHtml() if self.text_editor.toPlainText().strip() else ""
        mood = self.mood_combo.currentText()

        if content or self.current_image_path or self.current_is_locked:
            self.db.save_entry(
                self.current_date, content, mood, self.current_image_path, self.current_is_locked
            )
        else:
            self.db.delete_entry(self.current_date)

    def save_current_entry(self, show_prompt=True):
        """Saves current text, mood, image path and lock flag."""
        if self.entry_hidden():
            return

        self._write_entry()
        self.is_modified = False
        self.highlight_saved_dates()

        if show_prompt:
            QMessageBox.information(self, "Success", f"Entry saved for {self.current_date}!")

    def delete_current_entry(self):
        if self.entry_hidden():
            QMessageBox.warning(self, "Action Denied", "Unlock the vault first before deleting!")
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
        if self.confirm_unsaved(
            "Exit DateDiary", "You have unsaved changes. Do you want to save before exiting?"
        ):
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DiaryWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# DateDiary 📅

**DateDiary** is a sleek, lightweight desktop journaling application built with Python, PyQt6, and SQLite. Designed for privacy and ease of use, it allows you to record daily thoughts, track your moods with calendar highlights, customize your visual theme, and export your entries locally.

---

## ✨ Features

- 🎭 **Mood Tagging & Calendar Highlighting**: Categorize daily entries by mood (`Happy`, `Excited`, `Relaxed`, `Sad`, `Angry`, `Neutral`). Dates with saved entries automatically highlight on the calendar using custom mood color indicators.
- 📅 **Quick Navigation**: Instantly snap back to current date with the **Go to Today** button.
- 📊 **Real-Time Writing Statistics**: Live word and character counters update dynamically as you type.
- 🌙 **Light & Dark Theme Switcher**: Toggle between clean light mode and high-contrast dark mode styled with custom QSS.
- 📤 **File Export**: Export individual diary entries into formatted `.txt` or `.md` (Markdown) files via native OS file dialogs.
- 💾 **Local & Private Storage**: Entries are securely stored locally in an SQLite database (`datediary.db`) with auto-migration support.
- ⚠️ **Unsaved Changes Protection**: Intercepts tab navigation and window close events to ensure you never lose unsaved writing.

---

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **GUI Framework:** PyQt6
- **Database:** SQLite3 (Standard Library)

---

## 🚀 Getting Started

### Prerequisites

Ensure you have Python 3.10 or higher installed on your machine.

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/DateDiary.git](https://github.com/YOUR_USERNAME/DateDiary.git)
   cd DateDiary

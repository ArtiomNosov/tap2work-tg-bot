import sqlite3
from datetime import datetime

DB_PATH = "user_logs.db"  # путь должен совпадать с тем, что создавался ранее

# Инициализация базы данных и таблицы
def init_log_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            action_type TEXT NOT NULL,
            message_text TEXT,
            content_type TEXT,
            state TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_action(user_id: int, username: str, action_type: str, message_text: str = None, content_type: str = None, state: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO log (timestamp, user_id, username, action_type, message_text, content_type, state)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        user_id,
        username,
        action_type,
        message_text,
        content_type,
        state
    ))

    conn.commit()
    conn.close()

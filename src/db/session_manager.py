""" Luồng gửi tin nhắn overview và điều hướng overview/chatbot """

import sqlite3
from datetime import datetime, timedelta
from src.config.overview_config import OVERVIEW_NESSAGE

# Đường dẫn DB mặc định
DB_PATH = "database.db"

def init_db():
    """
    Tạo database chứa thời gian khách nhắn và trạng thái overview
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            sender_id TEXT PRIMARY KEY,
            last_customer_message_time DATETIME,
            last_overview_sent_time DATETIME,
            page_id TEXT,
            message_id TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Đã khởi tạo database user_sessions")

def save_conversation(sender_id: str, page_id: str, message_id: str):
    """
    Lưu thông tin cuộc trò chuyện
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO user_sessions (
            sender_id,
            last_customer_message_time,
            last_overview_sent_time,
            page_id,
            message_id
        )
        VALUES (?, ?, NULL, ?, ?)
        ON CONFLICT(sender_id) DO UPDATE SET
            last_customer_message_time = excluded.last_customer_message_time,
            page_id = excluded.page_id,
            message_id = excluded.message_id
    """, (sender_id, current_time, page_id, message_id))

    conn.commit()
    conn.close()
    print(f"✅ Đã lưu/cập nhật cuộc trò chuyện cho {sender_id}")

def get_conversation(sender_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sender_id, last_customer_message_time, last_overview_sent_time, page_id, message_id
        FROM user_sessions
        WHERE sender_id = ?
    """, (sender_id,))

    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "sender_id": row[0],
            "last_customer_message_time": row[1],
            "last_overview_sent_time": row[2],
            "page_id": row[3],
            "message_id": row[4]
        }
    return None

def should_send_overview(sender_id: str, hours: float = 24):
    """
    Kiểm tra xem có cần gửi overview không. Mặc định là 24 giờ.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT last_overview_sent_time
        FROM user_sessions
        WHERE sender_id = ?
    """, (sender_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None or row[0] is None:
        return True

    last_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()

    return (now - last_time) > timedelta(hours=hours)

def mark_overview_sent(sender_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE user_sessions
        SET last_overview_sent_time = ?
        WHERE sender_id = ?
    """, (current_time, sender_id))

    conn.commit()
    conn.close()
    print(f"✅ Đã cập nhật thời gian gửi overview cho {sender_id}")

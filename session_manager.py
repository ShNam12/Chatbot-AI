""" Luồng gửi tin nhắn overview và điều hướng overview/chatbot """

import sqlite3
from datetime import datetime, timedelta, timezone
from overview_config import OVERVIEW_NESSAGE


# print(OVERVIEW_NESSAGE)

#HÀM GỬI TIN NHẮN OVERVIEW

def send_message_overview(sender_id: str, message: str):
    """
    Gửi tin nhắn overview đến người dùng
    Args:
        sender_id: ID của người dùng
        message: Nội dung tin nhắn
    """

    DB_path = "database.db"
    Overview_time = 24 # thời gian để sau đó mỗi lần thì sẽ gửi lại 1 overview


#HÀM TẠO DATABASE CHỨA THỜI GIAN KHÁCH NHẮN VÀ TRẠNG THÁI OVERVIEW

def init_db():
    """
    Tạo database chứa thời gian khách nhắn và trạng thái overview
    """
    DB_path = "database.db"
    conn = sqlite3.connect(DB_path)
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
    print("Đã tạo database user_sessions")

def save_conversation(sender_id: str, page_id: str, message_id: str):
    """
    Lưu thông tin cuộc trò chuyện
    Args:
        sender_id: ID của người dùng
        page_id: ID của page
        message_id: ID của tin nhắn
        timestamp: Thời gian gửi tin nhắn
    """
    DB_path = "database.db"
    conn = sqlite3.connect(DB_path)
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

    print(f"Đã lưu/cập nhật cuộc trò chuyện cho {sender_id}")

def get_conversation(sender_id:str):
    DB_path = "database.db"
    con = sqlite3.connect(DB_path)
    cursor = con.cursor()

    cursor.execute("""
        SELECT sender_id, last_customer_message_time, last_overview_sent_time, page_id, message_id
        FROM user_sessions
        WHERE sender_id = ?
    """, (sender_id,))

    row = cursor.fetchone()
    con.close()
    
    if row:
        return {
            "sender_id": row[0],
            "last_customer_message_time": row[1],
            "last_overview_sent_time": row[2],
            "page_id": row[3],
            "message_id": row[4]
        }
    return None

#HÀM KIỂM TRA XEM CÓ CẦN GỬI OVERVIEW KHÔNG

# def check_overview(sender_id: str, hours: int = 24, minutes: int = 0):
#     """
#     Kiểm tra xem có cần gửi overview không
#     Args:
#         sender_id: ID của người dùng
#     Returns:
#         True nếu cần gửi overview, False nếu không
#     """

#     DB_path = "database.db"
#     conn = sqlite3.connect(DB_path)
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT last_overview_time 
#         FROM user_sessions 
#         WHERE sender_id = ?
#     """, (sender_id,))

#     result = cursor.fetchone()
#     conn.close()
    
#     if result is None:
#         return False

#     last_overview_time_str = result[0]
#     last_overview_time = datetime.strptime(last_overview_time_str, "%Y-%m-%d %H:%M:%S")
#     now = datetime.now()

#     return (now - last_overview_time) > timedelta(hours=24)

#HÀM KIỂM TRA XEM CÓ CẦN GỬI OVERVIEW KHÔNG
def should_send_overview(sender_id: str, hours: int = 24):
    DB_PATH = "database.db"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT last_overview_sent_time
        FROM user_sessions
        WHERE sender_id = ?
    """, (sender_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return True

    last_overview_sent_time = row[0]

    # Chưa từng gửi overview
    if last_overview_sent_time is None:
        return True

    last_time = datetime.strptime(last_overview_sent_time, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()

    return (now - last_time) > timedelta(hours=hours)


#Hàm cập nhật thời gian đã gửi overview
def mark_overview_sent(sender_id: str):
    DB_PATH = "database.db"
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
    print(f"Đã cập nhật thời gian gửi overview cho {sender_id}")
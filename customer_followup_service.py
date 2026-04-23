from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.database import engine
from datetime import datetime, timedelta
import os
import requests


load_dotenv()
 

def send_facebook_text(recipient_id: str, message_text: str) -> bool:
    page_access_token = os.getenv("PAGE_ACCESS_TOKEN")
    if not page_access_token:
        print("Missing PAGE_ACCESS_TOKEN in .env")
        return False

    url = "https://graph.facebook.com/me/messages"
    params = {"access_token": page_access_token}
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
    }

    try:
        response = requests.post(url, params=params, json=payload, timeout=15)
    except requests.RequestException as exc:
        print(f"Cannot connect to Facebook API: {exc}")
        return False

    if response.status_code == 200:
        print(f"Sent follow-up message to {recipient_id}")
        return True

    print(f"Facebook API error {response.status_code}: {response.text}")
    return False


def is_missing_phone(phone) -> bool:
    if phone is None:
        return True
    return str(phone).strip().upper() in {"", "EMPTY", "NULL"}


def get_followup_needed(hours: float = 0.000000000000005) -> list:
    query = text("""
        SELECT
            sender_id,
            sender_name,
            phone,
            page_id,
            last_message_at AS last_message_time,
            NOW() - last_message_at AS time_diff
        FROM users
        WHERE last_message_at IS NOT NULL
        AND last_message_at <= (NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh') - (:hours * INTERVAL '1 hour')
    """)

    with Session(engine) as db:
        result = db.execute(query, {"hours": hours})
        return result.mappings().all()
    
users = get_followup_needed(0.00000000000005)

for user in users:
    sender_id = user["sender_id"]
    sender_name = user["sender_name"]
    phone = user["phone"]
    page_id = user["page_id"]
    last_message_time = datetime.now() - user["last_message_time"]

    text_respone_15p = f"""Dạ {sender_name} ơi, chắc mình đang bận chút công việc ạ? Em thấy chị đang quan tâm đến dịch vụ [Gym/Yoga…] bên em. Bên em có lộ trình tập luyện riêng cho mục tiêu tập luyện. Anh/Chị nhắn em số điện thoại, em gửi qua để mình tham khảo trước nhé!"""

    print(sender_name, phone, last_message_time)

    if is_missing_phone(phone) and last_message_time > timedelta(minutes=2):
        print(f"Follow up with {sender_name} (Page ID: {page_id}) - No phone number, last message was {last_message_time} ago.")
        send_facebook_text(sender_id, text_respone_15p)

    


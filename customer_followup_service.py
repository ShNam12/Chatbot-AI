from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.database import engine
from datetime import datetime, timedelta
import os
import requests


load_dotenv()


def get_page_access_token(page_id) -> str | None:
    page_id = str(page_id).strip()
    env_name = f"PAGE_ACCESS_TOKEN_{page_id}"
    page_access_token = os.getenv(env_name)

    if not page_access_token:
        print(f"Missing {env_name} in .env")
        return None

    return page_access_token

def send_facebook_text(
    recipient_id: str,
    message_text: str,
    page_access_token: str,
) -> bool:
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

def get_followup_needed(hours: float = 0.000000000000000000000001) -> list:
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


users = get_followup_needed(0.000000000000000000000001)

for user in users:
    sender_id = user["sender_id"]
    sender_name = user["sender_name"]
    phone = user["phone"]
    page_id = user["page_id"]
    last_message_time = datetime.now() - user["last_message_time"]

    page_access_token = get_page_access_token(page_id)
    if not page_access_token:
        continue

    text_response_15p = f"""Dạ {sender_name} ơi, Gửi số điện thoại cho tôi"""

    if is_missing_phone(phone) and last_message_time > timedelta(minutes=0.000001):
        print(
            f"Follow up with {sender_name} "
            f"(Page ID: {page_id}) - No phone number, "
            f"last message was {last_message_time} ago."
        )

        send_facebook_text(
            recipient_id=sender_id,
            message_text=text_response_15p,
            page_access_token=page_access_token,
        )


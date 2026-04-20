import re
from typing import Optional

from src.db.models import UserSession
from src.db.database import engine
from sqlmodel import Session,select

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


def extract_phone(text):
    pattern = r'(?:\+84|84|0)(?:\d[\s\.-]?){8,9}\d'
    match = re.search(pattern, text)
    
    if not match:
        return None

    phone = match.group(0)

    # 🔧 normalize: xoá space, dấu
    phone = re.sub(r'[\s\.-]', '', phone)

    # 🔄 chuẩn hoá về 0xxxxxxxxx
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84"):
        phone = "0" + phone[2:]

    return phone

def detect_and_update_interest(user_id: str, user_text: str, store: dict) -> list:
    """Phát hiện sở thích của khách hàng dựa trên tin nhắn"""
    text = user_text.lower()
    new_interest = set()

    # --- EMS ---
    if any(keyword in text for keyword in [
        "bơi", "bể bơi", "hồ bơi", "pool"
    ]):
        new_interest.add("bơi & bể bơi")

    # --- Yoga ---
    if any(keyword in text for keyword in [
        "yoga", "thiền", "giãn cơ", "dẻo", "thư giãn"
    ]):
        new_interest.add("yoga & thiền")

    # --- Giảm cân ---
    if any(keyword in text for keyword in [
        "giảm cân", "giảm mỡ", "đốt mỡ", "ốm", "gầy", "bụng mỡ", "mỡ bụng", "eo thon"
    ]):
        new_interest.add("giảm cân")

    # --- Tăng cơ ---
    if any(keyword in text for keyword in [
        "tăng cơ", "lên cơ", "cơ bắp", "body", "to cơ", "6 múi"
    ]):
        new_interest.add("tăng cơ")

    # --- Gym (chung chung) ---
    if any(keyword in text for keyword in [
        "gym", "tập luyện", "fitness", "phòng tập"
    ]):
        new_interest.add("gym")
    
    # --- Nhảy (Dance) ---
    if any(keyword in text for keyword in [
        "nhảy", "dancing", "dance", "rumba"
    ]):
        new_interest.add("Dance")

    old_interests = store.get(user_id, set())

    if not new_interest:
        return list(old_interests) if old_interests else ["chung"]

    updated = old_interests.union(new_interest)
    store[user_id] = updated

    return list(updated)
        

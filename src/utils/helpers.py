import re
<<<<<<< HEAD

def extract_phone(text):
    """Trích xuất số điện thoại từ văn bản"""
    pattern = r'(0|\+84)[0-9]{9}'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def detect_interest(user_text: str) -> str:
    """Phát hiện sở thích của khách hàng dựa trên tin nhắn"""
    text = user_text.lower()
=======
from typing import Optional

from src.db.models import UserSession
from src.db.database import engine
from sqlmodel import Session,select

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


import re

def extract_phone(text: str) -> Optional[str | bool]:
    """Trích xuất số điện thoại từ text
    Return: 
      - str: Số điện thoại hợp lệ (0xxxxxxxxx)
      - False: Tìm thấy nhưng format sai
      - None: Không tìm thấy
    """
    pattern = r'(?:\+84|84|0)(?:\d[\s\.-]?){8,9}\d'
    match = re.search(pattern, text)
    
    if not match:
        return None  # Không tìm thấy
    
    phone = match.group(0)

    # 🔧 normalize: xoá space, dấu
    phone = re.sub(r'[\s\.-]', '', phone)

    # 🔄 chuẩn hoá về 0xxxxxxxxx
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84"):
        phone = "0" + phone[2:]
    
    # ❌ validate: reject đầu số sai hoặc độ dài sai
    if phone.startswith(("00", "01", "02", "04", "06")) or len(phone) != 10:
        return False  # Tìm nhưng sai format

    return phone  # Hợp lệ

def detect_and_update_interest(user_id: str, user_text: str, store: dict) -> list:
    """Phát hiện sở thích của khách hàng dựa trên tin nhắn"""
    text = user_text.lower()
    new_interest = set()
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

    # --- EMS ---
    if any(keyword in text for keyword in [
        "bơi", "bể bơi", "hồ bơi", "pool"
    ]):
<<<<<<< HEAD
        return "bơi & bể bơi"
=======
        new_interest.add("bơi & bể bơi")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

    # --- Yoga ---
    if any(keyword in text for keyword in [
        "yoga", "thiền", "giãn cơ", "dẻo", "thư giãn"
    ]):
<<<<<<< HEAD
        return "yoga"
=======
        new_interest.add("yoga & thiền")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

    # --- Giảm cân ---
    if any(keyword in text for keyword in [
        "giảm cân", "giảm mỡ", "đốt mỡ", "ốm", "gầy", "bụng mỡ", "mỡ bụng", "eo thon"
    ]):
<<<<<<< HEAD
        return "giảm cân"
=======
        new_interest.add("giảm cân")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

    # --- Tăng cơ ---
    if any(keyword in text for keyword in [
        "tăng cơ", "lên cơ", "cơ bắp", "body", "to cơ", "6 múi"
    ]):
<<<<<<< HEAD
        return "tăng cơ"
=======
        new_interest.add("tăng cơ")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

    # --- Gym (chung chung) ---
    if any(keyword in text for keyword in [
        "gym", "tập luyện", "fitness", "phòng tập"
    ]):
<<<<<<< HEAD
        return "gym"
=======
        new_interest.add("gym")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    
    # --- Nhảy (Dance) ---
    if any(keyword in text for keyword in [
        "nhảy", "dancing", "dance", "rumba"
    ]):
<<<<<<< HEAD
        return "Dance"

    # --- fallback ---
    return "chung"
=======
        new_interest.add("Dance")

    old_interests = store.get(user_id, set())

    if not new_interest:
        return list(old_interests) if old_interests else ["chung"]

    updated = old_interests.union(new_interest)
    store[user_id] = updated

    return list(updated)
        
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

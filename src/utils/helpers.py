import re

def extract_phone(text):
    """Trích xuất số điện thoại từ văn bản"""
    pattern = r'(0|\+84)[0-9]{9}'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def detect_interest(user_text: str) -> str:
    """Phát hiện sở thích của khách hàng dựa trên tin nhắn"""
    text = user_text.lower()

    # --- EMS ---
    if any(keyword in text for keyword in [
        "bơi", "bể bơi", "hồ bơi", "pool"
    ]):
        return "bơi & bể bơi"

    # --- Yoga ---
    if any(keyword in text for keyword in [
        "yoga", "thiền", "giãn cơ", "dẻo", "thư giãn"
    ]):
        return "yoga"

    # --- Giảm cân ---
    if any(keyword in text for keyword in [
        "giảm cân", "giảm mỡ", "đốt mỡ", "ốm", "gầy", "bụng mỡ", "mỡ bụng", "eo thon"
    ]):
        return "giảm cân"

    # --- Tăng cơ ---
    if any(keyword in text for keyword in [
        "tăng cơ", "lên cơ", "cơ bắp", "body", "to cơ", "6 múi"
    ]):
        return "tăng cơ"

    # --- Gym (chung chung) ---
    if any(keyword in text for keyword in [
        "gym", "tập luyện", "fitness", "phòng tập"
    ]):
        return "gym"
    
    # --- Nhảy (Dance) ---
    if any(keyword in text for keyword in [
        "nhảy", "dancing", "dance", "rumba"
    ]):
        return "Dance"

    # --- fallback ---
    return "chung"

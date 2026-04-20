from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import AI_MODEL_NAME, AI_REQUEST_TIMEOUT
from src.db.operations import update_user_location

load_dotenv()


@dataclass
class AddressExtractionResult:
    has_user_address: bool
    should_update_db: bool
    address_only: Optional[str] = None
    confidence: str = "low"
    reason: str = ""


# @dataclass
# class GeocodeResult:
#     success: bool
#     address: Optional[str] = None
#     formatted_address: Optional[str] = None
#     lat: Optional[float] = None
#     lon: Optional[float] = None
#     place_id: Optional[str] = None
#     error: Optional[str] = None


POSITIVE_ADDRESS_PATTERNS = [
    "tôi ở",
    "mình ở",
    "em ở",
    "anh ở",
    "chị ở",
    "nhà mình ở",
    "mình sống ở",
    "tôi sống ở",
    "địa chỉ của mình là",
    "nhà mình gần",
    "em gần",
    "mình gần",
    "tôi gần",
    "ở khu",
    "ở quận",
    "ở phường",
    "ở đường",
    "ở phố",
    "ngõ",
    "ngách",
    "số nhà",
    "chung cư",
    "tòa",
    "khu đô thị",
    "gần hoàng ngân",
    "gần cầu giấy",
    "gần láng",
    "gần khu",
    "chỗ thanh xuân",
    "khu vực thanh xuân",
    "thanh xuân",
    "cầu giấy",
    "đống đa",
    "hoàng mai",
    "hai bà trưng",
    "ba đình",
    "hoàn kiếm",
    "tây hồ",
    "hà đông",
]

NEGATIVE_ADDRESS_PATTERNS = [
    "có cơ sở ở",
    "có chi nhánh ở",
    "địa chỉ phòng tập",
    "địa chỉ bên mình",
    "địa chỉ của bên mình",
    "phòng tập ở đâu",
    "chi nhánh ở đâu",
    "cơ sở ở đâu",
    "ems ở đâu",
]

HANOI_AREAS = [
    "đống đa",
    "cầu giấy",
    "ba đình",
    "hai bà trưng",
    "thanh xuân",
    "hoàng mai",
    "hà đông",
    "nam từ liêm",
    "bắc từ liêm",
    "tây hồ",
    "long biên",
    "hoàn kiếm",
]


def remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt."""
    s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
    s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiiiiiouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
    s = ""
    for char in text:
        if char in s1:
            s += s0[s1.index(char)]
        else:
            s += char
    return s

def normalize_for_match(text: str) -> str:
    # Chuyển về chữ thường, xóa khoảng trắng thừa và LOẠI BỎ DẤU
    text = text.lower()
    text = remove_accents(text)
    return re.sub(r"\s+", " ", text).strip()

def may_contain_user_address(message_text: str) -> bool:
    text = normalize_for_match(message_text)

    # Các từ khóa trong list này cũng nên để dạng KHÔNG DẤU để khớp với text đã normalize
    for pattern in NEGATIVE_ADDRESS_PATTERNS:
        if remove_accents(pattern.lower()) in text:
            return False

    for pattern in POSITIVE_ADDRESS_PATTERNS:
        if remove_accents(pattern.lower()) in text:
            return True
            
    for area in HANOI_AREAS:
        if remove_accents(area.lower()) in text:
            # Nếu chỉ có tên quận/huyện, giới hạn độ dài tin nhắn để tránh bắt nhầm
            words = text.split()
            if len(words) <= 5:
                return True

    return False


def extract_address_with_llm(message_text: str) -> AddressExtractionResult:
    """Dùng Gemini để tách đúng phần địa chỉ từ tin nhắn."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return AddressExtractionResult(
            has_user_address=False,
            should_update_db=False,
            reason="Missing GOOGLE_API_KEY",
        )

    llm = ChatGoogleGenerativeAI(
        model=AI_MODEL_NAME,
        temperature=0,
        google_api_key=api_key,
        request_timeout=AI_REQUEST_TIMEOUT,
    )

    prompt = f"""
Bạn là bộ trích xuất địa chỉ người dùng từ tin nhắn tiếng Việt.

Nhiệm vụ:
- Xác định người dùng có đang cung cấp địa chỉ, nơi ở, vị trí hiện tại, hoặc khu vực muốn tìm gần đó không.
- Nếu có, chỉ trích xuất phần địa chỉ.
- Không trích xuất địa chỉ chi nhánh/phòng tập nếu người dùng chỉ đang hỏi địa chỉ của doanh nghiệp.
- Không tự bịa thêm phường/quận/số nhà.
- Trả về JSON hợp lệ, không thêm giải thích ngoài JSON.

Schema:
{{
  "has_user_address": boolean,
  "address_only": string | null,
  "should_update_db": boolean,
  "confidence": "low" | "medium" | "high",
  "reason": string
}}

Tin nhắn: {message_text}
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)

        return AddressExtractionResult(
            has_user_address=bool(data.get("has_user_address")),
            should_update_db=bool(data.get("should_update_db")),
            address_only=data.get("address_only"),
            confidence=data.get("confidence", "low"),
            reason=data.get("reason", ""),
        )
    except Exception as e:
        print(f"❌ [Location] Lỗi extract địa chỉ bằng LLM: {e}")
        return AddressExtractionResult(
            has_user_address=False,
            should_update_db=False,
            reason=str(e),
        )


def normalize_address(address_text: str) -> str:
    """Chuẩn hóa địa chỉ tránh bị lặp lại suffix."""
    address = re.sub(r"\s+", " ", address_text).strip(" ,.-")
    
    # Xóa các suffix đã có sẵn để tránh bị cộng dồn
    address = re.sub(r"(,\s*(Hà Nội|HN|Việt Nam|VN))+$", "", address, flags=re.IGNORECASE)
    
    return address

def text_to_coordinates(address: str, timeout: int = 10):
    """Chuyển đổi địa điểm thành tọa độ với cơ chế Fallback."""
    geolocator = Nominatim(user_agent="ems_chatbot_location")
    
    # 1. Thử với địa chỉ đầy đủ (có suffix chuẩn)
    full_query = f"{address}, Hà Nội, Việt Nam"
    try:
        location = geolocator.geocode(full_query, timeout=timeout, country_codes="vn")
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        print(f"⚠️ Lỗi geocode lần 1: {e}")

    # 2. FALLBACK: Nếu không ra, hãy thử lọc bỏ các ngõ/ngách chi tiết, chỉ giữ lại tên đường/khu vực
    # Ví dụ: "Ngõ 163 Hoàng Ngân" -> "Hoàng Ngân"
    if "ngõ" in address.lower() or "ngách" in address.lower() or "số" in address.lower():
        # Tìm phần tên đường (thường đứng sau ngõ/số nhà)
        simple_address = re.sub(r"^(ngõ|ngách|số|tầng|tòa)\s+\d+\s*", "", address, flags=re.IGNORECASE).strip()
        if simple_address and simple_address != address:
            print(f"🔄 Fallback Geocoding với: {simple_address}")
            try:
                location = geolocator.geocode(f"{simple_address}, Hà Nội, Việt Nam", timeout=timeout)
                if location:
                    return location.latitude, location.longitude
            except:
                pass

    return None

def detect_and_extract_address(message_text: str) -> AddressExtractionResult:
    """Nhận diện và tách địa chỉ từ tin nhắn."""
    if not may_contain_user_address(message_text):
        return AddressExtractionResult(
            has_user_address=False,
            should_update_db=False,
            reason="No address pattern matched",
        )

    result = extract_address_with_llm(message_text)

    if result.confidence == "low":
        result.should_update_db = False

    if not result.address_only:
        result.should_update_db = False

    return result

def handle_location_memory(sender_id: str, message_text: str) -> dict:
    """Luồng chính: detect -> normalize -> geocode -> update DB."""
    
    if not sender_id:
        return {
            "updated": False,
            "reason": "Missing sender_id",
        }

    if not message_text or not message_text.strip():
        return {
            "updated": False,
            "reason": "Empty message_text",
        }

    try:
        extraction = detect_and_extract_address(message_text)

        if not extraction.should_update_db:
            return {
                "updated": False,
                "reason": extraction.reason,
            }

        if not extraction.address_only:
            return {
                "updated": False,
                "reason": "No address extracted",
            }

        normalized_address = normalize_address(extraction.address_only)
        coordinates = text_to_coordinates(normalized_address)

        if not coordinates:
            return {
                "updated": False,
                "reason": "Geocoding returned no result",
                "address": normalized_address,
            }

        lat, lon = coordinates

        update_user_location(
            sender_id=sender_id,
            address=normalized_address,
            lat=lat,
            lon=lon,
        )

        return {
            "updated": True,
            "reason": "Location updated successfully",
            "address": normalized_address,
            "lat": lat,
            "lon": lon,
        }

    except Exception as e:
        print(f"[Location] Lỗi handle_location_memory: {e}")
        return {
            "updated": False,
            "reason": str(e),
        }

import math
import os
import re
from math import radians, cos, sin, asin, sqrt
from src.db.operations import get_all_branches, get_user_location, update_user_location
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

def haversine_km(lat1, lon1, lat2, lon2):
    """Tính khoảng cách Haversine giữa 2 điểm (km)"""
    if None in [lat1, lon1, lat2, lon2]:
        return float('inf')
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers.
    return c * r

def search_address(sender_id: str, user_address: str = None, top_n: int = 3) -> dict:
    """
    Tìm kiếm chi nhánh gần người dùng.
    1. Nếu có user_address mới -> Geocode và cập nhật DB.
    2. Nếu không -> Lấy tọa độ cuối cùng từ DB.
    3. Tính khoảng cách tới toàn bộ chi nhánh trong DB.
    """
    print(f"--- TOOL CALL: SEARCHING ADDRESS (Address requested: {user_address}) ---")
    
    # 1. Xác định tọa độ người dùng
    user_lat, user_lon = None, None
    
    if user_address:
        # Chuẩn hóa address đầu vào để tránh lặp suffix
        clean_address = re.sub(r"(,\s*(Hà Nội|HN|Việt Nam|VN))+$", "", user_address, flags=re.IGNORECASE)
        
        # Geocode địa chỉ mới
        try:
            geolocator = Nominatim(user_agent="ems_fitness_search")
            # Thử 1: Full address
            query = f"{clean_address}, Hà Nội, Việt Nam"
            location = geolocator.geocode(query, timeout=10)
            
            if not location:
                # Thử 2: Fallback (loại bỏ ngõ ngách chi tiết)
                simple_address = re.sub(r"^(ngõ|ngách|số|tầng|tòa)\s+\d+\s*", "", clean_address, flags=re.IGNORECASE).strip()
                if simple_address and simple_address != clean_address:
                    print(f"🔄 Fallback Geocoding với: {simple_address}")
                    location = geolocator.geocode(f"{simple_address}, Hà Nội, Việt Nam", timeout=10)

            if location:
                user_lat, user_lon = location.latitude, location.longitude
                print(f"📍 Geocoding thành công: {user_lat}, {user_lon}")
                # Lưu vào DB
                update_user_location(sender_id, user_address, user_lat, user_lon)
            else:
                print(f"⚠️ Không tìm thấy tọa độ cho: {user_address}")
        except Exception as e:
            print(f"❌ Lỗi Geocoding: {e}")

    # 2. Nếu chưa có tọa độ (hoặc geocode xịt), thử lấy từ DB
    if user_lat is None:
        saved_loc = get_user_location(sender_id)
        if saved_loc:
            user_lat, user_lon = saved_loc.get("lat"), saved_loc.get("lon")
            print(f"📍 Sử dụng vị trí đã lưu trong DB: {user_lat}, {user_lon}")

    # 3. Nếu vẫn không có tọa độ -> Báo lỗi cần địa chỉ
    if user_lat is None:
        return {
            "context": "Mình chưa có khu vực của bạn. Bạn cho mình xin khu vực/quận hoặc địa chỉ gần bạn nhé để mình tìm chi nhánh tiện nhất nha.",
            "source": "diachi"
        }

    # 4. Lấy danh sách chi nhánh từ Database
    try:
        branches = get_all_branches()
        if not branches:
            return {
                "context": "Hiện tại hệ thống chưa có dữ liệu chi nhánh. Vui lòng thử lại sau.",
                "source": "diachi"
            }
        
        # 5. Tính khoảng cách
        results = []
        for br in branches:
            dist = haversine_km(user_lat, user_lon, br.latitude, br.longitude)
            results.append({
                "branch_name": br.code,
                "branch_address": br.address,
                "distance_km": round(dist, 2)
            })
        
        # Sắp xếp theo khoảng cách
        results.sort(key=lambda x: x["distance_km"])
        nearest = results[:top_n]
        
        # Kiểm tra nếu chi nhánh gần nhất quá xa (ví dụ > 100km)
        if nearest[0]["distance_km"] > 100:
             return {
                "context": f"Hiện tại EMS Fitness chưa có cơ sở nào gần khu vực {user_address or 'vị trí của bạn'} ạ. Bạn có muốn tìm kiếm ở khu vực khác không?",
                "source": "diachi"
            }

        return {"context": nearest, "source": "diachi"}

    except Exception as e:
        print(f"❌ Lỗi truy xuất chi nhánh từ DB: {e}")
        return {"context": "Lỗi hệ thống khi tìm chi nhánh.", "source": "diachi"}
import os
from math import atan2, cos, radians, sin, sqrt

import pandas as pd

from src.config.settings import DIACHI_CSV_PATH
from src.db.operations import get_user_location


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 6371 * c


def search_address(sender_id: str, top_n: int = 3) -> dict:
    """Tìm các chi nhánh gần nhất dựa trên vị trí đã lưu của người dùng."""
    print("--- TOOL CALL: SEARCHING ADDRESS ---")

    location = get_user_location(sender_id)
    if not location:
        return {
            "context": "Mình chưa có khu vực của bạn. Bạn cho mình xin khu vực/quận hoặc địa chỉ gần bạn nhé.",
            "source": "diachi",
            "need_user_address": True,
        }

    if not os.path.exists(DIACHI_CSV_PATH):
        return {
            "context": "Hiện tại chưa có dữ liệu chi nhánh để tra cứu.",
            "source": "diachi",
        }

    try:
        df_br = pd.read_csv(DIACHI_CSV_PATH)
    except Exception as e:
        print(f"Lỗi khi tải dữ liệu chi nhánh: {e}")
        return {
            "context": "Lỗi truy xuất dữ liệu chi nhánh.",
            "source": "diachi",
        }

    required_cols = {"branch_name", "branch_address", "latitude", "longitude"}
    if not required_cols.issubset(df_br.columns):
        return {
            "context": "Dữ liệu chi nhánh đang thiếu cột latitude/longitude.",
            "source": "diachi",
        }

    user_lat = location["lat"]
    user_lon = location["lon"]

    filtered_df = df_br.dropna(subset=["latitude", "longitude"]).copy()
    filtered_df["distance_km"] = filtered_df.apply(
        lambda row: haversine_km(user_lat, user_lon, row["latitude"], row["longitude"]),
        axis=1,
    )

    nearest = filtered_df.sort_values("distance_km").head(top_n)
    nearest["distance_km"] = nearest["distance_km"].round(2)

    results = nearest[["branch_name", "branch_address", "distance_km"]].to_dict(orient="records")

    return {
        "context": results,
        "source": "diachi",
        "user_address": location.get("address"),
        "user_lat": user_lat,
        "user_lon": user_lon,
    }




# DIACHI_CSV_PATH = "D:\\2025.2\\Thực tập\\data\\diachi.csv"


# def search_address(user_location: str = "Hanoi,Vietnam", top_n: int = 3):
#     """ Tìm kiếm các địa chỉ gần người cần tư vấn nhất"""
#     print("--- TOOL CALL: SEARCHING ADDRESS ---")

#     try: 
#         if not os.path.exists(DIACHI_CSV_PATH):
#             print(f"⚠️ Không tìm thấy file dữ liệu tại {DIACHI_CSV_PATH}")
#             # Fallback nếu không có file CSV
#             return {"context": "Hiện tại không có thông tin chi nhánh.", "source": "diachi"}
            
#         df_br = pd.read_csv(DIACHI_CSV_PATH)
#         print("✅ Đã tải thành công dữ liệu các chi nhánh!")
#     except Exception as e:
#         print(f"❌ Lỗi khi tải dữ liệu: {e}")
#         return {"context": "Lỗi truy xuất địa chỉ.", "source": "diachi"}

#     user_lat, user_lon = DEFAULT_USER_COORD["lat"], DEFAULT_USER_COORD["lon"]

#     def haversine(lat1, lon1, lat2, lon2):
#         lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
#         dlon = lon2 - lon1
#         dlat = lat2 - lat1
#         a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
#         c = 2 * atan2(sqrt(a), sqrt(1-a))
#         return 6371 * c 

#     filtered_df = df_br.copy()
#     filtered_df['distance_km'] = filtered_df.apply(
#         lambda row: haversine(user_lat, user_lon, row['latitude'], row['longitude']), axis=1
#     )

#     nearest = filtered_df.sort_values('distance_km').head(top_n)
#     nearest["distance_km"] = nearest["distance_km"].round(2)
#     results = nearest[['branch_name', 'branch_address', 'distance_km']].to_dict(orient='records')
    
#     return {"context": results, "source": "diachi"}
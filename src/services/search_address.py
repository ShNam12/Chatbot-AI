DIACHI_CSV_PATH = "D:\\2025.2\\Thực tập\\data\\diachi.csv"


def search_address(user_location: str = "Hanoi,Vietnam", top_n: int = 3):
    """ Tìm kiếm các địa chỉ gần người cần tư vấn nhất"""
    print("--- TOOL CALL: SEARCHING ADDRESS ---")

    try: 
        if not os.path.exists(DIACHI_CSV_PATH):
            print(f"⚠️ Không tìm thấy file dữ liệu tại {DIACHI_CSV_PATH}")
            # Fallback nếu không có file CSV
            return {"context": "Hiện tại không có thông tin chi nhánh.", "source": "diachi"}
            
        df_br = pd.read_csv(DIACHI_CSV_PATH)
        print("✅ Đã tải thành công dữ liệu các chi nhánh!")
    except Exception as e:
        print(f"❌ Lỗi khi tải dữ liệu: {e}")
        return {"context": "Lỗi truy xuất địa chỉ.", "source": "diachi"}

    user_lat, user_lon = DEFAULT_USER_COORD["lat"], DEFAULT_USER_COORD["lon"]

    def haversine(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c 

    filtered_df = df_br.copy()
    filtered_df['distance_km'] = filtered_df.apply(
        lambda row: haversine(user_lat, user_lon, row['latitude'], row['longitude']), axis=1
    )

    nearest = filtered_df.sort_values('distance_km').head(top_n)
    nearest["distance_km"] = nearest["distance_km"].round(2)
    results = nearest[['branch_name', 'branch_address', 'distance_km']].to_dict(orient='records')
    
    return {"context": results, "source": "diachi"}
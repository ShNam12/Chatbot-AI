import sys
import os
import re
from sqlmodel import Session, select

# Thêm đường dẫn dự án vào PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.database import init_db
from src.db.operations import upsert_branch
from src.db.models import EmsBranch
from src.db.database import engine

CHINHANH_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "data", "chinhanh.txt")

# Tọa độ chuẩn cho 10 chi nhánh (Hardcoded để đảm bảo chính xác 100%)
COORDINATE_MAP = {
    "CS1": (20.985, 105.815), # Số 2 Kim Giang
    "CS2": (21.033, 105.777), # 99 Trần Bình
    "CS3": (21.009, 105.802), # 163 Hoàng Ngân
    "CS4": (20.999, 105.836), # 102 Trường Chinh
    "CS5": (21.032, 105.783), # 36 Phạm Hùng
    "CS6": (20.992, 105.891), # 440 Vĩnh Hưng
    "CS7": (20.983, 105.838), # 176 Định Công
    "CS8": (20.998, 105.865), # 250 Minh Khai
    "CS9": (20.950, 107.073), # Hạ Long, Quảng Ninh
    "CS10": (21.000, 105.816), # 108 Nguyễn Trãi
}

def parse_chinhanh_txt(filepath: str) -> list[dict]:
    branches = []
    pattern = re.compile(r"^(CS\d+):\s*(.+)$", re.IGNORECASE)

    if not os.path.exists(filepath):
        print(f"❌ Không tìm thấy file {filepath}")
        return []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if not m:
                continue

            code = m.group(1).strip()
            address = m.group(2).strip().rstrip(". ")
            parts = [p.strip() for p in address.split("-")]
            district = parts[-2].strip() if len(parts) >= 2 else None
            city = "Quảng Ninh" if "Hạ Long" in address or "Quảng Ninh" in address else "Hà Nội"

            branches.append({
                "code": code,
                "address": address,
                "district": district,
                "city": city,
            })
    return branches

def seed():
    print("🌱 Khởi tạo/Kiểm tra Database...")
    init_db()

    branches = parse_chinhanh_txt(CHINHANH_FILE)
    print(f"📋 Tìm thấy {len(branches)} chi nhánh trong file text\n")

    for b in branches:
        code = b["code"]
        print(f"🔍 Đang nạp {code}: {b['address']}")
        
        lat, lon = COORDINATE_MAP.get(code, (None, None))
        
        # Lưu vào DB
        upsert_branch(
            code=code,
            address=b["address"],
            district=b["district"],
            city=b["city"]
        )
        
        # Cập nhật tọa độ chuẩn
        with Session(engine) as session:
            statement = select(EmsBranch).where(EmsBranch.code == code)
            db_br = session.exec(statement).first()
            if db_br:
                db_br.latitude = lat
                db_br.longitude = lon
                session.add(db_br)
                session.commit()
                print(f"✅ Đã nạp {code} | Tọa độ chuẩn: {lat}, {lon}")

    print(f"\n✅ Đã đồng bộ 10 chi nhánh vào database!")

if __name__ == "__main__":
    seed()

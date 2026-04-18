"""
Script seed dữ liệu chi nhánh EMS từ chinhanh.txt vào PostgreSQL.
lat/lon để None — sẽ geocode sau bằng hàm riêng.

Chạy: python scripts/seed_branches.py
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import init_db
from src.db.operations import upsert_branch

CHINHANH_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "data", "chinhanh.txt")

def parse_chinhanh_txt(filepath: str) -> list[dict]:
    """Parse file chinhanh.txt → list[{code, address, district, city}]"""
    branches = []
    pattern = re.compile(r"^(CS\d+):\s*(.+)$", re.IGNORECASE)

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if not m:
                continue

            code = m.group(1).strip()
            address = m.group(2).strip().rstrip(". ")

            # Trích xuất quận và thành phố từ địa chỉ
            parts = [p.strip() for p in address.split("-")]
            district = parts[-2].strip() if len(parts) >= 2 else None
            city_raw = parts[-1].strip() if parts else ""

            if "Quảng Ninh" in city_raw:
                city = "Quảng Ninh"
            else:
                city = "Hà Nội"

            branches.append({
                "code": code,
                "address": address,
                "district": district,
                "city": city,
            })

    return branches


def seed():
    print("🌱 Khởi tạo database...")
    init_db()

    branches = parse_chinhanh_txt(CHINHANH_FILE)
    print(f"📋 Tìm thấy {len(branches)} chi nhánh\n")

    for b in branches:
        upsert_branch(
            code=b["code"],
            address=b["address"],
            district=b["district"],
            city=b["city"],
            # latitude, longitude để None — geocode sau
        )

    print(f"\n✅ Đã seed {len(branches)} chi nhánh vào bảng ems_branch")
    print("💡 Chạy scripts/geocode_branches.py để cập nhật tọa độ lat/lon")


if __name__ == "__main__":
    seed()

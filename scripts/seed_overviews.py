import sys
import os

# Thêm đường dẫn gốc của dự án vào sys.path để có thể import các module từ thư mục src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, delete
from src.db.database import engine
from src.db.models import VectorFAQ
from src.db.operations import insert_vector_faq
from src.utils.embeddings import embed_text
from sqlmodel import SQLModel

# Danh sách dữ liệu Overview cần đưa vào Database
OVERVIEWS = [
    {
        "sub_category": "Bơi",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Bể bơi EMS \"Bao sạch đẹp\" thiết kế hiện đại, hệ thống lọc muối khoáng tự nhiên, chuẩn 5 ⭐.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015604/Boi_su4bkc.jpg"
    },
    {
        "sub_category": "Gym",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Phòng Gym EMS chuyên biệt, trang bị cao cấp, rộng thoáng, chuẩn 5 ⭐.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015603/Gym1_koouya.jpg"
    },
    {
        "sub_category": "Yoga",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Phòng tập Yoga thoáng - sạch - đẹp, đa dạng khung giờ, HLV trong và ngoài nước.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015794/yoga_yuoceg.jpg"
    },
    {
        "sub_category": "Võ thuật",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Các lớp Boxing/Kickfit/MuayThai tăng sức bền, tự vệ. HLV chuyên nghiệp, nhiệt tình.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015603/Boxing_rnjrv5.jpg"
    },
    {
        "sub_category": "Dance",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] VỚi nhiều lớp Zumba/SexyDance/BellyDance/Múa cổ trang - Tiktok trong nền không gian & âm nhạc sôi động, vui vẻ. Giúp bạn đốt cháy năng lượng, xả Stress hiệu quả, cải thiện vóc dáng và sự tự tin.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015604/YogaDance_s76nj6.jpg"
    },
    {
        "sub_category": "Vật lý trị liệu",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Dịch vụ Sauna - vật lý trị liệu hỗ trợ phục hồi chấn thương, giảm đau cơ xương khớp và cải thiện khả năng vận động. Kết hợp các bài tập chuyên biệt cùng hướng dẫn từ chuyên gia giúp cơ thể phục hồi an toàn, tăng độ linh hoạt và phòng tránh các vấn đề sức khỏe lâu dài.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1745468152/yoga_images/yoga_class_d36913e5-7953-44d4-b210-cdd73a860585.jpg"
    },
    {
        "sub_category": "Xông hơi",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Dịch vụ Sauna - vật lý trị liệu hỗ trợ phục hồi chấn thương, giảm đau cơ xương khớp và cải thiện khả năng vận động. Kết hợp các bài tập chuyên biệt cùng hướng dẫn từ chuyên gia giúp cơ thể phục hồi an toàn, tăng độ linh hoạt và phòng tránh các vấn đề sức khỏe lâu dài.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015852/Tienich2_ofy5vm.jpg"
    },
    {
        "sub_category": "HLV",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Đội ngũ HLV EMS \"bao đẹp\" & chuyên nghiệp: Nhiệt tình, tận tâm, giàu kinh nghiệm, luôn sẵn sàng hỗ trợ và đồng hành cùng bạn trên hành trình cải thiện sức khỏe và vóc dáng.",
        "image_url": "https://res.cloudinary.com/da9rooi9r/image/upload/v1777015602/HLV2_fpngkq.jpg"
    },
    {
        "sub_category": "SDT",
        "content": "[QUY TẮC CỨNG: Trả về nguyên văn] Bạn cho mình xin SDT hoặc Zalo để bên mình tư vấn chi tiết hơn nhé",
        "image_url": ""
    }
]

def seed_overviews():
    """Hàm nạp dữ liệu Overview vào bảng vector_faq"""
    print("🚀 Bắt đầu quá trình nạp dữ liệu Overview vào Database...")
    
    # 0. Xóa dữ liệu Overview cũ để tránh trùng lặp (không xóa cả bảng để giữ FAQ khác)
    try:
        with Session(engine) as session:
            print("🗑️ Đang xóa dữ liệu Overview cũ...")
            statement = delete(VectorFAQ).where(VectorFAQ.category == "Overview")
            session.exec(statement)
            session.commit()
    except Exception as e:
        print(f"⚠️ Cảnh báo khi xóa dữ liệu cũ: {e}")

    for item in OVERVIEWS:
        try:
            print(f"--- Đang xử lý: {item['sub_category']} ---")
            
            # 1. Tạo Vector Embedding cho đoạn văn bản
            embedding = embed_text(item['content'])
            
            # 2. Lưu vào bảng vector_faq
            insert_vector_faq(
                category="Overview",
                sub_category=item['sub_category'],
                content=item['content'],
                embedding=embedding,
                image_url=item['image_url']
            )
            
            print(f"✅ Đã nạp thành công: {item['sub_category']}")
            
        except Exception as e:
            print(f"❌ Lỗi khi xử lý {item['sub_category']}: {e}")

    print("\n✨ Hoàn tất quá trình nạp dữ liệu!")

if __name__ == "__main__":
    seed_overviews()

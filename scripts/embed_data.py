import os
import sys

# Thêm thư mục gốc vào PYTHONPATH để nhận diện thư mục src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from dotenv import load_dotenv
from src.utils.embeddings import get_embeddings_model
from src.db.database import init_db
from src.db.operations import insert_vector_faq
from sqlmodel import Session, text
from src.db.database import engine

load_dotenv()

def embed_csv_data():
    # 1. Khởi tạo Database (Tạo bảng nếu chưa có)
    print("🚀 Khởi tạo Database...")
    init_db()

    # Xóa dữ liệu cũ nhưng giữ lại Overview
    print("🧹 Đang làm sạch dữ liệu cũ (không phải Overview) trong vector_faq...")
    with Session(engine) as session:
        # Chỉ xóa những cái không phải Overview để giữ lại dữ liệu seed có ảnh
        session.execute(text("DELETE FROM vector_faq WHERE category != 'Overview'"))
        session.commit()

    # 2. Sử dụng Gemini Embeddings từ utils
    print("🧬 Khởi tạo Gemini Embeddings qua Utils...")
    embeddings_model = get_embeddings_model()

    # 3. Đọc dữ liệu từ file master
    file_path = "src/data/EMS_Fitness_Yoga_DB.csv"
    if os.path.exists(file_path):
        print(f"📖 Đang đọc file kiến thức tổng hợp: {file_path}")
        combined_df = pd.read_csv(file_path)
    else:
        print(f"❌ Không tìm thấy file master: {file_path}")
        return

    if combined_df.empty:
        print("❌ Không có dữ liệu để xử lý!")
        return

    # 4. Loại bỏ trùng lặp (chỉ bỏ những dòng giống hệt nhau hoàn toàn ở tất cả các cột)
    combined_df = combined_df.drop_duplicates().reset_index(drop=True)
    total_records = len(combined_df)
    print(f"✅ Tổng số bản ghi thực tế nạp vào Database: {total_records}")

    # 5. Xử lý và nạp dữ liệu
    for index, row in combined_df.iterrows():
        category = str(row.get('Category', ''))
        sub_category = str(row.get('Sub_Category', ''))
        content = str(row.get('Information_Chunk', ''))

        image_url = str(row.get('image_url', '')) if 'image_url' in combined_df.columns else None
        
        # Tạo chuỗi văn bản đầy đủ để AI hiểu ngữ cảnh tốt hơn
        full_text = f"Category: {category} | Sub-Category: {sub_category} | Content: {content}"
        
        print(f"🔄 Đang embedding dòng {index + 1}/{total_records}...")
        
        try:
            # Tạo vector từ Gemini
            vector = embeddings_model.embed_query(full_text)
            
            # Lưu vào Postgres qua ORM
            insert_vector_faq(
                category=category,
                sub_category=sub_category,
                content=content,
                embedding=vector,
                image_url=image_url if image_url and image_url != "nan" else None
            )
        except Exception as e:
            print(f"❌ Lỗi khi xử lý dòng {index + 1}: {e}")

    print("✨ Hoàn thành nạp dữ liệu RAG vào PostgreSQL!")

if __name__ == "__main__":
    embed_csv_data()

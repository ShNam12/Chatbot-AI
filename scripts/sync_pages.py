import os
import sys
import json

# Thêm đường dẫn gốc vào sys.path để có thể import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import Session, select
from src.db.database import engine
from src.db.models import FacebookPage
from src.db.operations import add_facebook_page

def import_from_json(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Lỗi: Không tìm thấy file {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            pages = json.load(f)
            
        print(f"🚀 Bắt đầu đồng bộ {len(pages)} Fanpage từ file JSON...")
        
        count = 0
        for p in pages:
            page_id = p.get("page_id")
            token = p.get("access_token")
            name = p.get("page_name")
            
            if page_id and token:
                add_facebook_page(page_id, token, name)
                count += 1
            else:
                print(f"⚠️ Bỏ qua 1 bản ghi do thiếu page_id hoặc access_token: {p}")
                
        print(f"✅ Hoàn thành! Đã đồng bộ thành công {count} Fanpage.")
        
    except Exception as e:
        print(f"❌ Có lỗi xảy ra khi đọc file JSON: {e}")

if __name__ == "__main__":
    # Đường dẫn mặc định
    default_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'facebook_pages.json')
    
    # Cho phép truyền đường dẫn file khác qua đối số
    target_file = sys.argv[1] if len(sys.argv) > 2 else default_path
    
    import_from_json(target_file)

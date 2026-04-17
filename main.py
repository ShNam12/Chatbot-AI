import uvicorn
import os

if __name__ == "__main__":
    # Đưa thư mục hiện tại (gốc dự án) vào PYTHONPATH để các absolute import src.* hoạt động
    # Tuy nhiên, thông thường chạy từ gốc sẽ tự động có . trong path.
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=8000, reload=True)

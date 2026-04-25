import uvicorn
import os

if __name__ == "__main__":
<<<<<<< HEAD
    # Đưa thư mục hiện tại (gốc dự án) vào PYTHONPATH để các absolute import src.* hoạt động
    # Tuy nhiên, thông thường chạy từ gốc sẽ tự động có . trong path.
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=8000, reload=True)
=======
    # Lấy cổng từ biến môi trường của Render (mặc định là 8000 nếu chạy local)
    port = int(os.getenv("PORT", 8000))
    # Chạy server (tắt reload vì trên production không cần thiết và tốn tài nguyên)
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=port, reload=False)
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

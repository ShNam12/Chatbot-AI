import uvicorn
import os

if __name__ == "__main__":
    # Lấy cổng từ biến môi trường của Render (mặc định là 8000 nếu chạy local)
    port = int(os.getenv("PORT", 8000))
    # Chạy server (tắt reload vì trên production không cần thiết và tốn tài nguyên)
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=port, reload=False)

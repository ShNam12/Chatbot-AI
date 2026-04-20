# 🏗️ Cấu trúc dự án Chatbot AI EMS

Tài liệu này mô tả kiến trúc và cách tổ chức các thư mục trong dự án Chatbot AI sử dụng FastAPI, LangGraph và PostgreSQL.

---

## 📂 Sơ đồ thư mục chính

```text
Chatbot-AI/
├── main.py                 # File entry point để khởi chạy ứng dụng
├── .env                    # Lưu trữ các biến môi trường (Secrets)
├── pyproject.toml          # Quản lý dependencies (sử dụng uv)
├── src/                    # Thư mục mã nguồn chính (Source code)
│   ├── api/                # Tầng giao tiếp (API Routes/Webhooks)
│   ├── config/             # Cấu hình hệ thống & Prompt AI
│   ├── core/               # Trái tim của ứng dụng (FastAPI setup)
│   ├── db/                 # Tương tác với cơ sở dữ liệu
│   ├── services/           # Business Logic & Dịch vụ bên thứ 3
│   └── utils/              # Các hàm bổ trợ (Helpers)
├── scripts/                # Các script hỗ trợ bảo trì, setup
└── venv/                   # Môi trường ảo Python
```

---

## 🛠️ Chi tiết các thành phần

### 1. `main.py`
Là file khởi chạy ứng dụng. Nó thiết lập `PYTHONPATH` và gọi server `uvicorn` để chạy app FastAPI từ thư mục `src/core/app.py`.

### 2. `src/api/`
- **`routes.py`**: Chứa các endpoints xử lý Webhook của Facebook Messenger.
    - `GET /webhook`: Dùng để xác thực (Verify Token) với Facebook.
    - `POST /webhook`: Tiếp nhận tin nhắn từ người dùng và đẩy vào luồng xử lý AI.

### 3. `src/config/`
- **`settings.py`**: Đọc và quản lý các biến từ file `.env`.
- **`prompts.py`**: Lưu trữ các câu lệnh hướng dẫn (System Prompts) cho AI.
- **`overview_config.py`**: Các cấu hình tổng quát khác.

### 4. `src/core/`
- **`app.py`**: Định nghĩa instance FastAPI, đăng ký các routes và các sự kiện `startup`/`shutdown` (như khởi tạo kết nối Database).

### 5. `src/db/`
- **`db_postgres.py`**: Chứa `PostgresManager` để quản lý kết nối PostgreSQL, thực hiện lưu trữ lịch sử tin nhắn và Vector Search (nếu có sử dụng pgvector).

### 6. `src/services/`
- **`function_call.py`**: Định nghĩa các "Tool" mà AI có thể gọi (như tra cứu thông tin, tính toán).
- **`ggsheet_service.py`**: Tích hợp với Google Sheets để đọc/ghi dữ liệu (ví dụ: báo cáo hoặc danh sách sản phẩm).

### 7. `src/utils/`
- **`helpers.py`**: Các hàm tiện ích dùng chung trong toàn bộ dự án (định dạng thời gian, xử lý chuỗi, v.v.).

---

## 🚀 Hướng dẫn cho thành viên mới

1. **Cài đặt môi trường**: Sử dụng `uv` hoặc `pip` để cài đặt dependencies từ `pyproject.toml`.
2. **Biến môi trường**: Copy file mẫu thành `.env` và điền đầy đủ các KEY (Google AI, Facebook Token).
3. **Phát triển**: Luôn viết logic nghiệp vụ trong `services/` và giữ cho `routes.py` gọn gàng nhất có thể.

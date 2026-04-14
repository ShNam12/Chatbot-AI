# Báo cáo Kiến trúc & Chức năng Hệ thống Chatbot Multi-Agent

Hệ thống chatbot của bạn được thiết kế dựa trên kiến trúc **Multi-Agent (Đa Đặc vụ)** chuyên biệt, sử dụng khung **LangGraph**, **Gemini**, và kết nối trực tiếp với nền tảng **Facebook Messenger** thông qua **FastAPI**. 

Dưới đây là sơ đồ cấu trúc thư mục và ý nghĩa chi tiết của từng thành phần trong hệ thống:

## 1. Sơ đồ Cấu trúc Thư mục

```text
d:\2025.2\Thực tập\
├── .env                    # Lưu trữ các biến môi trường bảo mật (API keys, Tokens)
├── app.py                  # Server FastAPI chạy Webhook giao tiếp với Messenger
├── function_call.py        # Logic lõi của hệ thống AI Đa Đặc vụ (Multi-Agent bằng LangGraph)
├── main.py                 # File entry point cơ bản của Project
├── data/                   # Thư mục lưu trữ nguồn dữ liệu thô
│   ├── diachi.csv          # File dữ liệu toạ độ, địa chỉ của các chi nhánh phòng tập
│   ├── cauhoi.csv          # File dữ liệu các câu hỏi thường gặp (FAQ)
│   ├── BankBotMulti.ipynb  # File Notebook thử nghiệm (Test/Draft)
│   └── Cấu trúc.png        # Hình ảnh sơ đồ cấu trúc hệ thống (nếu có)
├── kho_du_lieu_vector/     # Thư mục lưu trữ cơ sở dữ liệu Vector (ChromaDB)
│   ├── chroma.sqlite3      # Tập tin cơ sở dữ liệu của ChromaDB
│   └── (UUID Folder)       # Dữ liệu index vector (Embeddings) của ChromaDB
├── pyproject.toml          # File cấu hình môi trường và các gói thư viện phụ thuộc (sử dụng Uv)
└── uv.lock                 # File khóa phiên bản các thư viện chuẩn xác
```

## 2. Chi tiết Chức năng các Module

### 2.1. `app.py` (Kênh Giao Diện - API Service)
- Đóng vai trò là **Webhook Server** tiếp nhận sự kiện từ Facebook Messenger.
- **Xác thực Webhook:** Hỗ trợ Meta verify HTTP GET Request (`hub.verify_token`).
- **Lắng nghe tin nhắn:** Phân tích payload JSON gửi từ Meta, bóc tách ra văn bản người chat (`message_text`) và UID người gửi (`sender_id`).
- **Gọi AI & Gửi phản hồi:** Chuyển nội dung người chat cho khối xử lý trung tâm `get_agent_response()`, chắt lọc câu trả lời và sử dụng Graph API trả kết quả lại Messenger thông qua `send_message_to_facebook()`.

### 2.2. `function_call.py` (Bộ não AI - Core Logic)
Đây là hệ thống cốt lõi điều hướng AI, chia làm 2 làn (2 Agents) để giảm tải và tăng tính chính xác:
- **`agent_main` (Chuyên viên Fitness & Yoga):**
   - Nhiệm vụ: Tiếp nhận, tư vấn và trả lời các hỏi đáp, chuyên môn tập luyện.
   - Công cụ: `retrival_data()` truy xuất ChromaDB (`kho_du_lieu_vector`) để lấy thông tin từ kho tri thức về `cauhoi_faq`.
   - **Định tuyến (Routing):** Nếu câu hỏi liên quan đến việc tìm kiếm địa chỉ/chi nhánh, agent này sẽ không tự trả lời mà phát tín hiệu `HANDOFF:agent_diachi`.

- **`agent_diachi` (Chuyên gia Địa điểm & Chi nhánh):**
   - Nhiệm vụ: Xử lý riêng biệt mọi câu hỏi liên quan đến Vị trí/Tìm phòng tập.
   - Công cụ: `search_address()`. Agent này truy xuất toạ độ trong `diachi.csv`, áp dụng phân tích **Haversine** để tính toán xem phòng tập nào gần toạ độ của người dùng nhất và gợi ý lộ trình/bảng chỉ dẫn đi kèm khoảng cách (`distance_km`).

- **Quy trình Quản lý Trạng thái (LangGraph Workflow):** Toàn bộ hệ thống Graph được kiểm soát theo vòng lặp, kiểm tra phản hồi đầu ra thông qua hàm `should_continue`. Tiến trình dừng lại khi chạm tới `ANSWER` cuối cùng.

### 2.3. Cụm Dữ Liệu (`data/` & `kho_du_lieu_vector/`)
- Mọi câu hỏi thường gặp (như "tập bao nhiêu buổi") được nhúng (Embedding) sẵn thành Vector đưa vào ChromaDB để AI thực hiện **RAG** (Retrieval-Augmented Generation).
- Dữ liệu địa chỉ chi nhánh để trong CSV giúp AI chỉ lọc và tính toán theo bài toán khoảng cách, giảm tỷ lệ rủi ro/sai số khi tự suy luận. Độ vĩ (lat), kinh (lon) giúp hàm toán học trả ra chính xác nhất vị trí cách số km đến khách hàng.

## 3. Luồng hoạt động Tổng Quan của Hệ thống
1. Người dùng nhắn tin vào Fanpage Meta.
2. `app.py` nhận tín hiệu tại URL `/webhook` -> Lấy ra đoạn text user viết.
3. Chuyển text đó vào Graph `agent_main`.
4. `agent_main` phân tích logic:
   - Nếu là tư vấn: Chọn Action -> Dùng `retrival_data` -> Đọc ChromaDB -> Tổng hợp RAG -> `ANSWER`
   - Nếu là hỏi chi nhánh: Ra lệnh `HANDOFF` -> `agent_diachi` tiếp nhận.
5. `agent_diachi` được kích hoạt: Chọn Action -> Gọi `search_address` -> Tính toán toạ độ (Haversine) bằng DataFrame -> Đưa ra `ANSWER`.
6. Output cuối cùng trả về `app.py`, và `app.py` request Post ngược lại giao diện Messenger để User thấy tin nhắn mới nhất.

> [!NOTE] 
> Hệ thống hiện tại đang cứng cấu hình test toạ độ Hà Nội `{"lat": 21.0285, "lon": 105.8542}`. Để áp dụng thực tế, sau này ở Messenger webhooks cần lấy được location payload từ user hoặc cho phép người dùng gửi vĩ độ/kinh độ của họ để thay thế biến `user_location`.

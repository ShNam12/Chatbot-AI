# 📊 Thiết Kế Chat History Database

## Tổng Quan
Hệ thống lưu trữ lịch sử chat hoàn chỉnh cho phép theo dõi tất cả các cuộc hội thoại từ người dùng và bot, cùng với metadata liên quan.

---

## 1. Schema Bảng `chat_history`

### SQL Definition
```sql
CREATE TABLE chat_history (
    -- Khóa chính
    id SERIAL PRIMARY KEY,
    
    -- Thông tin người dùng
    sender_id VARCHAR NOT NULL,          -- Facebook PSID
    sender_name VARCHAR,                  -- Tên người dùng
    message_type VARCHAR NOT NULL,        -- 'user' hoặc 'bot'
    
    -- Nội dung tin nhắn
    message_text VARCHAR NOT NULL,        -- Nội dung tin nhắn từ user
    response_text VARCHAR,                -- Phản hồi của bot
    
    -- Facebook metadata
    message_id VARCHAR,                   -- Facebook message ID
    page_id VARCHAR,                      -- Facebook page ID
    
    -- Metadata về cuộc hội thoại
    intent VARCHAR,                       -- Ý định/nhu cầu của user
    category VARCHAR,                     -- Danh mục (từ FAQ)
    interest VARCHAR,                     -- Lĩnh vực quan tâm
    phone VARCHAR,                        -- Số điện thoại detect được
    
    -- Context và Tool usage
    context_data JSONB,                   -- Dữ liệu context từ RAG
    tool_used VARCHAR,                    -- Tool được sử dụng
    tool_response JSONB,                  -- Phản hồi từ tool
    
    -- Timestamp
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_sender_id (sender_id),
    INDEX idx_created_at (created_at),
    INDEX idx_sender_created (sender_id, created_at),
    INDEX idx_message_id (message_id)
);
```

### Mô Tả Các Cột

| Cột | Kiểu | Mô Tả | Bắt Buộc |
|-----|------|-------|---------|
| `id` | INT | Khóa chính tự động tăng | ✅ |
| `sender_id` | VARCHAR | Facebook PSID của người dùng | ✅ |
| `sender_name` | VARCHAR | Tên người dùng | ❌ |
| `message_type` | VARCHAR | Loại tin nhắn: "user" hoặc "bot" | ✅ |
| `message_text` | VARCHAR | Nội dung tin nhắn từ user | ✅ |
| `response_text` | VARCHAR | Phản hồi của bot | ❌ |
| `message_id` | VARCHAR | Facebook message ID | ❌ |
| `page_id` | VARCHAR | Facebook page ID | ❌ |
| `intent` | VARCHAR | Ý định/nhu cầu detect được | ❌ |
| `category` | VARCHAR | Danh mục FAQ | ❌ |
| `interest` | VARCHAR | Lĩnh vực quan tâm | ❌ |
| `phone` | VARCHAR | Số điện thoại detect được | ❌ |
| `context_data` | JSONB | Dữ liệu context từ RAG/tools | ❌ |
| `tool_used` | VARCHAR | Tool được sử dụng | ❌ |
| `tool_response` | JSONB | Phản hồi chi tiết từ tool | ❌ |
| `created_at` | TIMESTAMP | Thời gian tạo | ✅ |
| `updated_at` | TIMESTAMP | Thời gian cập nhật lần cuối | ❌ |

---

## 2. Model SQLModel

```python
class ChatHistory(SQLModel, table=True):
    __tablename__ = "chat_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: str = Field(index=True)
    sender_name: Optional[str] = Field(default=None)
    message_type: str = Field(default="user")  # "user" hoặc "bot"
    message_text: str
    response_text: Optional[str] = Field(default=None)
    message_id: Optional[str] = Field(default=None, index=True)
    page_id: Optional[str] = Field(default=None)
    
    intent: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    interest: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    
    context_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    tool_used: Optional[str] = Field(default=None)
    tool_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: Optional[datetime] = Field(default=None)
    
    __table_args__ = (
        Index('idx_sender_created', 'sender_id', 'created_at'),
        Index('idx_created_at', 'created_at'),
    )
```

---

## 3. Các Hàm Hoạt Động

### 3.1 Lưu Tin Nhắn Người Dùng
```python
from src.db.operations import save_user_message

chat_record = save_user_message(
    sender_id="123456789",
    sender_name="Nguyễn Văn A",
    message_text="Tôi muốn hỏi về sản phẩm X",
    message_id="mid.1234567890",
    page_id="page_id_123",
    interest="Sản phẩm",
    phone="0987654321"
)
# Output: 
# ✅ [ChatHistory] Đã lưu tin nhắn của user 123456789
# Returns: ChatHistory object với id mới
```

### 3.2 Lưu Phản Hồi Bot
```python
from src.db.operations import save_bot_message

bot_response = save_bot_message(
    sender_id="123456789",
    response_text="Chúng tôi có sản phẩm X với các tính năng...",
    category="Sản phẩm",
    intent="Hỏi thông tin sản phẩm",
    tool_used="retrival_data",
    tool_response={"content": "...", "score": 0.95},
    context_data={"search_result": [...]}
)
# Returns: ChatHistory object
```

### 3.3 Lấy Lịch Sử Chat
```python
from src.db.operations import get_chat_history

# Lấy 50 tin nhắn gần nhất
history = get_chat_history(sender_id="123456789", limit=50, offset=0)

# Duyệt qua từng tin nhắn
for chat in history:
    print(f"[{chat.message_type}] {chat.created_at}: {chat.message_text}")
```

### 3.4 Lấy Lịch Sử Gần Đây
```python
from src.db.operations import get_recent_chat_history

# Lấy tin nhắn từ 24 giờ trước
recent = get_recent_chat_history(sender_id="123456789", hours=24)
```

### 3.5 Thống Kê Người Dùng
```python
from src.db.operations import get_user_stats

stats = get_user_stats(sender_id="123456789")
# Output:
# {
#     "sender_id": "123456789",
#     "total_messages": 25,
#     "user_messages": 12,
#     "bot_messages": 13,
#     "tools_used": ["retrival_data", "search_address"],
#     "interests": ["Sản phẩm", "Dịch vụ"]
# }
```

### 3.6 Danh Sách Tất Cả Người Dùng Hoạt Động
```python
from src.db.operations import get_all_users_active

users = get_all_users_active()
# Output:
# [
#     {"sender_id": "111", "message_count": 45, "last_message_time": "2024-01-20..."},
#     {"sender_id": "222", "message_count": 32, "last_message_time": "2024-01-19..."},
#     ...
# ]
```

### 3.7 Xóa Lịch Sử Chat
```python
from src.db.operations import delete_user_chat_history

deleted_count = delete_user_chat_history(sender_id="123456789")
# Output: ✅ [ChatHistory] Đã xóa 25 tin nhắn của user 123456789
```

---

## 4. Ví Dụ Tích Hợp vào Routes

### File: `src/api/routes.py`

```python
from src.db.operations import (
    save_user_message,
    save_bot_message,
    get_chat_history,
    get_user_stats
)

def process_message(body):
    try:
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                recipient_id = messaging_event.get("recipient", {}).get("id")
                message = messaging_event.get("message", {})
                message_id = message.get("mid")
                message_text = message.get("text")

                # 1️⃣ Lưu tin nhắn của user
                if message_text:
                    save_user_message(
                        sender_id=sender_id,
                        sender_name=get_user_name(sender_id),  # Hàm existing
                        message_text=message_text,
                        message_id=message_id,
                        page_id=recipient_id,
                        interest=detect_and_update_interest(sender_id, message_text, user_interest_store),
                        phone=extract_phone(message_text)
                    )

                # 2️⃣ Xử lý và lấy phản hồi từ AI
                response_text = get_agent_response(sender_id, message_text)

                # 3️⃣ Lưu phản hồi của bot
                save_bot_message(
                    sender_id=sender_id,
                    response_text=response_text,
                    category="Tư vấn sản phẩm",
                    intent="Hỏi thông tin",
                    tool_used="retrival_data",
                    context_data={"query": message_text}
                )

                # 4️⃣ Gửi phản hồi tới user
                send_message_to_facebook(sender_id, recipient_id, response_text)

    except Exception as e:
        print(f"❌ Lỗi: {e}")
```

---

## 5. API Endpoints (Tùy Chọn)

Bạn có thể thêm các endpoint để lấy lịch sử chat:

```python
# File: src/api/routes.py

from fastapi import FastAPI, Query
from typing import List

app = FastAPI()

@app.get("/chat-history/{sender_id}")
async def get_user_chat_history(
    sender_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0)
):
    """Lấy lịch sử chat của người dùng"""
    from src.db.operations import get_chat_history
    
    history = get_chat_history(sender_id, limit=limit, offset=offset)
    return {
        "sender_id": sender_id,
        "count": len(history),
        "messages": [
            {
                "id": h.id,
                "message_type": h.message_type,
                "message_text": h.message_text[:100],  # Truncate
                "response_text": h.response_text[:100] if h.response_text else None,
                "intent": h.intent,
                "tool_used": h.tool_used,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ]
    }

@app.get("/user-stats/{sender_id}")
async def get_user_statistics(sender_id: str):
    """Lấy thống kê trò chuyện của người dùng"""
    from src.db.operations import get_user_stats
    
    stats = get_user_stats(sender_id)
    return stats

@app.get("/users/active")
async def get_active_users():
    """Lấy danh sách người dùng hoạt động"""
    from src.db.operations import get_all_users_active
    
    users = get_all_users_active()
    return {"total_users": len(users), "users": users}
```

---

## 6. Query Examples

### Truy Vấn Trực Tiếp SQL

```sql
-- Lấy 20 tin nhắn gần nhất của một user
SELECT * FROM chat_history 
WHERE sender_id = '123456789' 
ORDER BY created_at DESC 
LIMIT 20;

-- Thống kê tin nhắn theo loại
SELECT message_type, COUNT(*) as count 
FROM chat_history 
WHERE sender_id = '123456789' 
GROUP BY message_type;

-- Các tool được sử dụng nhiều nhất
SELECT tool_used, COUNT(*) as usage_count 
FROM chat_history 
WHERE tool_used IS NOT NULL 
GROUP BY tool_used 
ORDER BY usage_count DESC;

-- Lịch sử chat từ 7 ngày trước
SELECT * FROM chat_history 
WHERE sender_id = '123456789' 
AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- Tìm các user có lịch sử chat gần đây nhất
SELECT sender_id, COUNT(*) as message_count, MAX(created_at) as last_message
FROM chat_history 
GROUP BY sender_id 
ORDER BY last_message DESC 
LIMIT 10;
```

---

## 7. Migration Steps

### Bước 1: Database Tự động Update
Khi khởi động ứng dụng, hàm `init_db()` sẽ tự động tạo bảng:

```python
# Trong src/core/app.py
@app.on_event("startup")
async def startup_event():
    init_db()  # ✅ Tự động tạo chat_history nếu chưa có
```

### Bước 2: Kiểm Tra Bảng (Optional)
```sql
-- Kết nối PostgreSQL và chạy:
\dt  -- Xem danh sách bảng
\d chat_history  -- Xem cấu trúc bảng
SELECT * FROM chat_history LIMIT 5;  -- Xem dữ liệu
```

---

## 8. Performance Tips

1. **Indexing**: Bảng đã có index trên `sender_id`, `created_at`, `message_id` → Query nhanh
2. **JSON Storage**: `context_data` và `tool_response` dùng JSONB → Tìm kiếm hiệu quả
3. **Partition** (Nếu dữ liệu lớn):
   ```sql
   -- Partition table theo tháng
   CREATE TABLE chat_history_2024_01 PARTITION OF chat_history
   FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
   ```
4. **Archival**: Có thể archive dữ liệu cũ vào bảng riêng nếu cần

---

## 9. Backup & Restore

```bash
# Backup
pg_dump -U "username" -d "database_name" -t "chat_history" > chat_history_backup.sql

# Restore
psql -U "username" -d "database_name" < chat_history_backup.sql
```

---

## 10. Tóm Tắt

✅ **Đã thiết kế:**
- Bảng `chat_history` với 17 cột
- 9 hàm hoạt động chính
- Index tối ưu cho tìm kiếm nhanh
- Hỗ trợ metadata đầy đủ

✅ **Sẵn sàng:**
- Lưu/truy vấn lịch sử chat
- Thống kê người dùng
- Phân tích tool usage
- Export dữ liệu

💡 **Next Steps:**
1. Chạy app để tự động tạo bảng
2. Tích hợp save functions vào `routes.py`
3. Thêm API endpoints để lấy lịch sử
4. Monitor table size và optimize khi cần

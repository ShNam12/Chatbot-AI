-- SQL Script để khởi tạo Database cho Chatbot AI EMS
-- Lưu ý: Bạn cần chạy lệnh này trong Database PostgreSQL của mình

-- 1. Kích hoạt extension pgvector (Yêu cầu quyền superuser)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Bảng lưu trữ phiên làm việc của người dùng (Thay thế SQLite)
CREATE TABLE IF NOT EXISTS user_sessions (
    sender_id TEXT PRIMARY KEY,               -- ID người nhắn (PSID)
    last_customer_message_time TIMESTAMP,     -- Thời gian tin nhắn cuối
    last_overview_sent_time TIMESTAMP,        -- Thời gian gửi overview cuối
    last_bot_message_time TIMESTAMP,          -- Thời gian tin nhắn cuối từ bot
    page_id TEXT,                             -- ID Fanpage nhận tin
    message_id TEXT                            -- ID tin nhắn cuối
);

-- 3. Bảng lưu trữ kiến thức RAG (Thay thế ChromaDB)
-- Embedding dimension là 384 cho model ONNXMiniLM_L6_V2
CREATE TABLE IF NOT EXISTS vector_faq (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,                    -- Nội dung kiến thức
    metadata JSONB,                           -- Thông tin bổ sung (nguồn, danh mục...)
    embedding vector(384)                     -- Vector đại diện
);

-- 4. (Tùy chọn) Index để tìm kiếm vector nhanh hơn (IVFFlat)
-- Tính toán số lists phù hợp (ví dụ: sqrt(số dòng) hoặc số dòng/1000)
-- CREATE INDEX ON vector_faq USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 5. Ví dụ chèn dữ liệu test
-- INSERT INTO vector_faq (content, embedding) VALUES ('EMS Fitness có các gói tập Yoga cơ bản.', '[...vector_384_dimensions...]');

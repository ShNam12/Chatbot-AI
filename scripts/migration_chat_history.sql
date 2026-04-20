-- ============================================================
-- Chat History Schema - PostgreSQL Migration
-- ============================================================
-- File: scripts/migration_chat_history.sql
-- 
-- Chạy file này nếu bạn muốn tạo bảng thủ công thay vì để app tự động tạo
-- psql -U username -d database_name -f scripts/migration_chat_history.sql
--

-- ============================================================
-- 1. Create chat_history Table
-- ============================================================

CREATE TABLE IF NOT EXISTS chat_history (
    -- Primary Key
    id SERIAL PRIMARY KEY,
    
    -- User Information
    sender_id VARCHAR NOT NULL,          -- Facebook PSID
    sender_name VARCHAR,                  -- User's name
    message_type VARCHAR NOT NULL 
        CHECK (message_type IN ('user', 'bot')),  -- 'user' or 'bot'
    
    -- Message Content
    message_text VARCHAR NOT NULL,        -- User's message content
    response_text VARCHAR,                -- Bot's response
    
    -- Facebook Metadata
    message_id VARCHAR,                   -- Facebook message ID
    page_id VARCHAR,                      -- Facebook page ID
    
    -- Conversation Metadata
    intent VARCHAR,                       -- Detected intent/need
    category VARCHAR,                     -- FAQ category
    interest VARCHAR,                     -- User interest area
    phone VARCHAR,                        -- Detected phone number
    
    -- Context & Tool Usage
    context_data JSONB,                   -- RAG context data
    tool_used VARCHAR,                    -- Tool used (retrival_data, search_address, etc)
    tool_response JSONB,                  -- Tool response details
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    CONSTRAINT chat_history_sender_id_not_empty CHECK (sender_id != ''),
    CONSTRAINT chat_history_message_text_not_empty CHECK (message_text != '')
);

-- ============================================================
-- 2. Create Indexes for Performance
-- ============================================================

-- Single column indexes
CREATE INDEX idx_chat_history_sender_id ON chat_history(sender_id);
CREATE INDEX idx_chat_history_created_at ON chat_history(created_at);
CREATE INDEX idx_chat_history_message_id ON chat_history(message_id);
CREATE INDEX idx_chat_history_message_type ON chat_history(message_type);
CREATE INDEX idx_chat_history_tool_used ON chat_history(tool_used);

-- Composite indexes
CREATE INDEX idx_chat_history_sender_created ON chat_history(sender_id, created_at DESC);
CREATE INDEX idx_chat_history_sender_type ON chat_history(sender_id, message_type);

-- Partial indexes (for common queries)
CREATE INDEX idx_chat_history_user_messages 
    ON chat_history(sender_id, created_at DESC)
    WHERE message_type = 'user';

CREATE INDEX idx_chat_history_bot_messages 
    ON chat_history(sender_id, created_at DESC)
    WHERE message_type = 'bot';

CREATE INDEX idx_chat_history_with_tools 
    ON chat_history(sender_id, created_at DESC)
    WHERE tool_used IS NOT NULL;

-- JSONB GIN index (for querying JSONB data efficiently)
CREATE INDEX idx_chat_history_context_data 
    ON chat_history USING GIN(context_data);
CREATE INDEX idx_chat_history_tool_response 
    ON chat_history USING GIN(tool_response);

-- ============================================================
-- 3. Create View: Recent Chat Summary
-- ============================================================

CREATE OR REPLACE VIEW v_recent_chat_summary AS
SELECT 
    ch.sender_id,
    ch.sender_name,
    COUNT(*) FILTER (WHERE ch.message_type = 'user') as user_message_count,
    COUNT(*) FILTER (WHERE ch.message_type = 'bot') as bot_message_count,
    COUNT(DISTINCT ch.interest) as interest_count,
    COUNT(DISTINCT ch.tool_used) as tool_count,
    MAX(ch.created_at) as last_message_time,
    DATE_TRUNC('hour', MAX(ch.created_at)) as last_hour_active
FROM chat_history ch
GROUP BY ch.sender_id, ch.sender_name
ORDER BY last_message_time DESC;

-- ============================================================
-- 4. Create View: Tool Usage Statistics
-- ============================================================

CREATE OR REPLACE VIEW v_tool_usage_stats AS
SELECT 
    tool_used,
    COUNT(*) as usage_count,
    COUNT(DISTINCT sender_id) as unique_users,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM chat_history WHERE tool_used IS NOT NULL), 2) as percentage,
    MAX(created_at) as last_used,
    AVG(LENGTH(response_text)) as avg_response_length
FROM chat_history
WHERE tool_used IS NOT NULL
GROUP BY tool_used
ORDER BY usage_count DESC;

-- ============================================================
-- 5. Create View: Interest Distribution
-- ============================================================

CREATE OR REPLACE VIEW v_interest_distribution AS
SELECT 
    interest,
    COUNT(*) as message_count,
    COUNT(DISTINCT sender_id) as user_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM chat_history WHERE interest IS NOT NULL), 2) as percentage
FROM chat_history
WHERE interest IS NOT NULL
GROUP BY interest
ORDER BY message_count DESC;

-- ============================================================
-- 6. Create Function: Get User Chat Timeline
-- ============================================================

CREATE OR REPLACE FUNCTION get_user_chat_timeline(
    p_sender_id VARCHAR,
    p_days INT DEFAULT 30
)
RETURNS TABLE (
    date DATE,
    message_count INT,
    user_msg_count INT,
    bot_msg_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        DATE(ch.created_at) as date,
        COUNT(*) as message_count,
        COUNT(*) FILTER (WHERE ch.message_type = 'user') as user_msg_count,
        COUNT(*) FILTER (WHERE ch.message_type = 'bot') as bot_msg_count
    FROM chat_history ch
    WHERE ch.sender_id = p_sender_id
        AND ch.created_at >= NOW() - (p_days || ' days')::INTERVAL
    GROUP BY DATE(ch.created_at)
    ORDER BY DATE(ch.created_at) DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 7. Create Function: Auto-update updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_chat_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
CREATE TRIGGER trig_chat_history_updated_at
BEFORE UPDATE ON chat_history
FOR EACH ROW
EXECUTE FUNCTION update_chat_history_updated_at();

-- ============================================================
-- 8. Verify Installation
-- ============================================================

-- Kiểm tra bảng được tạo thành công
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_history'
ORDER BY ordinal_position;

-- Kiểm tra indexes
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename = 'chat_history'
ORDER BY indexname;

-- ============================================================
-- 9. Sample Data (For Testing)
-- ============================================================

-- Thêm dữ liệu mẫu
INSERT INTO chat_history (
    sender_id, sender_name, message_type, message_text, 
    response_text, interest, category, tool_used, created_at
) VALUES 
(
    '123456789', 
    'Nguyễn Văn A',
    'user',
    'Tôi muốn hỏi về sản phẩm X',
    NULL,
    'Sản phẩm',
    NULL,
    NULL,
    NOW() - INTERVAL '2 hours'
),
(
    '123456789',
    'Nguyễn Văn A', 
    'bot',
    'Sản phẩm X có các tính năng: ...',
    NULL,
    'Sản phẩm',
    'Hỏi thông tin',
    'retrival_data',
    NOW() - INTERVAL '1.99 hours'
),
(
    '987654321',
    'Trần Thị B',
    'user',
    'Các chi nhánh ở đâu?',
    NULL,
    'Địa chỉ',
    NULL,
    NULL,
    NOW() - INTERVAL '1 hour'
),
(
    '987654321',
    'Trần Thị B',
    'bot',
    'Chi nhánh gần nhất là ...',
    NULL,
    'Địa chỉ',
    'Hỏi địa chỉ',
    'search_address',
    NOW() - INTERVAL '0.99 hours'
);

-- ============================================================
-- 10. Backup & Restore Commands
-- ============================================================

-- Backup table
-- pg_dump -U username -d database_name -t chat_history > chat_history_backup.sql

-- Restore table  
-- psql -U username -d database_name < chat_history_backup.sql

-- Backup with data
-- pg_dump -U username -d database_name -t chat_history --data-only > chat_history_data.sql

-- ============================================================
-- Done! ✅
-- ============================================================
-- 
-- Bảng chat_history đã được tạo với:
-- ✅ 17 cột để lưu trữ đầy đủ thông tin
-- ✅ 9 indexes để tăng hiệu suất query
-- ✅ 3 views để phân tích dữ liệu
-- ✅ 1 function để lấy timeline
-- ✅ 1 trigger để tự động cập nhật timestamp
-- 
-- Tiếp theo:
-- 1. Tích hợp save functions vào routes.py
-- 2. Test bằng cách gửi tin nhắn
-- 3. Kiểm tra dữ liệu trong bảng
--

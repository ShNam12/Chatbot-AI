-- Fix Chat History Schema
-- File: scripts/fix_chat_history_schema.sql
-- 
-- Chạy: psql -U username -d database_name -f scripts/fix_chat_history_schema.sql
--

-- ============================================================
-- Fix 1: Make message_text nullable (for bot messages)
-- ============================================================

ALTER TABLE chat_history 
ALTER COLUMN message_text DROP NOT NULL;

-- Verify change
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'chat_history'
AND column_name = 'message_text';

-- Expected output:
-- column_name  | data_type         | is_nullable
-- -------------|-------------------|----------
-- message_text | character varying | YES

-- ============================================================
-- Done! ✅
-- ============================================================
-- 
-- Giờ bạn có thể:
-- - Save user message với message_text
-- - Save bot message với message_text = NULL
--

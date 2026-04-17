import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

class PostgresManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PostgresManager, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD")
            )
            print("✅ PostgreSQL Connection Pool initialized")
        except Exception as e:
            print(f"❌ Error initializing PostgreSQL Pool: {e}")
            self.pool = None

    def get_connection(self):
        if self.pool:
            return self.pool.getconn()
        return None

    def release_connection(self, conn):
        if self.pool and conn:
            self.pool.putconn(conn)

    def init_db(self):
        """Khởi tạo các bảng cần thiết"""
        conn = self.get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # 1. Bật extension pgvector
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # 2. Tạo bảng lưu user sessions
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        sender_id TEXT PRIMARY KEY,
                        last_customer_message_time TIMESTAMP,
                        last_overview_sent_time TIMESTAMP,
                        page_id TEXT,
                        message_id TEXT
                    );
                """)
                
                # 3. Tạo bảng lưu kiến thức (Vector DB)
                # Lưu ý: vector(384) vì ONNXMiniLM_L6_V2 trả về 384 dimensions
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vector_faq (
                        id SERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector(384)
                    );
                """)
                
                conn.commit()
                print("✅ PostgreSQL Tables initialized")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error initializing tables: {e}")
        finally:
            self.release_connection(conn)

    # --- USER SESSION METHODS ---

    def save_conversation(self, sender_id: str, page_id: str, message_id: str):
        conn = self.get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                current_time = datetime.now()
                cur.execute("""
                    INSERT INTO user_sessions (sender_id, last_customer_message_time, page_id, message_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (sender_id) DO UPDATE SET
                        last_customer_message_time = EXCLUDED.last_customer_message_time,
                        page_id = EXCLUDED.page_id,
                        message_id = EXCLUDED.message_id;
                """, (sender_id, current_time, page_id, message_id))
                conn.commit()
                print(f"✅ [Postgres] Đã lưu/cập nhật session cho {sender_id}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error saving conversation: {e}")
        finally:
            self.release_connection(conn)

    def should_send_overview(self, sender_id: str, hours: float = 24):
        conn = self.get_connection()
        if not conn: return True
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT last_overview_sent_time FROM user_sessions WHERE sender_id = %s", (sender_id,))
                row = cur.fetchone()
                if not row or not row[0]:
                    return True
                last_time = row[0]
                return (datetime.now() - last_time) > timedelta(hours=hours)
        except Exception as e:
            print(f"❌ Error checking overview: {e}")
            return True
        finally:
            self.release_connection(conn)

    def mark_overview_sent(self, sender_id: str):
        conn = self.get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE user_sessions SET last_overview_sent_time = %s WHERE sender_id = %s", (datetime.now(), sender_id))
                conn.commit()
                print(f"✅ [Postgres] Đã cập nhật gửi overview cho {sender_id}")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error marking overview: {e}")
        finally:
            self.release_connection(conn)

    # --- VECTOR METHODS ---

    def search_faq(self, query_embedding, limit=1):
        """Tìm kiếm kiến thức bằng vector"""
        conn = self.get_connection()
        if not conn: return []
        try:
            with conn.cursor() as cur:
                # Sử dụng toán tử <=> (cosine distance) của pgvector
                cur.execute("""
                    SELECT content FROM vector_faq 
                    ORDER BY embedding <=> %s::vector 
                    LIMIT %s;
                """, (query_embedding, limit))
                results = cur.fetchall()
                return [r[0] for r in results]
        except Exception as e:
            print(f"❌ Error searching FAQ in Postgres: {e}")
            return []
        finally:
            self.release_connection(conn)

db_manager = PostgresManager()

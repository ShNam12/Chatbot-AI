import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, text
from sqlalchemy.orm import sessionmaker

# Import toàn bộ models để tất cả bảng được đăng ký vào metadata
from . import models  # noqa: F401 - cần import để SQLModel.metadata biết các bảng

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    from sqlalchemy import inspect, Text
    from sqlalchemy.dialects.postgresql import JSONB

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Tạo bảng mới nếu chưa có
    SQLModel.metadata.create_all(engine)

    # Auto-migrate: thêm cột mới vào bảng đã tồn tại
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name, table in SQLModel.metadata.tables.items():
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default_clause = ""
                    if col.default is not None and hasattr(col.default, "arg"):
                        default_clause = f"DEFAULT {col.default.arg!r}"
                    conn.execute(text(
                        f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS '
                        f'"{col.name}" {col_type} {default_clause} {nullable}'
                    ))
                    print(f"  ➕ Đã thêm cột '{col.name}' vào bảng '{table_name}'")
        conn.commit()

    # pgvector HNSW/IVFFLAT chỉ hỗ trợ tối đa 2000 dims, embedding 3072 dims → dùng sequential scan
    # Sequential scan đủ nhanh cho dataset FAQ vừa nhỏ (<10k rows)

    print("✅ Database initialized successfully")

def get_session():
    with Session(engine) as session:
        yield session

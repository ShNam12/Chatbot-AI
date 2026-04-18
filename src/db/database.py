import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, text
from sqlalchemy.orm import sessionmaker

# Import các models
from .models import UserSession, VectorFAQ

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # Tạo bảng trong CSDL nếu chưa có <3
    SQLModel.metadata.create_all(engine)
    print("✅ Database initialized successfully")

def get_session():
    with Session(engine) as session:
        yield session

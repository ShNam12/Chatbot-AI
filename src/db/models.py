from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from pgvector.sqlalchemy import Vector
from datetime import datetime

class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    
    sender_id: str = Field(primary_key=True)
    last_customer_message_time: Optional[datetime] = Field(default=None)
    last_overview_sent_time: Optional[datetime] = Field(default=None)
    page_id: Optional[str] = Field(default=None)
    message_id: Optional[str] = Field(default=None)
    
    address: Optional[str] = Field(default=None)
    lat: Optional[float] = Field(default=None)
    lon: Optional[float] = Field(default=None)
    address_updated_at: Optional[datetime] = Field(default=None)

class VectorFAQ(SQLModel, table=True):
    __tablename__ = "vector_faq"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str
    sub_category: str
    intent: str
    content: str
    keywords: Optional[str] = Field(default=None)
    extra_info: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    embedding: List[float] = Field(sa_column=Column(Vector(3072)))

class EmsBranch(SQLModel, table=True):
    __tablename__ = "ems_branch"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)          # CS1, CS2, ...
    address: str                             # Địa chỉ đầy đủ text
    district: Optional[str] = Field(default=None)   # Quận/Huyện
    city: Optional[str] = Field(default=None)        # Thành phố
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    is_active: bool = Field(default=True)


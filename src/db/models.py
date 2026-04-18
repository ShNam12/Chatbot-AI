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

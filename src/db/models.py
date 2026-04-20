from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from sqlalchemy import Index, ForeignKey

class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"
    
    sender_id: str = Field(primary_key=True)
    last_customer_message_time: Optional[datetime] = Field(default=None)
    last_overview_sent_time: Optional[datetime] = Field(default=None)
    last_bot_message_time: Optional[datetime] = Field(default=None)
    page_id: Optional[str] = Field(default=None)
    message_id: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None)


# ============================================================
# 📊 Optimized 3-Table Chat History Schema
# ============================================================

class User(SQLModel, table=True):
    """Bảng lưu thông tin người dùng"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: str = Field(unique=True, index=True)  # Facebook PSID
    sender_name: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    interest: Optional[str] = Field(default=None)
    page_id: Optional[str] = Field(default=None)  # Facebook page ID
    
    # Metadata
    first_message_at: Optional[datetime] = Field(default=None)
    last_message_at: Optional[datetime] = Field(default=None)
    total_messages: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    updated_at: Optional[datetime] = Field(default=None)
    
    # Relationship
    conversations: List["Conversation"] = Relationship(back_populates="user")
    
    __table_args__ = (
        Index('idx_user_created', 'created_at'),
    )


class Conversation(SQLModel, table=True):
    """Bảng lưu cuộc đối thoại"""
    __tablename__ = "conversations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)  # Liên kết tới users
    
    # Metadata cuộc hội thoại
    category: Optional[str] = Field(default=None)  # Danh mục chủ đề
    intent: Optional[str] = Field(default=None)   # Ý định/nhu cầu
    topic: Optional[str] = Field(default=None)    # Chủ đề chính
    
    # Trạng thái
    message_count: int = Field(default=0)  # Số tin nhắn trong cuộc
    
    started_at: datetime = Field(default_factory=datetime.now, index=True)
    ended_at: Optional[datetime] = Field(default=None)
    
    # Relationship
    user: Optional[User] = Relationship(back_populates="conversations")
    messages: List["Message"] = Relationship(back_populates="conversation", cascade_delete=True)
    
    __table_args__ = (
        Index('idx_conversation_user_started', 'user_id', 'started_at'),
    )


class Message(SQLModel, table=True):
    """Bảng lưu từng tin nhắn"""
    __tablename__ = "messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    
    # Thông tin tin nhắn
    message_type: str = Field(index=True)  # "user" hoặc "bot"
    content: str  # Nội dung tin nhắn
    
    # Facebook metadata
    fb_message_id: Optional[str] = Field(default=None)
    
    # Nếu là user message
    phone_detected: Optional[str] = Field(default=None)
    
    # Nếu là bot message
    tool_used: Optional[str] = Field(default=None)
    tool_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    context_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    
    # Relationship
    conversation: Optional[Conversation] = Relationship(back_populates="messages")
    
    __table_args__ = (
        Index('idx_message_conversation_created', 'conversation_id', 'created_at'),
        Index('idx_message_type', 'message_type'),
    )



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


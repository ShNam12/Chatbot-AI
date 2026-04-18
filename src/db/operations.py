from typing import List, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select, text
from .database import engine
from .models import UserSession, VectorFAQ, EmsBranch
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, func

def save_conversation(sender_id: str, page_id: str, message_id: str):
    """Lưu hoặc cập nhật session của người dùng"""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()
        
        current_time = datetime.now()
        if user_session:
            user_session.last_customer_message_time = current_time
            user_session.page_id = page_id
            user_session.message_id = message_id
        else:
            user_session = UserSession(
                sender_id=sender_id,
                last_customer_message_time=current_time,
                page_id=page_id,
                message_id=message_id
            )
            session.add(user_session)
        
        session.commit()
        print(f"✅ [Operations] Đã lưu/cập nhật session cho {sender_id}")

def should_send_overview(sender_id: str, hours: float = 24) -> bool:
    """Kiểm tra xem đã đến lúc gửi tin nhắn tổng quan chưa"""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()
        
        if not user_session or not user_session.last_overview_sent_time:
            return True
        
        last_time = user_session.last_overview_sent_time
        return (datetime.now() - last_time) > timedelta(hours=hours)

def mark_overview_sent(sender_id: str):
    """Đánh dấu đã gửi tin nhắn tổng quan"""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()
        
        if user_session:
            user_session.last_overview_sent_time = datetime.now()
            session.add(user_session)
            session.commit()
            print(f"✅ [Operations] Đã cập nhật gửi overview cho {sender_id}")

def search_faq(query_embedding: List[float], limit: int = 2) -> List[str]:
    """Tìm kiếm kiến thức bằng vector (Cosine Similarity) dùng pgvector ORM"""
    with Session(engine) as session:
        vec = cast(query_embedding, Vector(len(query_embedding)))
        statement = (
            select(VectorFAQ.content)
            .order_by(VectorFAQ.embedding.cosine_distance(vec))
            .limit(limit)
        )
        results = session.exec(statement).all()
        return list(results)

def insert_vector_faq(category: str, sub_category: str, intent: str, content: str, keywords: str, embedding: List[float]):
    """Chèn một bản ghi kiến thức mới vào database"""
    with Session(engine) as session:
        faq = VectorFAQ(
            category=category,
            sub_category=sub_category,
            intent=intent,
            content=content,
            keywords=keywords,
            embedding=embedding
        )
        session.add(faq)
        session.commit()

def upsert_branch(code: str, address: str,
                  district: Optional[str] = None, city: Optional[str] = None,
                  is_active: bool = True) -> EmsBranch:
    """Insert chi nhánh mới hoặc update nếu đã tồn tại (theo code)."""
    with Session(engine) as session:
        existing = session.exec(
            select(EmsBranch).where(EmsBranch.code == code)
        ).first()

        if existing:
            existing.address = address
            existing.district = district or existing.district
            existing.city = city or existing.city
            existing.is_active = is_active
            session.add(existing)
            session.commit()
            session.refresh(existing)
            print(f"♻️  [Branch] Đã cập nhật chi nhánh {code}")
            return existing
        else:
            branch = EmsBranch(
                code=code, address=address,
                district=district, city=city,
                is_active=is_active
            )
            session.add(branch)
            session.commit()
            session.refresh(branch)
            print(f"➕ [Branch] Đã thêm chi nhánh {code}: {address}")
            return branch


def get_all_branches() -> list[EmsBranch]:
    """Lấy tất cả chi nhánh đang hoạt động."""
    with Session(engine) as session:
        branches = session.exec(
            select(EmsBranch).where(EmsBranch.is_active == True)
        ).all()
        return list(branches)

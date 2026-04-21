from typing import List, Optional
from datetime import datetime, timedelta
from sqlmodel import Session, select, text
from .database import engine
# Đã gộp toàn bộ models của cả 2 file
from .models import UserSession, VectorFAQ, EmsBranch, User, Conversation, Message    
from pgvector.sqlalchemy import Vector
# Đã thêm desc từ file 2
from sqlalchemy import cast, func, desc

# ==================== SHARED BASE OPERATIONS ====================

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

def insert_vector_faq(category: str, sub_category: str, content: str, embedding: List[float]):
    """Chèn một bản ghi kiến thức mới vào database"""
    with Session(engine) as session:
        faq = VectorFAQ(
            category=category,
            sub_category=sub_category,
            content=content,
            embedding=embedding
        )
        session.add(faq)
        session.commit()


# ==================== BRANCH & LOCATION OPERATIONS (From File 1) ====================

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

def update_user_location(sender_id: str,
    address: str,
    lat: float,
    lon: float) -> UserSession:
    """Cập nhật địa chỉ và tọa độ của người dùng trong session."""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()

        if not user_session:
            user_session = UserSession(sender_id = sender_id)
            session.add(user_session)

        user_session.address = address
        user_session.lat = lat
        user_session.lon = lon
        user_session.address_updated_at = datetime.now()

        session.add(user_session)
        session.commit()
        session.refresh(user_session)

        print(f"📍 [Operations] Cập nhật vị trí cho {sender_id}: {address} ({lat}, {lon})")
        return user_session

def get_user_location(sender_id: str ) -> Optional[dict]:
    """Lấy vị trí của người dùng da luu trong session"""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()

        if not user_session:
            print(f"⚠️ Không tìm thấy session cho sender_id: {sender_id}")
            return None
        
        if user_session.lat is None or user_session.lon is None:
            return None
        
        return {
            "sender_id": user_session.sender_id,
            "address": user_session.address,
            "lat": user_session.lat,
            "lon": user_session.lon,
            "updated_at": user_session.address_updated_at,
        }


# ==================== 3-TABLE CHAT HISTORY OPERATIONS (From File 2) ====================

def get_or_create_user(
    sender_id: str,
    sender_name: Optional[str] = None,
    phone: Optional[str] = None,
    interest: Optional[str] = None,
    page_id: Optional[str] = None
) -> User:
    """Lấy hoặc tạo mới một người dùng"""
    with Session(engine) as session:
        statement = select(User).where(User.sender_id == sender_id)
        user = session.exec(statement).first()
        
        if user:
            if sender_name and not user.sender_name:
                user.sender_name = sender_name
            if phone and not user.phone:
                user.phone = phone
            if interest and not user.interest:
                user.interest = interest
            if page_id and not user.page_id:
                user.page_id = page_id
            user.last_message_at = datetime.now()
        else:
            user = User(
                sender_id=sender_id,
                sender_name=sender_name,
                phone=phone,
                interest=interest,
                page_id=page_id,
                first_message_at=datetime.now(),
                last_message_at=datetime.now(),
                total_messages=0
            )
            session.add(user)
        
        session.commit()
        session.refresh(user)
        return user


def get_or_create_conversation(
    user_id: int,
    category: Optional[str] = None,
    intent: Optional[str] = None,
    topic: Optional[str] = None
) -> Conversation:
    """Lấy hoặc tạo mới một cuộc trò chuyện (nếu chưa tồn tại hoặc đã kết thúc)"""
    with Session(engine) as session:
        statement = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.ended_at.is_(None)
            )
            .order_by(desc(Conversation.started_at))
        )
        conversation = session.exec(statement).first()
        
        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                category=category,
                intent=intent,
                topic=topic,
                message_count=0,
                started_at=datetime.now()
            )
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            print(f"✅ [Conversation] Tạo cuộc trò chuyện mới #{conversation.id} cho user #{user_id}")
        
        return conversation


def save_user_message(
    sender_id: str,
    sender_name: Optional[str] = None,
    message_text: str = "",
    message_id: Optional[str] = None,
    page_id: Optional[str] = None,
    interest: Optional[str] = None,
    phone: Optional[str] = None,
    category: Optional[str] = None,
    intent: Optional[str] = None,
) -> Message:
    """Lưu tin nhắn của người dùng (tạo User/Conversation nếu cần)"""
    with Session(engine) as session:
        try:
            user = get_or_create_user(
                sender_id=sender_id,
                sender_name=sender_name,
                phone=phone,
                interest=interest,
                page_id=page_id
            )
            
            conversation = get_or_create_conversation(
                user_id=user.id,
                category=category,
                intent=intent
            )
            
            message = Message(
                conversation_id=conversation.id,
                message_type="user",
                content=message_text,
                tool_used=None,
                fb_message_id=message_id,
                phone_detected=phone,
                tool_response=None,
                context_data=None,
                created_at=datetime.now()
            )
            session.add(message)
            
            conversation.message_count += 1
            user.total_messages += 1
            user.last_message_at = datetime.now()
            
            session.commit()
            session.refresh(message)
            print(f"✅ [Message] Lưu tin nhắn user: {sender_id} -> Message #{message.id} (Conversation #{conversation.id})")
            return message
        
        except Exception as e:
            print(f"❌ [Message] Lỗi lưu tin nhắn user: {str(e)}")
            session.rollback()
            raise


def save_bot_message(
    sender_id: str,
    response_text: str,
    category: Optional[str] = None,
    intent: Optional[str] = None,
    tool_used: Optional[str] = None,
    tool_response: Optional[dict] = None,
    context_data: Optional[dict] = None,
) -> Message:
    """Lưu phản hồi của bot vào database"""
    with Session(engine) as session:
        try:
            statement = select(User).where(User.sender_id == sender_id)
            user = session.exec(statement).first()
            
            if not user:
                print(f"❌ [Message] User {sender_id} không tồn tại")
                raise ValueError(f"User {sender_id} not found")
            
            statement = (
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.ended_at.is_(None)
                )
                .order_by(desc(Conversation.started_at))
            )
            conversation = session.exec(statement).first()
            
            if not conversation:
                print(f"❌ [Message] Không tìm thấy cuộc trò chuyện cho user {sender_id}")
                raise ValueError(f"No active conversation for user {sender_id}")
            
            message = Message(
                conversation_id=conversation.id,
                message_type="bot",
                content=response_text,
                tool_used=tool_used,
                fb_message_id=None,
                phone_detected=None,
                tool_response=tool_response,
                context_data=context_data,
                created_at=datetime.now()
            )
            session.add(message)
            
            conversation.message_count += 1
            conversation.intent = intent or conversation.intent
            conversation.category = category or conversation.category
            user.total_messages += 1
            user.last_message_at = datetime.now()
            
            session.commit()
            session.refresh(message)
            print(f"✅ [Message] Lưu phản hồi bot cho {sender_id} -> Message #{message.id}")
            return message
        
        except Exception as e:
            print(f"❌ [Message] Lỗi lưu phản hồi bot: {str(e)}")
            session.rollback()
            raise


def get_user_messages(sender_id: str, limit: int = 50, offset: int = 0) -> List[Message]:
    """Lấy lịch sử tin nhắn của một người dùng"""
    with Session(engine) as session:
        statement = (
            select(Message)
            .join(Conversation)
            .join(User)
            .where(User.sender_id == sender_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
            .offset(offset)
        )
        results = session.exec(statement).all()
        return list(results)


def get_conversation_messages(conversation_id: int) -> List[Message]:
    """Lấy tất cả tin nhắn trong một cuộc trò chuyện"""
    with Session(engine) as session:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        results = session.exec(statement).all()
        return list(results)


def get_recent_chat_history(sender_id: str, hours: int = 24) -> List[Message]:
    """Lấy lịch sử chat gần đây của một người dùng (trong N giờ)"""
    with Session(engine) as session:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        statement = (
            select(Message)
            .join(Conversation)
            .join(User)
            .where(
                User.sender_id == sender_id,
                Message.created_at >= cutoff_time
            )
            .order_by(Message.created_at)
        )
        results = session.exec(statement).all()
        return list(results)


def get_all_users_active() -> List[dict]:
    """Lấy danh sách tất cả người dùng có lịch sử chat"""
    with Session(engine) as session:
        statement = (
            select(
                User.sender_id,
                User.sender_name,
                User.total_messages.label("message_count"),
                User.last_message_at.label("last_message_time")
            )
            .where(User.total_messages > 0)
            .order_by(desc(User.last_message_at))
        )
        results = session.exec(statement).all()
        return [
            {
                "sender_id": row[0],
                "sender_name": row[1],
                "message_count": row[2],
                "last_message_time": row[3]
            }
            for row in results
        ]


def get_user_stats(sender_id: str) -> dict:
    """Lấy thống kê trò chuyện của một người dùng"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.sender_id == sender_id)).first()
        if not user:
            return {"error": f"User {sender_id} not found"}
        
        total_messages = session.exec(
            select(func.count(Message.id))
            .join(Conversation)
            .where(Conversation.user_id == user.id)
        ).first() or 0
        
        user_messages = session.exec(
            select(func.count(Message.id))
            .join(Conversation)
            .where(
                Conversation.user_id == user.id,
                Message.message_type == "user"
            )
        ).first() or 0
        
        bot_messages = total_messages - user_messages
        
        conversation_count = session.exec(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user.id)
        ).first() or 0
        
        tools_used = session.exec(
            select(Message.tool_used)
            .join(Conversation)
            .where(
                Conversation.user_id == user.id,
                Message.tool_used.is_not(None)
            )
            .distinct()
        ).all()
        
        return {
            "sender_id": sender_id,
            "sender_name": user.sender_name,
            "total_messages": total_messages,
            "user_messages": user_messages,
            "bot_messages": bot_messages,
            "conversation_count": conversation_count,
            "tools_used": list(tools_used),
            "first_message_at": user.first_message_at,
            "last_message_at": user.last_message_at
        }


def get_active_conversations() -> List[dict]:
    """Lấy danh sách tất cả cuộc trò chuyện đang hoạt động (chưa kết thúc)"""
    with Session(engine) as session:
        statement = (
            select(
                Conversation.id,
                User.sender_id,
                User.sender_name,
                Conversation.category,
                Conversation.intent,
                Conversation.message_count,
                Conversation.started_at
            )
            .join(User)
            .where(Conversation.ended_at.is_(None))
            .order_by(desc(Conversation.started_at))
        )
        results = session.exec(statement).all()
        return [
            {
                "conversation_id": row[0],
                "sender_id": row[1],
                "sender_name": row[2],
                "category": row[3],
                "intent": row[4],
                "message_count": row[5],
                "started_at": row[6]
            }
            for row in results
        ]


def close_conversation(conversation_id: int) -> bool:
    """Đánh dấu kết thúc một cuộc trò chuyện"""
    with Session(engine) as session:
        conversation = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).first()
        
        if conversation and not conversation.ended_at:
            conversation.ended_at = datetime.now()
            session.add(conversation)
            session.commit()
            print(f"✅ [Conversation] Đã kết thúc cuộc trò chuyện #{conversation_id}")
            return True
        
        return False


def get_conversation_context(sender_id: str, max_messages: int = 10) -> str:
    """Lấy lịch sử chat gần đây để làm context cho LLM"""
    with Session(engine) as session:
        try:
            user = session.exec(select(User).where(User.sender_id == sender_id)).first()
            if not user:
                return ""
            
            conversation = session.exec(
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.ended_at.is_(None)
                )
                .order_by(desc(Conversation.started_at))
            ).first()
            
            if not conversation:
                return ""
            
            # Lấy N tin nhắn MỚI NHẤT (DESC)
            messages_list = session.exec(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(desc(Message.created_at))
                .limit(max_messages)
            ).all()
            
            if not messages_list:
                return ""
            
            # Đảo ngược lại để AI đọc theo đúng thứ tự thời gian (Cũ -> Mới)
            messages = list(messages_list)
            messages.reverse()
            
            history_lines = ["📋 Lịch sử trò chuyện gần đây:"]
            for msg in messages:
                if msg.message_type == "user":
                    history_lines.append(f"👤 User: {msg.content}")
                else:
                    history_lines.append(f"🤖 Bot: {msg.content}")
            
            return "\n".join(history_lines)
        
        except Exception as e:
            print(f"❌ [Context] Lỗi lấy history: {str(e)}")
            return ""


def delete_user_all_data(sender_id: str) -> dict:
    """Xóa toàn bộ dữ liệu của một người dùng (GDPR compliant)"""
    with Session(engine) as session:
        try:
            user = session.exec(select(User).where(User.sender_id == sender_id)).first()
            if not user:
                return {"error": f"User {sender_id} not found", "deleted": 0}
            
            conversations = session.exec(
                select(Conversation).where(Conversation.user_id == user.id)
            ).all()
            
            message_count = 0
            for conv in conversations:
                messages = session.exec(
                    select(Message).where(Message.conversation_id == conv.id)
                ).all()
                message_count += len(messages)
                for msg in messages:
                    session.delete(msg)
            
            conversation_count = len(conversations)
            for conv in conversations:
                session.delete(conv)
            
            session.delete(user)
            session.commit()
            
            print(f"✅ [GDPR] Đã xóa toàn bộ dữ liệu của user {sender_id}: {message_count} messages, {conversation_count} conversations")
            return {
                "sender_id": sender_id,
                "messages_deleted": message_count,
                "conversations_deleted": conversation_count,
                "user_deleted": True
            }
        
        except Exception as e:
            print(f"❌ [GDPR] Lỗi xóa dữ liệu user {sender_id}: {str(e)}")
            session.rollback()
            raise

def update_last_bot_message_time(sender_id: str):
    """Update the last bot message time for a user session"""
    with Session(engine) as session:
        statement = select(UserSession).where(UserSession.sender_id == sender_id)
        user_session = session.exec(statement).first()
        
        if user_session:
            user_session.last_bot_message_time = datetime.now()
            session.add(user_session)
            session.commit()
            print(f"✅ [Operations] Updated last bot message time for {sender_id}")
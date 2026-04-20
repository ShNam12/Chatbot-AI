# ✨ Example Integration: routes_with_chat_history.py
# 
# Đây là ví dụ của file routes.py đã được cập nhật để lưu chat history
# Bạn có thể sao chép các phần này vào routes.py thực tế

from fastapi import Request, Response, BackgroundTasks
import requests
import os
import re
from datetime import datetime
from src.services.function_call import get_agent_response
from src.db.operations import (
    save_conversation,
    should_send_overview,
    mark_overview_sent,
    save_user_message,      # ✨ NEW
    save_bot_message,       # ✨ NEW
    get_chat_history,       # ✨ NEW
    get_user_stats          # ✨ NEW
)
from src.services.ggsheet_service import save_to_sheet
from src.config.overview_config import OVERVIEW_NESSAGE, IMAGE_OR_VIDEO, OVERVIEW_IMAGE_URL, OVERVIEW_VIDEO_URL
from src.config.settings import FB_GRAPH_BASE_URL, FB_GRAPH_VERSION
from src.utils.helpers import extract_phone, detect_and_update_interest

from dotenv import load_dotenv
load_dotenv()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

user_interest_store = {}

# ============================================================
# EXISTING FUNCTIONS (Giữ nguyên)
# ============================================================

async def verify_webhook(request: Request):
    """Facebook gọi vào đây để xác minh kết nối lần đầu"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Xác minh Webhook thành công!")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Xác minh thất bại", status_code=403)

def get_user_name(sender_id: str):
    """Lấy tên người dùng từ Facebook bằng PSID"""
    url = f"https://graph.facebook.com/{sender_id}?fields=first_name,last_name,name&access_token={PAGE_ACCESS_TOKEN}"
    print(f"DEBUG: Đang lấy tên cho sender_id: {sender_id}")

    try:
        response = requests.get(url)
        if response.status_code == 200:
            user_data = response.json()
            print(f"DEBUG: Dữ liệu Facebook trả về: {user_data}")
            
            full_name = user_data.get('name')
            first_name = user_data.get('first_name')
            last_name = user_data.get('last_name')

            if full_name:
                return full_name.strip()
            if first_name and last_name:
                return f"{last_name} {first_name}".strip()
                
            return first_name or last_name or "Khách hàng"
        else:
            print(f"❌ Lỗi khi lấy thông tin tên khách (Status {response.status_code}): {response.text}")
            if response.status_code == 400 and "does not exist" in response.text:
                print("💡 GỢI Ý: ID người dùng không tồn tại hoặc App đang ở Dev Mode mà người dùng này chưa được add làm Tester.")
            return "Khách hàng"
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API để lấy tên khách: {e}")
        return "Khách hàng"

def send_message_to_facebook(sender_id: str, recipient_id: str, message_text: str):
    """Gửi tin nhắn tới Facebook Messenger"""
    url = f"{FB_GRAPH_BASE_URL}/{FB_GRAPH_VERSION}/me/messages"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    data = {
        "recipient": {"id": sender_id},
        "message": {"text": message_text},
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"✅ Đã gửi tin nhắn tới {sender_id}")
        else:
            print(f"❌ Lỗi gửi tin nhắn: {response.text}")
    except Exception as e:
        print(f"❌ Exception khi gửi tin nhắn: {e}")

async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Nhận tin nhắn từ người dùng và phản hồi"""
    try:
        body = await request.json()

        if body.get("object") == "page":
            background_tasks.add_task(process_message, body)
            return Response(content="EVENT_RECEIVED", status_code=200)

        return Response(status_code=404)

    except Exception as e:
        print(f"Lỗi: {e}")
        return Response(status_code=500)


# ============================================================
# ✨ UPDATED: process_message với Chat History
# ============================================================

def process_message(body):
    try:
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):

                sender_id = messaging_event.get("sender", {}).get("id")
                recipient_id = messaging_event.get("recipient", {}).get("id")
                message = messaging_event.get("message", {})
                message_id = message.get("mid")
                message_text = message.get("text")

                print("----- MESSAGE EVENT -----")
                print("message_id    =", message_id)
                print("sender_id     =", sender_id)
                print("message_text  =", message_text)

                if sender_id and recipient_id and message_id:
                    # ✨ Lưu session (existing)
                    save_conversation(sender_id, recipient_id, message_id)

                customer_name = get_user_name(sender_id)
                print(f"Khách hàng: {customer_name}")

                if "message" in messaging_event and "text" in messaging_event["message"]:
                    message_text = messaging_event["message"]["text"]
                    interest = detect_and_update_interest(sender_id, message_text, user_interest_store)
                    interest_str = ", ".join(interest)
                    print(f"🎯 Interest: {interest_str}")
                    phone = extract_phone(message_text)

                    # ============================================================
                    # ✨ STEP 1: Lưu tin nhắn của user vào database
                    # ============================================================
                    try:
                        user_chat_record = save_user_message(
                            sender_id=sender_id,
                            sender_name=customer_name,
                            message_text=message_text,
                            message_id=message_id,
                            page_id=recipient_id,
                            interest=interest_str if interest else None,
                            phone=phone
                        )
                        print(f"✅ Đã lưu user message với ID: {user_chat_record.id}")
                    except Exception as e:
                        print(f"❌ Lỗi lưu user message: {e}")

                    # ============================================================
                    # ✨ STEP 2: Xử lý tin nhắn và lấy phản hồi từ AI
                    # ============================================================
                    try:
                        # Gọi hàm AI (existing)
                        response_text = get_agent_response(sender_id, message_text)
                        print(f"🤖 Bot response: {response_text}")
                        
                        # ============================================================
                        # ✨ STEP 3: Lưu phản hồi của bot vào database
                        # ============================================================
                        try:
                            bot_chat_record = save_bot_message(
                                sender_id=sender_id,
                                response_text=response_text,
                                category=None,  # Optional: có thể set từ AI
                                intent=interest_str if interest else None,
                                tool_used="retrival_data",  # Optional: detect từ AI
                                context_data={"query": message_text},
                                tool_response=None  # Optional
                            )
                            print(f"✅ Đã lưu bot message với ID: {bot_chat_record.id}")
                        except Exception as e:
                            print(f"❌ Lỗi lưu bot message: {e}")

                        # ============================================================
                        # ✨ STEP 4: Gửi tin nhắn tới Facebook
                        # ============================================================
                        send_message_to_facebook(sender_id, recipient_id, response_text)

                    except Exception as e:
                        print(f"❌ Lỗi xử lý AI: {e}")

                    # ============================================================
                    # ✨ OPTIONAL: Lưu vào Google Sheet (existing)
                    # ============================================================
                    try:
                        save_to_sheet(customer_name, message_text, phone)
                    except Exception as e:
                        print(f"❌ Lỗi lưu Google Sheet: {e}")

    except Exception as e:
        print(f"❌ Lỗi process_message: {e}")


# ============================================================
# ✨ NEW: API Endpoints để lấy Chat History
# ============================================================

# Thêm vào file routes.py:

async def get_chat_history_endpoint(request: Request, sender_id: str = None):
    """
    Endpoint để lấy lịch sử chat của một user
    Usage: GET /chat-history?sender_id=123456789&limit=50
    """
    try:
        limit = request.query_params.get("limit", 50)
        offset = request.query_params.get("offset", 0)
        
        if not sender_id:
            return Response(
                content="sender_id is required",
                status_code=400
            )
        
        history = get_chat_history(
            sender_id=sender_id,
            limit=int(limit),
            offset=int(offset)
        )
        
        # Format response
        messages = []
        for chat in history:
            messages.append({
                "id": chat.id,
                "type": chat.message_type,
                "sender_name": chat.sender_name,
                "text": chat.message_text if chat.message_type == "user" else chat.response_text,
                "interest": chat.interest,
                "category": chat.category,
                "tool_used": chat.tool_used,
                "phone": chat.phone,
                "created_at": chat.created_at.isoformat()
            })
        
        return Response(
            content=f'{{ "total": {len(messages)}, "messages": {messages} }}',
            media_type="application/json"
        )
        
    except Exception as e:
        print(f"❌ Lỗi GET chat history: {e}")
        return Response(
            content=f'{{ "error": "{str(e)}" }}',
            status_code=500
        )


async def get_user_stats_endpoint(request: Request, sender_id: str = None):
    """
    Endpoint để lấy thống kê của một user
    Usage: GET /user-stats?sender_id=123456789
    """
    try:
        if not sender_id:
            return Response(
                content="sender_id is required",
                status_code=400
            )
        
        stats = get_user_stats(sender_id=sender_id)
        
        return Response(
            content=f'{stats}',
            media_type="application/json"
        )
        
    except Exception as e:
        print(f"❌ Lỗi GET user stats: {e}")
        return Response(
            content=f'{{ "error": "{str(e)}" }}',
            status_code=500
        )


# ============================================================
# Cách đăng ký endpoints (thêm vào app.py):
# ============================================================
# 
# from src.api.routes import get_chat_history_endpoint, get_user_stats_endpoint
# 
# app.add_api_route("/chat-history", get_chat_history_endpoint, methods=["GET"])
# app.add_api_route("/user-stats", get_user_stats_endpoint, methods=["GET"])
#

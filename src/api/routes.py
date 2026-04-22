from fastapi import Request, Response, BackgroundTasks
import requests
import os
import re
from src.services.function_call import get_agent_response
# Đã gộp imports từ cả 2 file
from src.db.operations import (
    save_conversation, should_send_overview, mark_overview_sent, 
    save_user_message, save_bot_message, get_conversation_context, 
    update_last_bot_message_time, can_ask_phone, get_page_token,
    add_facebook_page, engine
)
from sqlmodel import Session, select
from src.db.models import FacebookPage
from src.services.ggsheet_service import save_to_sheet
from src.config.overview_config import OVERVIEW_NESSAGE, IMAGE_OR_VIDEO, OVERVIEW_IMAGE_URL, OVERVIEW_VIDEO_URL
from src.config.settings import FB_GRAPH_BASE_URL, FB_GRAPH_VERSION
from src.services.location_memory import handle_location_memory # Module location từ file 2
from src.utils.helpers import extract_phone, detect_and_update_interest

from dotenv import load_dotenv
load_dotenv()
PAGE_ACCESS_TOKEN_FALLBACK = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

user_interest_store = {}

async def verify_webhook(request: Request):
    """Facebook gọi vào đây để xác minh kết nối lần đầu"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Xác minh Webhook thành công!")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Xác minh thất bại", status_code=403)

def get_user_name(sender_id: str, access_token: str):
    """Lấy tên người dùng từ Facebook bằng PSID"""
    url = f"https://graph.facebook.com/{sender_id}?fields=first_name,last_name,name&access_token={access_token}"
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

                if sender_id and recipient_id and message_id:
                    save_conversation(sender_id, recipient_id, message_id)

                # Lấy Token của Page này từ Database
                access_token = get_page_token(recipient_id) or PAGE_ACCESS_TOKEN_FALLBACK
                if not access_token:
                    print(f"🛑 [Abort] Không tìm thấy Token cho Page {recipient_id}. Bỏ qua tin nhắn.")
                    continue

                customer_name = get_user_name(sender_id, access_token)
                print(f"Khách hàng: {customer_name} (Page: {recipient_id})")

                if "message" in messaging_event and "text" in messaging_event["message"]:
                    message_text = messaging_event["message"]["text"]
                    interest = detect_and_update_interest(sender_id, message_text, user_interest_store)
                    interest_str = ", ".join(interest)
                    print(f"🎯 Interest: {interest_str}")
                    phone = extract_phone(message_text)

                    # ========== XỬ LÝ SỐ ĐIỆN THOẠI ==========
                    if phone is False:
                        # 🚫 Tìm thấy nhưng SĐT sai format → Báo lỗi, yêu cầu nhập lại
                        print("❌ SĐT không hợp lệ (sai format)")
                        error_msg = "❌ Xin lỗi, số điện thoại bạn nhập không hợp lệ. Vui lòng nhập lại số điện thoại hợp lệ (0xxxxxxxxx)"
                        send_message_to_facebook(sender_id, error_msg, customer_name, page_id=recipient_id, access_token=access_token)
                        continue  # Không lưu DB, không gọi AI
                    
                    elif phone is not None and isinstance(phone, str):
                        # ✅ Tìm thấy và SĐT hợp lệ → Lưu sheet + Cảm ơn
                        print(f"📞 Phát hiện SĐT hợp lệ: {phone}")
                        try:
                            save_to_sheet(customer_name, phone, interest_str)
                            print(f"✅ Đã lưu vào Google Sheet")
                            send_thank_you_message(sender_id, access_token=access_token)
                        except Exception as e:
                            print(f"❌ Lỗi lưu Google Sheet: {e}")
                        continue  # Không lưu DB, không gọi AI
                    
                    # else: phone is None → Không tìm thấy SĐT → Continue với normal flow
                    else:
                        print(f"⚠️ Không phát hiện SĐT trong tin nhắn")

                    # 💾 SAVE USER MESSAGE TO DATABASE (Với phone=None nếu không tìm thấy)
                    try:
                        save_user_message(
                            sender_id=sender_id,
                            sender_name=customer_name,
                            message_text=message_text,
                            message_id=message_id,
                            page_id=recipient_id,
                            interest=interest_str if interest else None,
                            phone=phone if isinstance(phone, str) else None
                        )
                        print(f"✅ [ChatHistory] Đã lưu user message")
                    except Exception as e:
                        print(f"❌ [ChatHistory] Lỗi lưu user message: {e}")

                    send_sender_action(sender_id, "typing_on", access_token=access_token)

                    # 📍 Ghi nhớ vị trí (Từ File 2)
                    try:
                        location_result = handle_location_memory(sender_id, message_text)
                        print(f"[Location memory] {location_result}")
                    except Exception as e:
                        print(f"[Location memory] Bỏ qua do lỗi: {e}")
                    
                    # Lấy context lịch sử chat để AI hiểu được hội thoại (Từ File 1)
                    conversation_context = get_conversation_context(sender_id, max_messages=8)
                    
                    # Kiểm tra trạng thái có được hỏi SĐT không để tránh spam khách hàng (Anti-Spam)
                    ask_phone_flag = can_ask_phone(sender_id)
                    
                    #  Gọi AI với context và trạng thái SĐT
                    ai_reply = get_agent_response(
                        message_text, 
                        sender_id=sender_id, 
                        user_context=conversation_context,
                        can_ask_phone=ask_phone_flag
                    )
                    
                    send_sender_action(sender_id, "typing_off", access_token=access_token)
                    
                    # SAVE BOT MESSAGE TO DATABASE (Từ File 1)
                    try:
                        save_bot_message(
                            sender_id=sender_id,
                            response_text=ai_reply,
                            category=None,
                            intent=interest_str if interest else None,
                            tool_used="retrival_data" 
                        )
                        print(f"✅ [ChatHistory] Đã lưu bot message")
                    except Exception as e:
                        print(f"❌ [ChatHistory] Lỗi lưu bot message: {e}")
                    
                    send_message_to_facebook(sender_id, ai_reply, customer_name, page_id=recipient_id, access_token=access_token)

                    # Update last bot message time
                    update_last_bot_message_time(sender_id)

    except Exception as e:
        print(f"❌ Lỗi process_message: {e}")

def send_text_message(recipient_id: str, text: str, customer_name: str = None, access_token: str = None):
    if not access_token:
        access_token = PAGE_ACCESS_TOKEN_FALLBACK
        
    if not customer_name:
        customer_name = get_user_name(recipient_id, access_token)
        
    full_message = text.format(tag_name=customer_name)
    url = f"{FB_GRAPH_BASE_URL}/me/messages"
    params = {"access_token": access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": full_message}
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, params=params, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"📤 Đã gửi tin nhắn cho {recipient_id}: {text}")
            return True
        else:
            print(f"❌ Lỗi từ Facebook API: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API: {e}")
        return False

def send_message_to_facebook(recipient_id: str, text: str, customer_name: str = None, page_id: str = None, access_token: str = None):
    try:
        if not access_token and page_id:
            access_token = get_page_token(page_id) or PAGE_ACCESS_TOKEN_FALLBACK

        if should_send_overview(recipient_id):
            print(f"📨 Chưa gửi overview trong 24h cho {recipient_id}, gửi overview trước")
            overview_sent = send_text_message(recipient_id, OVERVIEW_NESSAGE, customer_name, access_token=access_token)
            send_media(recipient_id, access_token=access_token)
            if overview_sent:
                mark_overview_sent(recipient_id)
            else:
                print("❌ Gửi overview thất bại, bỏ qua cập nhật thời gian")
        else:
            print(f"✅ Đã gửi overview trong 24h cho {recipient_id}, bỏ qua overview")

        reply_sent = send_text_message(recipient_id, text, customer_name, access_token=access_token)
        
        # Đảm bảo record update bot time chạy đúng ở đây nếu reply sent (Từ File 1)
        if reply_sent:
            update_last_bot_message_time(recipient_id)
        else:
            print("❌ Gửi reply AI thất bại")

    except Exception as e:
        print(type(e))
        print(f"❌ Lỗi trong send_message_to_facebook: {e}")

def send_media(recipient_id: str, access_token: str = None):
    if IMAGE_OR_VIDEO == "image":
        return send_image_message(recipient_id, OVERVIEW_IMAGE_URL, access_token=access_token)
    elif IMAGE_OR_VIDEO == "video":
        return send_video_message(recipient_id, OVERVIEW_VIDEO_URL, access_token=access_token)
    else:
        print("❌ MEDIA_TYPE không hợp lệ")
        return False

def send_image_message(recipient_id: str, image_url: str, access_token: str = None):
    if not access_token: access_token = PAGE_ACCESS_TOKEN_FALLBACK
    url = f"{FB_GRAPH_BASE_URL}/me/messages"
    params = {"access_token": access_token}
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True}
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, params=params, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi hình ảnh: {e}")
        return False

def send_video_message(recipient_id: str, video_url: str, access_token: str = None):
    if not access_token: access_token = PAGE_ACCESS_TOKEN_FALLBACK
    url = f"{FB_GRAPH_BASE_URL}/me/messages"
    params = {"access_token": access_token}
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "video",
                "payload": {"url": video_url, "is_reusable": True}
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, params=params, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi video: {e}")
        return False

def send_thank_you_message(recipient_id: str, access_token: str = None):
    if not access_token: access_token = PAGE_ACCESS_TOKEN_FALLBACK
    text = "Cảm ơn bạn đã để lại thông tin, chuyên viên EMS sẽ liên hệ với bạn sớm nhất có thể!"
    url = f"{FB_GRAPH_BASE_URL}/me/messages?access_token={access_token}"
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi thank you: {e}")
        return False


def send_sender_action(recipient_id: str, action: str, access_token: str = None):
    if not access_token: access_token = PAGE_ACCESS_TOKEN_FALLBACK
    url = f"{FB_GRAPH_BASE_URL}/me/messages"
    params = {"access_token": access_token}
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action
    }
    headers = {"Content-Type": "application/json"}

    try:
        requests.post(url, params=params, json=payload, headers=headers)
    except Exception as e:
        print(f"❌ Lỗi sender_action: {e}")

# --- ADMIN API FOR MULTI-TENANT ---

async def admin_list_pages(request: Request):
    """Liệt kê toàn bộ Fanpage đang quản lý"""
    # Bạn nên thêm một lớp bảo mật ở đây (ví dụ check x-api-key)
    with Session(engine) as session:
        pages = session.exec(select(FacebookPage)).all()
        return {"total": len(pages), "pages": [p.dict() for p in pages]}

async def admin_add_page(request: Request):
    """Thêm hoặc cập nhật Token cho Fanpage"""
    data = await request.json()
    page_id = data.get("page_id")
    token = data.get("access_token")
    name = data.get("page_name")
    
    if not page_id or not token:
        return {"error": "Thiếu page_id hoặc access_token"}, 400
        
    try:
        add_facebook_page(page_id, token, name)
        return {"status": "success", "message": f"Đã cập nhật Page {page_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
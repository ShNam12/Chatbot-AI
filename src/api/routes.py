from fastapi import Request, Response, BackgroundTasks
import requests
import os
import re
from src.services.function_call import get_agent_response
from src.db.session_manager import save_conversation, should_send_overview, mark_overview_sent
from src.services.ggsheet_service import save_to_sheet
from src.config.overview_config import OVERVIEW_NESSAGE, IMAGE_OR_VIDEO, OVERVIEW_IMAGE_URL, OVERVIEW_VIDEO_URL
from src.utils.helpers import extract_phone, detect_interest

from dotenv import load_dotenv
load_dotenv()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

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

                customer_name = get_user_name(sender_id)
                print(f"Khách hàng: {customer_name}")

                if "message" in messaging_event and "text" in messaging_event["message"]:
                    message_text = messaging_event["message"]["text"]
                    interest = detect_interest(message_text)
                    print(f"🎯 Interest: {interest}")
                    phone = extract_phone(message_text)

                    if phone:
                        print(f"📞 Phát hiện SĐT: {phone}")
                        try:
                            save_to_sheet(customer_name, phone, interest)
                            print("✅ Đã lưu vào Google Sheet")
                            send_thank_you_message(sender_id)
                        except Exception as e:
                            print(f"❌ Lỗi lưu Google Sheet: {e}")
                        continue

                    ai_reply = get_agent_response(message_text)
                    send_message_to_facebook(sender_id, ai_reply, customer_name)

    except Exception as e:
        print(f"❌ Lỗi process_message: {e}")

def send_text_message(recipient_id: str, text: str, customer_name: str = None):
    if not customer_name:
        customer_name = get_user_name(recipient_id)
        
    full_message = text.format(tag_name=customer_name)
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {"text": full_message}
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"📤 Đã gửi tin nhắn cho {recipient_id}: {text}")
            return True
        else:
            print(f"❌ Lỗi từ Facebook API: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API: {e}")
        return False

def send_message_to_facebook(recipient_id: str, text: str, customer_name: str = None):
    try:
        if should_send_overview(recipient_id):
            print(f"📨 Chưa gửi overview trong 24h cho {recipient_id}, gửi overview trước")
            overview_sent = send_text_message(recipient_id, OVERVIEW_NESSAGE, customer_name)
            send_media(recipient_id)
            if overview_sent:
                mark_overview_sent(recipient_id)
            else:
                print("❌ Gửi overview thất bại, bỏ qua cập nhật thời gian")
        else:
            print(f"✅ Đã gửi overview trong 24h cho {recipient_id}, bỏ qua overview")

        reply_sent = send_text_message(recipient_id, text, customer_name)
        if not reply_sent:
            print("❌ Gửi reply AI thất bại")

    except Exception as e:
        print(f"❌ Lỗi trong send_message_to_facebook: {e}")

def send_media(recipient_id: str):
    if IMAGE_OR_VIDEO == "image":
        return send_image_message(recipient_id, OVERVIEW_IMAGE_URL)
    elif IMAGE_OR_VIDEO == "video":
        return send_video_message(recipient_id, OVERVIEW_VIDEO_URL)
    else:
        print("❌ MEDIA_TYPE không hợp lệ")
        return False

def send_image_message(recipient_id: str, image_url: str):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
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
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi hình ảnh: {e}")
        return False

def send_video_message(recipient_id: str, video_url: str):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
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
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi video: {e}")
        return False

def send_thank_you_message(recipient_id: str):
    text = "Cảm ơn bạn đã để lại thông tin, chuyên viên EMS sẽ liên hệ với bạn sớm nhất có thể!"
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
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

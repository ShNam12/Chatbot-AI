from fastapi import FastAPI, Request, Response, BackgroundTasks
import requests
import uvicorn
from function_call import get_agent_response # Gọi hàm AI bạn vừa bọc
from dotenv import load_dotenv
import os
load_dotenv()
from session_manager import init_db, save_conversation, should_send_overview, mark_overview_sent
from overview_config import OVERVIEW_NESSAGE, OVERVIEW_IMAGE_URL, OVERVIEW_VIDEO_URL, IMAGE_OR_VIDEO
import re
from ggsheet_service import save_to_sheet



app = FastAPI()

# ================= CẤU HÌNH BẢO MẬT =================
# 1. Mã do bạn tự đặt (Trùng với mã bạn sẽ điền trên web Meta)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# 2. Mã dài dằng dặc bạn đã Generate ở Fanpage
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
# ====================================================

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Facebook gọi vào đây để xác minh kết nối lần đầu"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Xác minh Webhook thành công!")
        # Facebook yêu cầu trả về nguyên văn challenge dưới dạng text
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Xác minh thất bại", status_code=403)

#----------------------------------------
#Khởi tạo database
init_db()
#---------------------------------------

# Nhận diện SDT trong tin nhắn (nếu có) để lưu vào Google Sheet
def extract_phone(text):
    pattern = r'(0|\+84)[0-9]{9}'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def get_user_name(sender_id: str):
    """Lấy tên người dùng từ Facebook bằng PSID"""
    url = f"https://graph.facebook.com/{sender_id}?fields=first_name,last_name&access_token={PAGE_ACCESS_TOKEN}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            user_data = response.json()
            first_name = user_data.get('first_name', 'Unknown')
            last_name = user_data.get('last_name', 'Unknown')
            return f"{last_name} {first_name} "
        else:
            print(f"❌ Lỗi khi lấy thông tin tên khách: {response.text}")
            return "Unknown"
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API để lấy tên khách: {e}")
        return "Unknown"

from fastapi import BackgroundTasks

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Nhận tin nhắn từ người dùng và phản hồi"""
    try:
        body = await request.json()

        if body.get("object") == "page":
            # Đẩy toàn bộ xử lý sang background
            background_tasks.add_task(process_message, body)

            # Trả 200 NGAY LẬP TỨC
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
                timestamp = messaging_event.get("timestamp")

                message = messaging_event.get("message", {})
                message_id = message.get("mid")
                message_text = message.get("text")

                print("----- MESSAGE EVENT -----")
                print("message_id    =", message_id)

                # Lưu DB
                if sender_id and recipient_id and message_id:
                    save_conversation(sender_id, recipient_id, message_id)

                # Lấy tên user
                customer_name = get_user_name(sender_id)
                print(f"Khách hàng: {customer_name}")

                # Chỉ xử lý text
                if "message" in messaging_event and "text" in messaging_event["message"]:
                    message_text = messaging_event["message"]["text"]

                    # Detect interest
                    interest = detect_interest(message_text)
                    print(f"🎯 Interest: {interest}")

                    phone = extract_phone(message_text)

                    # Nếu có SĐT → lưu + cảm ơn
                    if phone:
                        print(f"📞 Phát hiện SĐT: {phone}")

                        try:
                            save_to_sheet(customer_name, phone, interest)
                            print("✅ Đã lưu vào Google Sheet")

                            send_thank_you_message(sender_id)

                        except Exception as e:
                            print(f"❌ Lỗi lưu Google Sheet: {e}")

                        continue

                    # AI reply
                    ai_reply = get_agent_response(message_text)

                    # Gửi lại FB
                    send_message_to_facebook(sender_id, ai_reply)

    except Exception as e:
        print(f"❌ Lỗi process_message: {e}")

def send_text_message(recipient_id: str, text: str):

    customer_name = get_user_name(recipient_id)
    full_message = text.format(tag_name=customer_name)  # Gán tên vào tin nhắn

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
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

#-------------------- HÀM GỬI TIN NHẮN VĂN BẢN (AI REPLY) ------------------
def send_message_to_facebook(recipient_id: str, text: str):
    """
    Logic:
    - Nếu chưa gửi overview trong 24h -> gửi overview trước
    - Sau đó gửi luôn câu trả lời AI
    - Nếu đã gửi overview trong 24h -> chỉ gửi câu trả lời AI
    """

    try:
        # Bước 1: Kiểm tra có cần gửi overview không
        if should_send_overview(recipient_id):
            print(f"📨 Chưa gửi overview trong 24h cho {recipient_id}, gửi overview trước")

            overview_sent = send_text_message(recipient_id, OVERVIEW_NESSAGE) #Lệnh gửi tin nhắn overview

            media_sent = send_media(recipient_id)

            if overview_sent:
                mark_overview_sent(recipient_id)
            else:
                print("❌ Gửi overview thất bại, bỏ qua cập nhật thời gian")

        else:
            print(f"✅ Đã gửi overview trong 24h cho {recipient_id}, bỏ qua overview")

        # Bước 2: Gửi câu trả lời AI cho khách
        reply_sent = send_text_message(recipient_id, text)

        if not reply_sent:
            print("❌ Gửi reply AI thất bại")

    except Exception as e:
        print(f"❌ Lỗi trong send_message_to_facebook: {e}")


#------------------- HÀM GỬI TIN NHẮN HÌNH ẢNH (OVERVIEW) ------------------
def send_image_message(recipient_id: str, image_url: str):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": OVERVIEW_IMAGE_URL,
                    "is_reusable": True
                }
            }
        }
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"📤 Đã gửi hình ảnh cho {recipient_id}")
            return True
        else:
            print(f"❌ Lỗi từ Facebook API khi gửi hình ảnh: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API để gửi hình ảnh: {e}")
        return False
#-------------------- HÀM GỬI TIN NHẮN HÌNH ẢNH (OVERVIEW) ------------------       

#------------------- HÀM GỬI TIN NHẮN VIDEO (OVERVIEW) ------------------
def send_video_message(recipient_id: str, video_url: str):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "video",
                "payload": {
                    "url": OVERVIEW_VIDEO_URL,
                    "is_reusable": True
                }
            }
        }
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"📤 Đã gửi video cho {recipient_id}")
            return True
        else:
            print(f"❌ Lỗi từ Facebook API khi gửi video: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Không thể kết nối tới Facebook API để gửi video: {e}")
        return False
#-------------------- HÀM GỬI TIN NHẮN VIDEO (OVERVIEW) ------------------       

# kiểm tra cấu hình gửi video hay hình ảnh trong overview
def send_media(recipient_id: str):
    if IMAGE_OR_VIDEO == "image":
        return send_image_message(recipient_id, OVERVIEW_IMAGE_URL)
    elif IMAGE_OR_VIDEO == "video":
        return send_video_message(recipient_id, OVERVIEW_VIDEO_URL)
    else:
        print("❌ MEDIA_TYPE không hợp lệ")
        return False

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


#Hàm phát hiện sở thích của khách hàng dựa trên tin nhắn
def detect_interest(user_text: str) -> str:
    text = user_text.lower()

    # --- EMS ---
    if any(keyword in text for keyword in [
        "bơi", "bể bơi", "hồ bơi", "pool"
    ]):
        return "bơi & bể bơi"

    # --- Yoga ---
    if any(keyword in text for keyword in [
        "yoga", "thiền", "giãn cơ", "dẻo", "thư giãn"
    ]):
        return "yoga"

    # --- Giảm cân ---
    if any(keyword in text for keyword in [
        "giảm cân", "giảm mỡ", "đốt mỡ", "ốm", "gầy", "bụng mỡ", "mỡ bụng", "eo thon"
    ]):
        return "giảm cân"

    # --- Tăng cơ ---
    if any(keyword in text for keyword in [
        "tăng cơ", "lên cơ", "cơ bắp", "body", "to cơ", "6 múi"
    ]):
        return "tăng cơ"

    # --- Gym (chung chung) ---
    if any(keyword in text for keyword in [
        "gym", "tập luyện", "fitness", "phòng tập"
    ]):
        return "gym"
    
    # --- Nhảy (Dance) ---
    if any(keyword in text for keyword in [
        "nhảy", "dancing", "dance", "rumba"
    ]):
        return "Dance"

    # --- fallback ---
    return "chung"

def get_page_info():
    url = f"https://graph.facebook.com/v19.0/me?fields=name,link&access_token={PAGE_ACCESS_TOKEN}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                "name": data.get("name"),
                "link": data.get("link")
            }
        else:
            print("❌ Lỗi lấy page:", response.text)
            return None
    except Exception as e:
        print("❌ Exception:", e)
        return None


def send_thank_you_message(recipient_id: str):
    text = "Cảm ơn bạn đã để lại thông tin, chuyên viên EMS sẽ liên hệ với bạn sớm nhất có thể!"

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
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
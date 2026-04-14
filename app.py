from fastapi import FastAPI, Request, Response
import requests
import uvicorn
from function_call import get_agent_response # Gọi hàm AI bạn vừa bọc
from dotenv import load_dotenv
import os
load_dotenv()
from session_manager import init_db, save_conversation, should_send_overview, mark_overview_sent
from overview_config import OVERVIEW_NESSAGE



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

@app.post("/webhook")
async def receive_message(request: Request):
    """Nhận tin nhắn từ người dùng và phản hồi"""
    try:
        body = await request.json()

        #print("=== RAW WEBHOOK ===")

        if body.get("object") == "page":
            for entry in body.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    
                    # Lấy thông tin tin nhắn 

                    sender_id = messaging_event.get("sender", {}).get("id")
                    recipient_id = messaging_event.get("recipient", {}).get("id")
                    timestamp = messaging_event.get("timestamp")

                    message = messaging_event.get("message", {})
                    message_id = message.get("mid")
                    message_text = message.get("text")

                    print("----- MESSAGE EVENT -----")
                    #print("customer_psid =", sender_id)
                    #print("page_id       =", recipient_id)
                    print("message_id    =", message_id)
                    #print("timestamp     =", timestamp)
                    #print("text          =", message_text)

                    #Lưu/ cập nhật dữ liệu trò chuyện vào DB

                    if sender_id and recipient_id and message_id:
                        save_conversation(sender_id, recipient_id, message_id)

                    # Lấy tên người dùng
                    # Lấy tên khách hàng từ Facebook
                    customer_name = get_user_name(sender_id)
                    print(f"Khách hàng: {customer_name}")
                    
                    # Chỉ xử lý nếu có text message
                    if "message" in messaging_event and "text" in messaging_event["message"]:
                        sender_id = messaging_event["sender"]["id"]
                        message_text = messaging_event["message"]["text"]
                        
                        # --- 1. ĐƯA CHO AI SUY NGHĨ ---
                        ai_reply = get_agent_response(message_text)
                        
                        # --- 2. GỬI TIN NHẮN TRỞ LẠI FB ---
                        send_message_to_facebook(sender_id, ai_reply)
                        
            return Response(content="EVENT_RECEIVED", status_code=200)
        return Response(status_code=404)
        
    except Exception as e:
        print(f"Lỗi: {e}")
        return Response(status_code=500)

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

            overview_sent = send_text_message(recipient_id, OVERVIEW_NESSAGE)

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

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os

# Import các thành phần nội bộ
from src.db.database import init_db
from src.api.routes import verify_webhook, receive_message, admin_list_pages, admin_add_page

# Load environment variables
load_dotenv()

app = FastAPI(title="Chatbot AI EMS")

# Khởi tạo database
@app.on_event("startup")
async def startup_event():
    init_db()

# Đăng ký các route
app.add_api_route("/webhook", verify_webhook, methods=["GET"])
app.add_api_route("/webhook", receive_message, methods=["POST"])

# Admin routes cho đa Fanpage
app.add_api_route("/admin/pages", admin_list_pages, methods=["GET"])
app.add_api_route("/admin/pages", admin_add_page, methods=["POST"])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=port, reload=True)

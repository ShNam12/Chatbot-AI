from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os

# Import các thành phần nội bộ
from src.db.db_postgres import db_manager
from src.api.routes import verify_webhook, receive_message

# Load environment variables
load_dotenv()

app = FastAPI(title="Chatbot AI EMS")

# Khởi tạo database
@app.on_event("startup")
async def startup_event():
    db_manager.init_db()

# Đăng ký các route
app.add_api_route("/webhook", verify_webhook, methods=["GET"])
app.add_api_route("/webhook", receive_message, methods=["POST"])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=port, reload=True)

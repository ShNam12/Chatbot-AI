from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os

# Import các thành phần nội bộ
<<<<<<< HEAD
from src.db.db_postgres import db_manager
from src.api.routes import verify_webhook, receive_message
=======
from src.db.database import init_db
from src.api.routes import verify_webhook, receive_message, admin_list_pages, admin_add_page
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

# Load environment variables
load_dotenv()

app = FastAPI(title="Chatbot AI EMS")

# Khởi tạo database
@app.on_event("startup")
async def startup_event():
<<<<<<< HEAD
    db_manager.init_db()
=======
    init_db()
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

# Đăng ký các route
app.add_api_route("/webhook", verify_webhook, methods=["GET"])
app.add_api_route("/webhook", receive_message, methods=["POST"])

<<<<<<< HEAD
=======
# Admin routes cho đa Fanpage
app.add_api_route("/admin/pages", admin_list_pages, methods=["GET"])
app.add_api_route("/admin/pages", admin_add_page, methods=["POST"])

>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("src.core.app:app", host="0.0.0.0", port=port, reload=True)

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# ===== CONFIG =====
SHEET_NAME = "chatbot"
# Giả định chạy từ gốc dự án, credentials.json nằm ở gốc
CREDENTIAL_FILE = os.path.join(os.getcwd(), "credentials.json")

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        CREDENTIAL_FILE, scope
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def save_to_sheet(name, phone, interest, location):
    try:
        sheet = get_sheet()
        time_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        sheet.append_row([time_now, name, phone, interest, location])
        return True
    except Exception as e:
        print(f"❌ Lỗi ghi vào Google Sheet: {e}")
        print(type(e), e)
        return False

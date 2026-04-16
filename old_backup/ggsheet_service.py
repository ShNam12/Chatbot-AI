import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ===== CONFIG =====
SHEET_NAME = "chatbot"
CREDENTIAL_FILE = "credentials.json"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    CREDENTIAL_FILE, scope
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1


def save_to_sheet(name, phone, interest):
    time_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    sheet.append_row([time_now, name, phone, interest])
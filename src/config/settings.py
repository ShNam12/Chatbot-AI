import os

# Facebook Graph API Settings
FB_GRAPH_VERSION = "v19.0"
FB_GRAPH_BASE_URL = "https://graph.facebook.com"
FB_GRAPH_USER_PROFILE_URL = "https://graph.facebook.com/"

# AI Model Settings
AI_MODEL_NAME = "gemini-2.5-flash"
AI_REQUEST_TIMEOUT = 10
AI_MAX_STEPS = 5

# Location Settings (Default Hanoi)
DEFAULT_USER_COORD = {"lat": 21.0285, "lon": 105.8542}

# Path Settings
BASE_DIR = os.getcwd()
DIACHI_CSV_PATH = os.path.join(BASE_DIR, "data", "diachi.csv")

import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# Cấu hình tập trung cho Embedding Model
def get_embeddings_model():
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

def embed_text(text: str):
    """Hàm bổ trợ để chuyển đổi văn bản sang vector nhanh chóng"""
    model = get_embeddings_model()
    return model.embed_query(text)

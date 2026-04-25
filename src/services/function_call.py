import json
<<<<<<< HEAD
from src.db.db_postgres import db_manager
import pandas as pd
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from math import radians, sin, cos, sqrt, atan2
from typing import TypedDict
import os
from dotenv import load_dotenv
from src.config.settings import AI_MODEL_NAME, AI_REQUEST_TIMEOUT, AI_MAX_STEPS, DEFAULT_USER_COORD, DIACHI_CSV_PATH
from src.config.prompts import AGENT_MAIN_PROMPT, AGENT_DIACHI_PROMPT
=======
import os
import re
from typing import TypedDict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# Import các thành phần nội bộ
from src.config.settings import AI_MODEL_NAME, AI_REQUEST_TIMEOUT, AI_MAX_STEPS
from src.config.prompts import AGENT_MAIN_PROMPT, AGENT_DIACHI_PROMPT
from src.db.operations import save_conversation, search_faq
from src.utils.embeddings import get_embeddings_model
from src.services.search_address import search_address # Sử dụng module search_address đã được tách ra

>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

# AGENT SETUP
print("🔑 Cài đặt hệ thống AI")
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

<<<<<<< HEAD
=======
# Khởi tạo mô hình Chat LLM
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
llm = ChatGoogleGenerativeAI(
    model=AI_MODEL_NAME, 
    temperature=0,
    google_api_key=api_key,
    request_timeout=AI_REQUEST_TIMEOUT
)

<<<<<<< HEAD

print("✅ Đã kết nối thành công với Gemini!")

# 1. Khai báo lại hàm Embedding (Giữ nguyên để tạo vector query)
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
ef = ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])

def retrival_data(query):
    print("--- TOOL CALL: RETRIEVING CONTEXT FROM POSTGRES ---")
    
    # 1. Tạo embedding từ query người dùng
    query_embedding = ef([query])[0]
    
    # 2. Tìm kiếm vector trong PostgreSQL
    results = db_manager.search_faq(query_embedding, limit=1)
    
    if results:
        context_text = results[0]
    else:
        context_text = "Không tìm thấy thông tin liên quan trong cơ sở dữ liệu."
        
    return {"context": context_text, "source": "cauhoi"}

def search_address(user_location: str = "Hanoi,Vietnam", top_n: int = 3):
    """ Tìm kiếm các địa chỉ gần người cần tư vấn nhất"""
    print("--- TOOL CALL: SEARCHING ADDRESS ---")

    try: 
        if not os.path.exists(DIACHI_CSV_PATH):
            print(f"⚠️ Không tìm thấy file dữ liệu tại {DIACHI_CSV_PATH}")
            # Fallback nếu không có file CSV
            return {"context": "Hiện tại không có thông tin chi nhánh.", "source": "diachi"}
            
        df_br = pd.read_csv(DIACHI_CSV_PATH)
        print("✅ Đã tải thành công dữ liệu các chi nhánh!")
    except Exception as e:
        print(f"❌ Lỗi khi tải dữ liệu: {e}")
        return None

    user_lat, user_lon = DEFAULT_USER_COORD["lat"], DEFAULT_USER_COORD["lon"]

    def haversine(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c 

    filtered_df = df_br.copy()
    filtered_df['distance_km'] = filtered_df.apply(
        lambda row: haversine(user_lat, user_lon, row['latitude'], row['longitude']), axis=1
    )

    nearest = filtered_df.sort_values('distance_km').head(top_n)
    nearest["distance_km"] = nearest["distance_km"].round(2)
    results = nearest[['branch_name', 'branch_address', 'distance_km']].to_dict(orient='records')
    
    return {"context": results, "source": "diachi"}
=======
print("✅ Đã kết nối thành công với Gemini!")

# 1. Sử dụng Gemini Embeddings từ utils
print("🧬 Kết nối Gemini Embeddings qua Utils")
embeddings_model = get_embeddings_model()

def retrival_data(query):
    print(f"--- TOOL CALL: RETRIEVING CONTEXT FOR: {query} ---")
    
    try:
        # KIỂM TRA: Nếu tìm overview, hãy thử tìm chính xác theo sub_category trước
        if "overview" in query.lower():
            # Tách tên môn (ví dụ: overview Gym -> Gym)
            service_name = query.lower().replace("overview", "").strip()
            # Ánh xạ tên môn sang đúng nhãn sub_category trong DB
            from src.db.operations import get_faq_by_subcategory
            db_overview_dict = get_faq_by_subcategory(service_name.capitalize()) or get_faq_by_subcategory(service_name.upper()) or get_faq_by_subcategory(service_name)
            
            if db_overview_dict:
                print(f"🎯 Đã tìm thấy chính xác Overview cho môn {service_name}")
                content = db_overview_dict["content"]
                image_url = db_overview_dict.get("image_url")
                if image_url and query.lower().startswith("overview"):
                    content = f"{content}\n[IMAGE_URL: {image_url}]"
                return {"context": content, "source": "overview_match"}

        # Nếu không tìm thấy đích danh, quay lại dùng tìm kiếm Vector như cũ
        query_embedding = embeddings_model.embed_query(query)
        results = search_faq(query_embedding, limit=10)
        
        if results:
            # Kiểm tra từ khóa cụ thể
            SPECIFIC_KEYWORDS = ["giá", "phí", "tiền", "lịch", "địa chỉ", "cơ sở", "chi nhánh"]
            is_specific = any(kw in query.lower() for kw in SPECIFIC_KEYWORDS)
            is_overview_request = query.lower().startswith("overview")

            # 1. Ưu tiên Quy tắc cứng (Overview)
            hard_rule_results = [r for r in results if "[QUY TẮC CỨNG" in r["content"]]
            if hard_rule_results:
                res = hard_rule_results[0]
                content = res["content"]
                # CHỈ gắn ảnh nếu là yêu cầu Overview và không phải hỏi giá
                if res.get("image_url") and is_overview_request and not is_specific:
                    content = f"{content}\n[IMAGE_URL: {res['image_url']}]"
                
                # Nếu là câu hỏi cụ thể, xóa sạch mọi tag ảnh có sẵn trong nội dung
                if is_specific:
                    content = re.sub(r"\[?IMAGE_URL:\s*[^\]\s\n]+\]?", "", content, flags=re.IGNORECASE).strip()
                    
                return {"context": content, "source": "overview_vect"}
            
            # 2. Nếu là tìm kiếm thông thường, lấy 2 kết quả tốt nhất
            context_parts = []
            main_image_url = None
            
            for r in results[:2]:
                text = r["content"]
                # Nếu kết quả này có ảnh, lưu lại làm ảnh chính
                if r.get("image_url") and not main_image_url:
                    main_image_url = r["image_url"]
                context_parts.append(text)
            
            # 3. MẸO: Nếu kết quả tìm kiếm không có ảnh, hãy thử tìm ảnh Overview của môn này
            if not main_image_url and results:
                # Lấy sub_category và category của kết quả đầu tiên để tìm ảnh overview tương ứng
                sub_cat = results[0].get("sub_category")
                cat = results[0].get("category")
                
                from src.db.operations import get_faq_by_subcategory
                # Thử tìm theo sub_category trước
                overview = get_faq_by_subcategory(sub_cat) if sub_cat else None
                # Nếu không thấy, thử tìm theo category (vì trong CSV Category thường là tên môn như Gym, Yoga)
                if not overview and cat:
                    overview = get_faq_by_subcategory(cat)
                
                if overview and overview.get("image_url"):
                    main_image_url = overview["image_url"]
                    # print(f"🖼️ Đã tìm thấy ảnh bổ sung từ Overview cho: {sub_cat or cat}")

            context_text = "\n---\n".join(context_parts)
            
            # Chỉ đính kèm ảnh Overview nếu đúng ngữ cảnh
            if main_image_url and is_overview_request and not is_specific:
                context_text = f"{context_text}\n[IMAGE_URL: {main_image_url}]"
                print(f"✅ Tool đã đính kèm ảnh Overview vào context: {main_image_url}")
            else:
                # Nếu là câu hỏi cụ thể, XÓA sạch mọi tag ảnh có thể đang nằm trong nội dung FAQ
                if is_specific:
                    context_text = re.sub(r"\[?IMAGE_URL:\s*[^\]\s\n]+\]?", "", context_text, flags=re.IGNORECASE).strip()
                
                reason = "chứa từ khóa cụ thể" if is_specific else "không bắt đầu bằng 'overview'"
                if main_image_url:
                    print(f"ℹ️ Bỏ qua đính kèm ảnh vì {reason} (Query: {query})")
        else:
            context_text = "Không tìm thấy thông tin liên quan trong cơ sở dữ liệu."
            
    except Exception as e:
        print(f"❌ Lỗi khi thực hiện RAG: {e}")
        context_text = "Lỗi hệ thống khi truy xuất dữ liệu."
    
    # print(f"🛠️ [Tool Return Content]: {context_text[:200]}...")
    return {"context": context_text, "source": "cauhoi"}
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

TOOL_MAPPING = {
    "retrival_data": retrival_data,
    "search_address": search_address
}

AGENT_TOOLS_LIST ={
    "agent_main": [
        {
            "name": "retrival_data",
            "description": "Truy xuất thông tin từ database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu hỏi cần truy xuất thông tin"
                    }
                },
                "required": ["query"]
            }
        }
    ],
<<<<<<< HEAD
    "agent_diachi": [
        {
            "name": "search_address",
            "description": "Tìm kiếm địa chỉ gần nhất",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_location": {
                        "type": "string",
                        "description": "Địa chỉ của người dùng"
                    }
                },
                "required": ["user_location"]
=======

    "agent_diachi": [
        {
            "name": "search_address",
            "description": "Tìm các chi nhánh EMS gần người dùng nhất dựa trên địa chỉ/khu vực mà người dùng cung cấp hoặc tọa độ đã lưu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_address": {
                        "type": "string",
                        "description": "Địa chỉ hoặc khu vực cụ thể khách nhắc tới (ví dụ: 'Hoàng Ngân', 'Cầu Giấy')"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Số lượng chi nhánh gần nhất cần trả về, mặc định là 3"
                    }
                }
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
            }
        }
    ]
}

def build_tools_list(agent_name: str) -> str:
    tools = AGENT_TOOLS_LIST.get(agent_name, [])
    tool_lines = ["Available tools:\n"]
    for i, tool in enumerate(tools, start=1):
        tool_lines.append(
            f"""{i}. {tool['name']}
            Description: {tool['description']}
            Parameters: {tool['parameters']}
            """
        )
    return "\n".join(tool_lines)

# ĐỊNH NGHĨA AGENT PROFILES
AGENT_PROFILES = {
    "agent_main": {
        "role": "Chuyên viên tư vấn chính về Fitness & Yoga",
        "system_instruction": AGENT_MAIN_PROMPT,
        "tool_list": build_tools_list("agent_main")
    },
    "agent_diachi": {
        "role": "Chuyên gia về Địa điểm & Chi nhánh",
        "system_instruction": AGENT_DIACHI_PROMPT,
        "tool_list": build_tools_list("agent_diachi")
    }
}

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "Bạn là {role}"),
<<<<<<< HEAD
    ("system", "Bạn có thể truy cập các hành động sau:\n{tools_list}"),
    ("human", "Câu hỏi của người dùng: {query}"),
    ("system", "Phản hồi trước của agent:\n{last_agent_response}"),
    ("system", "Quan sát công cụ trước đó:\n{tool_observations}"),
=======
    ("system", "HÀNH ĐỘNG CÓ THỂ SỬ DỤNG:\n{tools_list}"),
    ("human", "CÂU HỎI CỦA NGƯỜI DÙNG: {query}"),
    ("system", "HÀNH ĐỘNG VỪA THỰC HIỆN: {last_agent_response}"),
    ("system", "KẾT QUẢ TỪ CƠ SỞ DỮ LIỆU:\n{tool_observations}"),
    ("system", "HƯỚNG DẪN QUAN TRỌNG: Nếu KẾT QUẢ TỪ CƠ SỞ DỮ LIỆU đã chứa thông tin chuẩn, bạn BẮT BUỘC phải dùng nó để TRẢ LỜI (ANSWER) ngay. TUYỆT ĐỐI KHÔNG được lặp lại HÀNH ĐỘNG (ACTION) cũ."),
    ("system", "TRẠNG THÁI HỆ THỐNG: can_ask_phone={can_ask_phone}"),
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    ("system", "{system_instruction}")
])

def call_agent(state: dict, agent_name: str) -> dict:
    profile = AGENT_PROFILES[agent_name]
    chain = prompt_template | llm
    response = chain.invoke({
        "role": profile["role"],
        "system_instruction": profile["system_instruction"],
        "query": state.get("query", ""),
        "last_agent_response": state.get("last_agent_response", ""),
<<<<<<< HEAD
        "tool_observations": "\n".join(state.get("tool_obervations", [])),
        "tools_list": profile["tool_list"]
=======
        "tool_observations": "\n".join(state.get("tool_observations", [])),
        "tools_list": profile["tool_list"],
        "can_ask_phone": state.get("can_ask_phone", True)
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    })
    state["last_agent_response"] = response.content
    state["last_agent"] = agent_name
    state["num_steps"] += 1
<<<<<<< HEAD
    print(f"\n=== 🤖{agent_name.upper()} ===\n{response.content}")
=======
    print(f"\n=== {agent_name.upper()} ===\n{response.content}")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    return state

def call_tool(state: dict) -> dict:
    action_text = state.get("last_agent_response", "")
    agent_name = state.get("last_agent")
<<<<<<< HEAD
    if "ACTION:" not in action_text:
        state.setdefault("tool_obervations", []).append(f"[No action found by {agent_name}]")
        return state
    tool_name = action_text.split("ACTION:")[1].split("\n")[0].strip()
    allowed_tools = [tool["name"] for tool in AGENT_TOOLS_LIST.get(agent_name, [])]
    if tool_name not in allowed_tools:
        msg = f"[Tool '{tool_name}' NOT allowed for {agent_name}]"
        state.setdefault("tool_obervations", []).append(msg)
        return state
    args = {}
    if "ARGUMENTS:" in action_text:
        args_text = action_text.split("ARGUMENTS:")[1].strip()
        try:
            args = json.loads(args_text)
        except:
            state.setdefault("tool_obervations", []).append("[Failed to parse arguments]")
            return state
    tool_func = TOOL_MAPPING.get(tool_name)
    if not tool_func:
        state.setdefault("tool_obervations", []).append("[Unknown tool]")
        return state
    results = tool_func(**args)
    state.setdefault("tool_obervations", []).append(f"[{tool_name} results: {results.get('context')}]")
=======
    
    # Tìm Tool Name
    tool_name = None
    if "ACTION:" in action_text:
        match = re.search(r"ACTION:\s*([a-zA-Z0-9_]+)", action_text)
        if match:
            tool_name = match.group(1).strip()
    
    # Tìm Arguments
    args = {}
    json_match = re.search(r"({.*})", action_text, re.DOTALL)
    if json_match:
        try:
            clean_json = json_match.group(1).strip()
            args = json.loads(clean_json)
            if not tool_name and "tool_code" in args:
                tool_name = args.get("tool_code")
        except:
            pass

    if not tool_name:
        state.setdefault("tool_observations", []).append(f"[No action found by {agent_name}]")
        return state

    allowed_tools = [tool["name"] for tool in AGENT_TOOLS_LIST.get(agent_name, [])]
    if tool_name not in allowed_tools:
        msg = f"[Tool '{tool_name}' NOT allowed for {agent_name}]"
        state.setdefault("tool_observations", []).append(msg)
        return state
        
    if tool_name == "search_address":
        args["sender_id"] = state.get("sender_id")
        if "top_n" not in args:
            args["top_n"] = 3

    tool_func = TOOL_MAPPING.get(tool_name)
    if not tool_func:
        state.setdefault("tool_observations", []).append("[Unknown tool]")
        return state
    results = tool_func(**args)
    if results and isinstance(results, dict):
        state.setdefault("tool_observations", []).append(f"[{tool_name} results: {results.get('context')}]")
    else:
        state.setdefault("tool_observations", []).append(f"[{tool_name} trả về kết quả không hợp lệ]")
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    return state

def should_continue(state: dict) -> str:
    if state.get("num_steps", 0) >= AI_MAX_STEPS: return "end"
<<<<<<< HEAD
    response = state.get("last_agent_response", "").upper()
    if "ANSWER" in response: return "end"
    if "ACTION" in response: return "continue"
    if "HANDOFF" in response: return "handoff"
=======
    response_upper = state.get("last_agent_response", "").upper()
    if "ANSWER:" in response_upper: return "end"
    if "ACTION:" in response_upper or "TOOL_CODE" in response_upper: return "continue"
    if "HANDOFF:" in response_upper: return "handoff"
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2
    return "end"

def which_agents(state: dict) -> str:
    return state.get("last_agent")

class AgentState(TypedDict):
    query: str
<<<<<<< HEAD
    last_agent_response: str
    last_agent: str
    tool_obervations: list
    num_steps: int
=======
    sender_id: str 
    last_agent_response: str
    last_agent: str
    tool_observations: list
    num_steps: int
    can_ask_phone: bool
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

workflow_m = StateGraph(AgentState)
workflow_m.add_node("agent_main", lambda s: call_agent(s, "agent_main"))
workflow_m.add_node("agent_diachi", lambda s: call_agent(s, "agent_diachi"))
workflow_m.add_node("tools", call_tool)
workflow_m.set_entry_point("agent_main")
workflow_m.add_conditional_edges("agent_main", should_continue, {"continue": "tools", "handoff": "agent_diachi", "end": END})
workflow_m.add_conditional_edges("agent_diachi", should_continue, {"continue": "tools", "handoff": "agent_main", "end": END})
workflow_m.add_conditional_edges("tools", which_agents, {"agent_main": "agent_main", "agent_diachi": "agent_diachi"})
agentic_graph_m = workflow_m.compile()

<<<<<<< HEAD
def get_agent_response(user_text: str) -> str:
    print(f"\n[Người dùng hỏi]: {user_text}")
    agent_state = {"query": user_text, "last_agent_response": "", "tool_obervations": [], "num_steps": 0}
    try:
        result = agentic_graph_m.invoke(agent_state)
        raw_response = result.get("last_agent_response", "")
        if "ANSWER:" in raw_response:
            return raw_response.split("ANSWER:")[1].strip().strip('"')
        return raw_response.strip()
    except Exception as e:
        print(f"Lỗi khi chạy LangGraph: {e}")
        return "Bạn cho bên mình xin SDT nhé, chuyên viên EMS sẽ tư vấn rõ hơn!"
=======
async def get_agent_response(user_text: str, sender_id: str, user_context: str = "", max_retries: int = 3, **kwargs) -> str:
    """Gọi AI agent để lấy response bằng chế độ Async"""
    if user_context and user_context.strip():
        query_with_context = f"{user_context}\n\n[Câu hỏi mới]: {user_text}"
    else:
        query_with_context = user_text
    
    agent_state = {
        "query": query_with_context,
        "sender_id": sender_id,
        "last_agent_response": "",
        "tool_observations": [],
        "num_steps": 0,
        "can_ask_phone": kwargs.get("can_ask_phone", True)
    }
    
    for attempt in range(max_retries):
        try:
            # Sử dụng ainvoke để không chặn luồng chính
            result = await agentic_graph_m.ainvoke(agent_state)
            raw_response = result.get("last_agent_response", "")
            
            if "ANSWER:" in raw_response:
                return raw_response.split("ANSWER:")[1].strip().strip('"')
            
            if "ACTION:" in raw_response:
                return "Dạ hiện tại mình đang kiểm tra thông tin này, bạn chờ mình một xíu nhé hoặc để lại SĐT mình phản hồi ngay ạ."
                
            return raw_response.strip()
        except Exception as e:
            print(f"Lỗi khi chạy LangGraph (Attempt {attempt+1}): {e}")
            continue
    
    return "Bạn cho bên mình xin SDT nhé, chuyên viên EMS sẽ tư vấn rõ hơn!"
>>>>>>> 5303b80e963b73aad4ecb764b31755665bbda9a2

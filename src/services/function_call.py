import json
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


# AGENT SETUP
print("🔑 Cài đặt hệ thống AI")
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Khởi tạo mô hình Chat LLM
llm = ChatGoogleGenerativeAI(
    model=AI_MODEL_NAME, 
    temperature=0,
    google_api_key=api_key,
    request_timeout=AI_REQUEST_TIMEOUT
)

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
            db_overview = get_faq_by_subcategory(service_name.capitalize()) or get_faq_by_subcategory(service_name.upper()) or get_faq_by_subcategory(service_name)
            
            if db_overview:
                print(f"🎯 Đã tìm thấy chính xác Overview cho môn {service_name}")
                return {"context": db_overview, "source": "overview_match"}

        # Nếu không tìm thấy đích danh, quay lại dùng tìm kiếm Vector như cũ
        query_embedding = embeddings_model.embed_query(query)
        results = search_faq(query_embedding, limit=10)
        
        if results:
            hard_rule_results = [r for r in results if "[QUY TẮC CỨNG" in r]
            if hard_rule_results:
                return {"context": hard_rule_results[0], "source": "overview_vect"}
            
            context_text = "\n---\n".join(results[:2])
        else:
            context_text = "Không tìm thấy thông tin liên quan trong cơ sở dữ liệu."
            
    except Exception as e:
        print(f"❌ Lỗi khi thực hiện RAG: {e}")
        context_text = "Lỗi hệ thống khi truy xuất dữ liệu."
        
    return {"context": context_text, "source": "cauhoi"}

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
    ("system", "HÀNH ĐỘNG CÓ THỂ SỬ DỤNG:\n{tools_list}"),
    ("human", "CÂU HỎI CỦA NGƯỜI DÙNG: {query}"),
    ("system", "HÀNH ĐỘNG VỪA THỰC HIỆN: {last_agent_response}"),
    ("system", "KẾT QUẢ TỪ CƠ SỞ DỮ LIỆU:\n{tool_observations}"),
    ("system", "HƯỚNG DẪN QUAN TRỌNG: Nếu KẾT QUẢ TỪ CƠ SỞ DỮ LIỆU đã chứa thông tin chuẩn, bạn BẮT BUỘC phải dùng nó để TRẢ LỜI (ANSWER) ngay. TUYỆT ĐỐI KHÔNG được lặp lại HÀNH ĐỘNG (ACTION) cũ."),
    ("system", "TRẠNG THÁI HỆ THỐNG: can_ask_phone={can_ask_phone}"),
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
        "tool_observations": "\n".join(state.get("tool_observations", [])),
        "tools_list": profile["tool_list"],
        "can_ask_phone": state.get("can_ask_phone", True)
    })
    state["last_agent_response"] = response.content
    state["last_agent"] = agent_name
    state["num_steps"] += 1
    print(f"\n=== {agent_name.upper()} ===\n{response.content}")
    return state

def call_tool(state: dict) -> dict:
    action_text = state.get("last_agent_response", "")
    agent_name = state.get("last_agent")
    
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
    return state

def should_continue(state: dict) -> str:
    if state.get("num_steps", 0) >= AI_MAX_STEPS: return "end"
    response_upper = state.get("last_agent_response", "").upper()
    if "ANSWER:" in response_upper: return "end"
    if "ACTION:" in response_upper or "TOOL_CODE" in response_upper: return "continue"
    if "HANDOFF:" in response_upper: return "handoff"
    return "end"

def which_agents(state: dict) -> str:
    return state.get("last_agent")

class AgentState(TypedDict):
    query: str
    sender_id: str 
    last_agent_response: str
    last_agent: str
    tool_observations: list
    num_steps: int
    can_ask_phone: bool

workflow_m = StateGraph(AgentState)
workflow_m.add_node("agent_main", lambda s: call_agent(s, "agent_main"))
workflow_m.add_node("agent_diachi", lambda s: call_agent(s, "agent_diachi"))
workflow_m.add_node("tools", call_tool)
workflow_m.set_entry_point("agent_main")
workflow_m.add_conditional_edges("agent_main", should_continue, {"continue": "tools", "handoff": "agent_diachi", "end": END})
workflow_m.add_conditional_edges("agent_diachi", should_continue, {"continue": "tools", "handoff": "agent_main", "end": END})
workflow_m.add_conditional_edges("tools", which_agents, {"agent_main": "agent_main", "agent_diachi": "agent_diachi"})
agentic_graph_m = workflow_m.compile()

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
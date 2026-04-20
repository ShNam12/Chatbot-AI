import json
import os
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
    print("--- TOOL CALL: RETRIEVING CONTEXT FROM POSTGRES (ORM) ---")
    
    # 1. Tạo embedding từ query người dùng qua Gemini
    try:
        query_embedding = embeddings_model.embed_query(query)
        
        # 2. Tìm kiếm vector trong PostgreSQL qua Operations
        results = search_faq(query_embedding, limit=2) # Tăng limit để AI có nhiều context hơn
        
        if results:
            context_text = "\n---\n".join(results)
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
            "description": "Tìm các chi nhánh EMS gần người dùng nhất dựa trên địa chỉ và tọa độ đã lưu trong user_sessions.",
            "parameters": {
                "type": "object",
                "properties": {
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
    ("system", "Bạn có thể truy cập các hành động sau:\n{tools_list}"),
    ("human", "Câu hỏi của người dùng: {query}"),
    ("system", "Phản hồi trước của agent:\n{last_agent_response}"),
    ("system", "Quan sát công cụ trước đó:\n{tool_observations}"),
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
        "tool_observations": "\n".join(state.get("tool_obervations", [])),
        "tools_list": profile["tool_list"]
    })
    state["last_agent_response"] = response.content
    state["last_agent"] = agent_name
    state["num_steps"] += 1
    print(f"\n=== 🤖{agent_name.upper()} ===\n{response.content}")
    return state

def call_tool(state: dict) -> dict:
    action_text = state.get("last_agent_response", "")
    agent_name = state.get("last_agent")
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
        
    # Inject sender_id tự động cho tool search_address
    if tool_name == "search_address":
        args["sender_id"] = state.get("sender_id")
        if "top_n" not in args:
            args["top_n"] = 3

    tool_func = TOOL_MAPPING.get(tool_name)
    if not tool_func:
        state.setdefault("tool_obervations", []).append("[Unknown tool]")
        return state
    results = tool_func(**args)
    if results and isinstance(results, dict):
        state.setdefault("tool_obervations", []).append(f"[{tool_name} results: {results.get('context')}]")
    else:
        state.setdefault("tool_obervations", []).append(f"[{tool_name} trả về kết quả không hợp lệ]")
    return state

def should_continue(state: dict) -> str:
    if state.get("num_steps", 0) >= AI_MAX_STEPS: return "end"
    response = state.get("last_agent_response", "").upper()
    if "ANSWER" in response: return "end"
    if "ACTION" in response: return "continue"
    if "HANDOFF" in response: return "handoff"
    return "end"

def which_agents(state: dict) -> str:
    return state.get("last_agent")

class AgentState(TypedDict):
    query: str
    sender_id: str 
    last_agent_response: str
    last_agent: str
    tool_obervations: list
    num_steps: int

workflow_m = StateGraph(AgentState)
workflow_m.add_node("agent_main", lambda s: call_agent(s, "agent_main"))
workflow_m.add_node("agent_diachi", lambda s: call_agent(s, "agent_diachi"))
workflow_m.add_node("tools", call_tool)
workflow_m.set_entry_point("agent_main")
workflow_m.add_conditional_edges("agent_main", should_continue, {"continue": "tools", "handoff": "agent_diachi", "end": END})
workflow_m.add_conditional_edges("agent_diachi", should_continue, {"continue": "tools", "handoff": "agent_main", "end": END})
workflow_m.add_conditional_edges("tools", which_agents, {"agent_main": "agent_main", "agent_diachi": "agent_diachi"})
agentic_graph_m = workflow_m.compile()

def get_agent_response(user_text: str, sender_id: str, user_context: str = "", max_retries: int = 3) -> str:
    """
    Gọi AI agent để lấy response
    
    Args:
        user_text: Tin nhắn từ người dùng
        sender_id: ID của người dùng để truy xuất vị trí/phiên làm việc
        user_context: Lịch sử hội thoại (tùy chọn) để giúp AI hiểu context
        max_retries: Số lần thử lại
    
    Returns:
        Response từ AI
    """
    # 🔑 Thêm context vào query nếu có
    if user_context and user_context.strip():
        query_with_context = f"{user_context}\n\n[Câu hỏi mới]: {user_text}"
        print(f"\n[Người dùng hỏi]: {user_text}")
        print(f"[Context đã thêm]: {len(user_context)} ký tự")
    else:
        query_with_context = user_text
        print(f"\n[Người dùng hỏi]: {user_text}")
    
    agent_state = {
        "query": query_with_context,
        "sender_id": sender_id,
        "last_agent_response": "",
        "tool_obervations": [],
        "num_steps": 0,
    }
    
    import time
    for attempt in range(max_retries):
        try:
            result = agentic_graph_m.invoke(agent_state)
            raw_response = result.get("last_agent_response", "")
            if "ANSWER:" in raw_response:
                return raw_response.split("ANSWER:")[1].strip().strip('"')
            return raw_response.strip()
        except Exception as e:
            error_str = str(e)
            print(f"Lỗi khi chạy LangGraph: {e}")
            break
    
    return "Bạn cho bên mình xin SDT nhé, chuyên viên EMS sẽ tư vấn rõ hơn!"
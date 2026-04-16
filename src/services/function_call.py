import json
import chromadb
import pandas as pd
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from math import radians, sin, cos, sqrt, atan2
from typing import TypedDict
import os
from dotenv import load_dotenv

# AGENT SETUP
print("🔑 Cài đặt hệ thống AI")
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0,
    google_api_key=api_key,
    request_timeout=10
)


print("✅ Đã kết nối thành công với Gemini!")

# Khai báo đường dẫn tương đối từ gốc dự án
BASE_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(BASE_DIR, "kho_du_lieu_vector")
DIACHI_CSV_PATH = os.path.join(BASE_DIR, "data", "diachi.csv")

# 1. Khai báo lại hàm Embedding
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
ef = ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])

# 2. Trỏ đường dẫn tới thư mục chứa database
client = chromadb.PersistentClient(path=VECTOR_DB_PATH)

# 3. Lấy collection ra
collection = client.get_or_create_collection(
    name="cauhoi_faq", 
    embedding_function=ef
)

def retrival_data(query):
    print("--- TOOL CALL: RETRIEVING CONTEXT ---")
    results = collection.query(
        query_texts=[query],
        n_results=1,
    )
    context_text = "\n".join(results['documents'][0])
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

    user_coord = {"lat": 21.0285, "lon": 105.8542} # giả lập tọa độ Hà Nội
    user_lat, user_lon = user_coord["lat"], user_coord["lon"]

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

# ĐỊNH NGHĨA AGENT PROFILES (giữ nguyên logic)
AGENT_PROFILES = {
    "agent_main": {
        "role": "Chuyên viên tư vấn chính về Fitness & Yoga",
        "system_instruction": """Hướng dẫn: ...""", # Lược bớt text mẫu để tối ưu
        "tool_list": build_tools_list("agent_main")
    },
    "agent_diachi": {
        "role": "Chuyên gia về Địa điểm & Chi nhánh",
        "system_instruction": """Hướng dẫn: ...""",
        "tool_list": build_tools_list("agent_diachi")
    }
}
# Khôi phục đầy đủ system_instruction trong file thực tế
AGENT_PROFILES["agent_main"]["system_instruction"] = """Hướng dẫn:
                1. Luôn bắt đầu bằng THOUGHT (Suy nghĩ), sau đó quyết định chọn (ACTION và ARGUMENTS) hoặc ANSWER (Trả lời) hoặc HANDOFF (Chuyển giao).
                2. Kiểm tra kỹ các kết quả từ công cụ trước đó (tool_observations) để xem câu trả lời đã có sẵn hay chưa.
                3. Nếu chưa có, hãy chọn công cụ (tool) phù hợp nhất để thu thập thêm thông tin.
                4. Vui lòng không trả lời bất cứ điều gì dựa trên kiến thức chung hoặc sự phỏng đoán khi chưa có đủ thông tin.
                5. ARGUMENTS (Tham số) bắt buộc phải là định dạng JSON hợp lệ với các khóa (keys) nằm trong dấu ngoặc kép.
                6. Vui lòng không thêm bất cứ nội dung nào nằm ngoài định dạng đã được chỉ định.
                7. Không hỏi người dùng về vị trí của họ vì chúng ta đã tự động lấy được thông tin đó từ Mobile App.
                8. Nếu câu hỏi liên quan đến TÌM ĐỊA ĐIỂM, CHI NHÁNH GẦN NHẤT, hoặc ĐỊA CHỈ PHÒNG TẬP, bạn BẮT BUỘC phải HANDOFF (Chuyển giao) cho Chuyên gia Địa điểm trước khi ANSWER. Chỉ cần phản hồi là HANDOFF:agent_diachi.
                ---"""
AGENT_PROFILES["agent_diachi"]["system_instruction"] = """Hướng dẫn:
                1. Luôn bắt đầu bằng THOUGHT (Suy nghĩ), sau đó quyết định chọn ACTION (Hành động) hoặc ANSWER (Trả lời).
                2. Kiểm tra kỹ các kết quả từ công cụ trước đó (tool_observations) để xem câu trả lời đã có sẵn hay chưa.
                3. Nếu chưa có, hãy chọn công cụ (tool) phù hợp nhất để thu thập thêm thông tin.
                4. Vui lòng không trả lời bất cứ điều gì dựa trên kiến thức chung hoặc sự phỏng đoán khi chưa có đủ thông tin.
                5. ARGUMENTS (Tham số) bắt buộc phải là định dạng JSON hợp lệ với các khóa (keys) nằm trong dấu ngoặc kép.
                6. Vui lòng không thêm bất cứ nội dung nào nằm ngoài định dạng đã được chỉ định.
                7. Không hỏi người dùng về vị trí của họ vì chúng ta đã tự động lấy được thông tin đó từ Mobile App.
                ---"""

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
    tool_func = TOOL_MAPPING.get(tool_name)
    if not tool_func:
        state.setdefault("tool_obervations", []).append("[Unknown tool]")
        return state
    results = tool_func(**args)
    state.setdefault("tool_obervations", []).append(f"[{tool_name} results: {results.get('context')}]")
    return state

def should_continue(state: dict) -> str:
    if state.get("num_steps", 0) >= 5: return "end"
    response = state.get("last_agent_response", "").upper()
    if "ANSWER" in response: return "end"
    if "ACTION" in response: return "continue"
    if "HANDOFF" in response: return "handoff"
    return "end"

def which_agents(state: dict) -> str:
    return state.get("last_agent")

class AgentState(TypedDict):
    query: str
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

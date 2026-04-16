import json
import chromadb
import pandas as pd
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from math import radians, sin, cos, sqrt, atan2 # tinh khoang cach gan nhat
from typing import TypedDict
import getpass
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
import os
from dotenv import load_dotenv

#AGENT SETUP
#
print("🔑 Cài đặt hệ thống AI")
load_dotenv()
api_key= os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0,
    google_api_key=api_key,
    request_timeout=6
)

print("✅ Đã kết nối thành công với Gemini!")

# 1. Khai báo lại hàm Embedding y hệt như lúc tạo Database
ef = ONNXMiniLM_L6_V2(preferred_providers=['CPUExecutionProvider'])

# 2. Trỏ đường dẫn tới thư mục chứa database
client = chromadb.PersistentClient(path="./kho_du_lieu_vector")

# 3. Lấy collection ra (BẮT BUỘC phải truyền kèm embedding_function)
collection = client.get_or_create_collection(
    name="cauhoi_faq", 
    embedding_function=ef
)

def retrival_data(query):
    print("--- TOOL CALL: RETRIEVING CONTEXT ---")
    results = collection.query(
        query_texts=[query],
        n_results=1, #tra ve 1 ket qua
    )
    context_text = "\n".join(results['documents'][0])
    return {"context": context_text, "source": "cauhoi"}

def search_address(user_location: str = "Hanoi,Vietnam", top_n: int = 3):
    """ Tìm kiếm các địa chỉ gần người cần tư vấn nhất"""
    print("--- TOOL CALL: SEARCHING ADDRESS ---")

    try: 
        df_br = pd.read_csv("data/diachi.csv")
        print("✅ Đã tải thành công dữ liệu các chi nhánh!")
    except Exception as e:
        print(f"❌ Lỗi khi tải dữ liệu: {e}")
        return None

    #user_coord = get_coordinates(user_location) Gốc là phải theo địa chỉ khách hàng nhưng mình giả lập đchi
    user_coord = {"lat": 21.0285, "lon": 105.8542} # giả lập tọa độ Hà Nội

    user_lat, user_lon = user_coord["lat"], user_coord["lon"]

    # Thuật toán tính khoảng cách đại viên (Haversine)
    def haversine(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c  # Trả về đơn vị Kilomet (km)

    # Trích xuất dữ liệu từ DataFrame dùng chung
    filtered_df = df_br.copy()

    # Áp dụng công thức để tính khoảng cách cho toàn bộ 15 chi nhánh
    filtered_df['distance_km'] = filtered_df.apply(
        lambda row: haversine(user_lat, user_lon, row['latitude'], row['longitude']), axis=1
    )

    # Sắp xếp kết quả từ gần đến xa và cắt lấy 'top_n' chi nhánh gần nhất
    nearest = filtered_df.sort_values('distance_km').head(top_n)
    
    # Làm tròn khoảng cách để hiển thị đẹp hơn (ví dụ: 1.25 thay vì 1.254326...)
    nearest["distance_km"] = nearest["distance_km"].round(2)
    
    # Chuyển đổi bảng kết quả thành dạng danh sách Từ điển (Dictionary) cho AI đọc
    results = nearest[['branch_name', 'branch_address', 'distance_km']].to_dict(orient='records')
    
    return {"context": results, "source": "diachi"}

    
#MAPPING TOOL

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



AGENT_PROFILES = {
    "agent_main": {
        "role": "Chuyên viên tư vấn chính về Fitness & Yoga",
        "system_instruction": """Hướng dẫn:
                1. Luôn bắt đầu bằng THOUGHT (Suy nghĩ), sau đó quyết định chọn (ACTION và ARGUMENTS) hoặc ANSWER (Trả lời) hoặc HANDOFF (Chuyển giao).
                2. Kiểm tra kỹ các kết quả từ công cụ trước đó (tool_observations) để xem câu trả lời đã có sẵn hay chưa.
                3. Nếu chưa có, hãy chọn công cụ (tool) phù hợp nhất để thu thập thêm thông tin.
                4. Vui lòng không trả lời bất cứ điều gì dựa trên kiến thức chung hoặc sự phỏng đoán khi chưa có đủ thông tin.
                5. ARGUMENTS (Tham số) bắt buộc phải là định dạng JSON hợp lệ với các khóa (keys) nằm trong dấu ngoặc kép.
                6. Vui lòng không thêm bất cứ nội dung nào nằm ngoài định dạng đã được chỉ định.
                7. Không hỏi người dùng về vị trí của họ vì chúng ta đã tự động lấy được thông tin đó từ Mobile App.
                8. Nếu câu hỏi liên quan đến TÌM ĐỊA ĐIỂM, CHI NHÁNH GẦN NHẤT, hoặc ĐỊA CHỈ PHÒNG TẬP, bạn BẮT BUỘC phải HANDOFF (Chuyển giao) cho Chuyên gia Địa điểm trước khi ANSWER. Chỉ cần phản hồi là HANDOFF:agent_diachi.

                ---

                Ví dụ mẫu về phiên giao dịch:

                Người dùng hỏi: "Tập gym bao nhiêu buổi một tuần là đủ?"

                THOUGHT: Người dùng đang hỏi xin lời khuyên về tần suất tập luyện. Mình nên tìm thông tin này trong cơ sở dữ liệu FAQ.
                ACTION: retrival_data
                ARGUMENTS: {"query": "tập gym bao nhiêu buổi một tuần"}

                [Kết quả từ công cụ trả về]

                THOUGHT: Ngữ cảnh được truy xuất đã cung cấp thông tin về tần suất tập luyện được khuyến nghị. Bây giờ mình nên trả lời người dùng.
                ANSWER: "Với người mới bắt đầu, tập 3-4 buổi/tuần là hợp lý để cơ thể có thời gian phục hồi bạn nhé."

                Người dùng hỏi: "Phòng tập nào đang gần tôi nhất vậy?"

                THOUGHT: Người dùng muốn tìm địa chỉ phòng tập gần nhất. Mình phải chuyển giao nhiệm vụ này cho Chuyên gia Địa điểm xử lý.
                HANDOFF:agent_diachi

                ---""",
        "tool_list": build_tools_list("agent_main")
    },
    "agent_diachi": {
        "role": "Chuyên gia về Địa điểm & Chi nhánh",
        "system_instruction": """Hướng dẫn:
                1. Luôn bắt đầu bằng THOUGHT (Suy nghĩ), sau đó quyết định chọn ACTION (Hành động) hoặc ANSWER (Trả lời).
                2. Kiểm tra kỹ các kết quả từ công cụ trước đó (tool_observations) để xem câu trả lời đã có sẵn hay chưa.
                3. Nếu chưa có, hãy chọn công cụ (tool) phù hợp nhất để thu thập thêm thông tin.
                4. Vui lòng không trả lời bất cứ điều gì dựa trên kiến thức chung hoặc sự phỏng đoán khi chưa có đủ thông tin.
                5. ARGUMENTS (Tham số) bắt buộc phải là định dạng JSON hợp lệ với các khóa (keys) nằm trong dấu ngoặc kép.
                6. Vui lòng không thêm bất cứ nội dung nào nằm ngoài định dạng đã được chỉ định.
                7. Không hỏi người dùng về vị trí của họ vì chúng ta đã tự động lấy được thông tin đó từ Mobile App.

                ---

                Ví dụ mẫu về phiên giao dịch:

                Người dùng hỏi: "Tìm chi nhánh EMS Fitness gần chỗ tôi nhất"

                THOUGHT: Người dùng muốn tìm chi nhánh gần nhất. Mình cần sử dụng công cụ search_address để tính toán khoảng cách dựa trên vị trí hiện tại của họ.
                ACTION: search_address
                ARGUMENTS: {"user_location": "Hanoi, Vietnam"}

                [Kết quả từ công cụ trả về]

                THOUGHT: Ngữ cảnh được truy xuất đã cung cấp các chi nhánh gần nhất và khoảng cách tương ứng. Bây giờ mình nên định dạng lại câu trả lời để gửi cho người dùng.
                ANSWER: "Chi nhánh gần bạn nhất là EMS Fitness & Yoga chi nhánh Lý Thường Kiệt, chỉ cách bạn khoảng 1.2 km. Bạn có muốn xem thêm hướng dẫn đường đi không?"

                ---""",
        "tool_list": build_tools_list("agent_diachi")
    }
}

#print(AGENT_PROFILES)



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
    # print("Response from llm: ", response.content)
    state["last_agent_response"] = response.content
    state["last_agent"] = agent_name
    state["num_steps"] += 1

    print(f"\n=== 🤖{agent_name.upper()} ===")
    print(response.content)

    return state

def call_tool(state: dict) -> dict:
    action_text = state.get("last_agent_response", "")
    agent_name = state.get("last_agent")

    if "ACTION:" not in action_text:
        state.setdefault("tool_obervations", []).append(
            f"[No action found by {agent_name}: {action_text}]"
        )
        return state

    print(f"--- ⚙️ CALLING TOOL OF({agent_name}) ---")

    # Extract tool name
    tool_name = action_text.split("ACTION:")[1].split("\n")[0].strip()
    print(f"Tool requested: {tool_name}")

    # Check permission
    allowed_tools = AGENT_TOOLS_LIST.get(agent_name, [])
    allowed_tools = [tool["name"] for tool in allowed_tools]
    print("Allowed tools = ", allowed_tools)
    if tool_name not in allowed_tools:
        msg = f"[Tool '{tool_name}' NOT allowed for {agent_name}]"
        print(msg)
        state.setdefault("tool_obervations", []).append(msg)
        return state

    # Parse arguments
    args = {}
    if "ARGUMENTS:" in action_text:
        args_text = action_text.split("ARGUMENTS:")[1].strip()

        if args_text.startswith("{"):
            brace_count = 0
            end_index = 0
            for i, char in enumerate(args_text):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                if brace_count == 0:
                    end_index = i + 1
                    break
            args_text = args_text[:end_index]

        try:
            args = json.loads(args_text)
        except json.JSONDecodeError:
            msg = f"[Failed to parse arguments: {args_text}]"
            print(msg)
            state.setdefault("tool_obervations", []).append(msg)
            return state

    # Execute tool
    tool_func = TOOL_MAPPING.get(tool_name)
    if not tool_func:
        msg = f"[Unknown tool: {tool_name}]"
        print(msg)
        state.setdefault("tool_obervations", []).append(msg)
        return state

    results = tool_func(**args)

    # Save results
    state.setdefault("tool_obervations", []).append(
        f"[{tool_name} results: {results.get('context')}]"
    )
    state["last_tool_results"] = results

    print(results)
    return state


########### LangGraph ###########

def should_continue(state: dict) -> str:
    if state.get("num_steps", 0) >= 5:
        print("Reached max steps → ending workflow.")
        return "end"
    
    response = state.get("last_agent_response", "").upper()

    if "ANSWER" in response:
        print("Found ANSWER → ending workflow.")
        return "end"

    if "ACTION" in response:
        print("Route to continue")
        return "continue"

    if "HANDOFF" in response:
        print("Route to handoff")
        return "handoff"

    return "end"

def which_agents(state: dict) -> str:
    response = state.get("last_agent", "")
    return response


# === State Schema ===
class AgentState(TypedDict):
    query: str
    last_agent_response: str
    last_agent: str
    tool_obervations: list
    num_steps: int
    user_location: str  #


# === Define nodes ===
def call_agent_main(state: AgentState):
    return call_agent(state, agent_name="agent_main")

def call_agent_diachi(state: AgentState):
    return call_agent(state, agent_name="agent_diachi")


# === Workflow Graph ===
workflow_m = StateGraph(state_schema=AgentState)

# Add nodes
workflow_m.add_node("agent_main", call_agent_main)
workflow_m.add_node("agent_diachi", call_agent_diachi)
workflow_m.add_node("tools", call_tool)

# Entry point
workflow_m.set_entry_point("agent_main")

# === Conditional routing for agent_1 ===
workflow_m.add_conditional_edges(
    "agent_main",
    should_continue,
    {
        "continue": "tools",
        "handoff": "agent_diachi",   # agent_1 gửi sang agent_2
        "end": END
    }
)

# === Conditional routing for agent_2 ===
workflow_m.add_conditional_edges(
    "agent_diachi",
    should_continue,
    {
        "continue": "tools",
        "handoff": "agent_main",   # agent_2 phản hồi lại agent_1
        "end": END
    }
)

workflow_m.add_conditional_edges(
    "tools",
    which_agents,
    {
        "agent_main": "agent_main",
        "agent_diachi": "agent_diachi"
    }
)


# Compile
agentic_graph_m = workflow_m.compile()


# # === CHẠY THỬ ===
# cau_hoi_nhap_tay = input("Nhập câu hỏi của bạn: ")
# # Khởi tạo state
# agent_state = {
#     "query": cau_hoi_nhap_tay,
#     "last_agent_response": "",
#     "tool_obervations": [],
#     "num_steps": 0
# }


# result = agentic_graph_m.invoke(agent_state)

# print("\n🎯 KẾT QUẢ CUỐI CÙNG:")
# print(result.get("last_agent_response"))

# === ĐÓNG GÓI HÀM CHO SERVER ===
def get_agent_response(user_text: str) -> str:
    """
    Nhận tin nhắn text, chạy LangGraph và trích xuất riêng câu trả lời (ANSWER)
    để gửi lại cho người dùng, ẩn đi phần THOUGHT của AI.
    """
    print(f"\n[Người dùng hỏi]: {user_text}")
    
    agent_state = {
        "query": user_text,
        "last_agent_response": "",
        "tool_obervations": [],
        "num_steps": 0
    }

    try:
        result = agentic_graph_m.invoke(agent_state)
        raw_response = result.get("last_agent_response", "")

        # AI của bạn có form: "THOUGHT: ... ANSWER: ...". 
        # Chúng ta bóc tách chỉ lấy đoạn sau chữ ANSWER: để nhắn cho khách
        if "ANSWER:" in raw_response:
            final_answer = raw_response.split("ANSWER:")[1].strip()
            
            # Xoá dấu ngoặc kép thừa nếu AI vô tình sinh ra ("...")
            if final_answer.startswith('"') and final_answer.endswith('"'):
                final_answer = final_answer[1:-1]
                
            return final_answer
        else:
            # Fallback nếu AI trả lời không đúng chuẩn form
            return raw_response.strip()
            
    except Exception as e:
        print(f"Lỗi khi chạy LangGraph: {e}")
        return "Bạn cho bên mình xin SDT nhé, chuyên viên EMS sẽ tư vấn rõ hơn!"
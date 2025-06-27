from attr import dataclass
import streamlit as st
from langchain_core.messages.chat import ChatMessage
from langchain_teddynote import logging
from langchain_teddynote.messages import random_uuid
from modules.agent import create_agent_executor
from dotenv import load_dotenv
from modules.handler import stream_handler, format_search_result
from modules.tools import WebSearchTool

# API KEY 정보로드
load_dotenv()

# 프로젝트 이름
# Perplexity? => LLM에 검색기능을 추가한 APP
logging.langsmith("Perplexity")

st.title("Perplexity 💬")
st.markdown(
    "LLM에 **웹검색 기능** 을 추가한 [Perplexity](https://www.perplexity.ai/) 클론 입니다. _멀티턴_ 대화를 지원합니다."
)

# 대화기록을 저장하기 위한 용도로 생성
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# from modules.agent import create_agent_executor
# -> modules라는 폴더 밑의 agent 파일의 create_agent_executor() 함수를 호출한다

# ReAct Agent 초기화
# ReAct: agent.py에서 가져옴
if "react_agent" not in st.session_state:
    st.session_state["react_agent"] = None

# include_domains 초기화
# 예) domain 제약을 걸었던 화면
if "include_domains" not in st.session_state:
    st.session_state["include_domains"] = []

# 사이드바 생성
with st.sidebar:
    # 초기화 버튼 생성
    clear_btn = st.button("대화 초기화")
    # 저작자 표기
    st.markdown("made by [@teddynote](https://youtube.com/c/teddynote)")

    # 모델 선택 메뉴
    # index=0; 0번째를 default로 설정하자
    selected_model = st.selectbox("LLM 선택", ["gpt-4o", "gpt-4o-mini"], index=0)

    # 검색 결과 개수 설정
    # 최대,최소,기본값 모두 조정 가능
    search_result_count = st.slider("검색 결과", min_value=1, max_value=10, value=3)

    # include_domains 설정
    # 세션 구분 헤더
    st.subheader("검색 도메인 설정")
    # news / general을 구분. news는 최신여부, general은 관련성 여부
    search_topic = st.selectbox("검색 주제", ["general", "news"], index=0)
    new_domain = st.text_input("추가할 도메인 입력")
    col1, col2 = st.columns([3, 1])
    with col1:
        # key="add_domain"를 지정 안해주면 오류가 발생함 (영역이 겹쳐짐)
        if st.button("도메인 추가", key="add_domain"):
            if new_domain and new_domain not in st.session_state["include_domains"]:
                st.session_state["include_domains"].append(new_domain)

    # 현재 등록된 도메인 목록 표시
    st.write("등록된 도메인 목록:")
    for idx, domain in enumerate(st.session_state["include_domains"]):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(domain)
        with col2:
            if st.button("삭제", key=f"del_{idx}"):
                st.session_state["include_domains"].pop(idx)
                st.rerun()

    # 설정 버튼
    # 아래 if 문으로 이어짐
    apply_btn = st.button("설정 완료", type="primary")

# 이부분 주목.
@dataclass
class ChatMessageWithType:
    chat_message: ChatMessage
    msg_type: str
    tool_name: str


# 이전 대화를 출력
def print_messages():
    for message in st.session_state["messages"]:
        # 새로운 메시지 추가와 연계 정
        # 텍스트 메시지
        if message.msg_type == "text":
            st.chat_message(message.chat_message.role).write(
                message.chat_message.content
            )
        # 웹호출 결과 
        elif message.msg_type == "tool_result":
            with st.expander(f"✅ {message.tool_name}"): # expander 형태 부여
                st.markdown(message.chat_message.content) # md 형태로 포맷팅


# 새로운 메시지를 추가
def add_message(role, message, msg_type="text", tool_name=""): #우선 tool_name 공란
    # 텍스트의 형태 메시지
    if msg_type == "text": 
        st.session_state["messages"].append(
            ChatMessageWithType(
                # 위 @dataclass 데코레이터와 인자가 똑같음
                chat_message=ChatMessage(role=role, content=message),
                msg_type="text",
                tool_name=tool_name,
            )
        )
    # 도구호출 (웹검색)
    elif msg_type == "tool_result":
        st.session_state["messages"].append(
            ChatMessageWithType(
                # 위 @dataclass 데코레이터와 인자가 똑같음
                chat_message=ChatMessage(
                    role="assistant", content=format_search_result(message)
                ),# 검색된 내용의 포맷팅 부여 by format_search_result(message)
                msg_type="tool_result",
                tool_name=tool_name,
            )
        )


# 초기화 버튼이 눌리면...
if clear_btn:
    st.session_state["messages"] = []
    st.session_state["thread_id"] = random_uuid()
# 이전 대화 기록 출력
print_messages()

# 사용자의 입력
user_input = st.chat_input("궁금한 내용을 물어보세요!")

# 경고 메시지를 띄우기 위한 빈 영역
warning_msg = st.empty()

# 설정 버튼이 눌리면...
if apply_btn:
    # WebSearchTool()호출
    # 참고) Tavily는 원래 다양한 옵션이 있는데, Langchain의 기본 implementation은
    # 이걸 다 반영하지 못함. Teddy가 그래서 integration하였음.
    tool = WebSearchTool().create()
    tool.max_results = search_result_count # 개수 동적 설정
    tool.include_domains = st.session_state["include_domains"] 
    tool.topic = search_topic
    # create_agent_executor() 호출
    st.session_state["react_agent"] = create_agent_executor(
        model_name=selected_model,
        # tool 추가하고 싶으면 [tool, tool2, tool3] 식으로 추가하면 됨
        tools=[tool], 
    )
    # 멀티턴 대화를 위한 thread_id 부여
    # -> clear_btn에서 thread_id 초기화 기능도 추가되어 있음
    st.session_state["thread_id"] = random_uuid()

# 만약에 사용자 입력이 들어오면...
if user_input:
    agent = st.session_state["react_agent"]
    # Config 설정
    
    if agent is not None:
        config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
        # 사용자의 입력
        st.chat_message("user").write(user_input)

        with st.chat_message("assistant"):
            # 빈 공간(컨테이너)을 만들어서, 여기에 토큰을 스트리밍 출력한다.
            container = st.empty()

            ai_answer = ""
            # stream_handler() 참고
            container_messages, tool_args, agent_answer = stream_handler(
                container,
                agent,
                {
                    "messages": [
                        ("human", user_input),
                    ]
                },
                config,
            )

            # 대화기록을 저장한다.
            add_message("user", user_input)
            for tool_arg in tool_args:
                add_message(
                    "assistant",
                    tool_arg["tool_result"],
                    "tool_result",
                    tool_arg["tool_name"],
                )
            add_message("assistant", agent_answer)
    # 설정버튼이 안눌렸을 경우
    else:
        warning_msg.warning("사이드바에서 설정을 완료해주세요.")

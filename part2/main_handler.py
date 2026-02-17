import re
import streamlit as st
from langsmith import uuid7

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

# models
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# custom tools
from src.code_interpreter import CodeInterpreterClient
from tools.code_interpreter import code_interpreter_tool, set_code_interpreter_client
from tools.bigquery import BigQueryClient

from youngjin_langchain_tools import StreamlitLanggraphHandler

###### dotenv을 사용하지 않는 경우 삭제해주세요 ######
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    import warnings

    warnings.warn(
        "dotenv not found. Please make sure to set your environment variables manually.",
        ImportWarning,
    )
################################################


@st.cache_data  # 캐시를 사용하도록 변경
def load_system_prompt(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def init_page():
    st.set_page_config(page_title="Data Analysis Agent", page_icon="🤗")
    st.header("Data Analysis Agent 🤗", divider="rainbow")
    st.sidebar.title("Options")

    # 메시지 초기화 / python runtime 초기화
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    if clear_button or "messages" not in st.session_state:
        welcome_message = "안녕하세요! BigQuery 데이터 분석 에이전트입니다. 분석하고 싶은 내용을 입력해주세요 🤗"
        st.session_state.messages = [{"role": "assistant", "content": welcome_message}]
        # 대화가 리셋될 때 Code Interpreter의 세션도 다시 생성
        st.session_state.code_interpreter_client = CodeInterpreterClient()
        set_code_interpreter_client(st.session_state.code_interpreter_client)
        st.session_state["checkpointer"] = InMemorySaver()
        st.session_state["thread_id"] = str(uuid7())
        st.session_state.custom_system_prompt = load_system_prompt(
            "./prompt/system_prompt.txt"
        )
        st.session_state.uploaded_files = []


def select_model():
    models = ("GPT-5.2", "Claude Sonnet 4.5", "Gemini 2.5 Flash")
    model = st.sidebar.radio("Choose a model:", models)
    if model == "GPT-5.2":
        return ChatOpenAI(temperature=0, model="gpt-5.2")
    elif model == "Claude Sonnet 4.5":
        return ChatAnthropic(temperature=0, model="claude-sonnet-4-5-20250929")
    elif model == "Gemini 2.5 Flash":
        return ChatGoogleGenerativeAI(temperature=0, model="gemini-2.5-flash")


def create_data_analysis_agent(bq_client):
    tools = [
        bq_client.get_table_info_tool(),
        bq_client.exec_query_tool(),
        code_interpreter_tool,
    ]
    llm = select_model()

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=st.session_state.custom_system_prompt,
        checkpointer=st.session_state["checkpointer"],
        debug=True,
    )

    return agent


def parse_response(response):
    """
    response에서 text와 image_paths를 가져옵니다

    response 예시
    ===
    비트코인의 종가 차트를 생성했습니다. 아래 이미지에서 확인할 수 있습니다.
    <img src="./files/file-s4W0rog1pjneOAtWeq21lbDy.png" alt="Bitcoin Closing Price Chart">

    image_path를 가져온 후에는 img 태그를 삭제합니다
    """
    # img 태그를 가져오기 위한 정규표현식 패턴
    img_pattern = re.compile(r'<img\s+[^>]*?src="([^"]+)"[^>]*?>')

    # img 태그를 검색하여 image_paths를 가져옴
    image_paths = img_pattern.findall(response)

    # img 태그를 삭제하여 텍스트를 가져옴
    text = img_pattern.sub("", response).strip()

    return text, image_paths


def display_content(content):
    text, image_paths = parse_response(content)
    st.write(text)
    for image_path in image_paths:
        st.image(image_path, caption="")


def main():
    init_page()
    bq_client = BigQueryClient(st.session_state.code_interpreter_client)
    data_analysis_agent = create_data_analysis_agent(bq_client)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            display_content(msg["content"])

    if prompt := st.chat_input(placeholder="분석하고 싶은 내용을 입력해주세요."):
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            handler = StreamlitLanggraphHandler(
                container=st.container(),
                expand_new_thoughts=True,
                max_thought_containers=4,
            )

            response = handler.invoke(
                agent=data_analysis_agent,
                input={"messages": [{"role": "user", "content": prompt}]},
                config={"configurable": {"thread_id": st.session_state["thread_id"]}},
            )

            if response:
                # handler가 반환한 응답에서 이미지 처리
                _, image_paths = parse_response(response)
                for image_path in image_paths:
                    st.image(image_path, caption="")
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )


if __name__ == "__main__":
    main()

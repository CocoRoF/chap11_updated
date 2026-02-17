from langchain_core.tools import tool
from pydantic import BaseModel, Field
import json


# 모듈 레벨 변수 - LangGraph가 별도 스레드에서 tool을 실행하므로
# st.session_state 대신 이 변수를 통해 client에 접근
_code_interpreter_client = None


def set_code_interpreter_client(client):
    """main.py에서 세션 초기화 시 호출하여 client를 설정"""
    global _code_interpreter_client
    _code_interpreter_client = client


class ExecPythonInput(BaseModel):
    """타입을 지정하기 위한 클래스"""

    code: str = Field()


@tool(args_schema=ExecPythonInput)
def code_interpreter_tool(code):
    """
    Code Interpreter를 사용해 Python 코드를 실행합니다.
    (Responses API 기반 - 새로운 마이그레이션 버전)

    - 데이터 가공, 시각화, 수식 계산, 통계 분석, 텍스트 분석에 적합합니다.
    - 인터넷 연결이 없어 외부 사이트 접근이나 라이브러리 설치는 불가합니다.
    - 코드 실행 결과와 생성 파일을 함께 확인할 수 있습니다.

    오류 발생 시:
    - 같은 코드를 반복하지 말고 다른 접근법 시도
    - seaborn 오류 → matplotlib 또는 pandas.plot 사용
    - 최대 2회 시도 후 사용자에게 보고

    Returns:
    - text: Code Interpreter의 코드 실행 결과
    - files: Code Interpreter가 생성한 파일 경로 (`./files/` 이하)
    """
    print("\n\n=== Executing Code (Responses API) ===")
    print(code)
    print("======================================\n\n")

    text_result, file_names = _code_interpreter_client.run(code)

    # 결과를 명확한 형식으로 포맷팅
    if file_names:
        return json.dumps([text_result, file_names], ensure_ascii=False)
    else:
        return json.dumps([text_result, []], ensure_ascii=False)

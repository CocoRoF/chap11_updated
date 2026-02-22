import os
import traceback
from openai import OpenAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class CodeInterpreterClient:
    """
    LangChain ChatOpenAI의 Responses API의 built-in Code Interpreter를 사용하여
    Python 코드를 실행하거나 파일을 읽고 분석을 수행하는 클래스

    이 클래스는 다음 기능을 제공합니다：
    1. LangChain ChatOpenAI + Responses API를 사용한 Python 코드 실행
    2. 파일 업로드 및 Container에 파일 등록
    3. 업로드한 파일을 사용한 데이터 분석 및 그래프 생성

    주요 메서드：
    - upload_file(file_content): 파일을 업로드하여 Container에 등록한다
    - run(code): LangChain ChatOpenAI의 built-in Code Interpreter를 사용해 Python 코드를 실행한다

    LangChain OpenAI Responses API 기반:
    - ChatOpenAI.bind_tools([{"type": "code_interpreter", ...}])
    - 서버사이드 코드 실행으로 대폭 간소화

    Example:
    ===============
    from src.code_interpreter import CodeInterpreterClient
    code_interpreter = CodeInterpreterClient()
    code_interpreter.upload_file(open('file.csv', 'rb').read(), 'file.csv')
    code_interpreter.run("print('hello')")
    """

    def __init__(self):
        self.openai_client = OpenAI()
        self.container_id = self._create_container()
        self._create_file_directory()
        # LangChain ChatOpenAI with built-in Code Interpreter (Responses API)
        self.llm = ChatOpenAI(
            model="gpt-5-mini",
            include=["code_interpreter_call.outputs"],
            temperature=0,
        ).bind_tools([
            {
                "type": "code_interpreter",
                "container": self.container_id,
            }
        ])


    def _create_file_directory(self):
        directory = "./files/"
        os.makedirs(directory, exist_ok=True)

    def _create_container(self):
        """
        Code Interpreter 실행을 위한 Container를 생성합니다.
        Container는 코드 실행 환경을 제공하며, 파일도 함께 관리됩니다.
        """
        container = self.openai_client.containers.create(
            name="code-interpreter-session"
        )
        return container.id

    def upload_file(self, file_content, filename="uploaded_file.csv"):
        # Container에 파일 직접 업로드 (Responses API 방식)
        self.openai_client.containers.files.create(
            container_id=self.container_id,
            file=(filename, file_content),
        )
        return filename

    def run(self, code):
        """
        LangChain ChatOpenAI의 built-in Code Interpreter를 사용하여
        Python 코드를 실행합니다.

        Args:
            code: 실행할 Python 코드 문자열

        Returns:
            tuple: (text_content, file_names)
                - text_content: 코드 실행 결과 텍스트
                - file_names: 생성된 파일 경로 리스트
        """
        prompt = f"""다음 코드를 실행하고 결과를 반환해 주세요.
```python
{code}
```
"""
        try:
            before_file_ids = self._list_container_file_ids()
            response = self.llm.invoke(prompt)
            text_parts = []
            content = response.content if isinstance(response.content, list) else []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "code_interpreter_call":
                    for item in block.get("outputs", []):
                        if isinstance(item, dict):
                            logs = item.get("logs", "")
                            if logs:
                                text_parts.append(logs)

            output = "\n".join(text_parts).strip()
            file_names = self._download_new_files(before_file_ids)

            return output, file_names

        except Exception as e:
            error_msg = f"[Code Interpreter 오류]\n{traceback.format_exc()}"
            return error_msg, []

    def _list_container_file_ids(self):
        """현재 Container에 존재하는 파일 ID 목록을 반환합니다."""
        file_ids = set()
        result = self.openai_client.containers.files.list(container_id=self.container_id)
        for f in result.data:
            file_ids.add(f.id)

        return file_ids

    def _download_new_files(self, before_file_ids):
        """실행 전후 Container 파일 목록을 비교하여 새로 생긴 파일을 다운로드합니다."""
        after_file_ids = self._list_container_file_ids()
        new_file_ids = after_file_ids - before_file_ids

        file_paths = []
        for file_id in new_file_ids:
            path = self._download_file(self.container_id, file_id)
            file_paths.append(path)
        return file_paths

    def _download_file(self, container_id, file_id):
        file_info = self.openai_client.containers.files.retrieve(
            container_id=container_id,
            file_id=file_id,
        )
        original_filename = os.path.basename(getattr(file_info, "path", None))

        content = self.openai_client.containers.files.content.retrieve(
            file_id=file_id,
            container_id=container_id,
        )

        file_name = f"./files/{original_filename}"
        with open(file_name, "wb") as f:
            f.write(content.read())

        return file_name

# GitHub: https://github.com/naotaka1128/llm_app_codes/chapter_011/part2/src/code_interpreter.py

import os
import traceback
import httpx
from openai import OpenAI
from langchain_openai import ChatOpenAI


class CodeInterpreterClient:
    """
    LangChain ChatOpenAI의 Responses API의 built-in Code Interpreter를 사용하여
    Python 코드를 실행하거나 파일을 읽고 분석을 수행하는 클래스

    이 클래스는 다음 기능을 제공합니다：
    1. LangChain ChatOpenAI + Responses API를 사용한 Python 코드의 실행
    2. 파일 업로드 및 Container에 파일 등록
    3. 업로드된 파일을 사용한 데이터 분석 및 그래프 생성

    주요 메서드：
    - upload_file(file_content): 파일을 업로드하여 Container에 등록한다
    - run(code): LangChain ChatOpenAI의 built-in Code Interpreter를 사용하여 Python 코드를 실행한다

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
            model="gpt-4o",
            include=["code_interpreter_call.outputs"],
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

        이전 Assistants API의 Assistant + Thread 조합을 대체합니다.
        """
        container = self.openai_client.containers.create(
            name="code-interpreter-bigquery-session"
        )
        return container.id

    def upload_file(self, file_content, filename="uploaded_file.csv"):
        """
        Upload file to Container for Code Interpreter

        Args:
            file_content: File content (bytes)
            filename: Original filename to preserve in container
        Returns:
            filename: The filename accessible in container
        """
        # Container에 파일 직접 업로드 (Responses API 방식)
        self.openai_client.containers.files.create(
            container_id=self.container_id,
            file=(filename, file_content),
        )
        return filename  # Container 내에서 접근 가능한 파일명 반환

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
**중요 규칙**:
- 코드 실행 결과(stdout, stderr)를 정확히 반환해주세요
- 오류 발생 시 전체 traceback을 포함해주세요
- 파일 경로 등이 조금 틀려 있는 경우 적절히 수정해주세요
"""
        try:
            # LangChain ChatOpenAI의 built-in Code Interpreter로 코드 실행
            response = self.llm.invoke(prompt)

            # 코드 실행 결과(stdout/stderr) 추출
            code_output = self._extract_code_output(response)

            # 모델의 텍스트 응답
            text_content = response.text or ""

            # 코드 실행 결과가 있으면 포함
            if code_output:
                text_content = f"[실행 결과]\n{code_output}\n\n{text_content}"

            # 파일 다운로드
            file_names = self._extract_and_download_files(response)

            return text_content, file_names

        except Exception as e:
            error_msg = f"[Code Interpreter 오류]\n{traceback.format_exc()}"
            print(error_msg)
            return error_msg, []

    def _extract_code_output(self, response):
        """content_blocks에서 코드 실행 결과(stdout/stderr)를 추출합니다."""
        output = ""
        content = response.content if isinstance(response.content, list) else []
        for block in content:
            if isinstance(block, dict):
                # code_interpreter_call 내의 outputs
                if block.get("type") == "code_interpreter_call":
                    for item in block.get("outputs", []):
                        if isinstance(item, dict):
                            output += item.get("logs", "")
                            output += item.get("output", "")
        return output.strip()

    def _extract_and_download_files(self, response):
        """content_blocks의 annotations에서 파일 참조를 추출하고 다운로드합니다."""
        file_paths = []
        content = response.content if isinstance(response.content, list) else []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                for ann in block.get("annotations", []):
                    if ann.get("type") == "container_file_citation":
                        extras = ann.get("extras", {})
                        file_id = extras.get("file_id") or ann.get("file_id")
                        container_id = extras.get("container_id") or ann.get("container_id")
                        if file_id and container_id:
                            path = self._download_file(container_id, file_id)
                            file_paths.append(path)
        return file_paths

    def _download_file(self, container_id, file_id):
        """
        Container 파일을 다운로드하여 로컬에 저장합니다.

        Args:
            container_id: OpenAI Container ID
            file_id: Container 내의 파일 ID

        Returns:
            str: 저장된 파일의 경로
        """
        # 파일명에서 확장자 추출 시도
        extension = ""
        if "." in file_id:
            # file_id가 "cfile_xxx.png" 같은 형식일 수 있음
            extension = "." + file_id.split(".")[-1]

        # 확장자가 없으면 PNG로 추정 (대부분의 이미지가 PNG)
        if not extension:
            extension = ".png"

        file_name = f"./files/{file_id}{extension}"

        # Container files content API를 사용하여 파일 다운로드
        api_key = self.openai_client.api_key
        base_url = self.openai_client.base_url
        url = f"{base_url}/containers/{container_id}/files/{file_id}/content"
        headers = {"Authorization": f"Bearer {api_key}"}

        resp = httpx.get(url, headers=headers)
        resp.raise_for_status()

        with open(file_name, "wb") as f:
            f.write(resp.content)

        return file_name

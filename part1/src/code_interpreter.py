import os

import mimetypes
import traceback
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class CodeInterpreterClient:
    """
    OpenAI의 Responses API의 Code Interpreter Tool을 사용하여
    Python 코드를 실행하거나 파일을 읽고 분석을 수행하는 클래스

    이 클래스는 다음 기능을 제공합니다：
    1. OpenAI Responses API를 사용한 Python 코드 실행
    2. 파일 업로드 및 Container에 파일 등록
    3. 업로드한 파일을 사용한 데이터 분석 및 그래프 생성

    주요 메서드：
    - upload_file(file_content): 파일을 업로드하여 Container에 등록한다
    - run(code): Responses API를 사용해 Python 코드를 실행하거나 파일 분석을 수행한다

    Assistants API에서 Responses API로 마이그레이션:
    - Assistant + Thread → Container
    - create_and_poll → responses.create (동기 방식)
    - 파일 관리 방식 간소화

    Example:
    ===============
    from src.code_interpreter import CodeInterpreterClient
    code_interpreter = CodeInterpreterClient()
    code_interpreter.upload_file(open('file.csv', 'rb').read())
    code_interpreter.run("file.csv의 내용을 읽어서 그래프를 그려주세요")
    """

    def __init__(self):
        self.file_ids = []
        self.openai_client = OpenAI()
        self.container_id = self._create_container()
        self._create_file_directory()
        self.code_intepreter_instruction = """
        제공된 데이터 분석용 Python 코드를 실행해주세요.
        실행한 결과를 반환해주세요. 당신의 분석 결과는 필요하지 않습니다.
        다시 한 번 반복합니다, 실행한 결과를 반환해주세요.
        파일 경로 등이 조금 틀려 있을 경우에는 적절히 수정해주세요.
        수정한 경우에는 수정 내용을 설명해주세요.
        """

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
        """
        Upload file to Container for Code Interpreter
        Args:
            file_content: File content (bytes)
            filename: Original filename to preserve in container
        Returns:
            filename: The filename accessible in container
        """
        # Container에 파일 직접 업로드 (Responses API 방식)
        container_file = self.openai_client.containers.files.create(
            container_id=self.container_id,
            file=(filename, file_content),
        )
        self.file_ids.append(container_file.id)
        return filename  # Container 내에서 접근 가능한 파일명 반환

    def run(self, code):
        """
        Responses API를 사용하여 Python 코드를 실행합니다.

        Args:
            code: 실행할 Python 코드 문자열

        Returns:
            tuple: (text_content, file_names)
                - text_content: 코드 실행 결과 텍스트
                - file_names: 생성된 파일 경로 리스트
        """

        prompt = f"""
        다음 코드를 실행하고 결과를 반환해 주세요.
        ```python
        {code}
        ```
        **중요 규칙**:
        - 코드 실행 결과(stdout, stderr)를 정확히 반환해주세요
        - 오류 발생 시 전체 traceback을 포함해주세요
        - 생성된 파일은 자동으로 첨부됩니다
        """

        try:
            # Responses API를 사용하여 코드 실행
            response = self.openai_client.responses.create(
                model="gpt-4o",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
                tools=[
                    {
                        "type": "code_interpreter",
                        "container": self.container_id,
                    }
                ],
                tool_choice="auto",
            )

            # 응답에서 텍스트와 파일 추출
            text_content = ""
            code_output = ""  # code_interpreter 실행 결과
            file_info_list = []  # (container_id, file_id) 튜플 리스트

            for item in response.output:
                # code_interpreter_call에서 실제 실행 결과 추출
                if item.type == "code_interpreter_call":
                    # 코드 실행 결과 (stdout/stderr) 추출
                    if hasattr(item, 'code_interpreter_call'):
                        call_info = item.code_interpreter_call
                        if hasattr(call_info, 'results'):
                            for result in call_info.results:
                                if hasattr(result, 'logs') and result.logs:
                                    code_output += result.logs + "\n"
                        if hasattr(call_info, 'error') and call_info.error:
                            code_output += f"\n[ERROR]: {call_info.error}\n"

                # 메시지 타입에서 텍스트 및 파일 추출
                elif item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            text_content += content.text

                            # annotations에서 파일 정보 추출
                            if hasattr(content, 'annotations') and content.annotations:
                                for annotation in content.annotations:
                                    if hasattr(annotation, 'type') and annotation.type == 'container_file_citation':
                                        if hasattr(annotation, 'file_id') and hasattr(annotation, 'container_id'):
                                            file_id = annotation.file_id
                                            container_id = annotation.container_id
                                            file_info_list.append((container_id, file_id))

            # 코드 실행 결과가 있으면 포함
            if code_output:
                text_content = f"[실행 결과]\n{code_output}\n\n{text_content}"

            # 파일 다운로드
            file_names = []
            if file_info_list:
                for container_id, file_id in file_info_list:
                    downloaded_path = self._download_container_file(container_id, file_id)
                    file_names.append(downloaded_path)

            return text_content, file_names

        except Exception as e:
            error_msg = f"[Code Interpreter 오류]\n{traceback.format_exc()}"
            print(error_msg)
            return error_msg, []

    def _download_container_file(self, container_id, file_id):
        """
        Container 파일을 다운로드하여 로컬에 저장합니다.

        Args:
            container_id: OpenAI Container ID
            file_id: Container 내의 파일 ID

        Returns:
            str: 저장된 파일의 경로
        """
        # Container files content API를 사용하여 파일 다운로드
        # API path: GET /v1/containers/{container_id}/files/{file_id}/content

        import httpx

        # OpenAI client의 base_url과 api_key 사용
        api_key = self.openai_client.api_key
        base_url = self.openai_client.base_url

        url = f"{base_url}/containers/{container_id}/files/{file_id}/content"

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        response = httpx.get(url, headers=headers)
        response.raise_for_status()

        data_bytes = response.content

        # 파일명에서 확장자 추출 시도
        extension = ""
        if "." in file_id:
            # file_id가 "cfile_xxx.png" 같은 형식일 수 있음
            extension = "." + file_id.split(".")[-1]

        # 확장자가 없으면 PNG로 추정 (대부분의 이미지가 PNG)
        if not extension:
            extension = ".png"

        file_name = f"./files/{file_id}{extension}"
        with open(file_name, "wb") as file:
            file.write(data_bytes)

        return file_name

import os
import magic
import traceback
import mimetypes
from openai import OpenAI


class CodeInterpreterClient:
    """
    OpenAI의 Assistants API의 Code Interpreter Tool을 사용해서
    Python 코드를 실행하거나 파일을 읽어서 분석을 수행하는 클래스

    이 클래스는 다음과 같은 기능을 제공합니다:
    1. OpenAI Assistants API를 사용한 Python 코드 실행
    2. 파일 업로드 및 Assistants API에 등록
    3 업로드한 파일을 사용해서 데이터 분석 및 그래프 작성

        주요 메서드:
    - upload_file(file_content): 파일을 업로드해서 Assistants API에 등록한다
    - run(prompt): Assistants API를 사용해서 Python 코드를 실행하거나 파일 분석을 수행한다

    Example:
    ===============
    from src.code_interpreter import CodeInterpreter
    code_interpreter = CodeInterpreter()
    code_interpreter.upload_file(open('file.csv', 'rb').read())
    code_interpreter.run("file.csv의 내용을 읽고 그래프를 그려 주세요")
    """

    def __init__(self):
        self.file_ids = []
        self.openai_client = OpenAI()
        self.assistant_id = self._create_assistant_agent()
        self.thread_id = self._create_thread()
        self._create_file_directory()
        self.code_intepreter_instruction = """
	제공된 데이터 분석용 Python 코드를 실행해 주세요.
	실행한 결과를 반환해 주세요. 당신의 분석 결과는 필요하지 않습니다.
	다시 한 번 말합니다. 실행한 결과를 반환해 주세요.
	파일 경로 등이 조금 틀린 경우에는 적절히 수정해 주세요.
        修正した場合は、修正内容を説明してください。
	수정한 경우에는 수정 내용을 설명해 주세요.
        """

    def _create_file_directory(self):
        directory = "./files/"
        os.makedirs(directory, exist_ok=True)

    def _create_assistant_agent(self):
        self.assistant = self.openai_client.beta.assistants.create(
            name="Python Code Runner",
            instructions="You are a python code runner. Write and run code to answer questions.",
            tools=[{"type": "code_interpreter"}],
            model="gpt-4o",
            tool_resources={"code_interpreter": {"file_ids": self.file_ids}},
        )
        return self.assistant.id

    def _create_thread(self):
        thread = self.openai_client.beta.threads.create()
        return thread.id

    def upload_file(self, file_content):
        """
        Upload file to assistant agent

        Args:
            file_content (_type_): open('file.csv', 'rb').read()
        """
        file = self.openai_client.files.create(file=file_content, purpose="assistants")
        self.file_ids.append(file.id)
        # Assistant에 새 파일을 추가해서 update하세요
        self._add_file_to_assistant_agent()
        return file.id

    def _add_file_to_assistant_agent(self):
        self.assistant = self.openai_client.beta.assistants.update(
            assistant_id=self.assistant_id,
            tool_resources={"code_interpreter": {"file_ids": self.file_ids}},
        )

    def run(self, code):
        prompt = f"""
	다음 코드를 실행하고 결과를 반환해 주세요
	파일 읽기에 실패한 경우, 가능한 범위 내에서 수정하고 다시 실행해 주세요.
        ```python
        {code}
        ```
	당신의 의견이나 감상은 필요 없으니 실행 결과만 반환해 주세요
        """

        # add message to thread
        self.openai_client.beta.threads.messages.create(
            thread_id=self.thread_id, role="user", content=prompt
        )

        # run assistant to get response
        run = self.openai_client.beta.threads.runs.create_and_poll(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            instructions=self.code_intepreter_instruction,
        )
        if run.status == "completed":
            message = self.openai_client.beta.threads.messages.list(
                thread_id=self.thread_id, limit=1  # Get the last message
            )
            try:
                file_ids = []
                for content in message.data[0].content:
                    if content.type == "text":
                        text_content = content.text.value
                        file_ids.extend(
                            [
                                annotation.file_path.file_id
                                for annotation in content.text.annotations
                            ]
                        )
                    elif content.type == "image_file":
                        file_ids.append(content.image_file.file_id)
                    else:
                        raise ValueError("Unknown content type")
            except:
                print(traceback.format_exc())
                return None, None
        else:
            raise ValueError("Run failed")

        file_names = []
        if file_ids:
            for file_id in file_ids:
                file_names.append(self._download_file(file_id))

        return text_content, file_names

    def _download_file(self, file_id):
        data = self.openai_client.files.content(file_id)
        data_bytes = data.read()

        # 파일의 내용으로부터 MIME 타입을 추출
        mime_type = magic.from_buffer(data_bytes, mime=True)

        # MIME 타입에서 확장자를 추출
        extension = mimetypes.guess_extension(mime_type)

        # 확장자를 얻을 수 없는 경우에는 기본 확장자를 사용
        if not extension:
            extension = ""

        file_name = f"./files/{file_id}{extension}"
        with open(file_name, "wb") as file:
            file.write(data_bytes)

        return file_name

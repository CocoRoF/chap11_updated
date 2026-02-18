11.2 데이터 분석 에이전트란?
이 장에서 구현할 에이전트의 목적은 데이터 분석입니다. 이 에이전트는 ChatGPT의 UI에도 탑재된 고급 데이터 분석 기능(Advanced Data Analysis)과 유사합니다.
이 기능은 CSV 파일을 업로드하면 ChatGPT가 Python 코드를 생성하고 실행해서 데이터 분석과 시각화를 수행해 줍니다. 매우 똑똑하고 사용하기도 편리하지만 기본적으로 ChatGPT의 UI를 통해서만 사용할 수 있다는 제약이 있습니다.
또한 업로드한 데이터가 OpenAI의 모델 학습에 사용될 가능성이 있기 때문에 기밀성이 높은 정보는 업로드하지 않을 것을 권장합니다. 이 문제는 ChatGPT Enterprise 계약으로 해결할 수 있지만 비용 등의 제약으로 계약이 가능한 기업은 한정적일 것입니다. 게다가 사내 데이터베이스나 Google BigQuery 같은 외부 데이터 소스와 연계할 수 없다는 제한도 있습니다.
그래서 이 장에서는 이런 문제를 해결하는 데이터 분석 에이전트를 구현합니다. 이 에이전트는 CSV 업로드나 BigQuery 연동을 통해 데이터를 취득하고 Python 코드를 사용해서 분석을 수행할 수 있습니다.
구체적인 구현 흐름은 다음과 같습니다. 상당히 기므로 한 단계씩 꾸준히 구현합시다.
1. OpenAI Assistants API(이하 Assistants API)를 이해한다
2. Assistants API를 사용해서 Python 코드를 실행하는 환경을 구축한다
3. CSV 파일을 업로드하고 에이전트에게 분석시킨다
4. 에이전트가 BigQuery에서 데이터를 가져와서 분석하게한다
이전 장에서는 장의 앞부분에 에이전트나 애플리케이션 동작의 흐름 그림을 넣었지만, 이번 장에서는 OpenAI Assistants API의 설명이 길어지는 관계로 그림은 나중에 수록합니다. 우선은 OpenAI Assistants API 설명부터 시작하겠습니다.

11.3 배경 지식: OpenAI Assistants API
이 장에서는 데이터 분석을 위해 Python 코드를 실행하는 에이전트를 구현합니다. 코드 실행 환경으로는 Assistants API가 제공하는 ‘Code Interpreter’를 활용합니다. Code Interpreter는 샌드박스 환경에서 Python 코드를 실행할 수 있을 뿐만 아니라 다음과 같은 장점이 있습니다.
● 코드 실행에 실패하면 자율적으로 코드를 수정해서 다시 실행한다.
● 이미지 파일이나 CSV 파일와 같은 여러 가지 데이터와 파일 형식을 처리할 수 있기 때문에 그래프 시각화와 같은 데이터 분석 작업에 활용할 수 있다.
Assistants API는 원래 에이전트를 구현하기 위한 것이지만 이 책에서는 Python 코드 실행 환경으로만 활용합니다. Assistants API를 사용할 때 알아두어야 할 사항이 많지 않지만, 작동 원리 정도는 알아두는 것도 매우 도움이 됩니다. 그래서 여기서 자세하게 설명합니다.

참고: OpenAI는 최근 Assistants API를 대체하는 새로운 Responses API를 발표했습니다. Responses API는 보다 간결하고 효율적인 인터페이스를 제공하지만, 본 서적에서는 안정적이고 검증된 Assistants API를 기준으로 설명합니다.

다음과 같은 흐름으로 Assistants API와 Code Interpreter를 이해한 뒤에 에이전트 구현으로 넘어가겠습니다
1. 먼저 Assistants API의 개요에 대해 설명합니다. 본 장에서는 최종적으로 사용하지 않는 것이므로, Code Interpreter 외에는 가볍게 다룰 것입니다.
2. 다음으로, Code Interpreter에 대해 설명합니다. 이는 Python 코드 실행 도구를 구축하는 데 필수적인 지식이 됩니다.
3. 그 후, 본 장의 에이전트 구축에 진행합니다. 강력한 도구를 구축함으로써, 유용한 에이전트가 간편하게 구축될 수 있음을 확인하시기 바랍니다.

11.3.1 Assistants API 개요
OpenAI Assistants API는 개발자가 강력한 AI 어시스턴트(에이전트)를 간단하게 개발할 수 있도록 설계된 API 모음입니다. 이 API가 제공하는 유용한 툴과 OpenAI의 모델을 조합하면 다양한 문제를 해결할 수 있는 고도화된 AI 어시스턴트를 구현할 수 있습니다.
2025년 12월 현재, Assistants API에는 다음 세 가지 도구가 내장되어 있습니다.
1. Code Interpreter: Python 코드를 샌드박스 환경에서 작성하고 실행할 수 있는 도구. 여러 가지 데이터와 파일을 처리하고 데이터나 이미지와 같은 파일을 생성할 수 있습니다.
2. File Search: 어시스턴트의 지식을 고유한 제품 정보나 사용자가 제공한 문서로 확장할 수 있는 툴. OpenAI가 문서를 자동으로 분석·분할하고 Embedding 해서 저장하고, 벡터 검색과 키워드 검색을 통해 사용자 쿼리와 관련된 콘텐츠를 가져옵니다.
3. Function calling: 어시스턴트가 외부 API나 툴을 호출할 수 있게 해주는 도구. 앞 장에서 다룬 것과 거의 동일하므로 이 장에서는 자세히 설명하지 않습니다.

11.3.2 Assistants API 사용법
Assistants API를 사용하기 위해서는 몇 가지 중요한 객체를 이해하는 것이 중요합니다. 아래 그림은 Assistants API의 주요 객체와 그 관계를 나타냅니다.

그림 11.1: Assistant, Thread, Run의 관계
각 객체의 역할은 아래 표와 같습니다.
객체	설명
Assistant	어시스턴트(에이전트)를 정의하는 객체. 사용할 ChatGPT 모델, 명령(≒System Prompt), 사용 가능한 툴과 툴이 참조할 파일 목록 등을 지정해서 생성한다.
Thread	사용자와 어시스턴트의 대화 세션을 저장하는 객체. 대화 기록을 Message 객체에 리스트로 저장하며 필요하면 자동으로 오래된 메시지를 삭제한다.[박41.1]
Message	사용자나 어시스턴트가 작성한 메시지를 나타내는 객체. 텍스트, 이미지, 그 외의 파일을 포함할 수 있으며 Thread에 리스트로 저장된다
Run	Thread에 대해 Assistant를 실행하는 것을 나타내는 객체.
Assistant는 Thread의 메시지를 입력으로 처리하고, 새로운 Message를 추가한다.
Run Step	Run 중에 어시스턴트가 수행한 개별 작업을 나타내는 객체. 툴 호출이나 메시지 생성 등의 세부 내역을 기록한다.

Assistants API를 사용하는 기본적인 흐름은 다음과 같습니다.
1. Assistant를 생성한다. 사용할 모델, 명령, 사용할 수 있는 툴등을 지정합니다.
2. 대화 세션을 기록할 Thread를 생성합니다.
3. Thread에 사용자 질문을 Message로 추가한다.
4. Thread를 지정해서 Assistant를 Run한다. 어시스턴트는 모델과 툴을 사용해서 응답을 생성하고 그 응답을 Thread에 추가한다.
5. 결과를 확인한다. 어시스턴트가 추가한 메시지 내용과 필요하다면 Run의 상세 정보를 확인한다.
Assistants API를 사용하는 에이전트 구축은 단계별로 코드 예시와 함께 자세히 설명합니다. LangChain은 현재 Assistants API의 기능을 충분히 지원하지 않기 때문에 OpenAI의 공식 라이브러리를 사용해서 코드 예시를 제시합니다.

▶Assistant 생성
Assistant는 OpenAI의 API를 사용해서 다음과 같이 생성합니다.
from openai import OpenAI

client = OpenAI()
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="당신은 개인 수학 튜터입니다. 수학 질문에 답하기 위해 코드를 작성하고 실행하세요.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}],
)

이 코드에서 다음과 같은 매개변수를 지정해서 Assistant를 생성합니다.
● name: 어시스턴트의 이름
● instructions: 어시스턴트의 역할이나 동작을 지시하는 명령(System Prompt와 거의 동일)
● model: 어시스턴트가 사용할 모델
● tools: 어시스턴트가 사용할 수 있는 툴(여기에서는 code_interpreter)

그 밖에도, 다음과 같은 매개변수를 지정할 수 있습니다.
● description: 어시스턴트에 대한 상세한 설명
● tool_resources: 툴이 사용할 리소스(예: 파일 등). Code Interpreter를 사용할 때는 여기에 분석할 파일 목록을 정의합니다. (자세한 내용은 뒤에서 설명합니다).
▶Thread 생성
Thread는 아래와 같이 생성합니다.
thread = client.beta.threads.create()

생성한 Thread에 Message를 추가할 수 있습니다.
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="방정식 3x + 11 = 14를 풀어야 합니다. 도와주실 수 있나요?",
)

이 코드는 다음과 같은 매개변수로를 지정해서 Message를 생성합니다.
● thread_id: 메시지를 추가할 Thread ID
● role: 메시지 역할(사용자 또는 어시스턴트)
● content: 메시지 내용
Thread에는 다음과 같은 특징이 있습니다.
● 여러 개의 메시지를 추가할 수 있다
● 모델의 컨텍스트 윈도우 크기를 초과하면 오래된 Message부터 순서대로 잘라낸다
● Message를 잘라내는 방식은 Run을 생성할 때 truncation_strategy로 지정할 수 있다

▶Run 생성과 실행
Run은 다음과 같은 방식으로 생성하고 실행합니다.
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant.id,
)

이 코드에서 다음과 같은 매개변수를 지정해서 Run을 생성합니다.
● thread_id: Run을 실행할 Thread ID
● assistant_id: Run에서 사용할 Assistant ID

create_and_poll 메서드를 사용하면 Run을 시작하고 Assistant의 응답이 완료될 때까지 기다리는 작업을 동시에 수행할 수 있습니다. Run에는 다음과 같은 옵션이 있습니다
● max_prompt_tokens: Run에서 사용할 프롬프트의 최대 토큰 수
● max_completion_tokens: Run에서 생성할 응답의 최대 토큰 수
● runcation_strategy: 메시지를 잘라내는 방식
   · "auto"로 지정하면 OpenAI의 기본 잘라내기 전략이 사용된다
   · "last_messages"로 지정하면 지정된 개수의 최신 메시지만 사용된다
Run이 완료되면 Assistant의 응답을 Thread의 가장 최신 Message로 얻을 수 있습니다.
response = client.beta.threads.messages.list(
    thread_id=thread_id,
    limit=1 # Get the last message
)

▶Message annotations
Assistant가 생성한 메시지에는 annotations가 포함된 경우가 있습니다. annotations는 메시지의 content 안에 배열 형태로 표현됩니다.
다음은 file_citation annotations가 포함된 메시지의 예시입니다.
{
    "id": "msg_abc123",
    "object": "thread.message",
    "created_at": 1698964262,
    "thread_id": "thread_abc123",
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": {
                "value": " According to the file [0], the total revenue in 2022 was $120
                        million.",
                "annotations": [
                    {
                        "type": "file_citation",
                        "text": "[0]",
                        "start_index": 24,
                        "end_index": 27,
                        "file_citation": {
                            "file_id": "file_abc123",
                            "quote": "the total revenue in 2022 was $120 million"
                        }
                    }
                ]
            }
        }
    ]
}

이 예시에서는 content의 annotations 배열에 file_citation이 있습니다. 이 annotations은 메시지의 특정 부분(start_index부터 end_index까지의 범위)이 파일에서 인용되었다는 것을 나타냅니다. file_id는 인용 출처 파일의 ID이고 quote는 실제 인용된 텍스트를 나타냅니다.
메시지에 annotations가 포함된 경우에는 text의 value에는 인용 표식(citation marker)(예: [0])이 포함되어 있습니다. 애플리케이션에서 메시지를 처리할 때는 이런 인용 표식을 annotations 정보를 사용해서 적절한 텍스트나 링크 등으로 치환해야 합니다.
이상으로 Assistants API의 주요 객체들에 대한 설명과 코드 예시를 마칩니다.
이런 객체들을 적절히 활용하면 강력한 AI 어시스턴트를 구축할 수 있습니다.

11.3.3 FileSearch 개요
다음으로는 Assistants API의 File Search 기능을 설명합니다. Assistants API의 File Search는 사용자가 제공한 문서를 Assistant에 포함하는 기능입니다. RAG(Retrieval-Augmented Generation)와 동일한 개념이며 다음 작업을 자동으로 수행합니다.
1. 문서의 분석 및 분할
2. 각 청크(chunk)에 대한 Embedding  및 저장
3. 사용자 쿼리에 대한 벡터 검색 및 키워드 검색
4. 사용자 쿼리와 관련된 콘텐츠 추출
이 책에서는 RAG의 동작 원리를 이해하기 위해서 LangChain을 사용해서 구현했습니다. 최근의 Assistants API의 File Search 기능은 파일 검색 정확도에 중점을 두고 있는 인상이며 앞으로 더 사용하기 쉬워질 가능성이 있습니다. 따라서 이 책에서는 사용하지는 않지만, Assistants API의 중요한 기능이기 때문에 설명합니다.

▶FileSearch의 동작 방식
File Search는 다음과 같은 흐름으로 동작 합니다.
1. 사용자가 파일(PDF, 텍스트 파일 등)을 업로드
2. OpenAI가 파일을 자동으로 분석해서 청크로 분할
3. 각 청크를 Embedding 한 후에 벡터 DB에 저장
4. 사용자가 질문하면 File Search가 Assistant와 Thread에 연결된 파일로부터 키워드 검색과 시맨틱 검색을 수행.
5. 필요에 따라 검색 결과를 리랭킹하고 가장 관련성이 높은 정보를 추출해서 Assistant의 응답에 포함한다.
File Search의 기본 설정은 다음과 같습니다.
● 청크 크기: 800토큰
● 청크 오버랩: 400토큰
● 내장 모델: text-embedding-3-large（256차원）
● 컨텍스트에 추가되는 청크의 최대 수: 20 (상황에 따라 적어질 가능성 있음)
단, File Search에는 몇 가지 제한 사항이 있습니다.
● Embedding 방식이나 기타 설정을 변경할 수 없다
● 사용자 정의 메타데이터를 활용한 필터링은 지원하지 않는다
● 문서 내의 이미지(그래프나 표 등의 이미지를 포함한다) 분석은 지원하지 않는다
● 구조화된 파일 형식(csv, jsonl 등)에 대한 검색 지원은 제한적이다
● 요약 기능은 제한적 (현재 도구는 검색 쿼리 최적화에 중점이 있음)
청크 분할 방식 등 자세한 사양은 OpenAI의 공식 문서를 참조해 주세요.
● Customizing File Search settings: https://platform.openai.com/docs/assistants/tools/file-search/customizing-file-search-settings

다음으로 Assistants API의 Vector Store 기능에 관해 설명합니다.
▶Vector Store 개요
Vector Store는 File Search에서 사용할 파일을 저장하기 위한 데이터베이스입니다. 파일을 Vector Store에 추가하면 자동으로 파일이 분석, 분할되고 Embedding 되어 벡터 DB에 저장됩니다.
각 Vector Store에는 최대 10,000개의 파일을 저장할 수 있으며, Assistant와 Thread 양쪽에 연결할 수 있습니다. 2024년 5월 현재 기준으로는 하나의 Assistant와 하나의 Thread 각각에 최대 1개의 Vector Store만 연결할 수 있습니다.
Vector Store를 사용할 때의 주의점은 다음과 같습니다.

▶Vector Store 사용에는 비용이 발생한다
- 처음 1GB는 무료. 이후 1GB / 일당 $0.10
- 비용을 절감하기 위해서는 유효기간(Expiration Policy)을 설정하는 것이 효과적
● 파일 크기의 제한은 512MB입니다
● 각 파일의 최대 토큰 수 제한은 500만
● 지원하는 파일 형식은 .pdf, .md, .docx 등
· 자세한 내용은 OpenAI 문서를 참고: https://platform.openai.com/docs/assistants/tools/file-search/supported-files
● Run을 실행하기 전에 Vector Store 준비가 완료되어 있어야 한다

▶File Search 사용법
기업의 재무제표에 관한 질문에 답변할 수 있는 Assistant를 만드는 예시로 File Search의 사용 방법을 살펴보겠습니다.
1. file_search를 활성화해서 Assistant를 생성한다
assistant = client.beta.assistants.create(
    name="Financial Analyst Assistant",
    instructions="당신은 전문 금융 분석가입니다. 기업의 재무제표에 관한 질문에 답하기 위해 자신의 지식 기반을 활용하세요.",
    model="gpt-4o",
    tools=[{"type": "file_search"}],
)

2. 파일을 업로드하고 Vector Store를 생성해서, Vector Store가 준비될 때까지 상태를 계속 확인(polling)한다.
vector_store = client.beta.vector_stores.create_and_poll(
    name="Financial Statements",
    file_ids=['goog-10k.pdf', 'brka-10k.txt']
)

3. 생성한 Vector Store를 Assistant에 연결한다
assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
)

4. 사용자와의 상호작용을 위한 Thread를 생성하고 사용자가 제공한 파일을 첨부한다.
message_file = client.files.create(file=open("aapl-10k.pdf", "rb"),
purpose="assistants")

thread = client.beta.threads.create(
messages=[
    {
        "role": "user",
        "content": "지난 회계연도 말 기준으로 AAPL의 발행 주식 수는 몇 주였나요?",
        "attachments": [
            {"file_id": message_file.id, "tools": [{"type": "file_search"}]}
            ],
        }
    ]
)

5. Assistant를 Thread에서 Run 해서, 파일 검색을 활용한 응답을 생성한다.
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant.id
)

6. 결과를 확인한다.
Assistant는 두 개의 Vector Store(goog-10k.pdf, brka-10k.txt를 포함한 것, aapl-10k.pdf를 포함한 것)를 검색하고 aapl-10k.pdf에서 해당 정보를 추출해서 응답합니다.
이상으로 File Search의 개요와 사용 방법에 대한 설명을 마칩니다. File Search는 강력한 기능이지만 아직 개발 중인 부분도 있으므로 향후 업데이트를 주목할 필요가 있습니다.

11.3.4 Code Interpreter 개요
다음으로 Code Interpreter를 설명합니다.
이 장의 첫머리에서 언급했듯이 Code Interpreter는 샌드박스 환경에서 Python 코드를 실행할 수 있는 기능을 제공합니다. 이번 장에서는 이것을 활용해서 데이터 분석 에이전트에 Python 코드 실행 환경을 제공합니다. Code Interpreter의 장점은 이미 설명했으므로 여기서는 사용 방법에 초점을 맞춰 설명하겠습니다.

▶Code Interpreter 설정
Assistant에 Code Interpreter를 사용하게 하려면 우선 Assistant를 생성할 때 tools에 code_interpreter를 지정해야 합니다.
assistant = client.beta.assistants.create(
    instructions="당신은 개인 수학 튜터입니다. 수학 질문을 받으면 답을 찾기 위해 코드를 작성하고 실행하세요.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}]
)

다음으로 tool_resources를 사용해서 Code Interpreter에 사용할 수 있는 파일을 전달합니다. code_interpreter에는 최대 20개의 파일을 첨부할 수 있으며 각 파일은 최대 512MB까지 지원됩니다.
file = client.files.create(
    file=open("revenue-forecast.csv", "rb"), purpose="assistants"
)

assistant = client.beta.assistants.create(
    name="Data visualizer",
    description=" 당신은 데이터 시각화를 만드는 데 매우 능숙합니다. CSV 파일을 읽고 그래프를 생성할 수 있습니다.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}],
    tool_resources={"code_interpreter": {"file_ids": [file.id]}},
)

▶Code Interpreter 실행
Assistant를 Thread에서 Run 하면 필요에 따라 Code Interpreter가 자동으로 호출됩니다. 코드의 입력과 출력을 확인하려면 Run Steps를 체크하면 됩니다.
run_steps = client.beta.threads.runs.steps.list(
    thread_id=thread.id,
    run_id=run.id
)
Run Steps의 step_details 필드에는 Code Interpreter로의 입력과 출력이 기록되어 있습니다.
또한 Code Interpreter가 이미지 파일을 생성하면 Assistant의 응답 메시지의 image_file 필드에 이미지 파일 ID가 포함됩니다. 그 ID를 사용하면 아래와 같이 파일 내용을 다운로드할 수 있습니다.
image_data = client.files.content("file-abc123")
image_data_bytes = image_data.read()

with open("./my-image.png", "wb") as file:
    file.write(image_data_bytes)

▶Code Interpreter를 사용하는 Assistant 생성
지금까지의 내용을 바탕으로 CSV 파일로부터 그래프를 생성해 주는 Assistant를 만들어봅시다.
# CSV 파일 업로드
file = client.files.create(
    file=open("revenue-forecast.csv", "rb"), purpose="assistants"
)

# Assistant 생성
assistant = client.beta.assistants.create(
    name="Data visualizer",
    description="CSV 파일로부터 데이터 시각화를 생성하는 어시스턴트입니다. 선 그래프, 막대 그래프, 원형 차트를 만들 수 있습니다.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}],
    tool_resources={"code_interpreter": {"file_ids": [file.id]}},
)

# 스레드 생성
thread = client.beta.threads.create(
    messages=[
        {
            "role": "user",
            "content": "매출 예측 데이터를 선 그래프로 시각화해 줄 수 있나요?",
        }
    ]
)

# Run 실행
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id, assistant_id=assistant.id
)

# 이미지 파일 다운로드
message = client.beta.threads.messages.list(thread_id=thread.id, limit=1)[0]
image_file_id = message.content[0].image_file.file_id
image_data = client.files.content(image_file_id)

with open("./revenue-graph.png", "wb") as file:
    file.write(image_data.read())

이렇게 CSV 파일을 읽은 Assistant에 시각화를 요청하면 Code Interpreter가 Python 코드를 실행해서 이미지 파일을 생성하고 그 이미지를 다운로드할 수 있습니다.
다음 절에서는 이 구현을 약간 개량해서 툴을 만들고 데이터 분석 에이전트가 Code Interpreter를 사용해서 CSV 파일의 내용을 분석할 수 있게 하겠습니다.
▶Code Interpreter 비용
Code Interpreter의 비용 체계는 다음과 같습니다.
● 세션당 $0.03
● 세션은 1시간 동안 활성화됨
● 모델사용료는 별도로 발생
2개의 스레드에서 동시에 Code Interpreter를 호출하면 각각에 대해 별도의 세션이 생성됩니다. 같은 스레드 내에서 1시간 이내에 Code Interpreter가 다시 호출되어도 세션이 계속 사용되며 세션 수는 1개로 계산됩니다.

11.3.5 Assistants API Tips
● File Search와 Code Interpreter의 병행 사용
File Search와 Code Interpreter는 동시에 사용할 수 있으며 다음과 같이 조합하면 편리합니다.
1. File Search로 필요한 정보를 포함한 파일을 검색하고 추출한다.
2. 추출한 파일을 Code Interpreter에 전달해서 데이터 분석이나 시각화를 수행한다.
이렇게 하면 Assistant는 다양한 파일에서 필요한 정보를 찾아내고 그 정보를 바탕으로 데이터 분석까지 자동으로 수행할 수 있게 됩니다.

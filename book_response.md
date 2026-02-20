11.2 데이터 분석 에이전트란?
이 장에서 구현할 에이전트의 목적은 데이터 분석입니다. 이 에이전트는 ChatGPT의 UI에도 탑재된 고급 데이터 분석 기능(Advanced Data Analysis)과 유사합니다.
이 기능은 CSV 파일을 업로드하면 ChatGPT가 Python 코드를 생성하고 실행해서 데이터 분석과 시각화를 수행해 줍니다. 매우 똑똑하고 사용하기도 편리하지만 기본적으로 ChatGPT의 UI를 통해서만 사용할 수 있다는 제약이 있습니다.
또한 업로드한 데이터가 OpenAI의 모델 학습에 사용될 가능성이 있기 때문에 기밀성이 높은 정보는 업로드하지 않을 것을 권장합니다. 이 문제는 ChatGPT Enterprise 계약으로 해결할 수 있지만 비용 등의 제약으로 계약이 가능한 기업은 한정적일 것입니다. 게다가 사내 데이터베이스나 Google BigQuery 같은 외부 데이터 소스와 연계할 수 없다는 제한도 있습니다.
그래서 이 장에서는 이런 문제를 해결하는 데이터 분석 에이전트를 구현합니다. 이 에이전트는 CSV 업로드나 BigQuery 연동을 통해 데이터를 취득하고 Python 코드를 사용해서 분석을 수행할 수 있습니다.
구체적인 구현 흐름은 다음과 같습니다. 상당히 기므로 한 단계씩 꾸준히 구현합시다.
1. OpenAI Responses API(이하 Responses API)를 이해한다
2. Responses API를 사용해서 Python 코드를 실행하는 환경을 구축한다
3. CSV 파일을 업로드하고 에이전트에게 분석시킨다
4. 에이전트가 BigQuery에서 데이터를 가져와서 분석하게한다
이전 장에서는 장의 앞부분에 에이전트나 애플리케이션 동작의 흐름 그림을 넣었지만, 이번 장에서는 OpenAI Responses API의 설명이 길어지는 관계로 그림은 나중에 수록합니다. 우선은 OpenAI Responses API 설명부터 시작하겠습니다.

11.3 배경 지식: OpenAI Responses API
이 장에서는 데이터 분석을 위해 Python 코드를 실행하는 에이전트를 구현합니다. 코드 실행 환경으로는 Responses API가 제공하는 'Code Interpreter'를 활용합니다. Code Interpreter는 샌드박스 환경에서 Python 코드를 실행할 수 있을 뿐만 아니라 다음과 같은 장점이 있습니다.
● 코드 실행에 실패하면 자율적으로 코드를 수정해서 다시 실행한다.
● 이미지 파일이나 CSV 파일와 같은 여러 가지 데이터와 파일 형식을 처리할 수 있기 때문에 그래프 시각화와 같은 데이터 분석 작업에 활용할 수 있다.
Responses API는 에이전트를 구현하기 위한 통합 API이지만 이 책에서는 Python 코드 실행 환경으로만 활용합니다. Responses API를 사용할 때 알아두어야 할 사항이 많지 않지만, 작동 원리 정도는 알아두는 것도 매우 도움이 됩니다. 그래서 여기서 자세하게 설명합니다.

참고: OpenAI는 기존의 Assistants API(beta)를 대체하는 Responses API를 발표하고, 2025년 8월에 Assistants API를 deprecated(지원 종료 예고)로 지정했습니다. Responses API는 보다 간결하고 효율적인 인터페이스를 제공하며, 향후 모든 신기능이 Responses API 중심으로 제공됩니다. 따라서 본 서적에서는 Responses API를 기준으로 설명합니다.

다음과 같은 흐름으로 Responses API와 Code Interpreter를 이해한 뒤에 에이전트 구현으로 넘어가겠습니다
1. 먼저 Responses API의 개요에 대해 설명합니다. 본 장에서는 최종적으로 사용하지 않는 것이므로, Code Interpreter 외에는 가볍게 다룰 것입니다.
2. 다음으로, Code Interpreter에 대해 설명합니다. 이는 Python 코드 실행 도구를 구축하는 데 필수적인 지식이 됩니다.
3. 그 후, 본 장의 에이전트 구축에 진행합니다. 강력한 도구를 구축함으로써, 유용한 에이전트가 간편하게 구축될 수 있음을 확인하시기 바랍니다.

11.3.1 Responses API 개요
OpenAI Responses API는 기존의 Chat Completions API를 진화시키고 Assistants API(beta)의 핵심 기능을 통합한 차세대 API입니다. 이 API가 제공하는 내장 도구와 OpenAI의 모델을 조합하면 다양한 문제를 해결할 수 있는 고도화된 AI 에이전트를 구현할 수 있습니다.
2025년 12월 현재, Responses API에는 다음과 같은 내장 도구가 포함되어 있습니다.
1. Code Interpreter: Python 코드를 샌드박스 환경(Container)에서 작성하고 실행할 수 있는 도구. 여러 가지 데이터와 파일을 처리하고 데이터나 이미지와 같은 파일을 생성할 수 있습니다.
2. File Search: 사용자가 제공한 문서를 Vector Store에 저장하고 시맨틱 검색을 통해 관련 콘텐츠를 가져오는 툴. OpenAI가 문서를 자동으로 분석·분할하고 Embedding 해서 저장하고, 벡터 검색과 키워드 검색을 통해 사용자 쿼리와 관련된 콘텐츠를 가져옵니다.
3. Function calling: 모델이 외부 API나 툴을 호출할 수 있게 해주는 도구. 앞 장에서 다룬 것과 거의 동일하므로 이 장에서는 자세히 설명하지 않습니다.
4. Web Search: 웹 검색을 수행하는 내장 도구.
5. 그 외: Image Generation, Computer Use, MCP 연동 등.

11.3.2 Responses API 사용법
Responses API는 Assistants API와 달리 여러 객체를 미리 생성하고 연결할 필요가 없습니다. **하나의 API 호출(responses.create)에 모든 것을 담아 보내면 됩니다.** 아래 그림은 Responses API의 기본 구조를 나타냅니다.

그림 11.1: Responses API의 요청과 응답 구조
Responses API의 핵심 구성 요소는 다음과 같습니다.

**1. Response 객체**
Response는 `responses.create` API 호출의 결과를 나타내는 핵심 객체입니다. 고유 ID를 가지며, 모델의 출력(output)에는 텍스트 메시지뿐 아니라 도구 호출 정보(code_interpreter_call, file_search_call 등)도 포함됩니다. 또한 토큰 사용량 등의 메타데이터도 담고 있습니다. 대화를 이어가려면 이 Response의 ID를 `previous_response_id`로 전달하면 되므로, Response 하나가 곧 대화 상태(state)를 관리하는 단위가 됩니다.

**2. Built-in Tools (내장 도구)**
Responses API의 가장 큰 특징은 강력한 내장 도구를 `tools` 매개변수에 배열로 지정하는 것만으로 바로 사용할 수 있다는 점입니다. 대표적인 내장 도구는 다음과 같습니다.
● **Code Interpreter**: 샌드박스 환경에서 Python 코드를 실행한다. 데이터 분석과 시각화에 활용된다.
● **File Search**: 사용자가 업로드한 문서를 벡터 검색해서 관련 콘텐츠를 추출한다.
● **Web Search**: 웹 검색을 수행해서 최신 정보를 가져온다.
● **Function Calling**: 개발자가 정의한 외부 함수를 모델이 호출할 수 있게 한다.
이 도구들은 하나의 API 호출에서 자유롭게 조합할 수 있으며, 모델이 상황에 따라 적절한 도구를 자율적으로 선택합니다.

**3. Container**
Container는 Code Interpreter가 코드를 실행하는 완전 격리된 샌드박스 환경입니다. 파일 업로드 및 관리도 Container를 통해 이루어집니다. 자동 생성(`"type": "auto"`)과 명시적 생성(`client.containers.create`) 두 가지 방식을 지원하며, 마지막 사용 후 20분 동안 활성 상태를 유지합니다. 이 장에서 구현할 에이전트의 핵심 구성 요소입니다.

**4. Instructions**
시스템 프롬프트(System Prompt)에 해당합니다. 모델의 역할이나 동작을 지시하는 명령을 설정합니다. Chat Completions API의 system 메시지와 동일한 역할을 합니다.

이처럼 Responses API는 **하나의 API 호출에 Response, Tools, Container, Instructions를 모두 담아 보내는 간결한 구조**가 특징입니다. Assistants API처럼 여러 객체를 미리 생성하고 연결할 필요가 없습니다.

Responses API를 사용하는 기본적인 흐름은 다음과 같습니다.
1. responses.create를 호출한다. 사용할 모델, instructions, tools, input을 지정합니다.
2. 결과를 확인한다. response.output에서 모델의 응답(텍스트, 도구 호출 결과 등)을 가져옵니다.
3. 대화를 계속하려면 previous_response_id를 사용해서 이전 응답과 연결합니다.
Assistants API처럼 Assistant, Thread, Run 등 여러 객체를 미리 생성하고 관리할 필요가 없기 때문에 코드가 매우 간결해집니다. LangChain은 현재 Responses API의 기능을 충분히 지원하지 않기 때문에 OpenAI의 공식 라이브러리를 사용해서 코드 예시를 제시합니다.

▶기본적인 텍스트 생성
Responses API의 가장 기본적인 사용법은 다음과 같습니다.
from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model="gpt-4o",
    instructions="당신은 개인 수학 튜터입니다. 수학 질문에 답하기 위해 코드를 작성하고 실행하세요.",
    tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
    input="방정식 3x + 11 = 14를 풀어야 합니다. 도와주실 수 있나요?",
)

이 코드에서 다음과 같은 매개변수를 지정해서 Response를 생성합니다.
● model: 사용할 모델
● instructions: 모델의 역할이나 동작을 지시하는 명령(System Prompt와 동일)
● tools: 사용할 수 있는 툴(여기에서는 code_interpreter)
● input: 사용자의 입력. 문자열 또는 메시지 배열

그 밖에도, 다음과 같은 매개변수를 지정할 수 있습니다.
● previous_response_id: 이전 응답의 ID. 대화를 이어가고 싶을 때 사용합니다.
● store: 응답을 서버에 저장할지 여부(기본값: true). false로 설정하면 데이터가 서버에 남지 않습니다.
● max_output_tokens: 생성할 응답의 최대 토큰 수.
● truncation: 입력이 컨텍스트 윈도우를 초과할 때의 처리 방식.
   · "auto"로 지정하면 오래된 메시지부터 자동으로 잘라낸다
   · "disabled"(기본값)로 지정하면 컨텍스트를 초과하면 에러를 반환한다

▶대화 상태 관리
Assistants API에서는 Thread가 대화 세션을 관리했지만, Responses API에서는 previous_response_id를 사용해서 이전 응답과 연결하는 방식으로 대화를 이어갑니다.
# 첫 번째 응답
response = client.responses.create(
    model="gpt-4o",
    input="안녕하세요! 수학 질문이 있습니다.",
)

# 두 번째 응답 (이전 응답의 컨텍스트가 자동으로 포함됨)
response2 = client.responses.create(
    model="gpt-4o",
    previous_response_id=response.id,
    input="방정식 3x + 11 = 14를 풀어주세요.",
)

previous_response_id를 사용하면 이전 대화 내용이 자동으로 포함되므로 별도의 Thread나 Message 관리가 필요하지 않습니다.
대화 상태 관리에는 다음과 같은 특징이 있습니다.
● previous_response_id로 이전 응답과 간단히 연결할 수 있다
● 모델의 컨텍스트 윈도우 크기를 초과하면 truncation 설정에 따라 처리된다
● 장기 세션이 필요한 경우 Conversations API를 사용할 수도 있다

▶응답 확인
Response 객체에서 결과를 확인하는 가장 간단한 방법은 output_text 헬퍼를 사용하는 것입니다.
print(response.output_text)

보다 상세한 정보가 필요한 경우, response.output을 순회하면서 각 Item의 타입을 확인할 수 있습니다.
for item in response.output:
    if item.type == "message":
        for content in item.content:
            if content.type == "output_text":
                print(content.text)
    elif item.type == "code_interpreter_call":
        # Code Interpreter 실행 결과 확인
        pass
    elif item.type == "file_search_call":
        # File Search 결과 확인
        pass

▶Message annotations
모델이 생성한 메시지에는 annotations가 포함된 경우가 있습니다. annotations는 메시지의 content 안에 배열 형태로 표현됩니다.
다음은 file_citation annotations가 포함된 메시지의 예시입니다.
{
    "id": "msg_67c09cd3091c819185af2be5d13d87de",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "output_text",
            "text": "According to the file, the total revenue in 2022 was $120 million.",
            "annotations": [
                {
                    "type": "file_citation",
                    "index": 24,
                    "file_id": "file-2dtbBZdjtDKS8eqWxqbgDi",
                    "filename": "financial_report.pdf"
                }
            ]
        }
    ]
}

이 예시에서는 content의 annotations 배열에 file_citation이 있습니다. 이 annotations은 메시지의 특정 위치(index)에 파일에서 인용된 정보가 사용되었다는 것을 나타냅니다. file_id는 인용 출처 파일의 ID이고 filename은 인용 출처 파일의 이름을 나타냅니다.
메시지에 annotations가 포함된 경우에는 text에는 인용 표식(citation marker)이 포함되어 있을 수 있습니다. 애플리케이션에서 메시지를 처리할 때는 이런 인용 표식을 annotations 정보를 사용해서 적절한 텍스트나 링크 등으로 치환해야 합니다.
이상으로 Responses API의 기본 사용법에 대한 설명과 코드 예시를 마칩니다.
Responses API를 적절히 활용하면 강력한 AI 에이전트를 간결한 코드로 구축할 수 있습니다.

11.3.3 FileSearch 개요
다음으로는 Responses API의 File Search 기능을 설명합니다. File Search는 사용자가 제공한 문서를 모델에 포함하는 기능입니다. RAG(Retrieval-Augmented Generation)와 동일한 개념이며 다음 작업을 자동으로 수행합니다.
1. 문서의 분석 및 분할
2. 각 청크(chunk)에 대한 Embedding  및 저장
3. 사용자 쿼리에 대한 벡터 검색 및 키워드 검색
4. 사용자 쿼리와 관련된 콘텐츠 추출
이 책에서는 RAG의 동작 원리를 이해하기 위해서 LangChain을 사용해서 구현했습니다. 최근의 Responses API의 File Search 기능은 파일 검색 정확도에 중점을 두고 있는 인상이며 앞으로 더 사용하기 쉬워질 가능성이 있습니다. 따라서 이 책에서는 사용하지는 않지만, Responses API의 중요한 기능이기 때문에 설명합니다.

▶FileSearch의 동작 방식
File Search는 다음과 같은 흐름으로 동작 합니다.
1. 사용자가 파일(PDF, 텍스트 파일 등)을 업로드하고 Vector Store에 저장
2. OpenAI가 파일을 자동으로 분석해서 청크로 분할
3. 각 청크를 Embedding 한 후에 벡터 DB에 저장
4. 사용자가 질문하면 File Search가 tools에 지정된 Vector Store로부터 키워드 검색과 시맨틱 검색을 수행.
5. 필요에 따라 검색 결과를 리랭킹하고 가장 관련성이 높은 정보를 추출해서 모델의 응답에 포함한다.
File Search의 기본 설정은 다음과 같습니다.
● 청크 크기: 800토큰
● 청크 오버랩: 400토큰
● 내장 모델: text-embedding-3-large（256차원）
● 컨텍스트에 추가되는 청크의 최대 수: 20 (상황에 따라 적어질 가능성 있음)
단, File Search에는 몇 가지 제한 사항이 있습니다.
● Embedding 방식이나 기타 설정을 변경할 수 없다
● 문서 내의 이미지(그래프나 표 등의 이미지를 포함한다) 분석은 지원하지 않는다
● 구조화된 파일 형식(csv, jsonl 등)에 대한 검색 지원은 제한적이다
● 요약 기능은 제한적 (현재 도구는 검색 쿼리 최적화에 중점이 있음)

참고: Assistants API에서는 사용자 정의 메타데이터를 활용한 필터링이 지원되지 않았지만, Responses API에서는 Vector Store 파일에 attributes(속성)를 설정하고 검색 시 filters로 필터링할 수 있습니다. 이것은 큰 개선점입니다.

청크 분할 방식 등 자세한 사양은 OpenAI의 공식 문서를 참조해 주세요.
● File Search: https://developers.openai.com/api/docs/guides/tools-file-search
● Retrieval: https://developers.openai.com/api/docs/guides/retrieval

다음으로 Vector Store 기능에 관해 설명합니다.
▶Vector Store 개요
Vector Store는 File Search에서 사용할 파일을 저장하기 위한 데이터베이스입니다. 파일을 Vector Store에 추가하면 자동으로 파일이 분석, 분할되고 Embedding 되어 벡터 DB에 저장됩니다.
각 Vector Store에는 최대 10,000개의 파일을 저장할 수 있습니다. Responses API에서는 tools 배열에서 vector_store_ids를 직접 지정하는 방식으로 Vector Store를 사용합니다.
Vector Store를 사용할 때의 주의점은 다음과 같습니다.

▶Vector Store 사용에는 비용이 발생한다
- 처음 1GB는 무료. 이후 1GB / 일당 $0.10
- 비용을 절감하기 위해서는 유효기간(Expiration Policy)을 설정하는 것이 효과적
● 파일 크기의 제한은 512MB입니다
● 각 파일의 최대 토큰 수 제한은 500만
● 지원하는 파일 형식은 .pdf, .md, .docx 등
· 자세한 내용은 OpenAI 문서를 참고: https://developers.openai.com/api/docs/guides/tools-file-search#supported-files
● API 호출 전에 Vector Store 준비가 완료되어 있어야 한다

▶File Search 사용법
기업의 재무제표에 관한 질문에 답변할 수 있는 에이전트를 만드는 예시로 File Search의 사용 방법을 살펴보겠습니다.
1. 파일을 업로드하고 Vector Store를 생성한다.
vector_store = client.vector_stores.create(name="Financial Statements")
client.vector_stores.files.upload_and_poll(
    vector_store_id=vector_store.id,
    file=open("goog-10k.pdf", "rb")
)
client.vector_stores.files.upload_and_poll(
    vector_store_id=vector_store.id,
    file=open("brka-10k.txt", "rb")
)

2. 추가 파일도 별도로 업로드할 수 있다.
client.vector_stores.files.upload_and_poll(
    vector_store_id=vector_store.id,
    file=open("aapl-10k.pdf", "rb")
)

3. file_search를 활성화해서 Responses API를 호출한다. Vector Store ID를 tools에 직접 지정합니다.
response = client.responses.create(
    model="gpt-4o",
    instructions="당신은 전문 금융 분석가입니다. 기업의 재무제표에 관한 질문에 답하기 위해 자신의 지식 기반을 활용하세요.",
    tools=[{
        "type": "file_search",
        "vector_store_ids": [vector_store.id]
    }],
    input="지난 회계연도 말 기준으로 AAPL의 발행 주식 수는 몇 주였나요?",
)

4. 결과를 확인한다.
print(response.output_text)

모델은 Vector Store에 저장된 파일들(goog-10k.pdf, brka-10k.txt, aapl-10k.pdf)을 검색하고 aapl-10k.pdf에서 해당 정보를 추출해서 응답합니다.

Assistants API에서는 Assistant 생성 → Vector Store 연결 → Thread 생성 → 파일 첨부 → Run 실행 등 여러 단계가 필요했지만, Responses API에서는 Vector Store를 생성하고 하나의 API 호출로 완결됩니다.

이상으로 File Search의 개요와 사용 방법에 대한 설명을 마칩니다. File Search는 강력한 기능이며 메타데이터 필터링 등 지속적으로 기능이 개선되고 있으므로 향후 업데이트를 주목할 필요가 있습니다.

11.3.4 Code Interpreter 개요
다음으로 Code Interpreter를 설명합니다.
이 장의 첫머리에서 언급했듯이 Code Interpreter는 샌드박스 환경에서 Python 코드를 실행할 수 있는 기능을 제공합니다. 이번 장에서는 이것을 활용해서 데이터 분석 에이전트에 Python 코드 실행 환경을 제공합니다. Code Interpreter의 장점은 이미 설명했으므로 여기서는 사용 방법에 초점을 맞춰 설명하겠습니다.

▶Code Interpreter 설정 — Container
Responses API에서 Code Interpreter를 사용하려면 Container가 필요합니다. Container는 코드가 실행되는 완전 격리된(sandboxed) 가상 머신입니다. Container를 생성하는 방식에는 두 가지가 있습니다.

방법1: Auto 모드 — Container를 자동으로 생성하거나 재사용합니다.
response = client.responses.create(
    model="gpt-4o",
    instructions="당신은 개인 수학 튜터입니다. 수학 질문을 받으면 답을 찾기 위해 코드를 작성하고 실행하세요.",
    tools=[{
        "type": "code_interpreter",
        "container": {"type": "auto"}
    }],
    input="3x + 11 = 14를 풀어주세요.",
)

방법2: Explicit 모드 — Container를 명시적으로 생성하고 ID를 전달합니다.
container = client.containers.create(name="my-session")

response = client.responses.create(
    model="gpt-4o",
    instructions="당신은 개인 수학 튜터입니다. 수학 질문을 받으면 답을 찾기 위해 코드를 작성하고 실행하세요.",
    tools=[{
        "type": "code_interpreter",
        "container": container.id
    }],
    input="3x + 11 = 14를 풀어주세요.",
)

Container에는 다음과 같은 특성이 있습니다.
● 마지막 사용 후 20분 동안 활성 상태 유지. 20분 비활동 시 만료된다
● 만료된 Container의 데이터는 삭제되며 복구할 수 없다. 새 Container를 생성해야 한다
● Container 조회, 파일 추가/삭제 등의 작업이 활성 시간을 자동 갱신한다
● 메모리 옵션: 1g(기본), 4g, 16g, 64g 중 선택 가능. Container 생명 주기 동안 고정됨

다음으로 Container에 파일을 업로드해서 Code Interpreter에서 사용할 수 있는 파일을 전달합니다. Container에는 여러 개의 파일을 업로드할 수 있으며 각 파일은 최대 512MB까지 지원됩니다.
container = client.containers.create(name="data-analysis-session")

container_file = client.containers.files.create(
    container_id=container.id,
    file=("revenue-forecast.csv", open("revenue-forecast.csv", "rb")),
)

response = client.responses.create(
    model="gpt-4o",
    instructions="당신은 데이터 시각화를 만드는 데 매우 능숙합니다. CSV 파일을 읽고 그래프를 생성할 수 있습니다.",
    tools=[{
        "type": "code_interpreter",
        "container": container.id
    }],
    input="매출 예측 데이터를 선 그래프로 시각화해 줄 수 있나요?",
)

▶Code Interpreter 실행과 결과 확인
Responses API를 호출하면 필요에 따라 Code Interpreter가 자동으로 호출됩니다. 코드의 입력과 출력을 확인하려면 response.output을 순회하면서 code_interpreter_call 타입의 Item을 확인합니다.
for item in response.output:
    if item.type == "code_interpreter_call":
        # 실행된 코드와 결과 확인
        call_info = item.code_interpreter_call
        for result in call_info.results:
            if hasattr(result, 'logs') and result.logs:
                print(result.logs)  # 코드 실행 결과 (stdout)

또한 Code Interpreter가 이미지 파일을 생성하면 모델의 응답 메시지의 annotations에 container_file_citation이 포함됩니다. 그 정보를 사용하면 아래와 같이 파일 내용을 다운로드할 수 있습니다.
import httpx

api_key = client.api_key
base_url = client.base_url
url = f"{base_url}/containers/{container_id}/files/{file_id}/content"
headers = {"Authorization": f"Bearer {api_key}"}

response = httpx.get(url, headers=headers)
image_data_bytes = response.content

with open("./my-image.png", "wb") as file:
    file.write(image_data_bytes)

▶Code Interpreter를 사용해서 그래프 생성
지금까지의 내용을 바탕으로 CSV 파일로부터 그래프를 생성해 주는 코드를 만들어봅시다.
# Container 생성
container = client.containers.create(name="data-visualizer")

# CSV 파일 업로드
client.containers.files.create(
    container_id=container.id,
    file=("revenue-forecast.csv", open("revenue-forecast.csv", "rb")),
)

# Responses API 호출
response = client.responses.create(
    model="gpt-4o",
    instructions="CSV 파일로부터 데이터 시각화를 생성하는 어시스턴트입니다. 선 그래프, 막대 그래프, 원형 차트를 만들 수 있습니다.",
    tools=[{
        "type": "code_interpreter",
        "container": container.id
    }],
    input="매출 예측 데이터를 선 그래프로 시각화해 줄 수 있나요?",
)

# 이미지 파일 다운로드
import httpx
for item in response.output:
    if item.type == "message":
        for content in item.content:
            if content.type == "output_text" and content.annotations:
                for annotation in content.annotations:
                    if annotation.type == "container_file_citation":
                        url = f"{client.base_url}/containers/{annotation.container_id}/files/{annotation.file_id}/content"
                        headers = {"Authorization": f"Bearer {client.api_key}"}
                        file_response = httpx.get(url, headers=headers)
                        with open("./revenue-graph.png", "wb") as f:
                            f.write(file_response.content)

이렇게 CSV 파일을 업로드한 Container에 시각화를 요청하면 Code Interpreter가 Python 코드를 실행해서 이미지 파일을 생성하고 그 이미지를 다운로드할 수 있습니다.
다음 절에서는 이 구현을 약간 개량해서 툴을 만들고 데이터 분석 에이전트가 Code Interpreter를 사용해서 CSV 파일의 내용을 분석할 수 있게 하겠습니다.
▶Code Interpreter 비용
Code Interpreter의 비용 체계는 다음과 같습니다.
● Container당 $0.03 (1GB 기본 메모리 기준)
● Container는 마지막 사용 후 20분 동안 활성화됨
● 메모리 옵션별 비용: 1GB: $0.03 / 4GB: $0.12 / 16GB: $0.48 / 64GB: $1.92
● 모델사용료는 별도로 발생

참고: 2026년 3월 31일부터 Container 사용료가 20분 단위 과금으로 전환됩니다. 예를 들어 1GB Container를 40분 사용하면 $0.03 × 2 = $0.06이 청구됩니다.

2개의 Container에서 동시에 Code Interpreter를 사용하면 각각에 대해 별도의 비용이 발생합니다. 같은 Container 내에서 20분 이내에 Code Interpreter가 다시 호출되어도 Container가 계속 사용되며 추가 비용은 발생하지 않습니다.

11.3.5 Responses API Tips
● File Search와 Code Interpreter의 병행 사용
File Search와 Code Interpreter는 동시에 사용할 수 있으며 다음과 같이 하나의 tools 배열에 조합하면 편리합니다.
response = client.responses.create(
    model="gpt-4o",
    tools=[
        {"type": "file_search", "vector_store_ids": [vector_store.id]},
        {"type": "code_interpreter", "container": {"type": "auto"}}
    ],
    input="재무 데이터에서 매출 추이를 찾아서 그래프로 그려주세요.",
)

1. File Search로 필요한 정보를 포함한 파일을 검색하고 추출한다.
2. 추출한 파일을 Code Interpreter에 전달해서 데이터 분석이나 시각화를 수행한다.
이렇게 하면 모델은 다양한 파일에서 필요한 정보를 찾아내고 그 정보를 바탕으로 데이터 분석까지 자동으로 수행할 수 있게 됩니다.

# OpenAI Responses API 심층 가이드 — Assistants API에서의 전환

> 이 문서는 기존 Assistants API(beta)에서 Responses API로 마이그레이션할 때 **FileSearch, VectorStore, Code Interpreter(Container)** 가 어떻게 달라지는지를 심층적으로 정리한 자료입니다.

---

## 1. 왜 Responses API인가?

### 1.1 배경

OpenAI는 2025년 8월 26일부로 Assistants API를 **공식 deprecated**(지원 종료 예고) 하였으며, 2026년 8월 26일을 sunset(완전 종료) 날짜로 설정했습니다. 그 후속으로 **Responses API**를 제시하고 있습니다.

Responses API는 기존 Chat Completions API의 진화판이면서, 동시에 Assistants API의 핵심 기능들을 흡수한 **통합 API**입니다. Chat Completions와 Assistants 양쪽의 장점을 하나의 인터페이스로 합쳤다고 이해하면 됩니다.

### 1.2 Responses API의 주요 장점

| 항목 | 설명 |
|------|------|
| **더 나은 성능** | Reasoning 모델(GPT-5 등)을 사용 시 Chat Completions 대비 SWE-bench에서 약 3% 성능 향상 (내부 평가 기준) |
| **에이전트 기본 탑재** | 하나의 API 요청 안에서 `web_search`, `file_search`, `code_interpreter`, `image_generation`, 커스텀 함수 등 여러 도구를 순차적으로 호출 가능 |
| **낮은 비용** | 향상된 캐시 활용으로 40%~80% 비용 절감 (내부 테스트) |
| **상태 관리** | `store: true` 설정 시 턴 간 상태 자동 유지, `previous_response_id`로 대화 체이닝, Conversations API로 장기 세션 관리 |
| **유연한 입력** | 문자열 직접 전달, 메시지 배열, `instructions`로 시스템 프롬프트 분리 등 |
| **미래 대비** | 향후 출시되는 모든 모델과 기능이 Responses API 중심으로 제공 |

### 1.3 아키텍처 비교: Assistants API vs Responses API

**Assistants API** (기존):
```
Assistant (설정 객체)
  └─ Thread (대화 세션)
       └─ Message (개별 메시지)
            └─ Run (실행 = Assistant + Thread 결합)
                 └─ Run Step (개별 작업 단위)
```

**Responses API** (신규):
```
Response (단일 API 호출 = 설정 + 입력 + 실행이 하나로 통합)
  ├─ input (입력 Items: 사용자 메시지, 이전 응답 등)
  ├─ tools (code_interpreter, file_search, function 등)
  ├─ instructions (시스템 프롬프트)
  └─ output (출력 Items: message, code_interpreter_call, file_search_call 등)
```

핵심 차이를 한 문장으로 요약하면:
> **Assistants API는 "객체를 만들고 → 연결하고 → 실행하는" 3단계였지만, Responses API는 "요청 하나에 모든 것을 담아 보내면 된다."**

---

## 2. Code Interpreter의 변화

### 2.1 개요

Code Interpreter는 샌드박스 환경에서 Python 코드를 실행하는 기능입니다. Responses API에서도 동일한 목적으로 사용되지만, 내부 구조가 크게 바뀌었습니다.

### 2.2 핵심 변경점: Container의 등장

| 항목 | Assistants API | Responses API |
|------|----------------|---------------|
| **실행 환경 설정** | `beta.assistants.create()` → Assistant ID 생성 | `client.containers.create()` → Container ID 생성 |
| **대화 세션** | `beta.threads.create()` → Thread ID | 불필요 (`previous_response_id` 또는 Conversations API 사용) |
| **코드 실행** | Thread에 Message 추가 → `beta.threads.runs.create_and_poll()` | `client.responses.create()` 한 번의 호출로 완결 |
| **파일 업로드** | `client.files.create(purpose="assistants")` → Assistant에 file_ids 연결 | `client.containers.files.create(container_id, file=...)` |
| **파일 다운로드** | `client.files.content(file_id)` | Container Files Content API: `GET /v1/containers/{id}/files/{file_id}/content` |
| **응답 형식** | `message.content` → `text` / `image_file` 타입 | `response.output` → `code_interpreter_call` / `message` 타입 |

### 2.3 Container란?

Container는 Responses API에서 Code Interpreter가 실행되는 **완전 격리된(sandboxed) 가상 머신**입니다. 기존 Assistants API에서 Assistant + Thread가 담당하던 "실행 환경 + 파일 관리" 역할을 Container 하나가 대체합니다.

#### Container 생성 방식

**방법 1: Auto 모드** — API 요청 시 자동으로 Container를 생성/재사용
```python
response = client.responses.create(
    model="gpt-4.1",
    tools=[{
        "type": "code_interpreter",
        "container": {"type": "auto", "memory_limit": "4g"}
    }],
    input="3x + 11 = 14를 풀어주세요."
)
```

**방법 2: Explicit 모드** — 명시적으로 Container를 생성하고 ID를 전달
```python
# 1. Container 생성
container = client.containers.create(
    name="code-interpreter-session",
    memory_limit="4g"
)

# 2. Container ID를 지정하여 코드 실행
response = client.responses.create(
    model="gpt-4.1",
    tools=[{
        "type": "code_interpreter",
        "container": container.id   # Container ID 직접 지정
    }],
    input="이 방정식을 풀어주세요: 3x + 11 = 14"
)
```

#### Container의 특성

| 특성 | 설명 |
|------|------|
| **수명** | 마지막 사용 후 **20분** 동안 활성 상태 유지. 20분 비활동 시 만료(expired) |
| **만료 시** | 데이터 모두 삭제, 복구 불가. 새 Container 생성 및 파일 재업로드 필요 |
| **활성 연장** | Container 조회, 파일 추가/삭제 등의 작업이 `last_active_at`을 자동 갱신 |
| **메모리 옵션** | `1g` (기본), `4g`, `16g`, `64g` — Container 생명 주기 동안 고정 |
| **임시 데이터** | 권장: Container를 **임시(ephemeral)** 로 취급하고, 필요한 파일은 즉시 다운로드하여 자체 시스템에 저장 |

#### (비교) 기존 Assistants API의 세션 관리

기존에는 Assistant와 Thread가 별개 객체로 존재했고, Thread는 명시적으로 삭제하지 않는 한 OpenAI 서버에 계속 남아 있었습니다. Container는 이와 달리 **능동적 만료** 매커니즘을 적용하여 리소스를 자동 회수합니다.

### 2.4 파일 관리

#### 파일 업로드

```python
# Assistants API (기존)
file = client.files.create(file=open("data.csv", "rb"), purpose="assistants")
client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"code_interpreter": {"file_ids": [file.id]}}
)

# Responses API (신규)
container_file = client.containers.files.create(
    container_id=container.id,
    file=("data.csv", file_content),   # (파일명, 바이트) 튜플
)
```

핵심 차이:
- **Assistants API**: `files.create()` → Purpose 지정 → Assistant에 연결 → 업데이트... **3단계**
- **Responses API**: `containers.files.create()` — **1단계**로 완결

#### 파일 다운로드

```python
# Assistants API (기존)
data = client.files.content(file_id)
data_bytes = data.read()

# Responses API (신규)
# Container Files Content API를 직접 호출
import httpx

url = f"{base_url}/containers/{container_id}/files/{file_id}/content"
headers = {"Authorization": f"Bearer {api_key}"}
response = httpx.get(url, headers=headers)
data_bytes = response.content
```

> 현재(2026년 2월) OpenAI Python SDK에 `containers.files.content()` 같은 편의 메서드가 아직 완비되지 않은 경우가 있어, `httpx`로 직접 HTTP 요청을 보내는 방식도 사용됩니다.

#### Container 내 파일 경로

Container 안에서 업로드된 파일은 `/mnt/user-data/uploads/파일명`에 위치합니다. 기존 Assistants API에서는 file_id로만 참조했지만, Responses API에서는 실제 파일 경로로 접근할 수 있어 더 직관적입니다.

### 2.5 응답 파싱

#### Assistants API 응답 구조
```python
# Run 완료 후 메시지 가져오기
message = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
for content in message.data[0].content:
    if content.type == "text":
        text = content.text.value
        annotations = content.text.annotations  # file_path, file_citation
    elif content.type == "image_file":
        file_id = content.image_file.file_id
```

#### Responses API 응답 구조
```python
response = client.responses.create(...)

for item in response.output:
    if item.type == "code_interpreter_call":
        # 코드 실행 결과 (stdout, stderr, 에러)
        call_info = item.code_interpreter_call
        for result in call_info.results:
            if hasattr(result, 'logs') and result.logs:
                print(result.logs)  # stdout 출력
        if call_info.error:
            print(call_info.error)  # 에러 메시지
            
    elif item.type == "message":
        for content in item.content:
            if content.type == "output_text":
                text = content.text
                # annotations에서 생성 파일 정보 추출
                for annotation in content.annotations:
                    if annotation.type == "container_file_citation":
                        file_id = annotation.file_id
                        container_id = annotation.container_id
                        filename = annotation.filename
```

핵심 차이:
- **Assistants API**: `text` / `image_file` 두 가지 content 타입
- **Responses API**: `code_interpreter_call` (실행 결과)과 `message` (텍스트+인용)이 분리. 파일 참조는 `container_file_citation` annotation으로 제공

### 2.6 비용 비교

| 항목 | Assistants API | Responses API |
|------|----------------|---------------|
| **기본 요금** | 세션당 $0.03(1시간 활성) | Container당 $0.03(20분 활성, 1GB 기준) |
| **메모리 옵션** | 없음 (고정) | 1GB: $0.03 / 4GB: $0.12 / 16GB: $0.48 / 64GB: $1.92 |
| **모델 사용료** | 별도 | 별도 |
| **과금 단위** | 2026년 3월 31일부터 20분 단위로 변경 예정 | Container 유지 시간 기준 (20분 단위) |

> **참고**: 2026년 3월 31일부터 Container 사용료가 **20분 단위 과금**으로 변경됩니다. 예를 들어, 1GB Container를 40분 사용하면 $0.03 × 2 = $0.06이 청구됩니다.

### 2.7 전체 코드 비교: "수학 문제 풀기" 예제

#### Assistants API 버전
```python
from openai import OpenAI
client = OpenAI()

# 1. Assistant 생성
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="수학 질문에 답하기 위해 코드를 실행하세요.",
    model="gpt-4o",
    tools=[{"type": "code_interpreter"}]
)

# 2. Thread 생성
thread = client.beta.threads.create()

# 3. Message 추가
client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="3x + 11 = 14를 풀어주세요."
)

# 4. Run 실행 (폴링 포함)
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant.id
)

# 5. 결과 확인
messages = client.beta.threads.messages.list(thread_id=thread.id, limit=1)
print(messages.data[0].content[0].text.value)
```

#### Responses API 버전
```python
from openai import OpenAI
client = OpenAI()

# 1단계로 완결
response = client.responses.create(
    model="gpt-4o",
    instructions="수학 질문에 답하기 위해 코드를 실행하세요.",
    tools=[{
        "type": "code_interpreter",
        "container": {"type": "auto"}
    }],
    input="3x + 11 = 14를 풀어주세요."
)

# 결과 확인
print(response.output_text)
```

**5단계 → 1단계**로 극적으로 간소화된 것을 확인할 수 있습니다.

---

## 3. File Search의 변화

### 3.1 개요

File Search는 사용자가 업로드한 문서에서 정보를 검색하여 모델 응답에 활용하는 RAG(Retrieval-Augmented Generation) 기능입니다.

Responses API에서의 File Search는 핵심 개념(Vector Store 기반의 시맨틱 검색)은 동일하지만, 사용 방식이 크게 간소화되었습니다.

### 3.2 핵심 변경점

| 항목 | Assistants API | Responses API |
|------|----------------|---------------|
| **도구 설정** | Assistant 생성 시 `tools=[{"type": "file_search"}]` | Response 요청 시 `tools=[{"type": "file_search", "vector_store_ids": [...]}]` |
| **VectorStore 연결** | Assistant에 tool_resources로 연결 | 도구 설정에 `vector_store_ids` 직접 지정 |
| **Thread 첨부** | Thread Message에 attachments로 파일 첨부 | 불필요 (Vector Store에 미리 업로드) |
| **응답 형식** | `text.annotations` → `file_citation` | `output_text.annotations` → `file_citation` |
| **검색 결과 포함** | Run Steps로 확인 | `include=["file_search_call.results"]`로 직접 요청 |
| **메타데이터 필터링** | 미지원 | `filters` 파라미터로 속성 기반 필터링 지원 |
| **결과 수 제한** | 제한적 제어 | `max_num_results` 파라미터로 직접 제어 |

### 3.3 사용 방법 비교

#### Assistants API 버전

```python
from openai import OpenAI
client = OpenAI()

# 1. Assistant 생성 (file_search 활성화)
assistant = client.beta.assistants.create(
    name="Financial Analyst",
    instructions="재무제표에 관한 질문에 답하세요.",
    model="gpt-4o",
    tools=[{"type": "file_search"}]
)

# 2. Vector Store 생성 + 파일 업로드
vector_store = client.beta.vector_stores.create_and_poll(
    name="Financial Statements",
    file_ids=["file-abc123", "file-def456"]
)

# 3. Vector Store를 Assistant에 연결
assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
)

# 4. Thread 생성 + 사용자 파일 첨부
message_file = client.files.create(file=open("report.pdf", "rb"), purpose="assistants")
thread = client.beta.threads.create(
    messages=[{
        "role": "user",
        "content": "매출 요약을 해주세요.",
        "attachments": [
            {"file_id": message_file.id, "tools": [{"type": "file_search"}]}
        ]
    }]
)

# 5. Run 실행
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id, assistant_id=assistant.id
)

# 6. 결과 확인
messages = client.beta.threads.messages.list(thread_id=thread.id, limit=1)
```

#### Responses API 버전

```python
from openai import OpenAI
client = OpenAI()

# 1. Vector Store 생성 (이것은 동일)
vector_store = client.vector_stores.create(name="Financial Statements")
client.vector_stores.files.upload_and_poll(
    vector_store_id=vector_store.id,
    file=open("report.pdf", "rb")
)

# 2. 한 번의 API 호출로 완결
response = client.responses.create(
    model="gpt-4o",
    instructions="재무제표에 관한 질문에 답하세요.",
    tools=[{
        "type": "file_search",
        "vector_store_ids": [vector_store.id]
    }],
    input="매출 요약을 해주세요."
)

# 3. 결과 확인
print(response.output_text)
```

**6단계 → 2단계**(Vector Store 생성 + Response 요청)로 간소화되었습니다.

### 3.4 Responses API에서의 File Search 향상점

1. **메타데이터 필터링 지원**: 파일에 속성(attributes)을 설정하고 검색 시 필터링 가능
   ```python
   response = client.responses.create(
       model="gpt-4o",
       tools=[{
           "type": "file_search",
           "vector_store_ids": [vector_store.id],
           "filters": {
               "type": "eq",
               "key": "category",
               "value": "finance"
           }
       }],
       input="매출 데이터를 알려주세요."
   )
   ```

2. **검색 결과 직접 포함**: `include` 파라미터로 검색 결과를 응답에 직접 포함 가능
   ```python
   response = client.responses.create(
       ...,
       include=["file_search_call.results"]
   )
   ```

3. **결과 수 제한**: `max_num_results`로 검색 결과 수를 직접 제어
   ```python
   tools=[{
       "type": "file_search",
       "vector_store_ids": [vector_store.id],
       "max_num_results": 5
   }]
   ```

4. **독립 Retrieval API**: `client.vector_stores.search()`로 모델 없이 직접 시맨틱 검색을 수행할 수도 있음

### 3.5 File Search 응답에서의 Annotation 변화

#### Assistants API
```json
{
  "type": "file_citation",
  "text": "[0]",
  "start_index": 24,
  "end_index": 27,
  "file_citation": {
    "file_id": "file_abc123",
    "quote": "실제 인용된 텍스트"
  }
}
```

#### Responses API
```json
{
  "type": "file_citation",
  "index": 992,
  "file_id": "file-2dtbBZdjtDKS8eqWxqbgDi",
  "filename": "deep_research_blog.pdf"
}
```

변경점:
- `start_index`/`end_index` → `index` (단일 위치)
- `file_citation.quote` 필드 제거 → `filename` 직접 제공
- 구조가 더 단순해짐

---

## 4. Vector Store의 변화

### 4.1 개요

Vector Store는 File Search가 사용하는 파일 저장소로, 파일을 자동으로 분석·분할(chunking)·임베딩하여 벡터 DB에 저장합니다.

### 4.2 핵심 변경점

**변경사항은 적습니다.** Vector Store는 Assistants API와 Responses API 양쪽에서 거의 동일하게 사용됩니다. 다만 API 경로와 일부 사용 방식에 차이가 있습니다.

| 항목 | Assistants API | Responses API |
|------|----------------|---------------|
| **API 경로** | `client.beta.vector_stores.*` | `client.vector_stores.*` (beta 제거됨) |
| **Assistant 연결** | `tool_resources`로 Assistant에 연결 | tools 배열에서 `vector_store_ids` 직접 지정 |
| **Thread 연결** | Thread에도 Vector Store 연결 가능 | 불필요 (tools 파라미터에 직접 지정) |
| **메타데이터 필터링** | 미지원 | `attributes` 설정 + `filters`로 검색 필터링 |
| **직접 검색** | 불가 (반드시 Run 실행 필요) | `client.vector_stores.search()` → 독립 검색 가능 |

### 4.3 Vector Store 설정 — 변하지 않은 것들

다음 사항들은 Responses API에서도 **동일**합니다:

- **최대 파일 수**: Vector Store당 최대 10,000개
- **파일 크기 제한**: 최대 512MB
- **최대 토큰 수**: 파일당 500만 토큰
- **기본 청크 크기**: 800토큰, 오버랩 400토큰
- **임베딩 모델**: text-embedding-3-large (256차원)
- **비용**: 첫 1GB 무료, 이후 $0.10/GB/일
- **만료 정책**: `expires_after` 설정으로 비용 절감 가능

### 4.4 Vector Store 사용법 (Responses API)

```python
from openai import OpenAI
client = OpenAI()

# 1. Vector Store 생성
vector_store = client.vector_stores.create(name="Support FAQ")

# 2. 파일 업로드 (poll로 완료 대기)
client.vector_stores.files.upload_and_poll(
    vector_store_id=vector_store.id,
    file=open("customer_policies.txt", "rb")
)

# 3. 속성 설정 (옵션 — 필터링용)
client.vector_stores.files.create(
    vector_store_id=vector_store.id,
    file_id="file_123",
    attributes={
        "region": "KR",
        "category": "Policy",
        "date": 1672531200
    }
)

# 4. 직접 검색
results = client.vector_stores.search(
    vector_store_id=vector_store.id,
    query="반품 정책은?",
    rewrite_query=True,  # 쿼리 최적화
    max_num_results=5
)

# 5. File Search 도구로 활용
response = client.responses.create(
    model="gpt-4o",
    tools=[{
        "type": "file_search",
        "vector_store_ids": [vector_store.id]
    }],
    input="반품 정책을 알려주세요."
)
```

---

## 5. 대화 상태 관리의 변화

Assistants API에서 Thread가 담당하던 대화 상태 관리는 Responses API에서 세 가지 방식으로 대체됩니다.

### 5.1 방법 1: `previous_response_id` 체이닝

가장 간단한 방법입니다. 이전 응답의 ID만 전달하면 됩니다.

```python
# 첫 번째 대화
response1 = client.responses.create(
    model="gpt-4o",
    input="농담 하나 해줘."
)

# 두 번째 대화 (이전 응답 컨텍스트 자동 포함)
response2 = client.responses.create(
    model="gpt-4o",
    previous_response_id=response1.id,
    input="왜 그게 웃긴 거야?"
)
```

### 5.2 방법 2: Conversations API

장기 세션에 적합한 방법입니다.

```python
# 대화 객체 생성
conversation = client.conversations.create()

# 여러 응답에 걸쳐 동일한 대화 객체 재사용
response = client.responses.create(
    model="gpt-4o",
    conversation=conversation.id,
    input="안녕하세요!"
)
```

### 5.3 방법 3: 수동 관리

기존 Chat Completions 방식처럼 직접 메시지 배열을 관리하는 방법입니다.

```python
history = [{"role": "user", "content": "안녕"}]
response = client.responses.create(model="gpt-4o", input=history, store=False)

# 응답을 히스토리에 추가
history += [{"role": el.role, "content": el.content} for el in response.output]
history.append({"role": "user", "content": "다음 질문"})

response2 = client.responses.create(model="gpt-4o", input=history, store=False)
```

### 5.4 (비교) Assistants API의 Thread

| 기능 | Assistants API (Thread) | Responses API |
|------|------------------------|---------------|
| 대화 기록 저장 | Thread에 자동 저장 | `store: true`로 자동 저장 또는 수동 관리 |
| 컨텍스트 윈도우 초과 시 | Thread가 자동으로 오래된 메시지 삭제 | `truncation: "auto"` 또는 Compaction API 사용 |
| 세션 지속성 | Thread ID로 영구 유지 | Conversations API 또는 `previous_response_id` 체이닝 |

---

## 6. Function Calling의 변화

Function calling도 약간의 구조적 변화가 있습니다.

### 6.1 함수 정의 방식

```python
# Assistants API (외부 태깅)
{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "날씨 조회",
        "parameters": { ... }
    }
}

# Responses API (내부 태깅)
{
    "type": "function",
    "name": "get_weather",
    "description": "날씨 조회",
    "parameters": { ... }
}
```

주요 차이:
- Assistants API: `"function": { "name": ... }` (중첩 구조)
- Responses API: `"name": ...` (플랫 구조)
- Responses API에서는 `strict: true`가 **기본값** (Assistants에서는 기본 false)

### 6.2 함수 호출 결과 전달

```python
# Assistants API
client.beta.threads.runs.submit_tool_outputs(
    thread_id=thread.id,
    run_id=run.id,
    tool_outputs=[{
        "tool_call_id": call.id,
        "output": "맑음, 25도"
    }]
)

# Responses API
response = client.responses.create(
    model="gpt-4o",
    previous_response_id=prev_response.id,
    input=[{
        "type": "function_call_output",
        "call_id": call.id,
        "output": "맑음, 25도"
    }]
)
```

---

## 7. 전체 마이그레이션 매핑 요약

| Assistants API | Responses API | 비고 |
|----------------|---------------|------|
| `client.beta.assistants.create()` | tools + instructions 파라미터 | Assistant 객체 불필요 |
| `client.beta.threads.create()` | `previous_response_id` 또는 Conversations API | Thread 객체 불필요 |
| `client.beta.threads.messages.create()` | `input` 파라미터 | Message 객체 불필요 |
| `client.beta.threads.runs.create_and_poll()` | `client.responses.create()` | Run 객체 불필요 |
| `client.beta.threads.runs.steps.list()` | `response.output` (Items 배열) | Run Step 불필요 |
| `client.files.create(purpose="assistants")` | `client.containers.files.create()` (CI) 또는 `client.vector_stores.files.upload_and_poll()` (FS) | 용도별 분리 |
| `client.beta.vector_stores.create()` | `client.vector_stores.create()` | beta 접두사 제거 |
| `tool_resources` | tools 배열에 직접 지정 | 연결 구조 단순화 |

---

## 8. 프로젝트 코드에서의 마이그레이션 실제 사례

### 8.1 CodeInterpreterClient 클래스 변화

현재 프로젝트(`part1/src/code_interpreter.py`)에서 이미 Responses API로 마이그레이션이 완료되어 있습니다. 주요 변화를 정리하면:

| 기존 (test.py) | 현재 (src/code_interpreter.py) |
|----------------|-------------------------------|
| `_create_assistant_agent()` — Assistant 생성 | `_create_container()` — Container 생성 |
| `_create_thread()` — Thread 생성 | 불필요 (삭제됨) |
| `upload_file()` — `files.create()` + Assistant 업데이트 | `upload_file()` — `containers.files.create()` |
| `run()` — Thread에 메시지 추가 → `runs.create_and_poll()` | `run()` — `responses.create()` 한 번 호출 |
| `_download_file()` — `files.content()` + `python-magic` | `_download_container_file()` — HTTP GET 직접 호출 |
| 응답 파싱: `message.data[0].content` 순회 | 응답 파싱: `response.output` → `code_interpreter_call` / `message` 분기 |

### 8.2 BigQuery 연동 부분의 변화

`part2/tools/bigquery.py`에서 SQL 실행 결과를 Code Interpreter에 업로드하는 방식:

```python
# 기존: files.create() → Assistant에 연결
file = client.files.create(file=csv_data, purpose="assistants")

# 현재: Container에 직접 업로드
file_id = self.code_interpreter.upload_file(csv_data)
# → 내부적으로 containers.files.create() 호출
```

---

## 9. 주의사항 및 팁

### 9.1 Container는 임시(Ephemeral)로 취급할 것

Container는 20분 비활동 시 자동 만료됩니다. 중요한 파일은 반드시 다운로드하여 자체 시스템에 저장하세요.

### 9.2 File Search와 Code Interpreter 병행 사용

Responses API에서는 하나의 `tools` 배열에 `file_search`와 `code_interpreter`를 동시에 지정할 수 있습니다:

```python
response = client.responses.create(
    model="gpt-4o",
    tools=[
        {
            "type": "file_search",
            "vector_store_ids": [vector_store.id]
        },
        {
            "type": "code_interpreter",
            "container": {"type": "auto"}
        }
    ],
    input="재무 데이터에서 매출 추이를 찾아서 그래프로 그려주세요."
)
```

### 9.3 Responses API에서만 가능한 새로운 기능들

- **Web Search**: `{"type": "web_search"}` — 웹 검색 내장 도구
- **MCP 연동**: `{"type": "mcp", ...}` — 외부 MCP 서버 연동
- **Image Generation**: `{"type": "image_generation"}` — 이미지 생성 내장 도구
- **Shell**: `{"type": "shell"}` — 셸 명령 실행 도구
- **Computer Use**: `{"type": "computer_use_preview"}` — 컴퓨터 조작 도구
- **Background Mode**: 장시간 실행 작업을 백그라운드로 처리

### 9.4 `store` 파라미터와 데이터 보안

```python
response = client.responses.create(
    model="gpt-4o",
    input="기밀 데이터 분석",
    store=False  # 응답을 OpenAI 서버에 저장하지 않음
)
```

`store=False`로 설정하면 OpenAI 서버에 응답이 저장되지 않아 데이터 보안이 필요한 경우에 유용합니다. 다만, 이 경우 `previous_response_id`를 사용한 대화 체이닝은 불가합니다.

---

## 10. 결론

| 관점 | Assistants API | Responses API |
|------|----------------|---------------|
| **복잡도** | Assistant → Thread → Message → Run → RunStep 다단계 객체 관리 필요 | 단일 `responses.create()` 호출로 완결 |
| **Code Interpreter** | Assistant + Thread + files.create() | Container + containers.files.create() |
| **File Search** | Assistant + VectorStore 연결 + Thread 첨부 | tools에 vector_store_ids 직접 지정 |
| **Vector Store** | `beta.vector_stores.*` | `vector_stores.*` (메타데이터 필터링 등 기능 강화) |
| **대화 관리** | Thread 기반 | previous_response_id / Conversations API / 수동 관리 |
| **비용** | 세션당 $0.03 (1시간) | Container당 $0.03 (20분, 메모리 티어별 상이) |
| **미래** | 2026년 8월 sunset 예정 | 앞으로의 모든 신기능은 여기에 집중 |

Responses API는 Assistants API의 복잡한 객체 관계를 제거하고, 하나의 통합된 인터페이스로 같은 기능(이상)을 제공합니다. 특히 Code Interpreter의 Container 기반 아키텍처와 File Search의 간소화된 사용법은 개발 생산성을 크게 향상시킵니다.

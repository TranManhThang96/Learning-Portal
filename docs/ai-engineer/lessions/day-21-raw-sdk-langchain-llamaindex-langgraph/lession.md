# Day 21: Raw SDK vs LangChain vs LlamaIndex vs LangGraph

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Phân biệt Raw SDK, LangChain LCEL, LlamaIndex, LangGraph và DSPy theo abstraction, control, latency, debugging, observability, vendor lock-in và team maturity.
- Biết chọn công cụ theo bài toán: một LLM call đơn giản, chain nhiều bước, document-heavy RAG, stateful agent workflow hoặc pipeline cần tối ưu bằng evaluation.
- Implement cùng một flow `ticket triage -> structured output` bằng Raw SDK và LangChain LCEL.
- Thiết kế observability tối thiểu cho LLM workflow: trace, span, token, cost, retry, schema validation, tool call và prompt/model version.
- Nhận diện abstraction risks: hidden retry, hidden prompt, khó debug, version churn, provider behavior khác nhau, leakage qua log/callback.
- Viết được production decision record: dùng framework nào, vì sao, điều kiện production là gì và cần monitor gì.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

Không có framework nào là "best" cho mọi LLM app. Best solution phụ thuộc vào shape của bài toán, SLA, độ phức tạp workflow, volume, yêu cầu audit, năng lực team và tốc độ thay đổi sản phẩm.

| Lựa chọn | Mạnh nhất ở đâu | Rủi ro chính |
|---|---|---|
| Raw SDK | Control cao, ít abstraction, dễ tối ưu latency/cost | Tự viết nhiều phần: retry, trace, schema, adapter, tool loop |
| LangChain LCEL | Build chain/tool flow nhanh, composable, nhiều integration | Version churn, abstraction che lỗi, khó biết framework đã làm gì nếu không trace kỹ |
| LlamaIndex | Data layer cho RAG: Document, Node, Index, Retriever, Query Engine | Dễ overkill nếu app không xoay quanh document ingestion/retrieval |
| LangGraph | Stateful agent workflow: state machine, loop, checkpoint, human-in-the-loop | Không thay thế schema validation, permission, eval, observability |
| DSPy | Tối ưu prompt/programmatic pipeline bằng evaluation | Cần golden set, metric rõ, mindset evaluation-driven |

Nguyên tắc thực tế: bắt đầu bằng abstraction thấp nhất đáp ứng bài toán. Thêm framework khi nó giảm complexity thật, không phải vì "LLM app thì phải dùng framework".

## 1. Day 21 Nằm Ở Đâu Trong Course

Day 17-20 đã xây nền tảng:

```text
Day 17: LLM fundamentals, token, model behavior
Day 18: prompt engineering thực chiến
Day 19: structured output và function/tool calling
Day 20: architecture production cho LLM app
Day 21: chọn abstraction/runtime/framework phù hợp
Day 22: agent patterns với LangGraph
Day 23+: RAG, evaluation, deployment và operations
```

Day 21 là bài học về engineering decision. Bạn không chỉ hỏi "framework nào phổ biến?", mà phải hỏi:

- Business flow có mấy bước?
- Có cần state, loop, retry từng bước, checkpoint hay human approval không?
- Data layer có document ingestion, chunking, metadata, retrieval, reranking không?
- Có cần multi-provider không?
- Debug production sẽ dựa vào trace nào?
- Khi package nâng version, làm sao biết chain vẫn đúng?
- Khi output sai schema, rollback ở prompt, model hay code?

## 2. Mental Model: Abstraction Là Chi Phí Và Lợi Ích

Abstraction tốt giúp giảm boilerplate, chuẩn hóa interface và tăng tốc delivery. Abstraction xấu che mất boundary quan trọng như timeout, retry, prompt, token usage, tool execution và schema validation.

Với LLM app, abstraction càng cao thì càng cần observability rõ:

```text
Raw SDK
  -> bạn thấy request/response rất rõ
  -> bạn tự chịu trách nhiệm mọi cross-cutting concern

LangChain LCEL
  -> bạn compose prompt/model/parser/tool như pipeline
  -> cần trace từng Runnable và pin version

LlamaIndex
  -> bạn dùng data abstractions cho RAG
  -> cần kiểm soát ingestion, chunking, metadata và retriever

LangGraph
  -> bạn mô hình workflow như graph có state
  -> cần kiểm soát transition, checkpoint, loop guard và HITL

DSPy
  -> bạn mô hình prompt/pipeline như program cần optimize
  -> cần dataset, metric và eval harness đáng tin
```

Một Senior Software Engineer nên đánh giá framework giống cách đánh giá ORM, message queue, workflow engine hoặc API gateway: nó giải quyết vấn đề thật nào, đổi lại bạn mất control ở đâu, và production debugging sẽ làm thế nào.

## 3. Raw SDK

Raw SDK nghĩa là gọi trực tiếp SDK/API của provider như OpenAI, Anthropic, Google, Azure OpenAI hoặc local inference service. Bạn tự thiết kế prompt, schema, retry, timeout, logging, cache, routing và wrapper nội bộ.

### Khi Nên Dùng

- Flow chỉ có 1-2 LLM calls.
- Task rõ ràng: classification, extraction, summarization, rewrite, moderation, routing.
- Cần latency thấp và kiểm soát request/response chi tiết.
- Cần custom retry, custom timeout, custom model routing hoặc custom audit.
- Team muốn hiểu boundary production trước khi thêm framework.
- App đã có architecture tốt từ Day 20: `LLMClient`, `Prompt Registry`, `Model Router`, `Observability`.

### Khi Không Nên Dùng Một Cách Thuần Túy

- Workflow có nhiều bước, nhiều branch, nhiều tool và loop.
- RAG có ingestion phức tạp, nhiều document type, metadata filter và reranking.
- Agent cần checkpoint, resume, human approval hoặc long-running state.
- Team liên tục thử nhiều provider/vector store/tool integration và cần tốc độ prototype cao.

### Ưu Điểm

- Ít magic, dễ đọc request thật.
- Dễ tính cost/request, token budget và latency từng call.
- Dễ enforce security boundary ở app layer.
- Dễ tối ưu cache, batching, streaming và backpressure theo đúng workload.
- Ít phụ thuộc vào version churn của framework.

### Nhược Điểm

- Dễ duplicate boilerplate nếu nhiều team cùng viết.
- Tool calling, retriever adapter, prompt template, parser, callback phải tự làm.
- Multi-provider abstraction không miễn phí: mỗi provider khác schema, streaming, tool protocol và structured output behavior.
- Nếu wrapper nội bộ thiết kế kém, bạn tự tạo framework tệ hơn framework có sẵn.

### Production Pattern

Không nên để business code gọi provider SDK rải rác. Nên có adapter nội bộ:

```text
Feature service
  -> LLMGateway hoặc LLMClient interface
      -> Prompt Registry
      -> Model Router
      -> Provider Adapter
      -> Observability
```

Raw SDK production không có nghĩa là "không abstraction". Nó nghĩa là abstraction do bạn sở hữu, mỏng, explicit và phù hợp domain.

## 4. LangChain LCEL

LangChain là application framework cho LLM app. LCEL, viết tắt của LangChain Expression Language, cho phép compose các thành phần như prompt, model, parser, retriever và function bằng toán tử pipeline.

Ví dụ mental model:

```text
input dict
  -> ChatPromptTemplate
  -> ChatModel.with_structured_output(...)
  -> typed result
```

### Khi Nên Dùng

- Cần build chain nhanh và vẫn giữ cấu trúc đọc được.
- Cần thay provider/model tương đối nhanh.
- Cần dùng prompt template, structured output, retriever, tool calling hoặc callbacks.
- Team prototype nhiều workflow và muốn có common interface.
- Flow vừa phải: vài bước, ít state lâu dài, ít checkpoint phức tạp.

### Khi Cần Cẩn Thận

- SLA rất chặt, cần tối ưu từng token và từng ms.
- Team không pin version hoặc không có regression test.
- Chain có nhiều Runnable lồng nhau nhưng thiếu trace.
- Dữ liệu nhạy cảm đi qua callback/tracing provider mà chưa kiểm soát retention.
- Tin rằng "multi-provider interface" nghĩa là behavior giống nhau. Không đúng. Interface giống không đảm bảo model trả cùng chất lượng/schema.

### LCEL Có Lợi Ở Đâu

- Pipeline rõ hơn so với code imperative dài.
- Có thể test từng component: prompt, model mock, parser.
- Dễ gắn callbacks/tracing nếu cấu hình đúng.
- Có `with_structured_output` để chuyển schema Pydantic thành structured output flow.
- Có nhiều integration cho retriever/vector store/tool.

### Production Pattern

Với LangChain, production cần thêm các lớp ngoài framework:

- Pin versions của `langchain`, `langchain-core`, `langchain-openai` và provider package.
- Wrap chain trong service function có timeout, retry policy, input validation và output validation.
- Log `run_id`, `trace_id`, prompt version, model, token usage, latency, retry count và schema error.
- Có golden tests cho prompt/schema.
- Không để chain tự quyết định permission khi gọi tool. Tool permission vẫn nằm ở app/service layer.

## 5. LlamaIndex

LlamaIndex mạnh ở data layer cho RAG. Nó cung cấp abstraction quanh document ingestion, parsing, chunking, node, index, retriever và query engine.

Mental model:

```text
Source files / DB rows / pages
  -> Document
  -> Node
  -> Index
  -> Retriever
  -> Query Engine
  -> Answer with citations
```

### Các Khái Niệm Cốt Lõi

| Khái niệm | Ý nghĩa production |
|---|---|
| Document | Đơn vị dữ liệu gốc, ví dụ PDF, Markdown, HTML, ticket, wiki page |
| Node | Chunk đã parse từ Document, thường kèm metadata |
| Index | Cấu trúc phục vụ search/retrieval, ví dụ vector index |
| Retriever | Component chọn Node liên quan với query |
| Query Engine | Ghép retrieval + synthesis để tạo answer |

### Khi Nên Dùng

- RAG là core của sản phẩm.
- Có nhiều nguồn dữ liệu và cần pipeline ingestion rõ.
- Cần chunking, metadata, incremental indexing, retriever, reranker, citation.
- Team muốn tách data/retrieval concern khỏi phần chat/agent.
- Cần thử nhiều retrieval strategy.

### Khi Không Nên Dùng

- App chỉ gọi model với prompt ngắn.
- Knowledge base nhỏ và retrieval đơn giản có thể tự viết bằng vài query.
- Vấn đề chính là workflow/state/tool approval, không phải document retrieval.

### Production Concerns

- Chunk size và overlap ảnh hưởng trực tiếp quality, latency và cost.
- Metadata filter sai có thể leak dữ liệu giữa tenant.
- Embedding model đổi version có thể làm retrieval behavior đổi.
- Ingestion phải idempotent, có document version, delete/update policy.
- Vector store cần backup, migration, TTL nếu dữ liệu có vòng đời.
- Citation cần trace được từ answer về source document/node.

## 6. LangGraph

LangGraph là runtime/orchestrator cho workflow có state. Thay vì chain tuyến tính, bạn mô hình hóa workflow thành graph gồm node, edge, conditional edge, state, checkpoint và human-in-the-loop.

Mental model:

```text
State
  -> Node: classify
  -> Conditional edge: needs_tool?
  -> Node: call_tool
  -> Node: review_or_finalize
  -> Checkpoint
  -> Final
```

### Khi Nên Dùng

- Workflow có loop, branch, retry theo state hoặc nhiều tool.
- Cần checkpoint/resume sau từng bước.
- Cần human approval trước khi gọi tool nhạy cảm.
- Agent chạy dài, có thể pause/resume.
- Cần nhìn workflow như state machine thay vì chain mơ hồ.

### Khi Không Nên Dùng

- Một LLM call đơn giản.
- Chain 2-3 bước không cần state lâu dài.
- Team chưa biết state schema, stop condition và tool permission.

### Production Concerns

- State schema phải rõ và versioned.
- Mỗi loop phải có stop condition, max iterations và timeout.
- Checkpointer production nên dùng persistent store phù hợp, không chỉ memory.
- HITL không chỉ là UI approve. Nó cần audit: ai approve, lúc nào, input/output gì.
- Tool execution phải idempotent hoặc có transaction boundary.
- Trace phải map được từng graph node, edge decision và tool call.

LangGraph không thay thế LangChain. Thực tế có thể dùng LangGraph để orchestrate, LangChain model/tool wrappers bên trong node, và Raw SDK cho call cần control cao.

## 7. DSPy

DSPy là framework theo hướng programmatic prompting và optimization. Thay vì viết prompt thủ công rồi đo cảm tính, bạn định nghĩa module/pipeline, metric và training/evaluation examples để tối ưu prompt hoặc instruction.

### Khi Nên Dùng

- Bạn có golden set hoặc có thể tạo dataset đánh giá đủ đại diện.
- Task lặp lại nhiều lần và chất lượng prompt ảnh hưởng trực tiếp business metric.
- Cần tối ưu classification, extraction, multi-hop QA hoặc RAG pipeline bằng metric.
- Team đã có discipline về evaluation.

### Khi Không Nên Dùng

- Chưa có metric rõ.
- Chưa có dữ liệu đánh giá.
- Sản phẩm còn thay đổi quá nhanh, schema/task chưa ổn định.
- Team chỉ cần một chain production đơn giản.

### Trade-off

DSPy có thể tăng chất lượng và giảm prompt guessing, nhưng đổi lại bạn phải đầu tư vào dataset, metric, eval harness và CI. Nếu không có evaluation, DSPy dễ trở thành thêm một abstraction khó giải thích.

## 8. Decision Rules

### Rule 1: Bắt Đầu Từ Shape Của Bài Toán

| Shape của bài toán | Lựa chọn mặc định |
|---|---|
| Một LLM call, output JSON, SLA chặt | Raw SDK |
| Prompt chain/tool flow nhanh, ít state | LangChain LCEL |
| RAG có ingestion/document/retriever là core | LlamaIndex |
| Agent có state, loop, checkpoint, HITL | LangGraph |
| Pipeline cần tối ưu bằng metric/golden set | DSPy |

### Rule 2: Chọn Theo Failure Mode

| Failure mode đáng sợ nhất | Công cụ/pattern nên ưu tiên |
|---|---|
| Latency/cost spike khó kiểm soát | Raw SDK + gateway policy |
| Chain logic rối và khó compose | LangChain LCEL |
| Retrieval sai tài liệu hoặc leak tenant | LlamaIndex + metadata discipline |
| Agent loop vô hạn hoặc mất state | LangGraph + checkpoint/loop guard |
| Prompt quality không ổn định qua phiên bản | DSPy/eval-driven workflow |

### Rule 3: Framework Không Thay Observability

Bất kể dùng framework nào, production trace tối thiểu nên có:

- `trace_id`, `request_id`, `tenant_id`, `user_id` hoặc hash/anonymized id.
- `workflow_name`, `workflow_version`, `node_name` hoặc `chain_step`.
- `prompt_id`, `prompt_version`, `schema_version`.
- `provider`, `model`, `model_version` nếu có.
- `input_tokens`, `output_tokens`, `total_tokens`, estimated cost.
- `latency_ms`, `queue_ms`, `retry_count`, timeout/error type.
- `structured_output_valid`, validation error nếu có.
- Tool calls: name, args hash, permission decision, latency, error.
- Retrieval: index version, retriever, top_k, document/node ids, score.
- Safety/audit flags: PII redaction, blocked tool, human approval.

## 9. Abstraction Risks

### Hidden Retry

Framework hoặc SDK có thể retry mặc định. Nếu app layer cũng retry, bạn có thể nhân số request lên nhiều lần, gây cost spike và duplicate tool execution.

Best practice:

- Biết retry nằm ở layer nào.
- Log `retry_count`.
- Retry LLM call có thể OK, retry tool side effect phải cực kỳ cẩn thận.
- Dùng idempotency key cho operation có side effect.

### Hidden Prompt

Chain/tool wrapper có thể thêm system prompt hoặc format instruction. Output thay đổi nhưng bạn không biết prompt thật là gì.

Best practice:

- Log prompt template id/version, không log raw PII nếu chưa redaction.
- Trong non-production, capture rendered prompt để debug.
- Có prompt snapshot tests.

### Provider Abstraction Ảo

Cùng một interface `chat.invoke()` không có nghĩa hai provider có cùng behavior. Tool calling, JSON schema, streaming, context window, refusal, safety policy và tokenization có thể khác.

Best practice:

- Test từng provider bằng golden set.
- Schema validation ở app layer.
- Fallback model phải có eval riêng.

### Version Churn

LLM frameworks thay đổi nhanh. Minor version cũng có thể đổi default behavior hoặc integration package.

Best practice:

- Pin dependency versions.
- Có lockfile.
- Có CI smoke test cho chain chính.
- Có ADR ghi version đang được production approve.

### Observability Leak

Tracing/callback có thể gửi prompt, output, tool args hoặc PII sang third-party observability service.

Best practice:

- Xác định data retention và redaction.
- Không log secret, access token, raw file content nhạy cảm.
- Có allowlist field được log.

## 10. Ticket Triage: Domain Và Output Contract

Flow thực hành của bài:

```text
Customer ticket text
  -> classify category
  -> estimate priority
  -> decide needs_human
  -> draft short reply
  -> return strict JSON
```

Output contract:

```json
{
  "category": "billing",
  "priority": "high",
  "needs_human": true,
  "draft_reply": "..."
}
```

Schema nên explicit:

- `category`: `billing`, `bug`, `howto`, `account`, `other`.
- `priority`: `low`, `medium`, `high`, `urgent`.
- `needs_human`: boolean.
- `draft_reply`: câu trả lời lịch sự, ngắn, không hứa hoàn tiền nếu chưa kiểm tra.
- `confidence`: số từ 0 đến 1.
- `reasons`: danh sách ngắn, phục vụ audit nội bộ.

Production lưu ý: `draft_reply` không nên gửi thẳng cho khách nếu ticket có refund, legal, security hoặc enterprise escalation. Model chỉ draft, policy quyết định publish.

## 11. Raw SDK Example Gần Production

Ví dụ dưới đây vẫn là single file để dễ học, nhưng đã có các yếu tố production-style: schema strict, timeout, retry có kiểm soát, trace metadata, validation bằng Pydantic và không parse text tự do.

```python
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Literal

from openai import OpenAI, APITimeoutError, RateLimitError
from pydantic import BaseModel, Field, ValidationError


class TicketTriage(BaseModel):
    category: Literal["billing", "bug", "howto", "account", "other"]
    priority: Literal["low", "medium", "high", "urgent"]
    needs_human: bool
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1, max_length=5)
    draft_reply: str = Field(min_length=1, max_length=1200)


TRIAGE_SCHEMA = TicketTriage.model_json_schema()

SYSTEM_PROMPT = """Bạn là support triage assistant cho SaaS B2B.
Nhiệm vụ:
- Phân loại ticket vào category hợp lệ.
- Chọn priority theo impact, urgency và rủi ro khách hàng.
- Đánh dấu needs_human=true nếu có refund, billing dispute, security, legal,
  enterprise escalation hoặc confidence thấp.
- Viết draft_reply bằng tiếng Việt lịch sự, không hứa hành động chưa được xác minh.
Chỉ trả về structured output theo schema."""


class TriageService:
    def __init__(self, model: str) -> None:
        self.client = OpenAI(timeout=20.0, max_retries=0)
        self.model = model

    def triage(self, ticket: str, tenant_id: str, user_id: str) -> TicketTriage:
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Ticket:\n{ticket}"},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "ticket_triage",
                            "schema": TRIAGE_SCHEMA,
                            "strict": True,
                        }
                    },
                    metadata={
                        "trace_id": trace_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "prompt_id": "support_triage",
                        "prompt_version": "v1",
                        "schema_version": "ticket_triage.v1",
                    },
                )

                raw_json = response.output_text
                result = TicketTriage.model_validate_json(raw_json)
                self._log_success(trace_id, started, attempt, response)
                return result

            except (APITimeoutError, RateLimitError) as exc:
                last_error = exc
                self._log_retry(trace_id, attempt, exc)
                time.sleep(0.25 * (2**attempt))
            except (ValidationError, json.JSONDecodeError) as exc:
                # Schema/validation error is usually not fixed by blind retry forever.
                self._log_validation_error(trace_id, started, exc)
                raise

        self._log_failure(trace_id, started, last_error)
        raise RuntimeError(f"ticket triage failed trace_id={trace_id}") from last_error

    def _log_success(self, trace_id: str, started: float, attempt: int, response: object) -> None:
        latency_ms = round((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        print(
            {
                "event": "llm.triage.success",
                "trace_id": trace_id,
                "latency_ms": latency_ms,
                "retry_count": attempt,
                "model": self.model,
                "usage": usage.model_dump() if hasattr(usage, "model_dump") else None,
            }
        )

    def _log_retry(self, trace_id: str, attempt: int, exc: Exception) -> None:
        print(
            {
                "event": "llm.triage.retry",
                "trace_id": trace_id,
                "attempt": attempt + 1,
                "error_type": type(exc).__name__,
            }
        )

    def _log_validation_error(self, trace_id: str, started: float, exc: Exception) -> None:
        print(
            {
                "event": "llm.triage.validation_error",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            }
        )

    def _log_failure(self, trace_id: str, started: float, exc: Exception | None) -> None:
        print(
            {
                "event": "llm.triage.failure",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__ if exc else None,
            }
        )


if __name__ == "__main__":
    service = TriageService(model=os.environ.get("MODEL", "gpt-4.1-mini"))
    result = service.triage(
        ticket="Khách bị tính phí hai lần sau khi nâng cấp gói enterprise và yêu cầu hoàn tiền ngay.",
        tenant_id="tenant_demo",
        user_id="user_123",
    )
    print(result.model_dump())
```

Điểm đáng chú ý:

- SDK retry bị tắt bằng `max_retries=0` để app kiểm soát retry. Trong thực tế bạn có thể dùng retry của SDK, nhưng phải tránh retry chồng retry.
- `TicketTriage` là contract nội bộ, không tin output raw.
- Metadata có `prompt_version` và `schema_version`.
- Validation error không retry vô hạn.
- Log ví dụ dùng `print` cho dễ học; production nên dùng structured logger/OpenTelemetry.

## 12. LangChain LCEL Example Gần Production

Ví dụ này dùng LCEL để compose prompt và model structured output. Nó vẫn bọc trong service để production code không phụ thuộc rải rác vào chain.

```python
from __future__ import annotations

import os
import time
import uuid
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, ValidationError


class TicketTriage(BaseModel):
    category: Literal["billing", "bug", "howto", "account", "other"]
    priority: Literal["low", "medium", "high", "urgent"]
    needs_human: bool
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1, max_length=5)
    draft_reply: str = Field(min_length=1, max_length=1200)


PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Bạn là support triage assistant cho SaaS B2B.
Phân loại ticket, chọn priority, quyết định needs_human và viết draft_reply.
needs_human=true nếu có refund, billing dispute, security, legal,
enterprise escalation hoặc confidence thấp.
Không hứa hoàn tiền hoặc thay đổi tài khoản khi chưa có xác minh.""",
        ),
        ("user", "Ticket:\n{ticket}"),
    ]
)


class LangChainTriageService:
    def __init__(self, model: str) -> None:
        llm = ChatOpenAI(
            model=model,
            temperature=0,
            timeout=20,
            max_retries=0,
        ).with_structured_output(TicketTriage)
        self.chain = PROMPT | llm
        self.model = model

    def triage(self, ticket: str, tenant_id: str, user_id: str) -> TicketTriage:
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()
        config = {
            "run_name": "support_ticket_triage",
            "tags": ["day21", "ticket_triage"],
            "metadata": {
                "trace_id": trace_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "prompt_id": "support_triage",
                "prompt_version": "v1",
                "schema_version": "ticket_triage.v1",
                "model": self.model,
            },
        }

        try:
            result = self.chain.invoke({"ticket": ticket}, config=config)
            if not isinstance(result, TicketTriage):
                result = TicketTriage.model_validate(result)
            self._log_success(trace_id, started)
            return result
        except ValidationError as exc:
            self._log_error(trace_id, started, exc)
            raise
        except Exception as exc:
            self._log_error(trace_id, started, exc)
            raise

    def _log_success(self, trace_id: str, started: float) -> None:
        print(
            {
                "event": "langchain.triage.success",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "model": self.model,
            }
        )

    def _log_error(self, trace_id: str, started: float, exc: Exception) -> None:
        print(
            {
                "event": "langchain.triage.error",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            }
        )


if __name__ == "__main__":
    service = LangChainTriageService(model=os.environ.get("MODEL", "gpt-4.1-mini"))
    result = service.triage(
        ticket="Khách báo không đăng nhập được sau khi bật SSO cho toàn bộ công ty.",
        tenant_id="tenant_demo",
        user_id="user_456",
    )
    print(result.model_dump())
```

Điểm đáng chú ý:

- LCEL làm flow ngắn và dễ đọc hơn.
- `with_structured_output(TicketTriage)` giảm code schema thủ công.
- `config.metadata` giúp tracing, nhưng bạn vẫn phải quyết định log gì, redaction ra sao.
- Timeout/retry vẫn cần explicit.
- Chain được giấu sau service class, giúp thay Raw SDK/LangChain dễ hơn về sau.

## 13. So Sánh Raw SDK Và LangChain Cho Ticket Triage

| Tiêu chí | Raw SDK | LangChain LCEL |
|---|---|---|
| LOC ban đầu | Dài hơn | Ngắn hơn |
| Control request | Rất cao | Trung bình đến cao, tùy wrapper |
| Structured output | Tự truyền JSON schema | Dùng Pydantic/schema qua wrapper |
| Observability | Tự thiết kế toàn bộ | Có config/callback/tracing integration |
| Debug prompt thật | Rõ nếu tự render | Cần biết chain render thế nào |
| Retry/timeout | Rất explicit | Phải kiểm soát SDK + wrapper |
| Vendor switch | Tự viết adapter | Dễ hơn về interface, không đảm bảo behavior |
| Performance tuning | Dễ tối ưu sâu | Có overhead nhỏ, thường không đáng kể so với LLM latency |
| Risk | Boilerplate và duplicate | Version churn và abstraction leak |

Kết luận thực tế:

- Nếu chỉ có ticket triage như trên và team có platform backend tốt, Raw SDK là lựa chọn rất mạnh.
- Nếu app có nhiều prompt chain, nhiều provider integration, cần prototype nhanh, LangChain LCEL đáng dùng.
- Nếu ticket triage cần lấy context từ knowledge base lớn, thêm LlamaIndex cho retrieval.
- Nếu ticket triage trở thành workflow nhiều bước có approval/refund/tool execution, cân nhắc LangGraph.
- Nếu muốn tối ưu prompt triage bằng golden set và metric như macro-F1 theo category/priority, cân nhắc DSPy.

## 14. Performance Considerations

### Latency

Framework overhead thường nhỏ hơn latency của model call. Nhưng workflow nhiều bước có thể nhân số LLM calls:

```text
1 call classification: 800 ms
5-step agent loop: 5 * 800 ms + tool latency + checkpoint IO
```

Vì vậy performance risk lớn thường không phải vài ms abstraction overhead, mà là:

- quá nhiều LLM calls;
- retrieval top_k quá lớn;
- prompt chứa context thừa;
- retry chồng retry;
- tool loop không có stop condition;
- streaming không dùng cho UX cần phản hồi sớm;
- không cache request lặp lại.

### Cost

Cost tăng theo:

- input tokens;
- output tokens;
- số calls;
- model choice;
- embedding/ingestion;
- reranking;
- tracing/log retention nếu lưu payload lớn.

Best practice:

- Đặt `max_output_tokens`.
- Dùng model nhỏ cho classification/extraction khi eval đạt yêu cầu.
- Cache exact hoặc semantic với tenant boundary rõ.
- Tách draft reply khỏi classification nếu một phần có thể dùng model rẻ hơn.
- Log estimated cost theo trace.

### Throughput

Raw SDK dễ custom batching và queue. LangChain/LlamaIndex/LangGraph vẫn có thể scale, nhưng cần hiểu runtime và IO:

- Dùng async nếu workload IO-bound.
- Giới hạn concurrency theo provider rate limit.
- Dùng queue cho long-running workflow.
- Với LangGraph, checkpoint persistent store có thể thành bottleneck.
- Với LlamaIndex, ingestion nên chạy async/background, không block request realtime.

## 15. Security Và Safety

LLM framework không tự giải quyết security. Các boundary vẫn nằm ở app:

- Input validation trước khi gửi model.
- Redaction hoặc policy cho PII.
- Prompt injection defense cho RAG/tool use.
- Tool allowlist và permission check.
- Không execute tool chỉ vì model yêu cầu.
- Audit log cho action nhạy cảm.
- Tenant isolation trong cache, index, metadata filter và trace.
- Human approval cho refund, billing action, account deletion, permission change.

Với ticket triage, model chỉ nên đề xuất `needs_human` và `draft_reply`. Hệ thống support thật cần policy layer quyết định có auto-send hay không.

## 16. Dùng Được Trong Production Không?

Có, cả Raw SDK, LangChain LCEL, LlamaIndex, LangGraph và DSPy đều có thể dùng trong production. Nhưng điều kiện khác nhau.

### Raw SDK Production Conditions

- Có wrapper nội bộ thay vì gọi SDK rải rác.
- Có timeout, retry, circuit breaker hoặc fallback phù hợp.
- Có structured output và validation.
- Có prompt/model/schema versioning.
- Có observability: latency, token, cost, error, retry, trace.
- Có security policy cho PII, logging, cache và tool access.

### LangChain Production Conditions

- Pin versions và có lockfile.
- Chain chính có regression tests/golden tests.
- Callback/tracing được cấu hình an toàn dữ liệu.
- Timeout/retry explicit.
- Không để framework quyết định business permission.
- Có plan rollback khi package/model/prompt thay đổi.

### LlamaIndex Production Conditions

- Ingestion idempotent, có document version và delete/update policy.
- Metadata filter bắt buộc cho tenant/user permission.
- Embedding/index version được quản lý.
- Retriever/reranker được eval bằng query set thật.
- Source citation trace được tới Document/Node.
- Vector store có backup, monitoring và migration plan.

### LangGraph Production Conditions

- State schema rõ, versioned và test được.
- Mỗi loop có max iterations, timeout và stop condition.
- Persistent checkpointer phù hợp workload.
- Tool node có permission, idempotency và audit.
- HITL có người approve, lý do, timestamp và trace.
- Observability map được node/edge/tool/model call.

### DSPy Production Conditions

- Có golden dataset đại diện.
- Metric đo đúng business quality.
- Optimization result được versioned.
- Có holdout set để tránh overfit.
- Có CI/eval gate trước rollout.
- Team hiểu pipeline thay đổi theo dữ liệu và metric, không chỉ theo prompt text.

## 17. Best Solution Theo Context

| Context | Best starting point | Lý do |
|---|---|---|
| Startup cần ship ticket classification trong 1 tuần | Raw SDK hoặc LangChain LCEL | Raw nếu backend mạnh; LCEL nếu cần prototype nhiều prompt |
| Enterprise support assistant có KB lớn | LlamaIndex + Raw/LangChain gateway | Retrieval/document layer là core |
| Refund workflow cần approval và tool execution | LangGraph + service-owned tools | State, checkpoint và HITL quan trọng hơn chain tuyến tính |
| Nhiều team dùng LLM chung | Internal LLM Gateway + adapter | Governance, cost, quota, audit |
| Prompt quality biến động và có nhãn đánh giá | DSPy hoặc eval-driven prompt pipeline | Cần tối ưu theo metric thay vì cảm tính |
| SLA realtime rất chặt | Raw SDK mỏng + cache/router | Tối ưu sâu, ít layer không cần thiết |

Không cần chọn một framework duy nhất cho toàn bộ công ty. Production stack thường là composition:

```text
API service
  -> internal LLM gateway
  -> Raw SDK provider adapter cho call quan trọng
  -> LangChain LCEL cho chain vừa phải
  -> LlamaIndex cho retrieval
  -> LangGraph cho stateful workflow
  -> eval/DSPy cho optimization loop
```

## 18. Checklist Kết Thúc Bài

- [ ] Giải thích được khác biệt giữa Raw SDK, LangChain LCEL, LlamaIndex, LangGraph và DSPy.
- [ ] Biết chọn tool theo shape của bài toán, không theo hype.
- [ ] Viết được flow ticket triage bằng Raw SDK.
- [ ] Viết được flow ticket triage bằng LangChain LCEL.
- [ ] Có schema structured output và validation.
- [ ] Có trace fields tối thiểu cho production debugging.
- [ ] Biết abstraction risks và cách giảm rủi ro.
- [ ] Trả lời được "dùng được trong production không, cần điều kiện gì?".

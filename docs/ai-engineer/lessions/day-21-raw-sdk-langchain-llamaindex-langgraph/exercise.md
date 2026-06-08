# Day 21 Exercise: Ticket Triage Bằng Raw SDK Và LangChain LCEL

## Mục Tiêu Thực Hành

Sau bài tập này, bạn cần chứng minh được:

- Implement cùng một flow `ticket triage -> structured output` bằng Raw SDK và LangChain LCEL.
- So sánh được LOC, control, latency, observability, retry và schema validation.
- Biết thêm trace metadata cần thiết cho production.
- Biết viết ADR ngắn để chọn abstraction theo context.
- Trả lời được: dùng được trong production không, cần điều kiện gì.

## Yêu Cầu Môi Trường

Tạo môi trường Python riêng:

```bash
cd lessions/day-21-raw-sdk-langchain-llamaindex-langgraph
python -m venv .venv
source .venv/bin/activate
pip install openai pydantic langchain langchain-core langchain-openai
```

Thiết lập API key và model:

```bash
export OPENAI_API_KEY="..."
export MODEL="gpt-5.5"
```

Nếu không muốn gọi provider thật, bạn vẫn có thể đọc code và thay phần gọi model bằng mock. Mục tiêu chính của bài là hiểu production shape và trade-off.

## Exercise 1: Viết Schema

Tạo file `ticket_schema.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TicketTriage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["billing", "bug", "howto", "account", "other"]
    priority: Literal["low", "medium", "high", "urgent"]
    needs_human: bool
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1, max_length=5)
    draft_reply: str = Field(min_length=1, max_length=1200)
```

Câu hỏi:

1. Vì sao `category` và `priority` nên dùng enum/Literal thay vì string tự do?
2. Vì sao `confidence` phải có range?
3. Vì sao `draft_reply` nên có giới hạn độ dài?

## Exercise 2: Raw SDK Implementation

Tạo file `raw_sdk_triage.py`:

```python
from __future__ import annotations

import os
import time
import uuid

from openai import OpenAI, APITimeoutError, RateLimitError
from pydantic import ValidationError

from ticket_schema import TicketTriage


SYSTEM_PROMPT = """Bạn là support triage assistant cho SaaS B2B.
Return structured output theo schema.
needs_human=true nếu có refund, billing dispute, security, legal,
enterprise escalation hoặc confidence thấp.
draft_reply phải lịch sự, ngắn và không hứa hành động chưa xác minh."""


class RawSdkTriage:
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
                            "schema": TicketTriage.model_json_schema(),
                            "strict": True,
                        }
                    },
                    max_output_tokens=1200,
                    store=False,
                    metadata={
                        "trace_id": trace_id,
                        "prompt_id": "support_triage",
                        "prompt_version": "v1",
                        "schema_version": "ticket_triage.v1",
                    },
                )
                if response.status != "completed" or not response.output_text:
                    raise RuntimeError("model response was incomplete, empty, or refused")
                result = TicketTriage.model_validate_json(response.output_text)
                self._log("success", trace_id, started, attempt)
                return result
            except (APITimeoutError, RateLimitError) as exc:
                last_error = exc
                self._log("retry", trace_id, started, attempt, exc)
                time.sleep(0.25 * (2**attempt))
            except ValidationError as exc:
                self._log("validation_error", trace_id, started, attempt, exc)
                raise
            except RuntimeError as exc:
                self._log("response_error", trace_id, started, attempt, exc)
                raise

        self._log("failure", trace_id, started, 2, last_error)
        raise RuntimeError(f"triage failed trace_id={trace_id}") from last_error

    def _log(
        self,
        event: str,
        trace_id: str,
        started: float,
        retry_count: int,
        exc: Exception | None = None,
    ) -> None:
        print(
            {
                "event": f"raw_sdk.triage.{event}",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "retry_count": retry_count,
                "model": self.model,
                "error_type": type(exc).__name__ if exc else None,
            }
        )


if __name__ == "__main__":
    service = RawSdkTriage(model=os.environ.get("MODEL", "gpt-5.5"))
    output = service.triage(
        ticket="Khách bị tính phí hai lần sau khi nâng cấp gói enterprise và yêu cầu hoàn tiền ngay.",
        tenant_id="tenant_demo",
        user_id="user_123",
    )
    print(output.model_dump_json(indent=2))
```

Chạy:

```bash
python raw_sdk_triage.py
```

Ghi lại:

- Output có valid schema không?
- Log có `trace_id`, `latency_ms`, `retry_count`, `model` không?
- Nếu API timeout, retry nằm ở layer nào?

## Exercise 3: LangChain LCEL Implementation

Tạo file `langchain_triage.py`:

```python
from __future__ import annotations

import os
import time
import uuid

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ticket_schema import TicketTriage


PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Bạn là support triage assistant cho SaaS B2B.
Return structured output theo schema.
needs_human=true nếu có refund, billing dispute, security, legal,
enterprise escalation hoặc confidence thấp.
draft_reply phải lịch sự, ngắn và không hứa hành động chưa xác minh.""",
        ),
        ("user", "Ticket:\n{ticket}"),
    ]
)


class LangChainTriage:
    def __init__(self, model: str) -> None:
        llm = ChatOpenAI(
            model=model,
            timeout=20,
            max_retries=0,
        ).with_structured_output(TicketTriage, method="json_schema")
        self.chain = PROMPT | llm
        self.model = model

    def triage(self, ticket: str, tenant_id: str, user_id: str) -> TicketTriage:
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()
        config = {
            "run_name": "support_ticket_triage",
            "tags": ["ticket_triage", "day21"],
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
            self._log("success", trace_id, started, None)
            return result
        except Exception as exc:
            self._log("error", trace_id, started, exc)
            raise

    def _log(self, event: str, trace_id: str, started: float, exc: Exception | None) -> None:
        print(
            {
                "event": f"langchain.triage.{event}",
                "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "model": self.model,
                "error_type": type(exc).__name__ if exc else None,
            }
        )


if __name__ == "__main__":
    service = LangChainTriage(model=os.environ.get("MODEL", "gpt-5.5"))
    output = service.triage(
        ticket="Khách báo không đăng nhập được sau khi bật SSO cho toàn bộ công ty.",
        tenant_id="tenant_demo",
        user_id="user_456",
    )
    print(output.model_dump_json(indent=2))
```

Chạy:

```bash
python langchain_triage.py
```

Ghi lại:

- Code có ngắn hơn Raw SDK không?
- Bạn còn thấy request schema thấp-level rõ như Raw SDK không?
- Metadata trace nằm ở đâu?
- Vì sao nên ghi rõ `method="json_schema"` khi muốn so sánh công bằng với Raw SDK structured output? Nếu bỏ tham số này, LangChain có thể dùng strategy structured output khác tùy model/provider.

## Exercise 4: So Sánh Hai Cách

Điền bảng:

| Tiêu chí | Raw SDK | LangChain LCEL | Nhận xét |
|---|---|---|---|
| LOC | | | |
| Control timeout/retry | | | |
| Control schema | | | |
| Dễ đọc flow | | | |
| Dễ debug request thật | | | |
| Dễ thêm step mới | | | |
| Dễ thay provider | | | |
| Risk version churn | | | |
| Observability effort | | | |
| Production readiness | | | |

Câu hỏi bắt buộc:

1. Với ticket triage đơn giản, bạn chọn Raw SDK hay LangChain? Vì sao?
2. Khi nào bạn sẽ thêm LlamaIndex?
3. Khi nào bạn sẽ thêm LangGraph?
4. Khi nào DSPy đáng cân nhắc?
5. Risk lớn nhất nếu dùng framework mà không có trace là gì?

## Exercise 5: Thêm Policy `needs_human`

Hiện tại model quyết định `needs_human`. Trong production, nên có rule-based guard sau model.

Tạo function:

```python
def enforce_human_policy(ticket: str, triage: TicketTriage) -> TicketTriage:
    risky_keywords = [
        "hoàn tiền",
        "refund",
        "security",
        "bảo mật",
        "rò rỉ dữ liệu",
        "legal",
        "sso",
        "enterprise",
    ]
    text = ticket.lower()
    if any(keyword in text for keyword in risky_keywords):
        return triage.model_copy(update={"needs_human": True})
    if triage.confidence < 0.7:
        return triage.model_copy(update={"needs_human": True})
    return triage
```

Câu hỏi:

1. Vì sao business policy không nên chỉ nằm trong prompt?
2. Rule này có thể gây false positive nào?
3. False positive và false negative, cái nào nguy hiểm hơn trong support triage?

## Exercise 6: Viết ADR Ngắn

Viết file `adr_day21.md` với nội dung:

```markdown
# ADR: Abstraction Cho Ticket Triage

## Context

Mô tả workload, SLA, dữ liệu, compliance, team skill và expected growth.

## Decision

Chọn Raw SDK, LangChain LCEL, LlamaIndex, LangGraph hoặc DSPy.

## Why

Giải thích theo control, complexity, performance, observability và maintainability.

## Trade-offs

Liệt kê ít nhất 3 ưu điểm và 3 nhược điểm.

## Production Conditions

Liệt kê điều kiện để dùng production.

## Revisit Trigger

Khi nào sẽ đổi quyết định?
```

## Exercise 7: Production Readiness Review

Review lại code của bạn và đánh dấu:

- [ ] Có timeout.
- [ ] Có retry policy rõ.
- [ ] Có schema validation.
- [ ] Schema từ chối field lạ và không drift khỏi type trong code.
- [ ] Có error path cho refusal/incomplete response.
- [ ] Đã quyết định rõ provider retention (`store=False` nếu phù hợp).
- [ ] Có `trace_id`.
- [ ] Có `prompt_version`.
- [ ] Có `schema_version`.
- [ ] Có log latency.
- [ ] Không log raw secret.
- [ ] Có policy guard ngoài prompt.
- [ ] Có câu trả lời production conditions.

## Câu Trả Lời Mẫu: Dùng Được Trong Production Không?

Có thể dùng trong production nếu:

- Code được bọc trong service/API có auth, quota và rate limit.
- Prompt, model và schema được versioned.
- Output luôn validate bằng Pydantic hoặc schema validator tương đương.
- Có timeout, retry, fallback/runbook.
- Có observability cho latency, token, cost, retry, validation error.
- Có redaction/logging policy cho PII.
- Có golden tests để kiểm tra category, priority và `needs_human`.
- Có human review cho billing dispute, refund, security, legal và enterprise escalation.

Chưa nên dùng production nếu:

- Business code gọi SDK rải rác.
- Prompt nằm hard-code không version.
- Output JSON được parse bằng regex/string split.
- Không biết request nào gây cost spike.
- Không có tenant isolation cho cache/retrieval.
- Tool/action nhạy cảm được execute trực tiếp theo model output.

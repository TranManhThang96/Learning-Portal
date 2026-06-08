# Day 49: UI, Monitoring, Evaluation Report

## Mục Tiêu

Sau bài này, capstone của bạn cần có bề mặt demo và bằng chứng đo lường:

- UI chat đơn giản gọi `/query` hoặc `/chat`.
- Hiển thị answer, citations, source metadata, latency, token/cost và trace ID.
- Thu feedback thumbs up/down gắn với `trace_id`.
- Có monitoring/report cho latency, cost, retrieval, citation, error và guardrail.
- Chạy golden evaluation trên pipeline hiện tại.
- Viết `evaluation_report.md` có metrics, lỗi chính, trade-off và release decision.
- Trả lời được: UI/monitoring/eval này dùng production được chưa, còn thiếu gì.

## TL;DR

Day 49 biến backend/API của Day 48 thành capstone có thể demo và review. UI không cần phức tạp, nhưng phải cho thấy answer có citation, source nào được dùng, request chậm ở đâu, tốn bao nhiêu token/cost và user có hài lòng không. Evaluation report là bằng chứng rằng RAG system được đo lường nghiêm túc, không chỉ "chat thử thấy đúng".

## 0. Phân Biệt Log, Trace Và Metric

| Signal | Trả lời câu hỏi | Ví dụ |
|---|---|---|
| Log | Sự kiện gì đã xảy ra? | validator fail, provider timeout |
| Trace | Một request đi qua các stage nào? | retrieve -> rerank -> generate |
| Metric | Xu hướng toàn hệ thống ra sao? | p95 latency, error rate, cost/request |

`trace_id` nối UI với backend evidence. Metric dùng để phát hiện xu hướng; trace dùng
để điều tra một request; log lưu event có schema ổn định. Không thay một signal bằng
signal khác.

## 1. UI Scope Cho Capstone

UI capstone nên chứng minh workflow production, không cần thành full enterprise portal.

Màn hình tối thiểu:

| View | Mục đích |
|---|---|
| Chat | User hỏi đáp với assistant |
| Citations | Xem source/page/section/chunk được dùng |
| Trace detail | Debug latency, token, cost, retrieval |
| Feedback | Thu thumbs up/down và reason |
| Eval summary | Xem metrics từ golden run |

Reviewer cần thấy:

- Câu hỏi đầu vào.
- Câu trả lời cuối cùng.
- Citation có thể đối chiếu.
- Trace ID để debug.
- Latency từng stage.
- Token/cost estimate.
- Kết quả eval gắn với version.
- No-answer/refusal behavior.

Không cần:

- Landing page marketing.
- Auth enterprise đầy đủ.
- UI quá nhiều animation.
- Dashboard realtime phức tạp.

## 2. Chat UI Contract

Request:

```json
{
  "question": "Nhân viên được nghỉ phép năm bao nhiêu ngày?",
  "tenant_id": "demo",
  "user_id": "reviewer",
  "roles": ["employee"],
  "conversation_id": "demo-session-001"
}
```

Response:

```json
{
  "answer": "Nhân viên full-time được nghỉ 12 ngày phép năm theo chính sách HR. [S1]",
  "citations": [
    {
      "source_id": "S1",
      "doc_id": "hr_policy_001",
      "title": "Chính sách nhân sự",
      "page": 4,
      "section": "Nghỉ phép năm",
      "chunk_id": "hr_policy_001:v1:0007",
      "document_version": "v3",
      "score": 0.87
    }
  ],
  "trace_id": "trace_20260510_001",
  "latency_ms": {
    "retrieve": 52,
    "rerank": 176,
    "generate": 1240,
    "total": 1530
  },
  "usage": {
    "input_tokens": 1180,
    "output_tokens": 96,
    "estimated_cost_usd": 0.0021
  },
  "policy_action": "allow",
  "needs_escalation": false
}
```

UI nên hiển thị:

- Answer ở khu vực chính.
- Citation cards bên dưới hoặc bên phải.
- Trace ID nhỏ nhưng copy được.
- Latency total và stage breakdown.
- Token/cost estimate.
- Warning nếu answer là fallback/no-answer.
- Feedback controls sau mỗi answer.
- Error state khi index chưa ready, provider timeout hoặc citation invalid.

## 3. Citation Experience

Citation không phải trang trí. Nó là guardrail chống hallucination và là cơ chế tạo trust.

Mỗi citation nên có:

| Field | Lý do |
|---|---|
| `source_id` | Map với marker `[S1]` trong answer |
| `doc_id` | Đối chiếu document |
| `title` | User đọc được |
| `page` | Tìm lại trong PDF |
| `section` | Hiểu ngữ cảnh |
| `chunk_id` | Debug retrieval/eval |
| `score` | Debug ranking |
| `document_version` | Audit stale docs |

UI behavior gợi ý:

- Click citation để mở source excerpt.
- Highlight exact chunk text nếu có.
- Nếu citation invalid, UI hiển thị warning thay vì im lặng.
- Nếu no-answer, không hiển thị citation giả.
- Nếu document có version mới, hiển thị `document_version`.

## 4. Feedback Loop

Endpoint:

```text
POST /feedback
```

Payload:

```json
{
  "trace_id": "trace_20260510_001",
  "conversation_id": "demo-session-001",
  "rating": "down",
  "reason": "wrong_source",
  "comment": "Câu trả lời đúng nhưng citation không phải policy mới nhất."
}
```

Reason categories:

- `helpful`.
- `wrong_answer`.
- `wrong_source`.
- `missing_citation`.
- `incomplete`.
- `too_slow`.
- `no_answer_wrong`.
- `policy_violation`.

Feedback phải gắn với `trace_id`. Nếu chỉ lưu thumbs down mà không có trace, bạn không biết fail do retrieval, reranker, prompt hay LLM.

Feedback endpoint nên có idempotency hoặc unique constraint theo
`trace_id + reviewer/session`, tránh double click tạo nhiều event. Comment phải qua
redaction và retention policy giống log.

## 5. Monitoring Metrics

Metrics tối thiểu:

| Nhóm | Metric | Ý nghĩa |
|---|---|---|
| Latency | p50/p95 total latency | UX và capacity |
| Latency | retrieve/rerank/generate latency | Biết chậm ở đâu |
| Cost | input/output tokens | Kiểm soát token budget |
| Cost | cost/request | Ước tính vận hành |
| Retrieval | empty retrieval rate | Indexing/query issue |
| Retrieval | top_k/rerank_top_k/context_top_k | Debug config |
| Citation | validity và correctness | Phân biệt ID hợp lệ với semantic support |
| Quality | thumbs down rate | User signal |
| Reliability | timeout/error rate | Production health |
| Security | ACL denial/leak count | Data protection |
| Guardrails | refusal/schema/PII rate | Safety monitoring |

Structured log mẫu:

```json
{
  "timestamp": "2026-05-10T10:30:00Z",
  "trace_id": "trace_20260510_001",
  "tenant_id": "demo",
  "user_id_hash": "sha256:...",
  "question_hash": "sha256:...",
  "model": "llm-default",
  "embedding_model": "embedding-v1",
  "prompt_version": "rag_prompt_v3",
  "index_version": "enterprise_docs_v1",
  "retrieval": {
    "bm25_top_k": 50,
    "vector_top_k": 50,
    "rerank_top_k": 20,
    "context_top_k": 6,
    "empty": false
  },
  "latency_ms": {
    "retrieve": 52,
    "rerank": 176,
    "generate": 1240,
    "total": 1530
  },
  "usage": {
    "input_tokens": 1180,
    "output_tokens": 96,
    "estimated_cost_usd": 0.0021
  },
  "citation": {
    "count": 1,
    "valid": true
  },
  "status": "success"
}
```

Không log raw question nếu có PII. Dùng hash hoặc redacted text.

Với hệ thống metrics kiểu Prometheus:

- Dùng base unit như seconds, không đặt tên metric histogram bằng milliseconds.
- Counter tích lũy nên có suffix `_total`.
- Không dùng `user_id`, email, `trace_id` hoặc giá trị không giới hạn làm label.
- `tenant_id` chỉ nên ở trace/log có access control; nếu cần metric, dùng segment hữu
  hạn như `tenant_tier`.

## 6. Dashboard Hoặc Report?

Với capstone, bạn có thể chọn report tĩnh thay vì dashboard phức tạp.

| Option | Ưu điểm | Trade-off | Khi dùng |
|---|---|---|---|
| Markdown report | Nhanh, dễ review trên GitHub | Không realtime | Portfolio |
| JSON/CSV report | Dễ parse và chart | Ít thân thiện | CI artifact |
| Streamlit/Next.js dashboard | Demo tốt | Tốn thời gian UI | Nếu đã có backend ổn |
| Grafana/Prometheus | Production-like | Setup nặng | Khi học observability sâu |

Best solution cho Day 49:

- UI chat tối giản.
- Trace panel trong UI hoặc JSON report.
- `evaluation_report.md` commit vào repo.
- Metrics summary có chart/table đủ đọc.

## 7. Evaluation Report

Report cần trả lời:

- Eval chạy trên version nào?
- Có bao nhiêu cases?
- Metrics hiện tại so với threshold thế nào?
- Mỗi metric áp dụng cho bao nhiêu case?
- Failures chính thuộc layer nào?
- Release decision là gì?
- Limitations là gì?

Release decision:

| Decision | Khi nào |
|---|---|
| `PASS` | Đạt threshold, không có critical failure |
| `CONDITIONAL PASS` | Có issue nhỏ, có mitigation/canary |
| `FAIL` | ACL/security/citation/format critical fail hoặc quality dưới ngưỡng |

Template ngắn:

```markdown
# Evaluation Report

Date:
Git SHA:
Eval set version:
Prompt version:
Index version:
Model:

## Summary

| Metric | Current | Threshold | Status |
|---|---:|---:|---|

## Failures By Layer

| Layer | Cases | Example | Fix |
|---|---:|---|---|

## Release Decision

Decision:
Reason:
Mitigation:
```

## 8. UI Implementation Notes

Pseudo state model:

```typescript
type Citation = {
  source_id: string;
  doc_id: string;
  title?: string;
  page?: number;
  section?: string;
  chunk_id: string;
  document_version?: string;
  score?: number;
};

type QueryResponse = {
  answer: string;
  citations: Citation[];
  trace_id: string;
  latency_ms: Record<string, number>;
  usage: {
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number;
  };
  policy_action: "allow" | "refuse" | "escalate";
  needs_escalation: boolean;
};
```

Fetch wrapper:

```typescript
async function askQuestion(question: string): Promise<QueryResponse> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        question,
        tenant_id: "demo",
        user_id: "reviewer",
        roles: ["employee"],
        conversation_id: "demo-session-001"
      })
    });

    if (!response.ok) {
      const traceId = response.headers.get("x-trace-id");
      throw new Error(`Query failed: ${response.status}; trace=${traceId ?? "n/a"}`);
    }
    return await response.json() as QueryResponse;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
```

Type assertion `as QueryResponse` không validate JSON ở runtime. Bản production nên
generate client/type từ OpenAPI và validate response ở trust boundary; tối thiểu hãy
test contract giữa UI và API. Abort ở client cũng không thay timeout/cancellation ở
backend.

UX states cần có:

- Empty state.
- Loading state.
- Success with citations.
- No-answer/refusal.
- Error with trace ID nếu có.
- Feedback submitted.

## 9. Performance Và Product Trade-Off

| Quyết định | Lợi ích | Trade-off |
|---|---|---|
| Hiển thị full trace cho reviewer | Debug tốt | Có thể lộ internal info |
| Ẩn raw prompt/output | An toàn | Debug khó hơn |
| Feedback reason bắt buộc | Data tốt | Friction cao |
| Cost hiển thị per request | Minh bạch | Có thể gây nhiễu với end user |
| Eval chart trong UI | Demo tốt | Tốn thời gian |
| Markdown report | Nhanh | Không realtime |

Best solution:

- Portfolio UI: hiển thị answer/citations/trace/latency/cost ở mức reviewer.
- Production UI: ẩn internal trace khỏi end user, chỉ admin/debug role xem.
- Monitoring dashboard: dùng redacted logs và aggregate metrics.

## 10. Dùng Được Trong Production Không?

Có, nếu UI chỉ là bề mặt trên một backend đã có guardrails, auth, logging và monitoring đúng.

Điều kiện tối thiểu:

- UI không hiển thị dữ liệu ngoài quyền user.
- Citation/source excerpt cũng phải enforce ACL.
- Feedback có trace ID và không lưu PII raw.
- Trace detail chỉ cho admin/support role.
- Monitoring có alert cho error, latency, cost, citation failure, empty retrieval và thumbs down.
- Evaluation report được tạo định kỳ và trước release.
- Có release decision và rollback plan.

Không nên claim production-ready nếu:

- UI chỉ hiển thị answer mà không có citation.
- Không có trace ID.
- Không có feedback loop.
- Không có eval report.
- Monitoring chỉ là log raw không redact.
- Citation panel có thể leak source user không được quyền xem.

## Checklist Cuối Bài

- [ ] UI gọi được `/query`.
- [ ] Hiển thị answer, citations, trace ID, latency và cost.
- [ ] Có feedback thumbs up/down gắn trace.
- [ ] Có structured logs đã redact.
- [ ] Có metrics summary.
- [ ] Metric labels không chứa user/trace/high-cardinality value.
- [ ] Có golden eval run mới nhất.
- [ ] Có `evaluation_report.md`.
- [ ] Có release decision.

## Quiz Tự Kiểm Tra

1. Metric và trace khác nhau ở mục đích nào?
2. Tại sao không dùng `trace_id` làm Prometheus label?
3. UI nhận HTTP 200 có đủ để tin response đúng schema không?
4. Citation ID hợp lệ có chứng minh answer đúng không?
5. Khi report không có case prompt injection, block rate nên là gì?

Đáp án: (1) aggregate trend và request-level investigation; (2) cardinality không
giới hạn; (3) chưa, cần runtime/contract validation; (4) chưa; (5) `N/A` và CI fail
nếu metric đó là gate bắt buộc.

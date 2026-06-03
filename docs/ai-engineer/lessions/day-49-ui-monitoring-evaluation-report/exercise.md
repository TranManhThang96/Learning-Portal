# Day 49 Exercise: Hoàn Thiện UI, Monitoring Và Eval Report

## Mục Tiêu

Bạn sẽ tạo UI demo và report chứng minh capstone có thể review:

- Chat UI gọi backend.
- Citation panel.
- Trace/usage panel.
- Feedback form.
- Monitoring summary.
- `evaluation_report.md`.

## Bài Tập 1: Chat UI Minimum

Tạo màn hình chat với các state:

- Empty.
- Loading.
- Success.
- No-answer/refusal.
- Error.

Response phải render:

- `answer`.
- `citations`.
- `trace_id`.
- `latency_ms.total`.
- `usage.estimated_cost_usd`.

Acceptance criteria:

- Submit câu hỏi tiếng Việt được.
- Disable submit khi loading.
- Error không làm mất câu hỏi cũ.
- Trace ID copy được.

## Bài Tập 2: Citation Panel

Mỗi citation card hiển thị:

- `source_id`.
- `title` hoặc `doc_id`.
- `page`.
- `section`.
- `chunk_id`.
- `score` nếu có.

Nếu API trả `source_excerpt`, hiển thị excerpt nhưng không quá dài. Nếu không có excerpt, vẫn hiển thị metadata.

## Bài Tập 3: Feedback Form

Payload:

```json
{
  "trace_id": "trace_20260510_001",
  "conversation_id": "demo-session-001",
  "rating": "down",
  "reason": "wrong_source",
  "comment": "Citation trỏ nhầm tài liệu."
}
```

Acceptance criteria:

- Không cho gửi feedback nếu thiếu `trace_id`.
- `down` bắt buộc chọn reason.
- Comment giới hạn độ dài.
- Sau khi submit, UI hiển thị trạng thái đã ghi nhận.

## Bài Tập 4: Trace Summary

Tạo panel:

| Field | UI |
|---|---|
| `trace_id` | Copyable text |
| `latency_ms.retrieve` | Stage row |
| `latency_ms.rerank` | Stage row |
| `latency_ms.generate` | Stage row |
| `latency_ms.total` | Highlight |
| `usage.input_tokens` | Number |
| `usage.output_tokens` | Number |
| `usage.estimated_cost_usd` | Currency |

Không hiển thị system prompt hoặc raw context cho end user.

## Bài Tập 5: Monitoring Summary

Tạo `monitoring_summary.md` hoặc dashboard page với:

```markdown
# Monitoring Summary

Period:
Request count:
p50 latency:
p95 latency:
Average cost/request:
Empty retrieval rate:
Citation failure rate:
Schema failure rate:
Thumbs down rate:
Top failure reasons:
```

Nếu chưa có real traffic, dùng eval run + demo traces và ghi rõ là sample.

## Bài Tập 6: Evaluation Report

Tạo `evaluation_report.md` theo template trong `document.md`.

Bắt buộc có:

- Date.
- Git SHA hoặc local version.
- Eval set version.
- Prompt version.
- Index version.
- Metrics table.
- Results by tag.
- Top failures.
- Release decision.
- Limitations.
- Next actions.

## Bài Tập 7: Release Decision

Chọn một trong ba:

- `PASS`.
- `CONDITIONAL PASS`.
- `FAIL`.

Viết lý do theo evidence, không viết cảm tính.

Ví dụ:

```markdown
Decision: CONDITIONAL PASS

Reason:
- Recall@5 đạt 0.86, vượt threshold 0.80.
- Citation correctness đạt 0.96, vượt threshold 0.95.
- Tag `multi-hop` chỉ đạt 0.70, thấp hơn kỳ vọng.

Mitigation:
- Canary chỉ dùng cho HR FAQ.
- Không bật cho legal/finance.
- Cải thiện chunking cho multi-hop trước release tiếp theo.
```

## Checklist Nộp Bài

- [ ] UI hỏi đáp chạy được.
- [ ] Citation panel hiển thị source metadata.
- [ ] Trace/usage panel hiển thị latency/token/cost.
- [ ] Feedback gắn với trace ID.
- [ ] Có monitoring summary.
- [ ] Có evaluation report.
- [ ] Có release decision dựa trên metrics.
- [ ] Có ghi rõ limitations.

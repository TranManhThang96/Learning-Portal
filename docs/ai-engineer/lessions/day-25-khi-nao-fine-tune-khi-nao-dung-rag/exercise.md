# Day 25 Exercise: Decision Records Cho Prompt, RAG, Tool Và Fine-tuning

## Mục Tiêu Thực Hành

Sau bài này, bạn cần tạo được 5 decision records gần production. Mỗi record phải trả lời:

- Vấn đề thật sự là facts, realtime state, action, format, tone, workflow, cost hay latency?
- Dùng prompt, RAG, tool calling, fine-tuning, distillation hay hybrid?
- Vì sao không chọn các option còn lại?
- Metric nào chứng minh decision đúng?
- Dùng được trong production không? Nếu có thì cần điều kiện gì?

## Chuẩn Bị

Tạo một file riêng để làm bài, ví dụ:

```bash
mkdir -p notes/day-25
touch notes/day-25/decision-records.md
```

Không cần API key. Bài này tập trung vào architecture decision và production checklist.

## Template Bắt Buộc

Copy template này cho mỗi use case:

```markdown
# Decision Record: <Tên use case>

## 1. Context

- Users:
- Workflow:
- Input:
- Output:
- Data sensitivity:
- Expected traffic:
- p95 latency target:
- Cost/request target:

## 2. Failure Mode Hiện Tại

- Facts sai:
- Không có citation:
- Cần realtime state/action:
- Format sai:
- Tone/style sai:
- Workflow sai:
- Latency/cost cao:
- Privacy/security risk:

## 3. Options

| Option | Quality | Cost | Latency | Ops complexity | Privacy risk | Rollback | Nhận xét |
|---|---:|---:|---:|---:|---:|---:|---|
| Prompt-only | | | | | | | |
| RAG | | | | | | | |
| Tool calling | | | | | | | |
| Fine-tune/PEFT | | | | | | | |
| Distillation | | | | | | | |
| Hybrid | | | | | | | |

## 4. Decision

- Chọn:
- Không chọn:
- Lý do:
- Trade-off chấp nhận:
- Điều kiện revisit:

## 5. Production Plan

- Data/index/tool cần chuẩn bị:
- Eval set:
- Metrics:
- Rollout:
- Rollback:
- Observability:

## 6. Dùng được trong production không? Nếu có thì cần điều kiện gì?

Trả lời cụ thể theo use case.
```

## Exercise 1: Chatbot Hỏi Đáp Policy Nội Bộ

Scenario:

```text
Công ty có 2.000 trang policy HR, security và finance. Policy thay đổi mỗi tuần.
User muốn hỏi bằng tiếng Việt, câu trả lời phải có citation. Một số tài liệu chỉ dành cho manager.
```

Yêu cầu:

- Chọn giữa prompt-only, RAG, fine-tune hoặc hybrid.
- Nêu cách enforce ACL.
- Đề xuất metric retrieval và citation.
- Trả lời vì sao không fine-tune policy vào model.

Gợi ý solution mong đợi:

- RAG là core.
- Fine-tune chỉ xét sau nếu tone/refusal/workflow lỗi dù context đúng.
- Permission phải filter trước context builder.

## Exercise 2: Support Assistant Tạo Ticket

Scenario:

```text
Assistant nhận complaint của khách, kiểm tra order/account, đọc refund policy,
trả lời khách và tạo ticket nếu cần. Ticket system yêu cầu JSON đúng schema.
```

Yêu cầu:

- Thiết kế flow có RAG, tool calling và structured output.
- Nêu side effect nào cần confirmation hoặc idempotency.
- Nêu khi nào nên fine-tune bằng resolved tickets.
- Đề xuất rollback nếu adapter mới làm tăng escalation sai.

Gợi ý output contract:

```json
{
  "customer_reply": "string",
  "ticket": {
    "category": "billing|delivery|account|other",
    "priority": "low|medium|high",
    "summary": "string"
  },
  "needs_human": true,
  "sources": ["policy://refund#section-2"]
}
```

## Exercise 3: Extract Invoice Thành JSON

Scenario:

```text
Hệ thống nhận invoice PDF đã OCR thành text. Cần extract vendor, invoice_number,
date, line_items, tax, total. Traffic 200.000 invoice/ngày.
```

Yêu cầu:

- Chọn baseline.
- Nêu metric field-level.
- Khi nào distillation/fine-tune model nhỏ đáng làm?
- Nêu data privacy checklist.

Gợi ý:

- Không cần RAG nếu toàn bộ thông tin nằm trong invoice.
- Structured output + validator là baseline.
- Distillation/fine-tune đáng cân nhắc vì traffic cao và task hẹp.

## Exercise 4: Code Review Assistant Theo Style Team

Scenario:

```text
Team muốn assistant review PR theo coding standard nội bộ,
comment ngắn, severity rõ, không tạo noise. Có lịch sử 30.000 review comments.
```

Yêu cầu:

- Tách phần nào nên là RAG, phần nào có thể fine-tune.
- Có cần tool không? Nếu có, tool nào?
- Nêu risk khi dùng lịch sử code review làm training data.
- Đề xuất eval chống false positive.

Gợi ý:

- Coding standard nên là RAG vì thay đổi.
- Review style/severity mapping có thể LoRA nếu dataset sạch.
- Tool có thể gồm static analysis, test result, code ownership.

## Exercise 5: Product FAQ Với Giá Và Tồn Kho Realtime

Scenario:

```text
E-commerce assistant trả lời câu hỏi sản phẩm. Mô tả sản phẩm thay đổi theo catalog.
Giá và tồn kho thay đổi từng phút. Không được trả lời sai giá.
```

Yêu cầu:

- Chọn RAG, tool hoặc fine-tune cho từng loại data.
- Thiết kế freshness guarantee.
- Nêu latency budget.
- Trả lời khi nào fine-tune có thể vẫn hữu ích.

Gợi ý:

- Product docs/catalog: RAG hoặc search.
- Price/inventory: tool.
- Fine-tune chỉ cho tone/sales behavior, không cho facts realtime.

## Exercise 6: Cost Và Latency Calculation

Với một assistant có số liệu:

```text
100.000 requests/day
Prompt-only:
- avg input 2.000 tokens
- avg output 300 tokens
- p95 latency 2.2s

RAG:
- retrieval + rerank p95 500ms
- avg context thêm 1.200 tokens
- p95 latency 3.0s

Fine-tuned small model:
- avg input giảm còn 900 tokens
- avg output 220 tokens
- p95 latency 1.4s
- cần 2 tuần data cleaning/training/eval
```

Yêu cầu:

- Nêu option nào nên ship trước nếu deadline là 1 tuần.
- Nêu option nào đáng thử nếu traffic tăng lên 1 triệu requests/day.
- Nêu metric cần đo trước khi kết luận fine-tune rẻ hơn.

## Rubric Tự Chấm

Bạn đạt yêu cầu nếu mỗi decision record có:

- [ ] Xác định đúng source of truth.
- [ ] Không dùng fine-tune để lưu facts realtime hoặc private docs thay đổi thường xuyên.
- [ ] Có RAG khi cần citation/knowledge external.
- [ ] Có tool calling khi cần realtime state/action.
- [ ] Có structured output/validator khi downstream cần parse.
- [ ] Có fine-tune/LoRA/QLoRA/distillation chỉ khi có failure mode và metric rõ.
- [ ] Có privacy checklist cho training data.
- [ ] Có eval metrics cụ thể.
- [ ] Có rollback plan.
- [ ] Có cost/latency trade-off.
- [ ] Có mục "Dùng được trong production không? Nếu có thì cần điều kiện gì?".

## Đáp Án Tham Khảo Ngắn

| Use case | Decision chính | Fine-tune có nên dùng không? |
|---|---|---|
| Internal policy Q&A | RAG + ACL + citation | Có thể, chỉ cho tone/refusal nếu context đúng mà behavior sai |
| Support ticket | RAG + tool + structured output | Có, nếu resolved tickets sạch và triage/tone lỗi lặp lại |
| Invoice extraction | Structured output + validator | Có, nếu volume cao hoặc schema/field accuracy cần cải thiện |
| Code review | RAG standards + tools + optional LoRA | Có, cho style/severity nếu data sạch |
| Product FAQ realtime | RAG/search + price/inventory tools | Không cho facts; có thể cho sales tone |

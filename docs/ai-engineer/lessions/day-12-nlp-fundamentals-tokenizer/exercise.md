# Day 12 Exercise: Tokenizer Lab

## Mục tiêu thực hành

Sau bài tập này, bạn phải có một notebook hoặc script nhỏ trả lời được:

- Tokenizer nào tạo bao nhiêu token cho tiếng Việt có dấu, không dấu và code-mixed?
- p95 token count của sample domain của bạn là bao nhiêu?
- `max_length` nên đặt thế nào cho classifier hoặc RAG chunk?
- Request vượt token budget sẽ bị reject, truncate hay split?
- Cost ước lượng trên 1,000,000 requests là bao nhiêu?

## Chuẩn bị

Cài dependency:

```bash
pip install transformers tokenizers sentencepiece
```

Tạo file script hoặc notebook trong môi trường học của bạn. Nếu tạo script minh họa trong repo này, đặt trong folder:

```text
lessions/day-12-nlp-fundamentals-tokenizer/
```

Không cần train model ở Day 12. Mục tiêu là hiểu và kiểm soát tokenizer.

## Bài 1: So sánh tokenizer

Dùng các model/tokenizer sau:

- `bert-base-multilingual-cased`: WordPiece, BERT-style.
- `gpt2`: byte-level BPE, GPT-style cũ để quan sát hành vi byte/subword.
- `vinai/phobert-base`: Vietnamese RoBERTa/PhoBERT-style.

Input mẫu:

```python
texts = {
    "vi_with_diacritics": "Tôi đang học xử lý ngôn ngữ tự nhiên và tokenizer cho hệ thống RAG.",
    "vi_no_diacritics": "Toi dang hoc xu ly ngon ngu tu nhien va tokenizer cho he thong RAG.",
    "support_ticket": "Khách hàng báo lỗi thanh toán PAY_403 lúc 09:30, cần retry idempotent.",
    "markdown": "## Lỗi thanh toán\n- Mã lỗi: PAY_403\n- User nói: không thanh toán được.",
    "phobert_segmented": "Tôi đang_học xử_lý ngôn_ngữ tự_nhiên với PhoBERT.",
}
```

Yêu cầu:

1. In `tokens`, `input_ids`, `attention_mask` cho từng text.
2. In `len(input_ids)` trước padding.
3. Với fast tokenizer, in `offset_mapping` cho ít nhất một câu.
4. Ghi nhận tokenizer nào tách tiếng Việt thành nhiều token hơn.
5. Ghi nhận khác biệt giữa có dấu và không dấu.

Câu hỏi tự trả lời:

- Token preview của WordPiece khác byte-level BPE như thế nào?
- Có tokenizer nào không có `pad_token` không? Bạn xử lý ra sao?
- PhoBERT khác gì khi input đã word-segmented bằng `_`?

## Bài 2: Token stats cho domain thật

Tạo ít nhất 30 câu/ticket/document snippet tiếng Việt từ domain bạn quan tâm. Ví dụ:

- Support ticket.
- Log lỗi thanh toán.
- FAQ nội bộ.
- Mô tả sản phẩm.
- Đoạn hợp đồng.
- Comment user có tiếng Việt không dấu.

Yêu cầu:

1. Normalize text bằng helper trong `document.md`.
2. Đếm token bằng đúng tokenizer bạn định dùng.
3. Tính `min`, `mean`, `p50`, `p95`, `p99`, `max`.
4. In 5 sample dài nhất cùng token count, nhưng redact PII nếu có.
5. Đề xuất `max_length` cho classifier.

Gợi ý quyết định:

| Kết quả đo | Quyết định khả thi |
|---|---|
| p95 <= 128, max <= 256 | `max_length=256` thường ổn cho classifier |
| p95 <= 256, p99 cao | `max_length=256` + policy cho outlier |
| p95 > 512 | Cần split/summarize hoặc đổi task design |
| Có nhiều mã lỗi/SKU bị tách nhỏ | Cần test quality riêng cho nhóm token này |

## Bài 3: Token budget và cost

Giả sử hệ thống RAG có:

```text
context_window = 8192
reserved_output_tokens = 1000
system_prompt_tokens = 350
tool_schema_tokens = 500
chat_history_tokens = 1200
```

Yêu cầu:

1. Tính budget còn lại cho retrieved context.
2. Nếu mỗi chunk là 450 tokens, tính số chunk tối đa có thể nhét vào context.
3. Nếu input price là `0.15 USD / 1M tokens`, output price là `0.60 USD / 1M tokens`, ước lượng cost cho 1 request.
4. Ước lượng cost cho 1,000,000 requests/tháng với p95 input tokens của bạn.
5. Đề xuất hard limit theo tenant hoặc feature.

Công thức:

```text
available_context =
  context_window
  - reserved_output_tokens
  - system_prompt_tokens
  - tool_schema_tokens
  - chat_history_tokens

cost_usd =
  input_tokens / 1_000_000 * input_price
  + output_tokens / 1_000_000 * output_price
```

## Bài 4: Implement policy khi input quá dài

Dùng `TokenizerService` trong `document.md`, viết 3 test case:

1. Input ngắn hơn `max_length`: encode thành công.
2. Input vượt `max_length` với `truncation_policy="reject"`: raise `TokenBudgetError`.
3. Input vượt `max_length` với `truncation_policy="truncate"`: encode thành công nhưng có warning log.

Acceptance criteria:

- Không có silent truncation.
- Log có `model`, `max_length`, `too_long_count`, `max_seen`, `action`.
- Test không assert raw text trong log.
- Batch size 1 và batch size N đều chạy.

## Bài 5: Mini design review

Viết một đoạn design note ngắn cho use case của bạn:

```text
Use case:
Model/tokenizer:
Preprocessing:
max_length:
Reserved output tokens:
Truncation policy:
Fallback khi quá dài:
Metrics:
PII/logging policy:
Cost estimate:
```

Trả lời bắt buộc:

- Dùng được trong production không?
- Nếu có, cần điều kiện gì?
- Trade-off lớn nhất là gì?
- Bạn sẽ monitor metric nào đầu tiên sau release?

## Quiz

1. Vì sao đổi tokenizer có thể làm hỏng model dù code inference không lỗi?
2. Vì sao tiếng Việt không nên chunk bằng số từ tách theo whitespace?
3. Khi nào `padding="max_length"` tốt hơn `padding="longest"`?
4. OOV/UNK rate cao báo hiệu vấn đề gì?
5. Vì sao `offset_mapping` cần thiết cho NER hoặc citation highlight?
6. Silent truncation có thể gây bug nghiệp vụ nào trong RAG?
7. Vì sao token count ảnh hưởng cả latency, memory và cost?

## Kết quả mong đợi

Bạn hoàn thành Day 12 khi có:

- Bảng so sánh token count của BERT, GPT-style và PhoBERT trên text tiếng Việt.
- Thống kê p50/p95/p99 token count cho sample domain.
- Một quyết định `max_length` có lý do.
- Một policy rõ cho input quá dài.
- Một ước lượng cost/request và cost/tháng.
- Một câu trả lời production readiness cụ thể, không chung chung.

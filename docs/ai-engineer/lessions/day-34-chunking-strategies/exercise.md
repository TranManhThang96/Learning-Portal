# Bài tập: Test 3 chunking strategies trên cùng document

## Mục tiêu

Bạn sẽ dùng corpus [acme-refund-policy-v4.md](./acme-refund-policy-v4.md) để so sánh fixed-size, recursive và markdown-aware chunking. `document.md` chỉ là reference về metadata, ground truth và expected observations. Kết quả cần trả lời được:

- Strategy nào retrieve đúng evidence nhất?
- Strategy nào citation rõ nhất?
- Strategy nào tốn nhiều chunk/token nhất?
- Strategy nào phù hợp production cho document dạng markdown policy?

## Yêu cầu đầu ra

Tạo một script hoặc notebook có các phần:

1. Load corpus từ `acme-refund-policy-v4.md`.
2. Tạo chunk bằng 3 strategy:
   - Fixed-size.
   - Recursive.
   - Markdown-aware.
3. In thống kê:
   - Số chunk.
   - Min/avg/max token count.
   - Top heading path nếu có.
   - Duplicate hoặc near-duplicate đơn giản.
4. Chạy 6 ground-truth queries.
5. Với mỗi query, in top 3 chunks gồm:
   - score,
   - chunk_id,
   - strategy,
   - heading_path,
   - token_count,
   - snippet.
6. Chấm điểm thủ công hoặc bán tự động:
   - expected evidence có xuất hiện không,
   - citation section có đúng không,
   - answer có nguy cơ thiếu context không.

## Setup gợi ý

Không bắt buộc dùng framework. Bạn có thể tạo file `day34_chunk_eval.py` trong scratch/local của bạn. Nếu muốn dùng code trong bài học, copy các hàm từ [lession.md](./lession.md) phần "Code gần production".

Với production hoặc portfolio, nên thay phần `simple_embed` bằng một trong các lựa chọn:

- Local embedding model qua sentence-transformers.
- OpenAI-compatible embedding API.
- Vector DB thật như pgvector hoặc Qdrant.

Trong bài tập này, mục tiêu chính là hiểu trade-off chunking, không phải benchmark embedding model.

## Step-by-step

### Bước 1: Chuẩn bị document

Load fixture trực tiếp để bài tập không phụ thuộc vào việc parse Markdown của file reference:

```python
from pathlib import Path


FIXTURE_PATH = Path(__file__).with_name("acme-refund-policy-v4.md")
POLICY_DOC = FIXTURE_PATH.read_text(encoding="utf-8")
```

Nếu chạy notebook ở thư mục khác, truyền path fixture qua config/CLI thay vì hardcode working directory.

Checklist:

- Giữ nguyên markdown heading.
- Giữ nguyên table.
- Giữ nguyên code block Python.
- Không bỏ dấu tiếng Việt.

### Bước 2: Chạy 3 strategy

Tham số khởi đầu:

| Strategy | Tham số |
|---|---|
| Fixed-size | `max_tokens=120`, `overlap_tokens=25` |
| Recursive | `max_tokens=180`, `overlap_sentences=1` |
| Markdown-aware | `max_tokens=220` |

Kỳ vọng:

- Fixed-size tạo nhiều chunk hơn và có thể cắt ngang section.
- Recursive tạo chunk theo paragraph tốt hơn.
- Markdown-aware giữ `heading_path`, hữu ích cho citation.

### Bước 3: Chạy query set

Query set:

```python
QUERIES = [
    {
        "id": "Q1",
        "query": "Gói Pro được gọi bao nhiêu request mỗi phút?",
        "expected_terms": ["Pro", "600"],
        "expected_heading": "Bảng giới hạn request",
    },
    {
        "id": "Q2",
        "query": "Khách hàng sau 30 ngày có được hoàn tiền không?",
        "expected_terms": ["Sau 30 ngày", "không hoàn tiền"],
        "expected_heading": "Cửa sổ hoàn tiền",
    },
    {
        "id": "Q3",
        "query": "Khi nào support phải chuyển manual review?",
        "expected_terms": ["incident id", "manual review"],
        "expected_heading": "Exception do lỗi hệ thống",
    },
    {
        "id": "Q4",
        "query": "Điều kiện usage để được hoàn tiền tự động là gì?",
        "expected_terms": ["20% quota", "tháng đầu tiên"],
        "expected_heading": "Cửa sổ hoàn tiền",
    },
    {
        "id": "Q5",
        "query": "Client nên xử lý HTTP 429 như thế nào?",
        "expected_terms": ["Retry-After", "exponential backoff", "jitter"],
        "expected_heading": "Bảng giới hạn request",
    },
    {
        "id": "Q6",
        "query": "Khách hàng mua qua reseller có được áp dụng chính sách này không?",
        "expected_terms": ["không áp dụng", "reseller"],
        "expected_heading": "Phạm vi áp dụng",
    },
]
```

### Bước 4: Ghi bảng kết quả

Mẫu bảng:

| Query | Strategy | Rank đúng đầu tiên | Evidence đúng? | Citation đúng? | Ghi chú |
|---|---|---:|---|---|---|
| Q1 | fixed | 2 | Có | Không chắc | Header table nằm chunk trước |
| Q1 | recursive | 1 | Có | Trung bình | Có bảng nhưng thiếu heading path |
| Q1 | markdown | 1 | Có | Có | Heading path rõ |

### Bước 5: Phân tích trade-off

Trả lời các câu hỏi:

1. Strategy nào tạo nhiều chunk nhất? Vì sao?
2. Strategy nào dễ cite nhất? Vì sao?
3. Query nào bị retrieval sai hoặc thiếu evidence?
4. Nếu dùng vector DB thật, strategy nào có chi phí index cao nhất?
5. Nếu document là PDF scan, kết quả sẽ thay đổi ở đâu?
6. Nếu document chứa ACL theo section, metadata cần thêm gì?

## Rubric tự chấm

| Tiêu chí | Điểm |
|---|---:|
| Có đủ 3 strategy | 2 |
| Có metadata chunk id, strategy, heading/source | 2 |
| Có thống kê chunk/token | 1 |
| Có chạy đủ 6 query | 2 |
| Có bảng so sánh retrieval result | 2 |
| Có kết luận production readiness | 1 |

Tổng: 10 điểm.

## Kết luận mong đợi

Với document markdown policy này, markdown-aware chunking thường là best solution vì giữ được heading path, table context và citation section. Recursive là baseline tốt và dễ dùng nếu parser markdown chưa sẵn sàng. Fixed-size chỉ nên dùng để prototype hoặc fallback vì dễ cắt ngang table/section.

Production answer:

Có thể dùng trong production nếu chunker được version hóa, metadata đủ để cite và audit, có eval query set trước mỗi lần thay đổi, có dedupe overlap, và có monitoring cho retrieval quality. Với policy document, không nên dùng fixed-size thuần làm strategy cuối cùng nếu citation và compliance quan trọng.

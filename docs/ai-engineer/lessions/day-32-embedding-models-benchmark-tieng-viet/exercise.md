# Exercise: Benchmark 3 embedding models trên 20 câu hỏi tiếng Việt

## Mục tiêu

Bạn sẽ viết một benchmark nhỏ nhưng có cấu trúc gần production:

- Có corpus tiếng Việt.
- Có 20 queries.
- Có qrels.
- Có adapter cho nhiều embedding models.
- Có validation dữ liệu trước khi chạy.
- Có Hit@1, Hit@3, Recall@5, MRR@5.
- Có latency p50/p95.
- Có storage estimate.
- Có report và failure analysis.

## 1. Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install "pydantic>=2" sentence-transformers numpy pandas tabulate
```

Nếu máy yếu, bắt đầu với model nhỏ hơn. Nếu có GPU, cài PyTorch đúng CUDA theo môi trường của bạn trước.

## 2. Chọn 3 models

Gợi ý cho bài học:

```python
MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-base",
    "BAAI/bge-m3",
]
```

Nếu muốn thử Vietnamese-specific model, thay một model bằng model Vietnamese bi-encoder bạn tin cậy. Nếu muốn thử managed API như OpenAI hoặc Cohere, giữ cùng interface nhưng không hardcode API key trong script.

## 3. Script benchmark

Tạo file tạm, ví dụ `benchmark_embeddings_day32.py`, rồi dùng nội dung sau.

```python
from __future__ import annotations

import argparse
import json
import math
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator
from sentence_transformers import SentenceTransformer


TOP_K = 5


class DocumentChunk(BaseModel):
    id: str
    title: str
    text: str
    category: str

    @field_validator("id", "title", "text", "category")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class QueryCase(BaseModel):
    id: str
    query: str
    category: str
    difficulty: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str]

    @field_validator("id", "query", "category")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("relevant_chunk_ids")
    @classmethod
    def has_relevance(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("query must have at least one relevant chunk")
        return value


DOCS = [
    {"id": "refund_policy", "title": "Chính sách hoàn tiền", "category": "billing", "text": "Khách hàng có thể yêu cầu hoàn tiền trong 7 ngày sau khi mua gói Pro nếu chưa sử dụng quá 20% quota. Yêu cầu hoàn tiền được xử lý qua cổng thanh toán trong 5 đến 10 ngày làm việc."},
    {"id": "invoice_vat", "title": "Xuất hóa đơn VAT", "category": "billing", "text": "Để xuất hóa đơn VAT, khách hàng cần cung cấp tên công ty, mã số thuế, địa chỉ đăng ký kinh doanh và email nhận hóa đơn. Thông tin phải được gửi trong vòng 30 ngày kể từ ngày thanh toán."},
    {"id": "sla_enterprise", "title": "SLA Enterprise", "category": "support", "text": "Gói Enterprise có SLA uptime 99.9% theo tháng. Sự cố P1 được phản hồi trong 2 giờ làm việc và được ưu tiên xử lý bởi nhóm hỗ trợ kỹ thuật."},
    {"id": "password_reset", "title": "Reset mật khẩu", "category": "security", "text": "Người dùng có thể reset mật khẩu bằng email đã đăng ký. Link reset hết hạn sau 30 phút và chỉ dùng được một lần."},
    {"id": "security_2fa", "title": "Xác thực hai lớp", "category": "security", "text": "Tài khoản admin bắt buộc bật xác thực hai lớp 2FA bằng ứng dụng authenticator. Recovery code phải được lưu ở nơi an toàn."},
    {"id": "api_rate_limit", "title": "Rate limit API", "category": "api", "text": "API public giới hạn 600 request mỗi phút cho mỗi API key. Khi vượt giới hạn, hệ thống trả về HTTP 429 kèm header Retry-After."},
    {"id": "sso_saml", "title": "SSO SAML", "category": "security", "text": "Khách hàng Enterprise có thể cấu hình SSO qua SAML 2.0. Metadata XML từ Identity Provider cần được upload trong trang quản trị."},
    {"id": "data_retention", "title": "Lưu trữ dữ liệu", "category": "privacy", "text": "Dữ liệu log ứng dụng được lưu trong 90 ngày. Bản sao lưu cơ sở dữ liệu được mã hóa và giữ trong 30 ngày trước khi xóa tự động."},
    {"id": "delete_account", "title": "Xóa tài khoản", "category": "privacy", "text": "Người dùng có thể yêu cầu xóa tài khoản và dữ liệu cá nhân. Quy trình xóa hoàn tất trong tối đa 15 ngày làm việc sau khi xác minh danh tính."},
    {"id": "webhook_retry", "title": "Retry webhook", "category": "api", "text": "Webhook thất bại sẽ được retry tối đa 5 lần với exponential backoff. Endpoint nhận webhook phải trả về HTTP 2xx trong 10 giây."},
    {"id": "pricing_seat", "title": "Tính phí theo seat", "category": "billing", "text": "Gói Team tính phí theo số lượng active seat trong chu kỳ thanh toán. Seat bị xóa giữa kỳ sẽ được prorate vào hóa đơn tiếp theo."},
    {"id": "trial_limit", "title": "Giới hạn dùng thử", "category": "billing", "text": "Tài khoản dùng thử có thời hạn 14 ngày và bị giới hạn 1.000 request API. Sau khi hết hạn trial, người dùng cần nâng cấp để tiếp tục sử dụng."},
    {"id": "audit_log", "title": "Audit log", "category": "security", "text": "Audit log ghi lại hành động đăng nhập, thay đổi quyền, tạo API key và cập nhật cấu hình bảo mật. Chỉ owner và admin được xem audit log."},
    {"id": "permission_roles", "title": "Vai trò và quyền", "category": "security", "text": "Hệ thống có ba vai trò mặc định: owner, admin và member. Owner có thể quản lý billing, admin quản lý cấu hình, member chỉ dùng tính năng được cấp quyền."},
    {"id": "model_region", "title": "Vùng xử lý model", "category": "privacy", "text": "Dữ liệu inference mặc định được xử lý tại vùng Singapore. Khách hàng Enterprise có thể yêu cầu cấu hình region riêng theo hợp đồng."},
    {"id": "file_upload_limit", "title": "Giới hạn upload", "category": "product", "text": "Mỗi file upload không được vượt quá 50 MB. Định dạng hỗ trợ gồm PDF, DOCX, TXT và CSV."},
    {"id": "ocr_quality", "title": "Chất lượng OCR", "category": "product", "text": "Tài liệu scan chất lượng thấp có thể làm OCR sai dấu tiếng Việt hoặc mất khoảng trắng. Nên kiểm tra preview trước khi đưa vào knowledge base."},
    {"id": "incident_status", "title": "Trang trạng thái sự cố", "category": "support", "text": "Khi có incident diện rộng, trạng thái hệ thống được cập nhật tại status page. Khách hàng có thể đăng ký email để nhận thông báo sự cố."},
    {"id": "api_key_rotation", "title": "Rotate API key", "category": "security", "text": "API key nên được rotate định kỳ 90 ngày một lần. Khi tạo key mới, hãy cập nhật ứng dụng trước khi thu hồi key cũ để tránh gián đoạn."},
    {"id": "export_data", "title": "Export dữ liệu", "category": "product", "text": "Người dùng có thể export dữ liệu dự án sang CSV hoặc JSON. File export được tạo bất đồng bộ và link tải xuống hết hạn sau 24 giờ."},
    {"id": "support_channels", "title": "Kênh hỗ trợ", "category": "support", "text": "Gói Free chỉ hỗ trợ qua community forum. Gói Pro hỗ trợ qua email, còn Enterprise có thêm Slack Connect và technical account manager."},
    {"id": "payment_failed", "title": "Thanh toán thất bại", "category": "billing", "text": "Nếu thanh toán thất bại, hệ thống sẽ thử lại trong 3 ngày liên tiếp. Sau 7 ngày chưa thanh toán, workspace bị chuyển sang trạng thái read-only."},
    {"id": "quota_overage", "title": "Vượt quota", "category": "billing", "text": "Khi vượt quota tháng, request mới có thể bị từ chối hoặc tính phí overage tùy cấu hình gói. Owner sẽ nhận email cảnh báo khi dùng quá 80% quota."},
    {"id": "ip_allowlist", "title": "IP allowlist", "category": "security", "text": "Enterprise admin có thể cấu hình IP allowlist để chỉ cho phép truy cập từ dải IP công ty. Thay đổi allowlist có hiệu lực sau vài phút."},
]


QUERIES = [
    {"id": "q001", "query": "tôi muốn hoàn tiền gói Pro", "category": "billing", "difficulty": ["synonym"], "relevant_chunk_ids": ["refund_policy"]},
    {"id": "q002", "query": "lam sao xuat hoa don VAT cho cong ty", "category": "billing", "difficulty": ["no-diacritic", "acronym"], "relevant_chunk_ids": ["invoice_vat"]},
    {"id": "q003", "query": "SLA của gói enterprise là bao nhiêu", "category": "support", "difficulty": ["acronym", "english-mix"], "relevant_chunk_ids": ["sla_enterprise"]},
    {"id": "q004", "query": "bật xác thực 2 lớp cho admin", "category": "security", "difficulty": ["synonym", "number"], "relevant_chunk_ids": ["security_2fa"]},
    {"id": "q005", "query": "API trả về 429 nghĩa là gì", "category": "api", "difficulty": ["exact-code"], "relevant_chunk_ids": ["api_rate_limit"]},
    {"id": "q006", "query": "quên mật khẩu thì reset như thế nào", "category": "security", "difficulty": ["english-mix"], "relevant_chunk_ids": ["password_reset"]},
    {"id": "q007", "query": "cau hinh SSO bang SAML 2.0", "category": "security", "difficulty": ["no-diacritic", "acronym"], "relevant_chunk_ids": ["sso_saml"]},
    {"id": "q008", "query": "log ứng dụng được giữ trong bao lâu", "category": "privacy", "difficulty": ["retention"], "relevant_chunk_ids": ["data_retention"]},
    {"id": "q009", "query": "xóa dữ liệu cá nhân mất mấy ngày", "category": "privacy", "difficulty": ["synonym"], "relevant_chunk_ids": ["delete_account"]},
    {"id": "q010", "query": "webhook fail co retry khong", "category": "api", "difficulty": ["no-diacritic", "english-mix"], "relevant_chunk_ids": ["webhook_retry"]},
    {"id": "q011", "query": "seat bị xóa giữa kỳ có được tính lại tiền không", "category": "billing", "difficulty": ["billing-term"], "relevant_chunk_ids": ["pricing_seat"]},
    {"id": "q012", "query": "trial được gọi bao nhiêu request API", "category": "billing", "difficulty": ["english-mix"], "relevant_chunk_ids": ["trial_limit"]},
    {"id": "q013", "query": "ai được xem audit log", "category": "security", "difficulty": ["english-mix"], "relevant_chunk_ids": ["audit_log"]},
    {"id": "q014", "query": "owner admin member khác nhau thế nào", "category": "security", "difficulty": ["role"], "relevant_chunk_ids": ["permission_roles"]},
    {"id": "q015", "query": "du lieu inference xu ly o region nao", "category": "privacy", "difficulty": ["no-diacritic", "english-mix"], "relevant_chunk_ids": ["model_region"]},
    {"id": "q016", "query": "upload file PDF tối đa bao nhiêu MB", "category": "product", "difficulty": ["exact-number"], "relevant_chunk_ids": ["file_upload_limit"]},
    {"id": "q017", "query": "OCR sai dấu tiếng Việt thì cần chú ý gì", "category": "product", "difficulty": ["ocr", "vietnamese"], "relevant_chunk_ids": ["ocr_quality"]},
    {"id": "q018", "query": "xem tình trạng incident ở đâu", "category": "support", "difficulty": ["english-mix", "synonym"], "relevant_chunk_ids": ["incident_status"]},
    {"id": "q019", "query": "bao lâu nên rotate API key", "category": "security", "difficulty": ["english-mix"], "relevant_chunk_ids": ["api_key_rotation"]},
    {"id": "q020", "query": "export dữ liệu sang csv json", "category": "product", "difficulty": ["acronym", "english-mix"], "relevant_chunk_ids": ["export_data"]},
]


@dataclass(frozen=True)
class ModelConfig:
    name: str
    batch_size: int = 16
    normalize: bool = True

    @property
    def uses_e5_prefix(self) -> bool:
        return "e5" in self.name.lower()

    @property
    def uses_bge_instruction(self) -> bool:
        return "bge" in self.name.lower()


class SentenceTransformerEmbedder:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.model = SentenceTransformer(config.name)
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def _format(self, texts: list[str], kind: str) -> list[str]:
        if self.config.uses_e5_prefix:
            prefix = "query: " if kind == "query" else "passage: "
            return [prefix + text for text in texts]
        if self.config.uses_bge_instruction and kind == "query":
            instruction = "Represent this sentence for searching relevant passages: "
            return [instruction + text for text in texts]
        return texts

    def encode(self, texts: list[str], kind: str) -> np.ndarray:
        formatted = self._format(texts, kind)
        vectors = self.model.encode(
            formatted,
            batch_size=self.config.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = np.asarray(vectors, dtype=np.float32)
        if self.config.normalize:
            vectors = normalize_rows(vectors)
        return vectors


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def load_dataset() -> tuple[list[DocumentChunk], list[QueryCase]]:
    try:
        docs = [DocumentChunk(**item) for item in DOCS]
        queries = [QueryCase(**item) for item in QUERIES]
    except ValidationError as exc:
        raise SystemExit(f"Dataset validation failed:\n{exc}") from exc

    doc_ids = [doc.id for doc in docs]
    duplicate_doc_ids = {doc_id for doc_id in doc_ids if doc_ids.count(doc_id) > 1}
    if duplicate_doc_ids:
        raise SystemExit(f"Duplicate doc ids: {sorted(duplicate_doc_ids)}")

    known_doc_ids = set(doc_ids)
    for query in queries:
        missing = set(query.relevant_chunk_ids) - known_doc_ids
        if missing:
            raise SystemExit(f"{query.id} references unknown chunks: {sorted(missing)}")

    if len(queries) < 20:
        raise SystemExit("Benchmark must contain at least 20 queries")

    return docs, queries


def rank_documents(
    embedder: SentenceTransformerEmbedder,
    docs: list[DocumentChunk],
    queries: list[QueryCase],
    top_k: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    doc_texts = [normalize_unicode(f"{doc.title}\n{doc.text}") for doc in docs]
    doc_vectors = embedder.encode(doc_texts, kind="passage")

    rows: list[dict[str, object]] = []
    latencies_ms: list[float] = []

    for query in queries:
        query_text = normalize_unicode(query.query)
        start = time.perf_counter()
        query_vector = embedder.encode([query_text], kind="query")
        latencies_ms.append((time.perf_counter() - start) * 1000)

        scores = (query_vector @ doc_vectors.T)[0]
        order = np.argsort(-scores)[:top_k]
        ranked_ids = [docs[index].id for index in order]
        ranked_scores = [float(scores[index]) for index in order]
        relevant = set(query.relevant_chunk_ids)

        first_relevant_rank = 0
        for rank, doc_id in enumerate(ranked_ids, start=1):
            if doc_id in relevant:
                first_relevant_rank = rank
                break

        rows.append(
            {
                "query_id": query.id,
                "query": query.query,
                "category": query.category,
                "difficulty": ",".join(query.difficulty),
                "expected": ",".join(query.relevant_chunk_ids),
                "top_ids": ranked_ids,
                "top_scores": ranked_scores,
                "hit@1": int(ranked_ids[0] in relevant),
                "hit@3": int(bool(set(ranked_ids[:3]) & relevant)),
                "recall@5": len(set(ranked_ids[:5]) & relevant) / len(relevant),
                "mrr@5": 0.0 if first_relevant_rank == 0 else 1.0 / first_relevant_rank,
            }
        )

    detail = pd.DataFrame(rows)
    summary = {
        "hit@1": float(detail["hit@1"].mean()),
        "hit@3": float(detail["hit@3"].mean()),
        "recall@5": float(detail["recall@5"].mean()),
        "mrr@5": float(detail["mrr@5"].mean()),
        "p50_query_embed_ms": percentile(latencies_ms, 0.50),
        "p95_query_embed_ms": percentile(latencies_ms, 0.95),
        "dimension": float(embedder.dimension),
        "storage_1m_float32_gb": estimate_storage_gb(1_000_000, embedder.dimension),
    }
    return detail, summary


def estimate_storage_gb(num_chunks: int, dimension: int) -> float:
    return num_chunks * dimension * 4 / 1_000_000_000


def write_report(output_dir: Path, model_name: str, detail: pd.DataFrame, summary: dict[str, float]) -> None:
    safe_name = model_name.replace("/", "__")
    output_dir.mkdir(parents=True, exist_ok=True)

    detail_path = output_dir / f"{safe_name}.details.csv"
    summary_path = output_dir / f"{safe_name}.summary.json"
    failures_path = output_dir / f"{safe_name}.failures.csv"

    detail.to_csv(detail_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    failures = detail[(detail["hit@3"] == 0) | (detail["recall@5"] < 1.0)].copy()
    failures.to_csv(failures_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "intfloat/multilingual-e5-base",
            "BAAI/bge-m3",
        ],
    )
    parser.add_argument("--output-dir", default="day32_embedding_benchmark_report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs, queries = load_dataset()
    output_dir = Path(args.output_dir)
    summaries: list[dict[str, object]] = []

    for model_name in args.models:
        print(f"Running benchmark for {model_name}")
        config = ModelConfig(name=model_name)
        embedder = SentenceTransformerEmbedder(config)
        detail, summary = rank_documents(embedder, docs, queries, top_k=TOP_K)
        write_report(output_dir, model_name, detail, summary)
        summaries.append({"model": model_name, **summary})

    summary_df = pd.DataFrame(summaries).sort_values(["mrr@5", "recall@5", "hit@1"], ascending=False)
    summary_df.to_csv(output_dir / "summary.csv", index=False)
    print(summary_df.to_markdown(index=False, floatfmt=".4f"))


if __name__ == "__main__":
    main()
```

## 4. Chạy benchmark

```bash
python benchmark_embeddings_day32.py
```

Chạy model tùy chọn:

```bash
python benchmark_embeddings_day32.py \
  --models sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 intfloat/multilingual-e5-base BAAI/bge-m3
```

Output:

```text
day32_embedding_benchmark_report/
  summary.csv
  sentence-transformers__paraphrase-multilingual-MiniLM-L12-v2.details.csv
  sentence-transformers__paraphrase-multilingual-MiniLM-L12-v2.summary.json
  sentence-transformers__paraphrase-multilingual-MiniLM-L12-v2.failures.csv
  ...
```

## 5. Phân tích kết quả

Điền report theo mẫu:

```markdown
# Day 32 Embedding Benchmark Report

## Dataset

- Số chunks: 24
- Số queries: 20
- Domain: SaaS support/product/security/billing/privacy
- Ngôn ngữ: tiếng Việt có dấu, không dấu, Viet-English mix

## Metrics

| Model | Hit@1 | Hit@3 | Recall@5 | MRR@5 | p50 ms | p95 ms | Dim | Storage/1M |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## Failure cases

| Model | Query | Difficulty | Expected | Top 5 | Nhận xét |
|---|---|---|---|---|---|
| ... | API trả về 429 nghĩa là gì | exact-code | api_rate_limit | ... | Dense model không ưu tiên mã lỗi |

## Decision

- Model chọn cho RAG project:
- Có dùng BM25 không:
- Có cần reranker không:
- Điều kiện production:
- Rủi ro còn lại:
```

## 6. Câu hỏi bắt buộc

Trả lời ngắn gọn sau khi chạy:

1. Model nào có `MRR@5` cao nhất?
2. Model nào có p95 latency tốt nhất?
3. Query không dấu có giảm chất lượng không?
4. Query acronym/mã lỗi như `429`, `SLA`, `SSO`, `VAT` có cần BM25 không?
5. Nếu corpus có 1M chunks, model nào làm storage tăng nhiều nhất?
6. Bạn có dám dùng model thắng benchmark này trong production không? Nếu có, cần điều kiện gì?

## 7. Mở rộng gần production

Sau khi hoàn thành bản dense-only, thêm các bước sau:

- Thêm BM25 bằng `rank-bm25` hoặc search engine sẵn có.
- Implement Reciprocal Rank Fusion để merge dense ranking và BM25 ranking.
- Tách qrels thành `dev` và `test`.
- Thêm query log ẩn danh từ người dùng thật.
- Thêm regression threshold, ví dụ fail CI nếu `Recall@5` giảm hơn 3%.
- Thêm metadata filter theo `category` để mô phỏng permission/domain filter.
- Thử chunking khác nhau và so sánh lại metric.

## 8. Tiêu chí hoàn thành

- [ ] Chạy được ít nhất 3 models hoặc giải thích rõ model nào không chạy được vì tài nguyên.
- [ ] Có `summary.csv`.
- [ ] Có file failure cases cho từng model.
- [ ] Có quyết định model chọn, không chỉ bảng điểm.
- [ ] Có trả lời production readiness.
- [ ] Có đề xuất hybrid baseline cho tiếng Việt.

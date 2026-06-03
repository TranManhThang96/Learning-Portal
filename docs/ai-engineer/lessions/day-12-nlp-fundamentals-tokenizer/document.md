# Day 12 Document: Tokenizer Reference & Production Code

## 1. Pipeline tham chiếu

```text
Client text
  -> validate size/type
  -> normalize Unicode + whitespace
  -> optional redaction for logs
  -> tokenizer(texts, padding, truncation, max_length)
  -> input_ids + attention_mask + optional offsets
  -> model
  -> decode / classify / rank / generate
```

Trong production, tokenizer wrapper nên là một dependency rõ ràng, có config và test. Không nên rải `AutoTokenizer.from_pretrained(...)` khắp codebase.

## 2. API notes từ Hugging Face

Các điểm cần nhớ khi dùng Hugging Face:

- `AutoTokenizer.from_pretrained(model_name, use_fast=True)` load tokenizer theo model repository.
- Tokenizer có thể nhận một string hoặc một batch `list[str]`.
- `padding="longest"` pad theo sequence dài nhất trong batch; `padding="max_length"` pad cố định theo `max_length`.
- `truncation=True` hoặc strategy như `"longest_first"`, `"only_first"`, `"only_second"` sẽ cắt input vượt `max_length`.
- `return_attention_mask=True` trả mask để model bỏ qua padding.
- `return_offsets_mapping=True` trả `(char_start, char_end)` cho token, nhưng chỉ hỗ trợ fast tokenizer.
- `return_length=True` trả length sau khi tokenization/padding/truncation.
- `pad_to_multiple_of=8` có thể hữu ích cho tensor cores/GPU khi có padding.
- Với thư viện `tokenizers`, `encode_batch` xử lý batch song song và trả `tokens`, `ids`, `attention_mask`, `offsets`, `special_tokens_mask`.

Context7 library IDs đã dùng khi viết bài:

- `/websites/huggingface_co_transformers_main`
- `/huggingface/tokenizers`
- `/huggingface/course`

## 3. Preprocessing helper tối thiểu

Helper này cố tình normalize nhẹ. Nó không xóa dấu, không lowercase mặc định, không xóa punctuation.

```python
from __future__ import annotations

import re
import unicodedata


ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"


def normalize_text(text: str, *, unicode_form: str = "NFC") -> str:
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text)!r}")

    normalized = unicodedata.normalize(unicode_form, text)
    normalized = normalized.translate({ord(ch): None for ch in ZERO_WIDTH_CHARS})
    normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
```

Nếu cần parse HTML, dùng parser như BeautifulSoup/lxml ở ingestion layer. Không nên dùng regex tùy tiện cho HTML phức tạp.

## 4. Production-oriented tokenizer wrapper

Ví dụ dưới đây tập trung vào phần tokenizer, không gọi model. Nó phù hợp để dùng trong API service, batch inference hoặc ingestion pipeline sau khi bạn bổ sung test, metric exporter và model-specific preprocessing.

```python
from __future__ import annotations

import logging
import re
import statistics
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from transformers import AutoTokenizer, PreTrainedTokenizerBase


logger = logging.getLogger("day12.tokenizer")


ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
TruncationPolicy = Literal["reject", "truncate"]
PaddingPolicy = Literal[False, "longest", "max_length"]


class TokenBudgetError(ValueError):
    def __init__(self, *, max_length: int, too_long_count: int, max_seen: int) -> None:
        super().__init__(
            f"input exceeds token budget: max_length={max_length}, "
            f"too_long_count={too_long_count}, max_seen={max_seen}"
        )
        self.max_length = max_length
        self.too_long_count = too_long_count
        self.max_seen = max_seen


@dataclass(frozen=True)
class TokenizerConfig:
    model_name: str
    max_length: int
    truncation_policy: TruncationPolicy = "reject"
    truncation_strategy: Literal["longest_first", "only_first", "only_second"] = "longest_first"
    padding: PaddingPolicy = "longest"
    pad_to_multiple_of: int | None = 8
    add_special_tokens: bool = True
    return_offsets: bool = False
    use_fast: bool = True
    warning_ratio: float = 0.9
    allow_eos_as_pad: bool = False


@dataclass(frozen=True)
class PriceConfig:
    input_usd_per_1m_tokens: float
    output_usd_per_1m_tokens: float


@dataclass(frozen=True)
class TokenStats:
    count: int
    min_tokens: int
    max_tokens: int
    mean_tokens: float
    p50_tokens: int
    p95_tokens: int
    p99_tokens: int
    too_long_count: int


@dataclass(frozen=True)
class BatchTokenizationResult:
    encoded: dict[str, Any]
    raw_token_lengths: list[int]
    stats: TokenStats
    tokenization_latency_ms: float


def normalize_text(text: str, *, unicode_form: str = "NFC") -> str:
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text)!r}")

    normalized = unicodedata.normalize(unicode_form, text)
    normalized = normalized.translate({ord(ch): None for ch in ZERO_WIDTH_CHARS})
    normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = round((len(ordered) - 1) * pct)
    return ordered[idx]


def build_stats(lengths: list[int], *, max_length: int) -> TokenStats:
    if not lengths:
        return TokenStats(0, 0, 0, 0.0, 0, 0, 0, 0)

    too_long = sum(length > max_length for length in lengths)
    return TokenStats(
        count=len(lengths),
        min_tokens=min(lengths),
        max_tokens=max(lengths),
        mean_tokens=statistics.fmean(lengths),
        p50_tokens=percentile(lengths, 0.50),
        p95_tokens=percentile(lengths, 0.95),
        p99_tokens=percentile(lengths, 0.99),
        too_long_count=too_long,
    )


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    price: PriceConfig,
    requests: int = 1,
) -> float:
    per_request = (
        input_tokens / 1_000_000 * price.input_usd_per_1m_tokens
        + output_tokens / 1_000_000 * price.output_usd_per_1m_tokens
    )
    return per_request * requests


class TokenizerService:
    def __init__(self, config: TokenizerConfig) -> None:
        self.config = config
        self.tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(
            config.model_name,
            use_fast=config.use_fast,
        )

        if config.return_offsets and not self.tokenizer.is_fast:
            raise ValueError("return_offsets=True requires a fast tokenizer")

        if self.tokenizer.pad_token is None:
            if config.allow_eos_as_pad and self.tokenizer.eos_token is not None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            else:
                raise ValueError(
                    f"{config.model_name} has no pad_token. Set a pad token explicitly "
                    "or enable allow_eos_as_pad for GPT-style inference-only batching."
                )

    @property
    def vocab_size(self) -> int:
        return int(self.tokenizer.vocab_size)

    @property
    def special_tokens(self) -> dict[str, str | list[str]]:
        return dict(self.tokenizer.special_tokens_map)

    def count_tokens(self, texts: list[str]) -> list[int]:
        normalized = [normalize_text(text) for text in texts]
        encoded = self.tokenizer(
            normalized,
            add_special_tokens=self.config.add_special_tokens,
            padding=False,
            truncation=False,
            return_attention_mask=False,
            verbose=False,
        )
        return [len(input_ids) for input_ids in encoded["input_ids"]]

    def encode_batch(self, texts: list[str]) -> BatchTokenizationResult:
        if not texts:
            raise ValueError("texts must not be empty")

        started = time.perf_counter()
        normalized = [normalize_text(text) for text in texts]
        raw_lengths = self.count_tokens(normalized)
        stats = build_stats(raw_lengths, max_length=self.config.max_length)

        warn_threshold = int(self.config.max_length * self.config.warning_ratio)
        near_limit_count = sum(length >= warn_threshold for length in raw_lengths)
        if near_limit_count:
            logger.warning(
                "token budget near limit: model=%s max_length=%s near_limit_count=%s "
                "max_seen=%s p95=%s",
                self.config.model_name,
                self.config.max_length,
                near_limit_count,
                stats.max_tokens,
                stats.p95_tokens,
            )

        if stats.too_long_count:
            logger.warning(
                "token budget exceeded: model=%s max_length=%s too_long_count=%s "
                "max_seen=%s action=%s",
                self.config.model_name,
                self.config.max_length,
                stats.too_long_count,
                stats.max_tokens,
                self.config.truncation_policy,
            )
            if self.config.truncation_policy == "reject":
                raise TokenBudgetError(
                    max_length=self.config.max_length,
                    too_long_count=stats.too_long_count,
                    max_seen=stats.max_tokens,
                )

        should_truncate = self.config.truncation_policy == "truncate"
        encoded = self.tokenizer(
            normalized,
            add_special_tokens=self.config.add_special_tokens,
            padding=self.config.padding,
            truncation=self.config.truncation_strategy if should_truncate else False,
            max_length=self.config.max_length if should_truncate or self.config.padding == "max_length" else None,
            pad_to_multiple_of=self.config.pad_to_multiple_of,
            return_attention_mask=True,
            return_offsets_mapping=self.config.return_offsets,
            return_length=True,
        )

        latency_ms = (time.perf_counter() - started) * 1000
        return BatchTokenizationResult(
            encoded=dict(encoded),
            raw_token_lengths=raw_lengths,
            stats=stats,
            tokenization_latency_ms=latency_ms,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    samples = [
        "Tôi đang học xử lý ngôn ngữ tự nhiên và tokenizer cho hệ thống RAG.",
        "Toi dang hoc xu ly ngon ngu tu nhien va tokenizer cho he thong RAG.",
        "Khách hàng báo lỗi thanh toán PAY_403 lúc 09:30, cần retry idempotent.",
        "Tôi đang_học xử_lý ngôn_ngữ tự_nhiên với PhoBERT.",
    ]

    service = TokenizerService(
        TokenizerConfig(
            model_name="bert-base-multilingual-cased",
            max_length=64,
            truncation_policy="reject",
            padding="longest",
            return_offsets=True,
        )
    )

    result = service.encode_batch(samples)
    print("model:", service.config.model_name)
    print("vocab_size:", service.vocab_size)
    print("special_tokens:", service.special_tokens)
    print("raw_token_lengths:", result.raw_token_lengths)
    print("stats:", result.stats)
    print("latency_ms:", round(result.tokenization_latency_ms, 2))

    first_ids = result.encoded["input_ids"][0]
    print("first_tokens:", service.tokenizer.convert_ids_to_tokens(first_ids))

    demo_price = PriceConfig(input_usd_per_1m_tokens=0.15, output_usd_per_1m_tokens=0.60)
    print(
        "estimated_monthly_cost_usd:",
        round(
            estimate_cost_usd(
                input_tokens=result.stats.p95_tokens,
                output_tokens=700,
                price=demo_price,
                requests=1_000_000,
            ),
            2,
        ),
    )
```

## 5. Cách chạy thử

Cài dependency:

```bash
pip install transformers tokenizers sentencepiece
```

Chạy với các tokenizer khác nhau bằng cách đổi `model_name`:

```python
TokenizerConfig(model_name="bert-base-multilingual-cased", max_length=128)
TokenizerConfig(model_name="vinai/phobert-base", max_length=256)
TokenizerConfig(model_name="gpt2", max_length=256, allow_eos_as_pad=True)
```

Ghi chú:

- `gpt2` là ví dụ byte-level BPE theo phong cách GPT cũ, hữu ích để quan sát tokenization, không đại diện cho toàn bộ tokenizer của các LLM mới.
- Với PhoBERT, hãy kiểm tra model card/preprocessing chính thức. Nhiều workflow PhoBERT yêu cầu Vietnamese word segmentation trước khi tokenize.
- Với tokenizer không có `pad_token`, không nên âm thầm dùng `eos_token` làm pad trong mọi trường hợp. Chỉ bật `allow_eos_as_pad=True` khi bạn hiểu tác động với model và task.

## 6. Công thức chọn `max_length`

Quy trình thực tế:

1. Lấy sample production hoặc staging đủ đại diện.
2. Normalize đúng như inference.
3. Đếm token bằng đúng tokenizer của model.
4. Xem p50/p95/p99 và max.
5. Chọn `max_length` theo SLA, VRAM/CPU, quality và cost.
6. Quyết định policy cho phần vượt budget: reject, truncate, sliding window hoặc summarize.
7. Thêm metric và alert cho too-long rate.

Ví dụ:

```text
p50 = 72 tokens
p95 = 238 tokens
p99 = 480 tokens
max = 3,900 tokens
```

Nếu classifier dùng BERT/PhoBERT:

- `max_length=256` có thể cover khoảng 95%.
- 5% còn lại cần policy rõ: reject, truncate hoặc split.
- Nếu 5% này là nhóm ticket VIP/complex case, truncate có thể làm giảm business quality.

Nếu RAG ingestion:

- Đừng dùng `max_length=256` để cắt document gốc.
- Split document thành chunk 300-800 tokens tùy embedding model và retrieval benchmark.
- Giữ overlap vừa đủ, ví dụ 50-120 tokens, nhưng phải evaluate.

## 7. Trade-off nhanh

| Quyết định | Lợi ích | Chi phí/rủi ro |
|---|---|---|
| Dynamic padding | Ít waste compute | Shape thay đổi giữa batch |
| Padding `max_length` | Shape ổn định | Lãng phí nếu text ngắn |
| Reject quá dài | Không mất dữ liệu âm thầm | User cần retry hoặc hệ thống cần hướng dẫn |
| Truncate | Dễ vận hành | Có thể mất thông tin quyết định |
| Sliding window | Xử lý document dài tốt hơn | Tăng compute, cần aggregate output |
| Cache tokenized chunks | Tăng throughput ingestion/RAG | Cache invalidation khi tokenizer đổi |
| Offset mapping | Debug/citation/NER tốt | Chỉ fast tokenizer, thêm payload |
| Xóa dấu | Có thể tăng recall search thô | Giảm semantic quality cho NLP/LLM |

## 8. Production checklist riêng cho tokenizer

- Tokenizer, model weights, config, preprocessing code và label mapping cùng version.
- Unit test cho token count và special tokens với sample cố định.
- Contract test: batch size 1 và batch size N cho output tương thích.
- Test tiếng Việt có dấu, không dấu, word-segmented, code-mixed, markdown, JSON/log.
- Log token length, truncation, rejection, latency và cost; không log raw PII.
- Alert khi p95 token tăng bất thường hoặc rejection rate tăng.
- Benchmark dynamic padding vs max padding với QPS thật.
- Document rõ policy khi input vượt budget.

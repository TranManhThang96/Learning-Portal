# Document: Schema Và Code Mẫu Cho Permission-aware RAG

Tài liệu này gom các artifact có thể dùng lại khi thiết kế enterprise RAG: schema, query flow, code mẫu gần production và test case cốt lõi.

## 1. Kiến Trúc Tham Khảo

```text
Client
  -> API Gateway/AuthN
  -> RAG API
      -> Authz/Directory service
      -> Query normalizer
      -> Retriever
          -> Vector DB pre-filter tenant/ACL/deleted_at
          -> BM25/hybrid search optional
      -> Backend post-filter
      -> Reranker optional
      -> Context builder + source_map
      -> LLM
      -> Citation validator
      -> Citation renderer via proxy/signed URL
      -> Audit logger
```

Security boundary nằm ở RAG API/Retriever, không nằm trong prompt.

## 2. Canonical Data Model

### DocumentRecord

```json
{
  "document_id": "policy_001",
  "tenant_id": "company_a",
  "title": "Employee Leave Policy",
  "source_type": "pdf",
  "source_uri": "s3://private-kb/company_a/hr/policy.pdf",
  "document_version": "2026-01",
  "status": "active",
  "acl_policy_id": "acl_policy_789",
  "acl_version": "acl-2026-05-09T10:00:00Z",
  "created_at": "2026-05-01T00:00:00Z",
  "updated_at": "2026-05-09T10:00:00Z",
  "deleted_at": null
}
```

### ChunkRecord

```json
{
  "chunk_id": "company_a:policy_001:v2026-01:00012",
  "document_id": "policy_001",
  "tenant_id": "company_a",
  "text": "Nhân viên full-time có 12 ngày nghỉ phép năm...",
  "metadata": {
    "document_title": "Employee Leave Policy",
    "source_type": "pdf",
    "source_uri": "s3://private-kb/company_a/hr/policy.pdf",
    "page_start": 12,
    "page_end": 13,
    "section_path": ["HR", "Leave Policy", "Annual Leave"],
    "document_version": "2026-01",
    "chunk_index": 12,
    "chunking_version": "pdf-layout-v3",
    "embedding_model": "BAAI/bge-m3",
    "embedding_dimension": 1024,
    "index_version": "rag-index-2026-05-09",
    "visibility": "restricted",
    "acl_roles": ["hr", "manager"],
    "acl_groups": [],
    "acl_users": [],
    "acl_version": "acl-2026-05-09T10:00:00Z",
    "text_hash": "sha256:...",
    "deleted_at": null
  }
}
```

### SourceMap Entry

```json
{
  "source_id": "S1",
  "chunk_id": "company_a:policy_001:v2026-01:00012",
  "document_id": "policy_001",
  "tenant_id": "company_a",
  "title": "Employee Leave Policy",
  "page_start": 12,
  "page_end": 13,
  "section_path": ["HR", "Leave Policy", "Annual Leave"],
  "document_version": "2026-01",
  "raw_source_uri": "s3://private-kb/company_a/hr/policy.pdf"
}
```

`raw_source_uri` chỉ dùng server-side. Client nhận `access_url` được tạo bởi renderer.

## 3. Code Mẫu Python

Code dưới đây không phụ thuộc framework để dễ đọc, nhưng tổ chức theo hướng có thể đưa vào service thật: auth context rõ ràng, deny-by-default, context builder tạo source map, citation validator và audit event. `build_vector_filter` tạo policy AST nội bộ; không truyền dict đó thẳng vào SDK vendor nếu chưa có adapter và contract test.

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import re
from typing import Any


PRIVATE_URI_PREFIXES = ("s3://", "gs://", "file://", "/mnt/", "/var/")


@dataclass(frozen=True)
class UserContext:
    user_id: str
    tenant_id: str
    roles: frozenset[str]
    groups: frozenset[str]
    attributes: dict[str, str]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]
    score: float = 0.0


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    chunk_id: str
    document_id: str
    title: str
    page_start: int | None
    page_end: int | None
    section_path: list[str]
    document_version: str
    raw_source_uri: str


def hash_for_log(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _has_any(left: frozenset[str], right: list[str] | tuple[str, ...]) -> bool:
    return bool(left.intersection(right))


def can_read(user: UserContext, chunk: Chunk) -> bool:
    meta = chunk.metadata

    if meta.get("tenant_id") != user.tenant_id:
        return False
    if meta.get("deleted_at"):
        return False

    visibility = meta.get("visibility", "restricted")
    if visibility == "public_to_tenant":
        return True
    if visibility != "restricted":
        return False

    roles = meta.get("acl_roles") or []
    groups = meta.get("acl_groups") or []
    users = meta.get("acl_users") or []

    if not roles and not groups and not users:
        return False

    return (
        _has_any(user.roles, roles)
        or _has_any(user.groups, groups)
        or user.user_id in users
    )


def build_vector_filter(user: UserContext) -> dict[str, Any]:
    return {
        "must": [
            {"key": "tenant_id", "match": user.tenant_id},
            {"key": "deleted", "match": False},
        ],
        "should": [
            {"key": "visibility", "match": "public_to_tenant"},
            {"key": "acl_roles", "intersects": sorted(user.roles)},
            {"key": "acl_groups", "intersects": sorted(user.groups)},
            {"key": "acl_users", "contains": user.user_id},
        ],
        "minimum_should_match": 1,
    }


def post_filter_chunks(user: UserContext, candidates: list[Chunk]) -> list[Chunk]:
    return [chunk for chunk in candidates if can_read(user, chunk)]


def build_context(
    user: UserContext,
    candidates: list[Chunk],
    *,
    max_chars: int = 6000,
) -> tuple[str, dict[str, SourceRef]]:
    visible_chunks = post_filter_chunks(user, candidates)
    source_map: dict[str, SourceRef] = {}
    context_blocks: list[str] = []
    used_chars = 0

    for chunk in visible_chunks:
        meta = chunk.metadata
        source_id = f"S{len(source_map) + 1}"
        section_path = list(meta.get("section_path") or [])
        section_text = " > ".join(section_path) if section_path else "Unknown section"
        title = meta.get("document_title") or chunk.document_id

        block = (
            f"[{source_id}]\n"
            f"Title: {title}\n"
            f"Version: {meta.get('document_version', 'unknown')}\n"
            f"Page: {meta.get('page_start')}-{meta.get('page_end')}\n"
            f"Section: {section_text}\n"
            f"Text: {chunk.text}\n"
        )
        if used_chars + len(block) > max_chars:
            continue

        source_map[source_id] = SourceRef(
            source_id=source_id,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            title=title,
            page_start=meta.get("page_start"),
            page_end=meta.get("page_end"),
            section_path=section_path,
            document_version=meta.get("document_version", "unknown"),
            raw_source_uri=meta.get("source_uri", ""),
        )
        context_blocks.append(block)
        used_chars += len(block)

    return "\n---\n".join(context_blocks), source_map


def validate_citations(
    answer: str,
    source_map: dict[str, SourceRef],
    user: UserContext,
    chunk_lookup: dict[str, Chunk],
) -> list[str]:
    errors: list[str] = []
    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))

    for source_id in sorted(cited_ids):
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"invalid_citation:{source_id}")
            continue

        chunk = chunk_lookup.get(source.chunk_id)
        if chunk is None:
            errors.append(f"missing_chunk:{source_id}")
            continue
        if not can_read(user, chunk):
            errors.append(f"not_visible:{source_id}")

    if answer.strip() and not cited_ids:
        errors.append("missing_citation")

    return errors


def render_access_url(source: SourceRef, *, trace_id: str) -> dict[str, str]:
    if source.raw_source_uri.startswith(PRIVATE_URI_PREFIXES):
        access_url = f"/api/rag/traces/{trace_id}/sources/{source.source_id}"
    else:
        access_url = f"/api/rag/traces/{trace_id}/sources/{source.source_id}"

    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    return {
        "source_id": source.source_id,
        "title": source.title,
        "page": str(source.page_start or ""),
        "section": " > ".join(source.section_path),
        "document_version": source.document_version,
        "access_url": access_url,
        "expires_at": expires_at.isoformat(),
    }


def build_audit_event(
    *,
    trace_id: str,
    user: UserContext,
    query: str,
    vector_filter: dict[str, Any],
    retrieved: list[Chunk],
    visible: list[Chunk],
    source_map: dict[str, SourceRef],
    citation_errors: list[str],
    redacted_query: str | None = None,
) -> dict[str, Any]:
    event = {
        "trace_id": trace_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "query_hash": hash_for_log(query),
        "permission_snapshot": {
            "roles": sorted(user.roles),
            "groups": sorted(user.groups),
        },
        "vector_filter": vector_filter,
        "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieved],
        "visible_chunk_ids": [chunk.chunk_id for chunk in visible],
        "context_source_ids": list(source_map.keys()),
        "citation_errors": citation_errors,
    }
    if redacted_query is not None:
        event["query_redacted"] = redacted_query[:300]
    return event
```

Không gọi `query[:300]` là redaction: cắt ngắn chuỗi vẫn có thể giữ nguyên PII, secret hoặc dữ liệu hợp đồng. Chỉ truyền `redacted_query` khi một redaction pipeline đã được kiểm thử; mặc định chỉ log hash.

### Qdrant adapter hiện hành

Ví dụ dưới đây chuyển policy sang `qdrant-client`. Vector payload cần có `deleted: false`; canonical store vẫn giữ `deleted_at` để audit lifecycle.

```python
from qdrant_client import models


def build_qdrant_filter(user: UserContext) -> models.Filter:
    visible_conditions = [
        models.FieldCondition(
            key="visibility",
            match=models.MatchValue(value="public_to_tenant"),
        )
    ]
    if user.roles:
        visible_conditions.append(
            models.FieldCondition(
                key="acl_roles",
                match=models.MatchAny(any=sorted(user.roles)),
            )
        )
    if user.groups:
        visible_conditions.append(
            models.FieldCondition(
                key="acl_groups",
                match=models.MatchAny(any=sorted(user.groups)),
            )
        )
    visible_conditions.append(
        models.FieldCondition(
            key="acl_users",
            match=models.MatchAny(any=[user.user_id]),
        )
    )

    return models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=user.tenant_id),
            ),
            models.FieldCondition(
                key="deleted",
                match=models.MatchValue(value=False),
            ),
        ],
        should=visible_conditions,
    )
```

Tạo payload index kiểu `KEYWORD` cho tenant/visibility/ACL và kiểu `BOOL` cho `deleted`. Dù đã pre-filter trong Qdrant, vẫn chạy `can_read` trước context builder để defense-in-depth.

## 4. Test Cases Tối Thiểu

Các test sau có thể chuyển thẳng thành `pytest`.

```python
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="company_a:policy:v1:001",
            document_id="policy",
            text="Nhân viên full-time có 12 ngày nghỉ phép năm.",
            metadata={
                "tenant_id": "company_a",
                "document_title": "Leave Policy",
                "source_uri": "s3://private/company_a/policy.pdf",
                "page_start": 1,
                "page_end": 1,
                "section_path": ["HR", "Leave"],
                "document_version": "v1",
                "visibility": "public_to_tenant",
                "deleted_at": None,
            },
        ),
        Chunk(
            chunk_id="company_a:salary:v1:001",
            document_id="salary",
            text="Bảng lương chỉ dành cho HR.",
            metadata={
                "tenant_id": "company_a",
                "document_title": "Salary Policy",
                "source_uri": "s3://private/company_a/salary.pdf",
                "page_start": 2,
                "page_end": 2,
                "section_path": ["HR", "Compensation"],
                "document_version": "v1",
                "visibility": "restricted",
                "acl_roles": ["hr"],
                "acl_groups": [],
                "acl_users": [],
                "deleted_at": None,
            },
        ),
        Chunk(
            chunk_id="company_b:policy:v1:001",
            document_id="policy_b",
            text="Policy của tenant B.",
            metadata={
                "tenant_id": "company_b",
                "document_title": "Tenant B Policy",
                "visibility": "public_to_tenant",
                "deleted_at": None,
            },
        ),
        Chunk(
            chunk_id="company_a:old:v1:001",
            document_id="old",
            text="Document đã xóa.",
            metadata={
                "tenant_id": "company_a",
                "document_title": "Old Policy",
                "visibility": "public_to_tenant",
                "deleted_at": "2026-05-09T10:00:00Z",
            },
        ),
    ]


def test_employee_cannot_read_hr_or_other_tenant_or_deleted():
    user = UserContext(
        user_id="u1",
        tenant_id="company_a",
        roles=frozenset({"employee"}),
        groups=frozenset({"engineering"}),
        attributes={},
    )

    visible = post_filter_chunks(user, sample_chunks())

    assert [chunk.chunk_id for chunk in visible] == ["company_a:policy:v1:001"]


def test_hr_can_read_restricted_salary_policy():
    user = UserContext(
        user_id="u2",
        tenant_id="company_a",
        roles=frozenset({"hr"}),
        groups=frozenset(),
        attributes={},
    )

    visible = post_filter_chunks(user, sample_chunks())

    assert "company_a:salary:v1:001" in {chunk.chunk_id for chunk in visible}


def test_citation_validator_rejects_unknown_source():
    user = UserContext("u1", "company_a", frozenset({"employee"}), frozenset(), {})
    chunks = sample_chunks()
    context, source_map = build_context(user, chunks)
    chunk_lookup = {chunk.chunk_id: chunk for chunk in chunks}

    errors = validate_citations(
        "Bạn có 12 ngày nghỉ phép năm [S1]. Thông tin khác [S99].",
        source_map,
        user,
        chunk_lookup,
    )

    assert "invalid_citation:S99" in errors
```

## 5. Query Flow Pseudocode

```python
def answer_question(user: UserContext, query: str) -> dict:
    trace_id = create_trace_id()
    vector_filter = build_vector_filter(user)

    candidates = vector_db.search(
        query_embedding=embed(query),
        top_k=80,
        filter=vector_filter,
    )

    visible = post_filter_chunks(user, candidates)
    reranked = rerank(query, visible)[:8]
    context, source_map = build_context(user, reranked, max_chars=6000)

    llm_answer = llm.generate(
        system=(
            "Trả lời chỉ dựa trên context. "
            "Mỗi claim factual phải cite bằng [S1], [S2]. "
            "Không tự tạo citation ngoài source đã có."
        ),
        user=f"Question: {query}\n\nContext:\n{context}",
    )

    chunk_lookup = {chunk.chunk_id: chunk for chunk in reranked}
    errors = validate_citations(llm_answer, source_map, user, chunk_lookup)
    if errors:
        raise CitationValidationError(errors)

    citations = [
        render_access_url(source, trace_id=trace_id)
        for source in source_map.values()
        if f"[{source.source_id}]" in llm_answer
    ]

    audit_logger.write_async(
        build_audit_event(
            trace_id=trace_id,
            user=user,
            query=query,
            vector_filter=vector_filter,
            retrieved=candidates,
            visible=visible,
            source_map=source_map,
            citation_errors=[],
        )
    )

    return {
        "trace_id": trace_id,
        "answer": llm_answer,
        "citations": citations,
    }
```

## 6. Production Readiness Checklist

- Metadata có `tenant_id`, ACL, source, page/section, version và tombstone.
- Retriever dùng pre-filter cho tenant/ACL/deleted state.
- Backend vẫn post-filter trước context builder.
- Context builder tạo `source_map`, không để LLM tự tạo source.
- Citation validator reject source không tồn tại hoặc không visible.
- Citation link đi qua signed URL/proxy, không expose raw private URI.
- Delete path có tombstone trước physical delete.
- Cache key có tenant/user/permission version.
- Audit log redacted, có retention và access control.
- Regression tests chạy trong CI.

## 7. Nguồn Kỹ Thuật Đã Đối Chiếu

- [Qdrant filtering](https://qdrant.tech/documentation/concepts/filtering/): `must`, `should`, `MatchValue`, `MatchAny` và payload filtering.
- [Qdrant Python client](https://github.com/qdrant/qdrant-client): `Filter`, `FieldCondition`, payload indexes và `query_points`.
- [pgvector](https://github.com/pgvector/pgvector): filtered nearest-neighbor query và iterative scans khi ACL filter làm candidate set nhỏ.

Authorization semantics vẫn thuộc ứng dụng của bạn. Vector DB filter chỉ là một enforcement layer; directory/policy service, post-filter và regression test mới tạo thành boundary đầy đủ.

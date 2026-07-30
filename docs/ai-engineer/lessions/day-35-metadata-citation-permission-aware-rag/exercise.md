# Exercise: Thiết Kế Metadata Schema Cho Enterprise RAG

## Bối Cảnh

Bạn đang xây một RAG assistant cho công ty SaaS B2B. Mỗi customer là một tenant. Corpus gồm:

- HR policy PDF.
- Engineering runbook Markdown.
- Pricing spreadsheet export.
- Legal contract PDF.
- Customer support FAQ.

Yêu cầu bảo mật:

- User chỉ được xem document cùng tenant.
- HR document chỉ dành cho role `hr` hoặc `manager`.
- Pricing chỉ dành cho group `sales` và `finance`.
- Legal contract có một số section chỉ dành cho user cụ thể.
- Document đã xóa phải biến mất khỏi retrieval gần như ngay lập tức.
- Citation phải mở được đúng document, page và section nếu user còn quyền.

## Mục Tiêu

Hoàn thành một thiết kế production-oriented cho Day 35:

1. Metadata schema cho document và chunk.
2. Pre-filter và post-filter logic.
3. Citation source map và validation rule.
4. Signed URL/proxy flow khi user mở citation.
5. Tombstone/delete flow.
6. Audit log schema.
7. Regression tests cho permission và citation.
8. Kết luận production readiness.

## Phần 1: Thiết Kế Schema

Tạo hai schema JSON: `DocumentRecord` và `ChunkRecord`.

`DocumentRecord` bắt buộc có:

- `document_id`
- `tenant_id`
- `title`
- `source_type`
- `source_uri`
- `document_version`
- `acl_policy_id`
- `acl_version`
- `status`
- `deleted_at`

`ChunkRecord` bắt buộc có:

- `chunk_id`
- `document_id`
- `tenant_id`
- `text`
- `document_title`
- `page_start`
- `page_end`
- `section_path`
- `document_version`
- `chunk_index`
- `chunking_version`
- `embedding_model`
- `index_version`
- `visibility`
- `acl_roles`
- `acl_groups`
- `acl_users`
- `acl_version`
- `text_hash`
- `deleted_at`

Câu hỏi cần trả lời:

- Field nào phải được index trong Vector DB?
- Field nào chỉ dùng để render citation?
- Field nào là security-critical?
- Nếu một chunk thiếu `acl_roles`, `acl_groups`, `acl_users` thì xử lý thế nào?

## Phần 2: Sample Data

Tạo ít nhất 6 chunks:

| Chunk | Tenant | Visibility | Permission | Ghi chú |
|---|---|---|---|
| HR leave policy | `company_a` | `public_to_tenant` | Không cần role đặc biệt | User thường đọc được |
| HR salary policy | `company_a` | `restricted` | role `hr` | User thường không đọc được |
| Pricing playbook | `company_a` | `restricted` | group `sales` hoặc `finance` | Sales đọc được |
| Legal contract section | `company_a` | `restricted` | user `u_legal_1` | User cụ thể đọc được |
| Tenant B policy | `company_b` | `public_to_tenant` | Tenant B | Tenant A không đọc được |
| Deleted policy | `company_a` | `public_to_tenant` | Đã tombstone | Không ai retrieve được |

Tạo ít nhất 4 user contexts:

- Employee thường của `company_a`.
- HR của `company_a`.
- Sales của `company_a`.
- Employee của `company_b`.

## Phần 3: Implement Permission Logic

Viết function:

```python
def can_read(user: UserContext, chunk: Chunk) -> bool:
    ...
```

Acceptance criteria:

- Sai tenant trả về `False`.
- `deleted_at != None` trả về `False`.
- `public_to_tenant` cùng tenant trả về `True`.
- `restricted` chỉ trả về `True` nếu match role, group hoặc user.
- Metadata thiếu ACL với `restricted` phải deny.

Sau đó viết:

```python
def build_vector_filter(user: UserContext) -> dict:
    ...

def post_filter_chunks(user: UserContext, chunks: list[Chunk]) -> list[Chunk]:
    ...
```

Giải thích vì sao production nên dùng cả pre-filter và post-filter.

## Phần 4: Context Builder Và Citation

Viết function:

```python
def build_context(user: UserContext, chunks: list[Chunk], max_chars: int) -> tuple[str, dict]:
    ...
```

Yêu cầu:

- Chỉ chunk visible mới được vào context.
- Mỗi chunk trong context có source ID dạng `[S1]`, `[S2]`.
- `source_map` phải chứa `chunk_id`, `document_id`, `title`, `page_start`, `page_end`, `section_path`, `document_version`.
- Không đưa raw private URI vào prompt nếu không cần.

Ví dụ context block:

```text
[S1]
Title: Employee Leave Policy
Version: 2026-01
Page: 12-13
Section: HR > Leave Policy > Annual Leave
Text: Nhân viên full-time có 12 ngày nghỉ phép năm.
```

## Phần 5: Citation Validator

Viết function:

```python
def validate_citations(
    answer: str,
    source_map: dict,
    user: UserContext,
    chunk_lookup: dict[str, Chunk],
) -> list[str]:
    ...
```

Validator cần bắt được:

- Answer cite `[S99]` nhưng `source_map` không có.
- Answer không có citation nào dù có factual claim.
- Citation trỏ tới chunk không còn visible với user.
- Citation trỏ tới chunk đã tombstone.

`source_map` một mình không đủ để re-check quyền. Validator phải lookup chunk/document hiện tại bằng `chunk_id`, hoặc gọi authorization repository/service tương đương.

Test case bắt buộc:

```text
"Bạn có 12 ngày nghỉ phép năm [S1]. Mức lương theo bảng nội bộ [S99]."
```

Kết quả kỳ vọng: validator trả lỗi `invalid_citation:S99`.

## Phần 6: Signed URL Hoặc Source Proxy

Thiết kế endpoint:

```http
GET /api/rag/traces/{trace_id}/sources/{source_id}
```

Endpoint cần làm:

- Load `source_map` theo `trace_id`.
- Check `source_id` có tồn tại.
- Re-check user permission với chunk/document hiện tại.
- Nếu source là file object storage, tạo signed URL TTL ngắn.
- Nếu source là wiki/private system, proxy nội dung hoặc redirect qua backend.
- Ghi audit event `source_opened`.

Trả lời:

- Vì sao không trả `s3://bucket/path.pdf` trực tiếp cho client?
- TTL signed URL nên dài bao lâu trong context enterprise?
- Khi user mất quyền sau khi answer được tạo, click citation phải xử lý thế nào?

## Phần 7: Tombstone Và Delete Flow

Thiết kế flow khi document bị xóa:

```text
delete event
  -> mark tombstone
  -> invalidate cache
  -> remove vector chunks
  -> remove BM25 entries
  -> revoke signed URL if possible
  -> write audit
  -> verify not retrievable
```

Trả lời:

- Vì sao tombstone phải xảy ra trước physical delete?
- Cache nào cần invalidate?
- Nếu vector delete job fail giữa chừng thì retriever vẫn an toàn bằng cách nào?

## Phần 8: Audit Log

Thiết kế audit event cho query:

```json
{
  "trace_id": "trace_123",
  "timestamp": "2026-05-09T10:02:03Z",
  "user_id": "u123",
  "tenant_id": "company_a",
  "query_hash": "sha256:...",
  "permission_snapshot": {},
  "filters": {},
  "retrieved_chunk_ids": [],
  "visible_chunk_ids": [],
  "context_source_ids": [],
  "citation_ids": [],
  "citation_errors": [],
  "index_version": "rag-index-2026-05-09"
}
```

Trả lời:

- Field nào cần redact?
- Audit log nên sync hay async?
- Ai được quyền đọc audit log?
- Retention policy nên nghĩ đến những yếu tố nào?

## Phần 9: Regression Tests

Viết test checklist hoặc `pytest` cho các case:

- Employee tenant A không thấy document tenant B.
- Employee thường không thấy HR salary policy.
- HR thấy HR salary policy.
- Sales thấy pricing playbook.
- User không phải `u_legal_1` không thấy legal restricted section.
- Deleted policy không xuất hiện trong context.
- Citation `[S99]` bị reject.
- Citation access endpoint không trả raw private URI.
- Query cache key có tenant ID và permission version.
- Khi ACL đổi, permission cache bị invalidate hoặc hết hạn trong TTL ngắn.

## Phần 10: Production Readiness Answer

Viết đoạn kết luận 8-12 dòng trả lời:

```text
Dùng được trong production không?
Nếu có thì cần điều kiện gì?
Nếu chưa đủ thì đang thiếu gì?
```

Kết luận tốt cần nhắc đến:

- Metadata contract.
- Backend permission enforcement.
- Deny-by-default.
- Citation validation.
- Source proxy/signed URL.
- Tombstone/delete.
- Audit log.
- Regression tests.
- Monitoring latency và security metrics.

## Gợi Ý Rubric Tự Chấm

| Tiêu chí | Đạt |
|---|---|
| Schema có đủ tenant, ACL, source, page/section, version, tombstone | |
| Permission logic deny-by-default | |
| Có cả pre-filter và post-filter | |
| Citation do backend cấp source ID | |
| Validator bắt citation ảo | |
| Source link không expose raw private URI | |
| Delete flow có tombstone và verification | |
| Audit log có trace retrieval/citation | |
| Regression tests bao phủ cross-tenant, ACL, delete, citation | |
| Kết luận production readiness rõ ràng | |

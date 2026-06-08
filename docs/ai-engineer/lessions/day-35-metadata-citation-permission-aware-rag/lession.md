# Day 35: Metadata, Citation, Permission-aware RAG

## Mục Tiêu

Sau bài này, bạn cần làm được những việc sau:

- Hiểu metadata là data contract của RAG, không phải field phụ.
- Thiết kế chunk schema có source metadata, page number, section heading, document version, tenant ID, ACL và user permission.
- Biết enforce permission trước khi đưa chunk vào prompt.
- Render citation có thể trace ngược về document, page, section và version thật.
- Validate citation để giảm hallucination và citation ảo.
- Thiết kế audit log phục vụ debug, compliance và incident investigation.
- Xử lý stale ACL, stale index, tombstone, delete và cache invalidation.
- Trả lời rõ: hệ thống này dùng được trong production không, và cần điều kiện gì.

## TL;DR

Production RAG không được chỉ làm `embed query -> vector search -> nhét top_k vào prompt`. Mỗi chunk phải có metadata đủ để filter, cite, audit, version và delete. Permission-aware RAG phải enforce ACL ở backend/retriever trước khi build context, không giao cho LLM tự quyết. Citation phải do backend cấp `source_id`, LLM chỉ được cite source đã cấp, sau đó backend validate citation trước khi trả về người dùng.

## 1. Vì Sao Metadata Là Contract

Trong app CRUD, database schema quyết định record nào thuộc tenant nào, ai được đọc, trạng thái đã xóa hay chưa. Trong RAG cũng vậy, nhưng dữ liệu thường đi qua nhiều bước hơn:

```text
source document
  -> parser
  -> chunker
  -> metadata enricher
  -> embedding
  -> vector/BM25 index
  -> retriever
  -> context builder
  -> LLM
  -> answer + citation
```

Nếu metadata sai hoặc thiếu, lỗi không chỉ là "tìm kiếm kém". Lỗi có thể thành data leak:

- User tenant A thấy tài liệu tenant B.
- Nhân viên thường thấy tài liệu chỉ dành cho HR.
- Câu trả lời cite một page không tồn tại.
- Document đã xóa vẫn được retrieve từ vector index.
- Audit log không biết answer dựa trên chunk nào.

Rule production: field nào dùng cho security, citation, deletion hoặc audit thì phải do backend/parser sinh ra và validate, không lấy từ text do LLM đoán.

## 2. Metadata Tối Thiểu Cho Enterprise RAG

Một chunk production nên có bốn nhóm metadata.

| Nhóm | Field ví dụ | Dùng để làm gì |
|---|---|---|
| Identity | `chunk_id`, `document_id`, `tenant_id` | Định danh, multi-tenancy, delete |
| Source/citation | `document_title`, `source_uri`, `source_type`, `page_start`, `page_end`, `section_path` | Render citation và trace source |
| Permission | `visibility`, `acl_roles`, `acl_groups`, `acl_users`, `acl_version`, `acl_updated_at` | Permission-aware retrieval |
| Lifecycle/ops | `document_version`, `index_version`, `chunking_version`, `embedding_model`, `text_hash`, `deleted_at` | Reindex, rollback, tombstone, audit |

Schema gợi ý:

```json
{
  "chunk_id": "company_a:policy_001:v2026-01:00012",
  "document_id": "policy_001",
  "document_title": "Employee Leave Policy",
  "text": "Nhân viên full-time có 12 ngày nghỉ phép năm...",
  "metadata": {
    "tenant_id": "company_a",
    "source_type": "pdf",
    "source_uri": "s3://private-kb/company_a/hr/policy.pdf",
    "page_start": 12,
    "page_end": 13,
    "section_path": ["HR", "Leave Policy", "Annual Leave"],
    "document_version": "2026-01",
    "chunk_index": 12,
    "chunking_version": "markdown-pdf-v3",
    "embedding_model": "BAAI/bge-m3",
    "index_version": "rag-index-2026-05-09",
    "visibility": "restricted",
    "acl_roles": ["hr", "manager"],
    "acl_groups": [],
    "acl_users": [],
    "acl_version": "acl-2026-05-09T10:00:00Z",
    "acl_updated_at": "2026-05-09T10:00:00Z",
    "text_hash": "sha256:...",
    "deleted_at": null,
    "created_at": "2026-05-09T09:00:00Z",
    "updated_at": "2026-05-09T10:00:00Z"
  }
}
```

Không nên expose `source_uri` thẳng ra client nếu đó là S3 path, internal wiki URL hoặc file path nội bộ. Client nên nhận một citation object đã được backend render qua proxy hoặc signed URL ngắn hạn.

Trong Vector DB, nên project thêm field boolean `deleted=false` để pre-filter nhanh. `deleted_at` vẫn nằm trong canonical metadata/audit store để biết thời điểm xóa. Hai field phải được cập nhật atomically hoặc qua event idempotent; nếu chúng lệch nhau, rule an toàn là deny.

## 3. Permission-aware Retrieval

Permission-aware RAG có nguyên tắc đơn giản: chunk không được đọc thì không được vào prompt.

Flow chuẩn:

```text
user auth context
  -> normalize tenant, roles, groups, attributes
  -> pre-filter tenant + ACL trong search query
  -> retrieve candidate chunks
  -> post-filter lại ở backend
  -> build context + source_map
  -> call LLM
  -> validate citation + permission lần cuối
```

Các mode permission thường gặp:

| Mode | Ví dụ | Ghi chú |
|---|---|---|
| Tenant-level | User chỉ thấy data của `company_a` | Bắt buộc trong B2B SaaS |
| Role-level | `hr`, `manager`, `finance` | Dễ vận hành nhưng hơi coarse |
| Group-level | `engineering-backend`, `sales-vn` | Phù hợp enterprise directory |
| User-level | Document share riêng cho `u123` | Chính xác nhưng filter lớn |
| Attribute-based | `region=VN`, `employment_type=full_time` | Mạnh nhưng cần policy engine |

Default production: deny by default. Nếu chunk thiếu tenant, thiếu ACL hoặc metadata không parse được, không retrieve chunk đó.

## 4. Pre-filter Và Post-filter

Pre-filter là đưa tenant/ACL vào query trước hoặc trong search:

```text
tenant_id = current_user.tenant_id
AND deleted_at IS NULL
AND (
  acl_roles intersects current_user.roles
  OR acl_groups intersects current_user.groups
  OR acl_users contains current_user.user_id
)
```

Post-filter là lấy candidate rồi lọc lại bằng code backend. Production nên dùng cả hai:

| Cách | Điểm mạnh | Điểm yếu | Khi dùng |
|---|---|---|---|
| Pre-filter | Giảm leak vì chunk cấm không vào candidate | Có thể giảm recall nếu filter/index yếu | Default cho tenant/ACL |
| Post-filter | Defense-in-depth, độc lập với Vector DB | Không đủ làm security boundary duy nhất | Luôn bật thêm |
| Pre + post | An toàn hơn và dễ test | Phức tạp hơn, phải benchmark latency | Enterprise RAG |

Nếu Vector DB không hỗ trợ filter đủ tốt, không nên dùng nó làm security boundary. Khi đó cần partition theo tenant, search service riêng hoặc authz layer trước retriever.

## 5. Citation Không Phải Trang Trí

Citation là audit trail của answer. Citation tốt phải trả lời được:

- Answer dựa trên chunk nào?
- Chunk thuộc document nào, version nào?
- Page/section nào trong source?
- User hiện tại có quyền mở source không?
- Link source có an toàn không?

Flow tốt:

```text
retrieved visible chunks
  -> backend gán source_id S1/S2/S3
  -> build context có [S1], [S2]
  -> LLM chỉ được cite source_id đã cấp
  -> validator kiểm tra citation
  -> renderer tạo citation link qua proxy/signed URL
```

Citation object nên là structured data:

```json
{
  "source_id": "S1",
  "chunk_id": "company_a:policy_001:v2026-01:00012",
  "document_id": "policy_001",
  "title": "Employee Leave Policy",
  "page_start": 12,
  "page_end": 13,
  "section": "HR > Leave Policy > Annual Leave",
  "document_version": "2026-01",
  "access_url": "/api/rag/sources/S1?trace_id=trace_123",
  "expires_at": "2026-05-09T10:15:00Z"
}
```

Không để LLM tự tạo URL, document ID hoặc page number. LLM chỉ nên nhìn thấy nội dung context và `source_id` được backend cấp.

## 6. Citation Validation

Validator tối thiểu cần check:

- Citation id trong answer có tồn tại trong `source_map`.
- `source_id` map về chunk thật đã nằm trong context.
- Chunk vẫn visible với user tại thời điểm response.
- Chunk không bị tombstone hoặc document không bị delete.
- Citation renderer không expose raw private URI.
- Answer có claim quan trọng nhưng không citation thì flag để review hoặc yêu cầu model trả lời lại.

Mức validate có thể tăng dần:

| Mức | Cách làm | Trade-off |
|---|---|---|
| Regex source id | Check `[S1]`, `[S2]` có trong source_map | Rẻ, bắt được citation ảo cơ bản |
| Sentence-level citation | Mỗi câu factual phải có source | Tốt hơn nhưng prompt/parse phức tạp |
| Claim grounding | Trích claim rồi verify bằng retrieved chunks | Chính xác hơn, tốn thêm LLM/reranker |
| Human review | Sampling answer rủi ro cao | Chậm nhưng cần cho compliance |

Với capstone hoặc v1 production, regex + structured answer + regression tests là baseline hợp lý.

## 7. Signed URL Và Source Proxy

Citation link không nên là `s3://...`, path nội bộ hoặc URL wiki private. Có hai cách phổ biến:

| Cách | Khi dùng | Ghi chú |
|---|---|---|
| Signed URL | File object storage, PDF/image | TTL ngắn, bind theo user/tenant nếu có thể |
| Source proxy | Wiki, SharePoint, internal docs, redaction | Backend check permission mỗi lần mở |

Recommended flow:

```text
client click citation
  -> GET /api/rag/traces/{trace_id}/sources/{source_id}
  -> backend load source_map
  -> re-check user permission
  -> generate signed URL or proxy page snippet
  -> audit source_opened event
```

Điểm quan trọng: permission phải được check lại khi user mở citation, vì quyền có thể đã thay đổi sau lúc answer được tạo.

`source_map` chỉ là snapshot để trace answer, không phải authorization grant có hiệu lực mãi mãi. Endpoint mở source phải load trạng thái document/ACL hiện tại rồi mới tạo signed URL hoặc proxy nội dung.

## 8. Versioning, Tombstone Và Delete

RAG index dễ stale vì source document, ACL, chunking hoặc embedding có thể thay đổi độc lập.

Các version cần track:

- `document_version`: version của source document.
- `acl_version`: version permission tại thời điểm index.
- `chunking_version`: version parser/chunker.
- `embedding_model`: model tạo vector.
- `index_version`: batch/index release.
- `text_hash`: phát hiện duplicate hoặc content drift.

Delete path production:

```text
source delete event
  -> mark document/chunks as tombstone: deleted_at != null
  -> invalidate query/result cache
  -> remove chunks from vector index and BM25 index
  -> remove or revoke generated signed URLs
  -> write deletion audit event
  -> run verification job: deleted chunks not retrievable
```

Tombstone quan trọng vì physical delete thường async. Trong khoảng thời gian job xóa chưa xong, retriever vẫn phải bỏ qua chunk có `deleted_at`.

## 9. Audit Log

Audit log không chỉ để debug. Với enterprise RAG, audit log là cách chứng minh hệ thống đã enforce permission và citation đúng.

Một query trace nên log:

```json
{
  "trace_id": "trace_123",
  "timestamp": "2026-05-09T10:02:03Z",
  "user_id": "u123",
  "tenant_id": "company_a",
  "query_hash": "sha256:...",
  "query_redacted": "tôi còn bao nhiêu ngày nghỉ phép",
  "permission_snapshot": {
    "roles": ["employee"],
    "groups": ["engineering"],
    "acl_version": "acl-2026-05-09T10:00:00Z"
  },
  "retrieval": {
    "index_version": "rag-index-2026-05-09",
    "filters": ["tenant", "acl", "deleted_at"],
    "retrieved_chunk_ids": ["c1", "c2"],
    "post_filtered_chunk_ids": []
  },
  "context_source_ids": ["S1", "S2"],
  "citation_ids": ["S1"],
  "latency_ms": {
    "embedding": 45,
    "retrieval": 38,
    "rerank": 120,
    "llm": 1400
  }
}
```

Không log raw prompt chứa PII nếu không có redaction, retention policy và access control. Audit log cũng là sensitive data.

## 10. Regression Tests Bắt Buộc

Production RAG cần test như một data system:

- Cross-tenant: user tenant A không bao giờ retrieve chunk tenant B.
- Role/group ACL: user mất role thì chunk biến mất khỏi result.
- Missing ACL: chunk thiếu permission bị deny.
- Tombstone: chunk có `deleted_at` không vào candidate/context/citation.
- Stale ACL: cache permission hết hạn hoặc bị invalidate khi ACL đổi.
- Citation hallucination: answer cite `[S99]` bị reject.
- Source link: citation renderer không trả raw private URI.
- Reindex: không mix `document_version` cũ với mới trong cùng answer nếu policy không cho phép.
- Audit: trace có đủ `trace_id`, user, filters, chunk IDs, source IDs, index version.

Các test này nên nằm trong CI cho retriever/context builder, không chỉ test prompt.

## 11. Trade-off Quan Trọng

| Lựa chọn | Nên dùng khi | Không nên dùng khi | Production note |
|---|---|---|---|
| Document-level ACL | Permission đồng nhất trên cả document | Một document có section restricted | Đơn giản, dễ vận hành |
| Chunk-level ACL | Document có nhiều vùng visibility | Metadata pipeline chưa đáng tin | Chính xác hơn, tốn ops hơn |
| Pre-filter ACL | Security quan trọng | Vector DB filter quá yếu | Default cho tenant/ACL |
| Post-filter ACL | Defense-in-depth | Dùng một mình làm security | Bắt lỗi index/filter sai |
| Stable source ID | Cần deep link/bookmark lâu dài | Source đổi version liên tục | Cần version rõ |
| Per-response source ID | Dễ prompt model cite `[S1]` | Cần citation permanent | Tốt cho answer rendering |
| Signed URL | File source trong object storage | Cần redact dynamic theo user | TTL ngắn, audit click |
| Source proxy | Cần re-check permission/redaction | Latency cực chặt | An toàn hơn raw link |
| Async deletion | Corpus lớn, update nhiều | Legal delete cần immediate hard delete | Cần tombstone trước |
| Permission cache | Authz service chậm | ACL đổi rất thường xuyên | TTL ngắn + invalidation |

## 12. Performance Considerations

- Metadata filter có thể làm vector search chậm nếu field không được index.
- ACL list quá lớn làm query filter phình to; group-based ACL thường tốt hơn user list dài.
- Post-filter sau `top_k=5` có thể lọc hết kết quả; nên retrieve candidate lớn hơn, ví dụ 50-100, rồi rerank/lọc.
- Tenant partition giảm search space nhưng tăng số collection/index cần vận hành.
- Citation rendering có thể cần fetch metadata/document page; nên batch fetch và cache có TTL.
- Audit log nên ghi async qua queue, nhưng failure phải được monitor.
- Permission cache giảm latency nhưng tăng stale ACL risk.
- Delete/reindex jobs phải idempotent để retry an toàn.

## 13. Dùng Được Trong Production Không?

Có, nhưng chỉ khi xem RAG như một backend data system có security boundary rõ ràng, không phải chỉ là prompt engineering.

Điều kiện tối thiểu:

- Metadata schema có tenant, ACL, source, page/section, version, tombstone và index version.
- Permission được enforce ở backend/retriever trước khi context builder.
- Default deny khi metadata thiếu hoặc permission không xác định.
- Citation do backend cấp source ID, validate trước khi trả response.
- Source link đi qua signed URL hoặc proxy có re-check permission.
- Có tombstone/delete path, cache invalidation và verification job.
- Có audit log redacted và retention policy.
- Có regression tests cho cross-tenant leak, stale ACL, deleted document và citation ảo.
- Có monitoring latency, retrieval quality, citation invalid rate và permission denied rate.

Nếu thiếu các điều kiện trên, chỉ nên gọi là prototype/internal demo. Đặc biệt, một hệ thống đưa chunk không được phép vào prompt rồi yêu cầu LLM "đừng tiết lộ" là không đạt chuẩn production.

## Checklist Học Xong

- [ ] Giải thích được metadata contract trong RAG.
- [ ] Thiết kế được chunk schema có tenant, ACL, source, page, section, version.
- [ ] Phân biệt pre-filter và post-filter.
- [ ] Biết vì sao ACL phải enforce trước prompt.
- [ ] Thiết kế được `source_map` và citation object.
- [ ] Validate được citation ảo như `[S99]`.
- [ ] Biết dùng signed URL/proxy cho citation link.
- [ ] Thiết kế được tombstone/delete flow.
- [ ] Biết audit log cần field nào.
- [ ] Viết được regression tests cho permission-aware retrieval.

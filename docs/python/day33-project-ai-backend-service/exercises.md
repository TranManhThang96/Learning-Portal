# Bài Tập — Ngày 33: Project Thực Chiến — AI Backend Service

## Bài 1 — Setup Project & Docker Compose (Cơ bản)

**Mô tả:** Setup toàn bộ môi trường development cho AI Backend Service.

**Yêu cầu:**
1. Clone/copy project scaffold từ `day33-project-ai-backend-service/project/`
2. Tạo file `.env` từ `.env.example`, điền các giá trị cần thiết
3. Chạy `docker-compose up -d db redis qdrant` để start infrastructure
4. Kiểm tra các services đang chạy:
   - FastAPI: `http://localhost:8000/docs`
   - Qdrant: `http://localhost:6333/dashboard`
   - PostgreSQL: kết nối được qua psql hoặc DBeaver
5. Chạy Alembic migration: `uv run alembic upgrade head`
6. Test health check endpoint
7. Nếu chưa có OpenAI key, set `MOCK_AI=true` để smoke test wiring trước

**Expected output:**
```
$ docker-compose ps
NAME              STATUS
ai-api            Up (healthy)
ai-db             Up (healthy)
ai-redis          Up (healthy)
ai-qdrant         Up

$ curl http://localhost:8000/api/v1/health
{"status": "healthy", "services": {"db": "up", "redis": "up", "qdrant": "up"}}
```

**Hint:**
- Qdrant không cần authentication mặc định
- PostgreSQL connection string format: `postgresql+asyncpg://user:password@localhost:5432/dbname`
- Dùng `docker-compose logs api` để debug nếu API không start được

---

## Bài 2 — Implement Document Upload & RAG Query (Trung bình)

**Mô tả:** Implement flow upload document và chat với nội dung document đó.

**Yêu cầu:**
1. Implement endpoint `POST /api/v1/documents/upload` nhận file PDF hoặc TXT
2. Extract text từ file (dùng `pypdf` cho PDF, built-in cho TXT)
3. Gọi `rag_pipeline.ingest_document()` với content đã extract
4. Lưu metadata document vào PostgreSQL (bảng `documents`)
5. Test với một file TXT mẫu (bất kỳ nội dung gì)
6. Gọi streaming chat endpoint để hỏi về nội dung file đã upload

**Expected flow:**
```bash
# Upload document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@my_document.txt"
# Response: {"id": "uuid", "filename": "my_document.txt", "chunks": 15, "status": "ready"}

# Chat về document
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Tóm tắt nội dung document"}' \
  --no-buffer
# Response: data: {"chunk": "Theo", "done": false}
#           data: {"chunk": " nội dung...", "done": false}
#           data: {"chunk": "", "done": true}
```

**Hint:**
- Dùng `python-multipart` để xử lý file upload trong FastAPI
- `UploadFile` trong FastAPI là async — dùng `await file.read()`
- Text splitter nên overlap để tránh mất context ở ranh giới chunks
- Test SSE với `curl --no-buffer` hoặc dùng EventSource trong browser

---

## Bài 3 — Multi-Tenant Support (Nâng cao / Challenge)

**Mô tả:** Thêm multi-tenant support để mỗi user chỉ thấy/search documents của mình.

**Yêu cầu:**
1. Implement authentication flow hoàn chỉnh:
   - `POST /api/v1/auth/register` — đăng ký user mới
   - `POST /api/v1/auth/login` — đăng nhập, trả về JWT
   - FastAPI dependency `get_current_user` từ JWT token
2. Inject `current_user` vào tất cả endpoints cần authentication
3. Document ingestion: gán `user_id` vào metadata của mỗi chunk trong Qdrant
4. RAG query: filter theo `metadata.user_id` khi search Qdrant qua `QdrantVectorStore`
5. Verify isolation: user A không thể search thấy documents của user B
6. Implement `GET /api/v1/documents` — liệt kê documents của user hiện tại
7. Implement `DELETE /api/v1/documents/{id}` — xóa document và vectors tương ứng

**Expected behavior:**
```bash
# Đăng ký 2 users
curl -X POST http://localhost:8000/api/v1/auth/register \
  -d '{"email": "alice@test.com", "password": "secret123"}'

curl -X POST http://localhost:8000/api/v1/auth/register \
  -d '{"email": "bob@test.com", "password": "secret123"}'

# Alice upload document về Python
TOKEN_ALICE=$(curl -s -X POST .../auth/login -d '{"email":"alice@test.com",...}' | jq -r '.access_token')
curl -X POST .../documents/upload -H "Authorization: Bearer $TOKEN_ALICE" -F "file=@python_doc.txt"

# Bob hỏi về Python — KHÔNG thấy document của Alice
TOKEN_BOB=$(...)
curl -X POST .../chat/stream -H "Authorization: Bearer $TOKEN_BOB" \
  -d '{"question": "Python là gì?"}'
# Expected: Bot không có context về Python (vì document của Alice, không phải Bob)
```

**Bonus challenges:**
- Implement pagination cho `GET /api/v1/documents` với cursor-based pagination
- Thêm rate limiting per-user (mỗi user max 10 chat requests/phút)
- Cache responses trong Redis với key `{user_id}:{question_hash}`
- Thêm endpoint `POST /api/v1/documents/{id}/reprocess` để re-embed document

## 🔍 Gợi ý kiểm tra kết quả

### Kiểm tra Vector isolation
```python
# Script test isolation
import asyncio
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Search không có filter — thấy tất cả
all_results = client.search(
    collection_name="documents",
    query_vector=[0.1] * 1536,  # dummy vector
    limit=10,
)
print(f"Total vectors: {len(all_results)}")

# Search với filter theo user_id
alice_results = client.search(
    collection_name="documents",
    query_vector=[0.1] * 1536,
    query_filter={
        "must": [{"key": "metadata.user_id", "match": {"value": "alice_uuid"}}]
    },
    limit=10,
)
print(f"Alice's vectors: {len(alice_results)}")
```

### Kiểm tra rate limiting
```bash
# Gửi 11 requests liên tiếp
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/v1/chat/stream \
    -H "Content-Type: application/json" \
    -d '{"question": "test"}'
done
# Expect: 10 lần 200, lần 11: 429
```

### Performance benchmark
```bash
# Test streaming latency
time curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Tóm tắt nội dung chính"}' \
  --no-buffer -s > /dev/null
# Time to first token nên < 1 second
```

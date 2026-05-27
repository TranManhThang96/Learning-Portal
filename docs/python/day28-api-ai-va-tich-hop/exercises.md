# Bài Tập — Ngày 28: AI APIs & Integrations

## Bài 1 — Multi-Provider Text Analyzer (Cơ bản)

**Mô tả:** Xây dựng script gọi cùng một prompt lên cả Claude và Gemini, so sánh responses về chất lượng và tốc độ.

**Yêu cầu:**
1. Nhận text input từ user (hoặc hardcode đoạn văn tiếng Việt về một chủ đề bất kỳ)
2. Gọi cả Claude và Gemini với cùng system prompt: *"Bạn là content analyzer. Phân tích văn bản và trả về: 1) Tone (formal/casual/technical), 2) Chủ đề chính, 3) Độ phức tạp (1-10), 4) Tóm tắt 1 câu"*
3. Measure response time của mỗi provider bằng `time.time()`
4. Format kết quả side-by-side (cạnh nhau)
5. In ra provider nào nhanh hơn và đề xuất dùng provider nào cho use case này

**Expected output:**
```
Text analyzed: "Python được tạo ra bởi Guido van Rossum..."

┌─────────────────────────┬─────────────────────────┐
│ Claude (1.23s)          │ Gemini (0.87s)           │
├─────────────────────────┼─────────────────────────┤
│ Tone: Technical         │ Tone: Technical/formal   │
│ Topic: Python history   │ Topic: Python language   │
│ Complexity: 4/10        │ Complexity: 3/10         │
│ Summary: ...            │ Summary: ...             │
└─────────────────────────┴─────────────────────────┘

⚡ Gemini nhanh hơn 0.36s (29.3%)
💡 Recommendation: Dùng Gemini cho real-time use case này
```

**Hint:**
- Wrap API calls trong `try/except` để handle khi thiếu API key
- `time.time()` trước và sau API call để tính duration
- Format bảng bằng f-string với padding: `f"{text:<25}"` (left-align, 25 chars)
- Nếu không có API keys, dùng mock clients cho cả hai provider; test logic không được phụ thuộc API thật

---

## Bài 2 — Tool-Use Research Agent (Trung bình)

**Mô tả:** Xây dựng một research agent sử dụng Claude với tools để trả lời câu hỏi phức tạp cần nhiều bước.

**Yêu cầu:**
1. Implement ít nhất 4 tools sau:
   - `search_web(query: str) -> dict` — Mock: trả về fake search results
   - `get_current_time(timezone: str) -> dict` — Thật: dùng `datetime` và `pytz`
   - `calculate(expression: str) -> dict` — Thật: eval an toàn
   - `get_fact(topic: str) -> dict` — Mock: database facts về Python, AI, tech
2. Agent loop hoàn chỉnh: gửi tools → nhận tool_use → execute → gửi results → lặp
3. Log mỗi tool call với format: `[TOOL] get_current_time("Asia/Ho_Chi_Minh") → {"time": "14:32:05"}`
4. Track và in tổng số tool calls sau khi done
5. Handle edge case: nếu Claude loop quá 10 lần, break và trả về partial result

**Test queries:**
```python
queries = [
    "Bây giờ là mấy giờ ở Hà Nội và London?",
    "Tính: nếu tôi có 1000 USD và lãi suất 5%/năm, sau 3 năm tôi có bao nhiêu?",
    "Cho tôi biết một fact thú vị về Python và một fact về AI"
]
```

**Expected log:**
```
Query: "Bây giờ là mấy giờ ở Hà Nội và London?"

[TOOL] get_current_time("Asia/Ho_Chi_Minh") → {"time": "14:32:05", "timezone": "Asia/Ho_Chi_Minh"}
[TOOL] get_current_time("Europe/London") → {"time": "08:32:05", "timezone": "Europe/London"}

Agent: Hiện tại là 14:32 tại Hà Nội (UTC+7) và 08:32 tại London (UTC+0). Hà Nội sớm hơn London 7 giờ.

[Stats: 2 tool calls, 1 LLM round trips]
```

**Hint:**
- `uv add pytz` cho timezone
- `datetime.now(pytz.timezone(tz_name)).strftime("%H:%M:%S")` cho current time
- Mock `search_web` trả về list of dicts: `[{"title": "...", "snippet": "..."}]`
- Loop condition: `while response.stop_reason == "tool_use" and iteration < max_iterations`

---

## Bài 3 — Multimodal Document Processor (Nâng cao / Challenge)

**Mô tả:** Xây dựng pipeline xử lý document đa phương tiện: nhận file audio meeting → transcribe → tóm tắt → extract action items → export JSON.

**Yêu cầu:**

1. **Audio Transcription (mock hoặc thật):**
   - Nếu có Whisper: transcribe file MP3/WAV thật
   - Nếu không: dùng hardcoded mock transcript (đoạn text giả vờ là transcript cuộc họp)

2. **Structured Extraction với Claude:**
   - Parse transcript thành structured data
   - Extract: participants, topics, decisions, action_items (với assignee và deadline)
   - Dùng Claude để trả về **JSON** format thông qua system prompt

3. **Follow-up Questions:**
   - Sau khi có structured data, cho phép user hỏi follow-up về cuộc họp
   - Ví dụ: "Ai responsible cho database migration?" → tìm trong action items
   - Dùng conversation history để maintain context

4. **Export:**
   - Save kết quả ra file `meeting_summary.json`
   - Format đẹp (pretty-print JSON)

**Mock transcript để dùng:**
```python
MOCK_TRANSCRIPT = """
Speaker 1 (John): Okay everyone, let's start the Q4 planning meeting.
Speaker 2 (Sarah): Sure. First agenda item - we need to migrate our database to PostgreSQL by end of month.
Speaker 1 (John): I can handle that. Give me 2 weeks - should be done by November 15th.
Speaker 3 (Mike): I'll review the migration script. Can you send it to me by November 10th John?
Speaker 1 (John): Absolutely. Also, we decided last meeting to upgrade to Python 3.12. Any updates Sarah?
Speaker 2 (Sarah): I've tested it locally, no breaking changes. I'll update the CI pipeline by November 8th.
Speaker 1 (John): Great. Mike, what about the API documentation?
Speaker 3 (Mike): I'll have the first draft ready by November 20th. Using Sphinx.
Speaker 2 (Sarah): One more thing - we're moving our standup to 9am starting next Monday.
Speaker 1 (John): Agreed. Anything else? No? Okay, meeting adjourned.
"""
```

**Expected JSON output:**
```json
{
  "meeting_date": "unknown",
  "participants": ["John", "Sarah", "Mike"],
  "topics": ["Database migration to PostgreSQL", "Python 3.12 upgrade", "API documentation"],
  "decisions": [
    "Migrate database to PostgreSQL by end of month",
    "Upgrade to Python 3.12",
    "Move standup to 9am starting next Monday"
  ],
  "action_items": [
    {"task": "Database migration", "assignee": "John", "deadline": "November 15"},
    {"task": "Review migration script", "assignee": "Mike", "deadline": "November 10"},
    {"task": "Update CI pipeline for Python 3.12", "assignee": "Sarah", "deadline": "November 8"},
    {"task": "Write API documentation", "assignee": "Mike", "deadline": "November 20"}
  ]
}
```

**Hint:**
- System prompt: *"Extract meeting information and return ONLY valid JSON with keys: participants, topics, decisions, action_items"*
- Parse JSON response: `json.loads(claude_response)` — handle JSONDecodeError nếu Claude trả về text khác
- For follow-up: giữ original transcript + structured JSON trong context
- `json.dump(data, f, indent=2, ensure_ascii=False)` để save tiếng Việt đúng

---

## 🔍 Gợi ý kiểm tra kết quả

**Bài 1:**
- Chạy với text tiếng Anh và tiếng Việt, kết quả có khác nhau không?
- Mock provider thứ 2 nếu không có API key: trả về dict cố định với delay giả lập
- Unit test provider comparison bằng `FakeProvider` thay vì gọi Claude/Gemini thật

**Bài 2:**
- Test với query cần nhiều tool calls (ví dụ: "So sánh giờ ở 3 thành phố khác nhau")
- Test max_iterations protection: tạo tool luôn trả về partial info để Claude loop mãi
- Verify tool logging đúng format

**Bài 3:**
- JSON output phải valid (dùng `json.loads()` để verify)
- Follow-up question phải answer dựa vào context, không phải knowledge cutoff
- Test follow-up: "Khi nào meeting kết thúc?" → nên trả lời không biết (không có trong transcript)

**Environment check:**
```bash
# Test Claude
python -c "import anthropic; print('Claude SDK OK')"
echo $ANTHROPIC_API_KEY | head -c 10

# Test Gemini
python -c "from google import genai; print('Gemini GenAI SDK OK')"
echo ${GEMINI_API_KEY:-$GOOGLE_API_KEY} | head -c 10

# Test Whisper (optional)
python -c "import whisper; print('Whisper OK')"
```

# Bài Tập — Ngày 24: LangGraph & Agentic Workflows

## Bài 1 — Code Review Agent (Cơ bản)

**Mô tả:** Xây dựng một LangGraph workflow để automatically review code, đưa ra feedback, và iteratively improve code cho đến khi đạt chất lượng chấp nhận được.

**Yêu cầu:**
1. Define `CodeReviewState` với các fields: `code`, `language`, `review_feedback`, `revision_count`, `quality_score` (0-10), `final_code`
2. Implement 3 nodes:
   - `analyze_code`: LLM analyze code, trả về list issues và quality score
   - `improve_code`: LLM rewrite code dựa trên feedback
   - `finalize`: Format final output
3. Conditional routing: nếu `quality_score >= 7` hoặc `revision_count >= 3` → finalize, còn lại → improve
4. Test với đoạn code Python có ít nhất 5 issues (không có type hints, no error handling, bad naming...)

**Expected output:**
```
=== Code Review Workflow ===

Input code:
def calc(x,y,z):
    result = x+y
    return result/z

[Iteration 1]
Quality score: 3/10
Issues found:
  - Missing type hints
  - No error handling for division by zero
  - Poor function naming
  - Missing docstring
  - Unused parameter z in addition

[Iteration 2]
Quality score: 6/10
Issues found:
  - Docstring incomplete
  - Should use more descriptive variable names

[Iteration 3]
Quality score: 8/10 ✓ (threshold met)
→ Moving to finalize

=== FINAL CODE ===
def calculate_weighted_sum(x: float, y: float, divisor: float) -> float:
    """
    Calculate the sum of x and y, then divide by divisor.
    ...
    """
    # [improved code...]

Total revisions: 2
Final quality score: 8/10
```

**Hint:**
- Dùng `TypedDict` cho state definition
- Parse quality score từ LLM response bằng regex: `re.search(r'SCORE:\s*(\d+)', response)`
- Guard condition: `if revision_count >= 3: return "finalize"` để tránh infinite loop
- `add_messages` reducer cho messages list

---

## Bài 2 — Data Pipeline với Human Approval (Trung bình)

**Mô tả:** Xây dựng một ETL pipeline agent với human-in-the-loop cho các operations có risk cao, và đầy đủ checkpointing.

**Yêu cầu:**

**Phần A — Pipeline Nodes:**
1. `extract_node`: "Extract" data từ source (simulate với fake data)
2. `validate_node`: Validate data quality, tính quality metrics
3. `transform_node`: Transform data theo business rules
4. `risk_assessment_node`: Assess risk của load operation (dựa trên data size, type, destination)
5. `human_approval_node`: Nếu risk > threshold → interrupt và chờ approval
6. `load_node`: Simulate loading data
7. `report_node`: Generate execution report

**Phần B — Risk Matrix:**
```
Risk = LOW nếu: records < 100 AND destination = "staging"
Risk = MEDIUM nếu: records 100-1000 OR destination = "staging_prod"
Risk = HIGH nếu: records > 1000 OR destination = "production"
```
- LOW → auto-proceed
- MEDIUM → human approval required
- HIGH → human approval + additional confirmation phrase

**Phần C — Checkpointing:**
1. Dùng `InMemorySaver()` hoặc `MemorySaver()` theo LangGraph version pin cho checkpointing
2. Implement function `resume_pipeline(thread_id, decision)` để resume từ interrupt
3. In ra checkpoint history sau khi workflow complete
4. Lưu ý lifecycle: cùng compiled app/checkpointer và cùng `thread_id` phải được dùng khi resume; nếu app restart, dùng persistent checkpointer như SQLite/Postgres thay vì MemorySaver
5. Thêm guard: `recursion_limit`, max tool/LLM calls, và timeout cho mỗi operation

**Expected output:**
```
=== Data Pipeline: Customer Update Job ===
Thread ID: pipeline_20240115_001

[Extract] Loaded 850 records from source
[Validate] Quality score: 94.2% (pass)
  - Null values: 12 (1.4%)
  - Format errors: 2 (0.2%)
[Transform] Applied 3 business rules, 850 records processed
[Risk Assessment] Risk: MEDIUM
  - Record count: 850 (threshold: 100-1000)
  - Destination: staging_prod

⚠️  HUMAN APPROVAL REQUIRED
Action: Load 850 transformed records to staging_prod
Risk level: MEDIUM
Quality score: 94.2%

[Workflow paused — Thread: pipeline_20240115_001]
[Simulating human approval: APPROVED]

[Resume: pipeline_20240115_001]
[Load] Successfully loaded 850 records to staging_prod
[Report] Pipeline execution complete

=== Execution Report ===
Duration: 2.34s
Records processed: 850
Risk level: MEDIUM
Approval: Human approved at 14:23:07
Status: SUCCESS

Checkpoint history: 7 snapshots
```

**Hint:**
- `interrupt({"prompt": "...", "data": {...}})` để pause
- `Command(resume={"approved": True, "confirmation": "CONFIRM_PRODUCTION"})` để resume
- `app.get_state_history(config)` để view checkpoint history
- Check interrupt bằng `result.interrupts` khi dùng `version="v2"`; nếu version cũ trả dict thì dùng `result.get("__interrupt__", [])`. Resume với `Command(resume=...)` và cùng `configurable.thread_id`
- Risk thresholds: kiểm tra cả `record_count` và `destination` trong routing function

---

## Bài 3 — Multi-Step Research Agent với Parallel Execution (Nâng cao / Challenge)

**Mô tả:** Xây dựng một research agent phức tạp có khả năng: parallel research từ nhiều "sources", iterative refinement, human review checkpoint, và comprehensive reporting.

**Yêu cầu:**

**Phần A — Graph Architecture:**
```
START
  │
  ▼
[query_analysis]  ← Phân tích query, xác định subtopics
  │
  ├──────────────────────────────────┐
  ▼                                  ▼
[research_subtopic_1]    [research_subtopic_2]    ← Parallel!
  │                                  │
  └──────────────┬───────────────────┘
                 ▼
         [aggregate_research]  ← Fan-in: merge results
                 │
                 ▼
           [draft_report]
                 │
                 ▼
         [quality_check]
                 │
         ┌───────┴───────┐
         ▼               ▼
    [human_review]   [auto_approve]  ← Based on quality score
         │               │
         └───────┬───────┘
                 ▼
         [generate_report]
                 │
                 ▼
               END
```

**Phần B — State Design:**
```python
class ResearchState(TypedDict):
    original_query: str
    subtopics: list[str]              # Generated by query_analysis
    research_by_subtopic: dict        # {subtopic: research_content}
    aggregated_research: str
    draft_report: str
    quality_score: float              # 0.0 - 1.0
    human_feedback: str               # From human review
    final_report: str
    metadata: dict                    # timing, word counts, etc.
```

**Phần C — Features cần implement:**
1. `query_analysis_node`: Dùng LLM để identify 2-3 subtopics từ original query
2. Dynamic fan-out: tạo research node cho MỖI subtopic (không hardcode)
3. `aggregate_node`: Merge tất cả subtopic research thành coherent summary
4. `quality_check_node`: Score report quality (0-1). Score >= 0.75 → auto_approve, < 0.75 → human_review
5. `human_review_node`: Interrupt, collect feedback, incorporate feedback vào report
6. Timing metadata: track thời gian mỗi node

**Phần D — Visualization:**
In ra graph execution summary:
```
=== Graph Execution Summary ===
Query: "Compare Python, Node.js, and Go for microservices"
Subtopics identified: ["Python microservices", "Node.js microservices", "Go microservices"]

Execution timeline:
  query_analysis:        0.00s - 0.87s  (0.87s)
  research_python:       0.87s - 2.34s  (1.47s) [PARALLEL]
  research_nodejs:       0.87s - 2.01s  (1.14s) [PARALLEL]
  research_go:           0.87s - 2.18s  (1.31s) [PARALLEL]
  aggregate_research:    2.34s - 3.12s  (0.78s)
  draft_report:          3.12s - 4.89s  (1.77s)
  quality_check:         4.89s - 5.23s  (0.34s)
  [human_review]:        5.23s - ?      (waiting...)
  generate_report:       ...

Quality score: 0.72 → human review required
Human feedback: "Add more concrete performance benchmarks"
Final quality score: 0.89 (after incorporating feedback)

Total time: 8.45s (parallel research saved ~2.3s vs sequential)
Final report: 847 words
```

**Hint:**
- Dynamic fan-out: tạo nodes trong loop, `graph.add_node(f"research_{topic}", make_research_fn(topic))`
- Closure pattern để capture subtopic: `def make_research_fn(topic): return lambda state: research(state, topic)`
- `operator.add` reducer để merge list results từ parallel nodes
- Parallel tier chỉ nên chứa tasks độc lập; nếu các branch update cùng field, dùng reducer rõ ràng thay vì overwrite
- `app.get_state(config).next` để check pending nodes
- `time.perf_counter()` và metadata dict để track timing

---

## 🔍 Gợi ý kiểm tra kết quả

### Checklist Bài 1:
- [ ] Quality score được parse đúng từ LLM response (test với mock response)
- [ ] Max revisions (3) được enforce — không có infinite loop
- [ ] `recursion_limit` hoặc max iteration guard được set khi invoke graph
- [ ] Có token/cost guard đơn giản cho số LLM/tool calls
- [ ] Code thực sự improve qua từng revision (chạy và check output)
- [ ] State transition đúng: analyze → improve → analyze (cycle) → finalize

### Checklist Bài 2:
- [ ] Risk assessment đúng với risk matrix (test edge cases: 100 records, 1001 records)
- [ ] Interrupt hoạt động đúng — workflow dừng lại tại human_approval_node
- [ ] Resume với `Command(resume=...)` tiếp tục từ đúng điểm
- [ ] Resume dùng đúng `thread_id` và checkpointer còn sống/persistent
- [ ] Checkpoint history có đủ snapshots (mỗi node = 1 snapshot)
- [ ] Thread IDs khác nhau cho các runs khác nhau

### Checklist Bài 3:
- [ ] Parallel execution xác nhận bằng timing (research nodes chạy concurrently)
- [ ] Dynamic fan-out hoạt động với số subtopics bất kỳ (2, 3, 4 subtopics)
- [ ] Fan-in aggregate đúng kết quả từ tất cả parallel branches
- [ ] Human review properly incorporates feedback vào final report
- [ ] Timing metadata chính xác

### Debug Snippets:
```python
# Visualize graph structure
from IPython.display import Image, display
try:
    display(Image(app.get_graph().draw_mermaid_png()))
except Exception:
    # ASCII fallback
    print(app.get_graph().draw_ascii())

# Debug node execution order
for event in app.stream(initial_state, stream_mode="updates"):
    for node_name, node_output in event.items():
        print(f"Node executed: {node_name}")
        print(f"  Output keys: {list(node_output.keys())}")

# Check if workflow hit interrupt
state = app.get_state(config)
print(f"Next nodes: {state.next}")  # Empty if finished, has value if interrupted
print(f"Pending tasks: {state.tasks}")
```

# Bài Tập — Ngày 25: Multi-Agent Systems

> **Primary lab cho ngày này:** Hoàn thành Bài 1 end-to-end. Bài 2 là optional extension nếu còn thời gian. Bài 3 là optional challenge/reference cho cuối tuần hoặc project day, không kỳ vọng hoàn tất trong 2 giờ.

## Bài 1 — Tool Design Workshop (Primary Lab / Cơ bản)

**Mô tả:** Thiết kế và implement một bộ tools theo đúng best practices, sau đó test với một ReAct agent để verify tools hoạt động đúng như mong đợi.

**Yêu cầu:**

**Phần A — Implement 4 tools theo chuẩn:**
1. `get_stock_price(symbol: str, exchange: str = "HOSE")` — Lấy giá cổ phiếu (simulate)
2. `calculate_portfolio_value(holdings: dict[str, int], prices: dict[str, float])` — Tính tổng giá trị portfolio
3. `search_company_news(company_name: str, max_results: int = 5)` — Tìm tin tức về công ty
4. `generate_investment_report(portfolio_analysis: str, market_context: str)` — Tạo báo cáo đầu tư

Mỗi tool phải có:
- Pydantic `BaseModel` làm `args_schema`
- Docstring đầy đủ với "Use for", "Do NOT use for", "Returns"
- Input validation với raise ValueError nếu input invalid
- Error handling với try/except, trả về error string (không raise)

**Phần B — Bad Tool Anti-patterns:**
Implement 2 versions của một tool: một "bad" và một "good", giải thích sự khác biệt:
```python
@tool
def bad_get_data(x: str) -> str:  # Bad version
    """Gets data"""
    return "data"

@tool
def good_get_stock_price(symbol: str, exchange: str = "HOSE") -> str:  # Good version
    """..."""  # Full docstring
```

**Phần C — Agent Test:**
1. Create một ReAct agent với tất cả 4 tools
2. Test với 3 queries:
   - "VCB đang ở giá bao nhiêu?"
   - "Portfolio của tôi có VCB 100 cổ, FPT 50 cổ, VNM 200 cổ. Tổng giá trị là bao nhiêu?"
   - "Phân tích và tạo báo cáo đầu tư cho portfolio trên"
3. Verify agent chọn đúng tool cho từng query
4. Thêm guard bắt buộc:
   - `max_agent_steps = 6`
   - output token cap cho LLM/agent
   - timeout cho tool có I/O
   - rate limiter đơn giản nếu nhiều tool cùng gọi API giả lập

**Expected output:**
```
=== Tool Registry ===
Tools registered: 4
  data_retrieval:
    - get_stock_price: Get current stock price for a Vietnamese stock symbol
    - calculate_portfolio_value: Calculate total portfolio value given holdings
  research:
    - search_company_news: Search recent news articles about a company
  output:
    - generate_investment_report: Generate formatted investment analysis report

=== Agent Test ===

Query: "VCB đang ở giá bao nhiêu?"
Tool called: get_stock_price(symbol="VCB", exchange="HOSE")
Result: VCB (HOSE): 85,400 VND (+1.2% today)
Answer: "Cổ phiếu VCB hiện đang ở mức 85,400 VND..."

Query: "Portfolio... Tổng giá trị?"
Tool calls:
  1. get_stock_price("VCB") → 85,400
  2. get_stock_price("FPT") → 125,600
  3. get_stock_price("VNM") → 62,300
  4. calculate_portfolio_value({...}, {...}) → 22,175,000 VND
Answer: "Tổng giá trị portfolio: 22,175,000 VND..."

Query: "Phân tích và tạo báo cáo..."
Tool calls:
  1. search_company_news("VCB") → [news...]
  2. search_company_news("FPT") → [news...]
  3. generate_investment_report(...) → [report]
Answer: [Formatted report...]
```

**Hint:**
- `from langchain_core.tools import tool, StructuredTool`
- `from pydantic import BaseModel, Field, field_validator`
- `@field_validator('symbol')` để validate trong Pydantic model
- `create_react_agent(llm, tools=[...])` để xem tool selection; tham số prompt có thể là `prompt` hoặc `state_modifier` tùy LangGraph version pin
- Track token budget đơn giản bằng `estimated_tokens += len(text) // 4`; production dùng usage metadata từ provider

---

## Bài 2 — Orchestrator / Sub-Agent System (Optional Extension / Trung bình)

**Mô tả:** Xây dựng một content creation multi-agent system với orchestrator điều phối các sub-agents chuyên biệt.

**Yêu cầu:**

**Architecture:**
```
User Request
     │
     ▼
[Orchestrator]  ← Analyze request, plan workflow
     │
     ├──→ [Research Agent]    ← Gather facts và data
     │         ↓ (kết quả)
     ├──→ [Writing Agent]     ← Draft content
     │         ↓ (kết quả)
     ├──→ [SEO Agent]         ← Optimize cho search
     │         ↓ (kết quả)
     ├──→ [Fact-Check Agent]  ← Verify accuracy
     │         ↓ (kết quả)
     └──→ [Finalize]          ← Orchestrator assembles final
```

**State Design:**
```python
class ContentState(TypedDict):
    user_request: str        # Original request
    content_type: str        # blog_post, social_media, technical_doc
    target_audience: str     # Ai sẽ đọc
    research_data: str       # Research agent output
    draft_content: str       # Writing agent output
    seo_suggestions: str     # SEO agent output
    fact_check_results: str  # Fact-check agent output
    final_content: str       # Assembled final
    workflow_log: list[str]  # Track which agents ran và khi nào
    quality_scores: dict     # Score từ mỗi agent
```

**Sub-Agents:**
Mỗi sub-agent là một `create_react_agent` với tools riêng:
- Research Agent: tools `search_web`, `summarize_sources`
- Writing Agent: tools `draft_content`, `improve_readability`
- SEO Agent: tools `extract_keywords`, `suggest_headings`
- Fact-Check Agent: tools `verify_claim`, `find_sources`

**Orchestrator Logic:**
1. Analyze request → determine `content_type` và `target_audience`
2. Sequence agents dựa trên content type:
   - `blog_post`: Research → Write → SEO → Fact-Check
   - `social_media`: Research → Write → SEO (skip fact-check)
   - `technical_doc`: Research → Fact-Check → Write (fact-check trước)
3. Sau mỗi agent, Orchestrator đánh giá quality (1-10)
4. Nếu quality < 6 → agent phải redo (với feedback)
5. Assemble final content từ tất cả agent outputs
6. Budget/rate guards:
   - `max_total_agent_steps = 10`
   - `max_retries_per_step = 2`
   - `max_estimated_tokens = 20_000`
   - shared semaphore/queue cho mọi tool search/API
   - stop workflow với partial result nếu budget vượt ngưỡng

**Expected output:**
```
=== Content Creation System ===
Request: "Write a blog post about Python vs NodeJS for backend development"
Content type: blog_post
Target audience: senior developers

Workflow plan: research → writing → seo → fact_check

[Step 1/4] Research Agent
  Tools used: search_web (3x), summarize_sources (1x)
  Quality score: 8/10 ✓
  Output: 450 words of research data

[Step 2/4] Writing Agent
  Tools used: draft_content (1x)
  Quality score: 5/10 ✗ (too generic)
  → Redo requested with feedback: "Be more specific, add benchmarks"
  Tools used: draft_content (1x), improve_readability (1x)
  Quality score: 7/10 ✓

[Step 3/4] SEO Agent
  Tools used: extract_keywords (1x), suggest_headings (1x)
  Quality score: 9/10 ✓
  Keywords: python, nodejs, backend, performance, comparison

[Step 4/4] Fact-Check Agent
  Tools used: verify_claim (4x)
  Quality score: 8/10 ✓
  Claims verified: 4/4 accurate

=== FINAL CONTENT ===
Word count: 1,247
Quality scores: Research=8, Writing=7, SEO=9, FactCheck=8
Overall: 8.0/10
[Blog post content...]
```

**Hint:**
- Orchestrator state có `current_step` và `max_retries_per_step`
- Thêm `agent_step_count`, `estimated_tokens`, `budget_exceeded` vào state
- Quality assessment: `llm.invoke([HumanMessage(content="Rate this output 1-10: {output}. Return only a number.")])`
- Workflow log: append `f"{agent_name}: {timestamp}: {action}"` vào list
- Parse content_type từ LLM response với fallback: `if "blog" in response: type = "blog_post"`

---

## Bài 3 — Resilient Parallel Research Network (Optional Challenge)

**Mô tả:** Xây dựng một multi-agent research network hoàn chỉnh với parallel execution, circuit breakers, self-healing, và comprehensive monitoring.

**Yêu cầu:**

**Phần A — Research Network Architecture:**
```
                    [Controller Agent]
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    [Primary Search]  [Academic]  [News Aggregator]  ← Parallel tier 1
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  [Synthesis Agent]
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    [Fact Checker]  [Bias Detector]  [Quality Scorer]  ← Parallel tier 2
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  [Final Assembler]
```

**Phần B — Resilience Features:**
Implement tất cả 4 resilience patterns:

1. **Retry với Exponential Backoff:**
```python
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 30.0
    jitter: bool = True  # Add random jitter để tránh thundering herd
```

2. **Circuit Breaker per Agent:**
```python
# Mỗi agent có circuit breaker riêng
circuit_breakers = {
    "primary_search": CircuitBreaker(failure_threshold=3),
    "academic": CircuitBreaker(failure_threshold=2),
    "news": CircuitBreaker(failure_threshold=3),
}
```

3. **Fallback Hierarchy:**
```
primary_search fails → academic_search → news_search → cached_results → "No data available"
```

4. **Self-Healing:** Nếu Tier 1 không đủ dữ liệu (< 200 words) → automatically spawn thêm research agents
   - Chỉ spawn đến `max_extra_agents = 2`
   - Không spawn nếu token/cost budget đã vượt 80%

**Phần C — Monitoring Dashboard:**
Implement `AgentMonitor` class track:
```python
class AgentMonitor:
    def record_call(self, agent_name: str, success: bool, latency: float, tokens_used: int)
    def get_dashboard(self) -> str:
        # Print summary:
        # - Total calls per agent
        # - Success rate per agent
        # - Avg/P95 latency per agent
        # - Total tokens used
        # - Circuit breaker states
        # - Fallback usage rate
```

**Phần D — Benchmark:**
Run research network 3 lần với:
1. Normal conditions (no failures)
2. High failure rate (40% của search calls fail)
3. Simulated outage (một agent hoàn toàn down)

So sánh:
- Thời gian hoàn thành
- Data quality (word count của synthesis)
- Fallback usage rate
- Cost (estimated tokens)
- Rate-limit hits / queued calls

**Expected output:**
```
=== Resilient Research Network ===
Topic: "Quantum computing applications in cybersecurity"

=== Benchmark Results ===

Scenario 1: Normal conditions
  Wall time: 4.23s
  Parallel tier 1: 3.12s (3 agents concurrent)
  Parallel tier 2: 1.89s (3 agents concurrent)
  Synthesis words: 847
  Fallback usage: 0%
  Estimated tokens: 4,230

Scenario 2: 40% failure rate
  Wall time: 6.78s (+60%)
  Retries triggered: 7
  Circuit breakers tripped: 0 (not enough failures)
  Fallbacks used: 2/3 search agents
  Synthesis words: 694 (-18% quality degradation)
  Estimated tokens: 5,890 (+39% due to retries)

Scenario 3: Academic agent down
  Wall time: 5.12s (+21%)
  Academic agent: CIRCUIT OPEN after 2 failures
  Fallback: news_search used instead
  Self-healing triggered: Yes (insufficient data from tier 1 → spawned extra research)
  Synthesis words: 789 (-7%)
  Recovery time: 2.3s

=== Agent Monitor Dashboard ===
Agent           | Calls | Success | Avg Latency | P95   | Tokens | Fallback
----------------|-------|---------|-------------|-------|--------|--------
primary_search  |    9  |  78%    |    1.23s    | 2.1s  | 1,240  |  22%
academic        |    9  |  55%    |    0.98s    | 2.4s  |   890  |  45%
news_aggregator |    9  |  89%    |    1.45s    | 2.8s  | 1,120  |  11%
synthesis       |    3  | 100%    |    2.34s    | 2.8s  | 2,340  |   0%
fact_checker    |    9  | 100%    |    0.67s    | 0.9s  |   560  |   0%

Circuit Breaker States:
  primary_search: CLOSED
  academic: HALF_OPEN (testing recovery)
  news_aggregator: CLOSED
```

**Hint:**
- `random.random() < failure_rate` để simulate failures
- Jitter: `delay = base_delay + random.uniform(0, base_delay * 0.1)`
- P95 latency: `sorted(latencies)[int(len(latencies) * 0.95)]`
- Monitor: dùng `collections.defaultdict(list)` để accumulate metrics
- Self-healing: check `len(synthesis_draft.split()) < 200` sau Tier 1
- Cost guard: stop benchmark scenario nếu `estimated_tokens > max_estimated_tokens` và ghi rõ partial result

---

## 🔍 Gợi ý kiểm tra kết quả

### Checklist Bài 1:
- [ ] Mỗi tool có Pydantic schema (không phải chỉ type hints)
- [ ] Docstring có "Use for" và "Do NOT use for" sections
- [ ] Input validation raise ValueError với clear message
- [ ] Error handling return error string (không raise)
- [ ] Agent chọn đúng tool cho mỗi query (verify bằng logs/tracing hoặc stream events theo version)
- [ ] Có max step/token/timeout/rate guard tối thiểu
- [ ] Bad vs Good tool comparison rõ ràng sự khác biệt

### Checklist Bài 2:
- [ ] Orchestrator xác định đúng content_type từ request
- [ ] Workflow sequence khác nhau cho mỗi content_type
- [ ] Redo logic hoạt động khi quality < 6 (test với forcing low quality)
- [ ] Workflow log có timestamps và actions
- [ ] Final content assembled từ tất cả agent outputs
- [ ] Budget exceeded path dừng workflow và trả partial result rõ ràng

### Checklist Bài 3:
- [ ] Parallel execution xác nhận bằng timing (tier 1 và tier 2 chạy parallel)
- [ ] Circuit breaker đổi state đúng (CLOSED → OPEN → HALF_OPEN)
- [ ] Fallback hierarchy hoạt động đúng thứ tự
- [ ] Self-healing trigger khi data < threshold
- [ ] Monitor dashboard hiển thị tất cả metrics
- [ ] Benchmark so sánh 3 scenarios với real numbers
- [ ] Token/cost guard và rate-limit metrics xuất hiện trong benchmark

### Debug Snippets:
```python
# Test circuit breaker state machine
cb = CircuitBreaker(failure_threshold=3)
print(f"Initial: {cb.state}")  # CLOSED

for i in range(3):
    cb.record_failure()
    print(f"After failure {i+1}: {cb.state}")
# Expected: CLOSED, CLOSED, OPEN

print(f"Can execute: {cb.can_execute()}")  # False

# Test retry với backoff
import time

def flaky_function():
    if random.random() < 0.7:
        raise Exception("Service unavailable")
    return "success"

try:
    result = with_retry(flaky_function, max_retries=5)
    print(f"Result: {result}")
except RuntimeError as e:
    print(f"All retries failed: {e}")

# Verify parallel execution timing
import asyncio

async def time_parallel_agents():
    start = time.perf_counter()
    # If agents truly run in parallel, total time ≈ max(individual times)
    # If sequential, total time ≈ sum(individual times)
    results = await asyncio.gather(
        async_research_agent_1(),
        async_research_agent_2(),
        async_research_agent_3(),
    )
    total = time.perf_counter() - start
    print(f"Total: {total:.2f}s (should be ~max of individual times, not sum)")
```

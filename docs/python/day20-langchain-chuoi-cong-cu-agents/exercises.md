# Bài Tập — Ngày 20: LangChain — Chains, Tools & Agents

## Bài 1 — Developer Toolkit Agent (Cơ bản)

**Mô tả:**
Xây dựng agent đóng vai "Developer Assistant" với bộ tools hữu ích cho NodeJS-to-Python migration.

**Yêu cầu:**

**Bước 1 — Tạo ít nhất 4 tools:**

```python
@tool
def convert_js_to_python_syntax(js_snippet: str) -> str:
    """
    Gợi ý chuyển đổi JavaScript/TypeScript syntax sang Python equivalent.
    Xử lý: arrow functions, destructuring, ternary, template literals, etc.
    Không cần LLM trong tool này — dùng rule-based conversion.
    """
    # Hint: dùng string replacements + regex
    # js: "const x = arr.filter(i => i > 0)"
    # py: "x = [i for i in arr if i > 0]"
    ...

@tool
def check_python_syntax(code: str) -> str:
    """
    Kiểm tra Python code syntax có lỗi không.
    Trả về: 'Valid' hoặc mô tả lỗi cụ thể với line number.
    """
    import ast
    try:
        ast.parse(code)
        return "Valid Python syntax"
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"

@tool
def estimate_code_complexity(code: str) -> str:
    """
    Đánh giá độ phức tạp code: Simple/Medium/Complex.
    Dựa trên: số dòng, số functions, nested loops, conditions.
    """
    ...

@tool
def lookup_python_builtin(function_name: str) -> str:
    """
    Tra cứu Python built-in functions và common stdlib.
    Ví dụ: map, filter, zip, enumerate, sorted, any, all.
    Trả về: signature + mô tả ngắn + example.
    """
    builtins_info = {
        "map": "map(func, iterable) -> Returns iterator. Example: list(map(str, [1,2,3])) = ['1','2','3']",
        "filter": "filter(func, iterable) -> Returns iterator. Example: list(filter(lambda x: x>0, [-1,0,1])) = [1]",
        "zip": "zip(*iterables) -> Pairs items. Example: list(zip([1,2], ['a','b'])) = [(1,'a'),(2,'b')]",
        "enumerate": "enumerate(iterable, start=0) -> (index, value) pairs. Example: list(enumerate(['a','b'])) = [(0,'a'),(1,'b')]",
        "sorted": "sorted(iterable, key=None, reverse=False) -> new sorted list",
        "any": "any(iterable) -> True if any element is truthy. Like: arr.some(Boolean) in JS",
        "all": "all(iterable) -> True if all elements truthy. Like: arr.every(Boolean) in JS",
    }
    return builtins_info.get(function_name.lower(), f"Not found: {function_name}. Try: map, filter, zip, enumerate, sorted, any, all")
```

**Bước 2 — Tạo agent với system prompt phù hợp:**
- System: "Bạn là Developer Assistant giúp NodeJS developers chuyển đổi sang Python"
- Agent nên proactively dùng tools để provide helpful responses

**Bước 3 — Test với các queries sau:**
```python
test_queries = [
    "Kiểm tra syntax của đoạn code này: def hello world(): print('hi')",
    "Python có hàm gì tương đương Array.some() và Array.every() của JavaScript?",
    "Giúp tôi chuyển đổi: const result = arr.filter(x => x > 0).map(x => x * 2)",
]
```

**Expected output mẫu:**
```
Query: "Kiểm tra syntax..."
[Agent thinking] → calls check_python_syntax
[Tool result] SyntaxError at line 1: invalid syntax
[Agent response] Code của bạn có lỗi: thiếu dấu gạch dưới trong tên function.
                 Đúng phải là: def hello_world():

Query: "Python có hàm gì tương đương..."
[Agent thinking] → calls lookup_python_builtin("any"), lookup_python_builtin("all")
[Agent response] Python có any() và all()...
```

**Hint:**
- Dùng `create_agent(model="openai:gpt-5", tools=[...], system_prompt=...)` cho path chính của LangChain v1
- Chỉ dùng `create_react_agent(llm, tools, prompt=system_prompt)` khi bạn muốn luyện thêm LangGraph
- Tools nên return string (kể cả khi có lỗi)
- Test tools riêng trước: `my_tool.invoke({"arg": "value"})`

---

## Bài 2 — Monitoring Dashboard với Callbacks (Trung bình)

**Mô tả:**
Xây dựng comprehensive monitoring system cho LangChain application, tracking cost, latency, và quality metrics.

**Yêu cầu:**

**Bước 1 — Build `CostTrackingCallback`:**
```python
class CostTrackingCallback(BaseCallbackHandler):
    """
    Track token usage và optional cost theo pricing config.
    """
    def __init__(self, pricing_per_token: dict[str, dict[str, float]] | None = None):
        # Inject từ config cập nhật theo pricing page; không hardcode giá trong source.
        self.pricing_per_token = pricing_per_token or {}
        self.total_cost_usd = 0.0
        self.calls = []

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        # Extract: model name, input tokens, output tokens
        # Nếu có pricing_per_token cho model thì calculate cost
        # Append to self.calls
        ...

    def get_cost_report(self) -> str:
        """Trả về formatted cost report"""
        ...
```

**Bước 2 — Build `LatencyTracker`:**
```python
class LatencyTracker(BaseCallbackHandler):
    """
    Track P50, P90, P99 latency cho LLM calls.
    Giống metrics trong Prometheus/Datadog.
    """
    def __init__(self):
        self.latencies: list = []

    def get_percentile(self, p: float) -> float:
        """Tính percentile latency. p: 50.0, 90.0, 99.0"""
        import statistics
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * p / 100)
        return sorted_latencies[min(index, len(sorted_latencies)-1)]

    def get_stats(self) -> dict:
        """Trả về: p50, p90, p99, avg, min, max"""
        ...
```

**Bước 3 — Build `QualityChecker`:**
```python
class QualityChecker(BaseCallbackHandler):
    """
    Flag responses có thể có vấn đề về quality.
    Kiểm tra: độ dài, ngôn ngữ unexpected, refusal patterns.
    """
    REFUSAL_PATTERNS = [
        "i cannot", "i can't", "i'm unable",
        "as an ai", "i don't have the ability",
    ]

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        content = response.generations[0][0].text.lower()
        flags = []

        # Check refusals
        for pattern in self.REFUSAL_PATTERNS:
            if pattern in content:
                flags.append(f"REFUSAL: contains '{pattern}'")

        # Check suspiciously short response
        if len(content) < 20:
            flags.append(f"SHORT: only {len(content)} chars")

        # Check if response is in expected language
        # Hint: simple heuristic — count Vietnamese vs English chars

        if flags:
            self.flagged_responses.append({"content": content[:200], "flags": flags})
```

**Bước 4 — Dashboard function:**
```python
def print_dashboard(cost_tracker, latency_tracker, quality_checker):
    """
    In ra đẹp như Grafana dashboard (text version):

    ╔════════════════════════════════════╗
    ║     LLM Operations Dashboard       ║
    ╠════════════════════════════════════╣
    ║ Cost:    $0.0023 (15 calls)         ║
    ║ Latency: P50=1.2s P90=2.8s P99=5s  ║
    ║ Quality: 14/15 clean (1 flagged)   ║
    ╚════════════════════════════════════╝
    """
    ...
```

**Bước 5 — Integration test:**
```python
# Chạy 10+ LLM calls với các callbacks
# In dashboard sau mỗi 5 calls
# Simulate một call có lỗi để test error tracking
```

**Expected output:**
```
╔════════════════════════════════════════╗
║       LLM Operations Dashboard         ║
╠════════════════════════════════════════╣
║ Total Calls:  12                        ║
║ Total Cost:   $0.0034 USD               ║
║ Cost/Call:    $0.00028 avg              ║
╠════════════════════════════════════════╣
║ Latency (seconds):                      ║
║   P50: 1.34s   P90: 2.89s   P99: 4.1s  ║
║   Min: 0.8s    Max: 5.2s    Avg: 1.6s  ║
╠════════════════════════════════════════╣
║ Quality:                                ║
║   Clean: 11/12 (91.7%)                 ║
║   Flagged: 1 (REFUSAL)                 ║
╚════════════════════════════════════════╝
```

**Hint:**
- `BaseCallbackHandler.on_llm_end` nhận `LLMResult` — access tokens qua `response.llm_output`
- Track start time trong `on_llm_start`, calculate duration trong `on_llm_end`
- Multiple callbacks: `llm = ChatOpenAI(callbacks=[cost_tracker, latency_tracker, quality_checker])`

---

## Bài 3 — Autonomous Code Migration Agent (Nâng cao / Challenge)

**Mô tả:**
Xây dựng một autonomous agent có khả năng phân tích NodeJS project và suggest/generate Python equivalent code. Agent phải reason qua nhiều bước, dùng nhiều tools, và produce structured migration report.

**Yêu cầu:**

**Bước 1 — Build Tool Suite:**

```python
@tool
def analyze_nodejs_patterns(code: str) -> str:
    """
    Phân tích NodeJS/TypeScript code và identify các patterns cần migrate.
    Tìm: Express routes, async/await, TypeScript types, common packages.
    Trả về JSON với: patterns_found, complexity_score, migration_effort.
    """
    ...

@tool
def find_python_equivalent_package(npm_package: str) -> str:
    """
    Tìm Python package tương đương với npm package.
    Database: express->fastapi/flask, axios->httpx/requests, lodash->toolz/built-ins,
    winston->loguru, jest->pytest, mongoose->sqlalchemy, redis->redis-py, etc.
    """
    package_map = {
        "express": "FastAPI hoặc Flask. FastAPI recommended cho new projects (type hints, async native, auto docs)",
        "axios": "httpx (async support) hoặc requests (simple sync). uv add httpx",
        "lodash": "Mostly Python built-ins: functools, itertools. uv add toolz cho advanced FP",
        "mongoose": "SQLAlchemy (ORM) hoặc Motor (async MongoDB). uv add sqlalchemy",
        "winston": "loguru hoặc logging stdlib. uv add loguru",
        "jest": "pytest. uv add pytest pytest-asyncio",
        "dotenv": "python-dotenv. uv add python-dotenv",
        "joi": "pydantic. uv add pydantic",
        "bull": "celery (full-featured) hoặc arq (async, Redis). uv add celery[redis]",
        "socket.io": "python-socketio hoặc FastAPI WebSockets",
        "passport": "fastapi-users hoặc python-jose + passlib",
        "sequelize": "SQLAlchemy với alembic cho migrations",
    }
    result = package_map.get(npm_package.lower())
    if result:
        return f"npm: {npm_package} → Python: {result}"
    return f"No direct equivalent found for '{npm_package}'. Consider: 1) PyPI search, 2) stdlib alternatives, 3) different architectural pattern"

@tool
def generate_python_migration_snippet(nodejs_pattern: str, context: str) -> str:
    """
    Generate Python code snippet cho một NodeJS pattern cụ thể.
    nodejs_pattern: tên pattern (express_route, mongoose_model, redis_cache, etc.)
    context: thông tin thêm về use case
    """
    templates = {
        "express_route": """
# Express route → FastAPI endpoint
# NodeJS:
# app.get('/users/:id', async (req, res) => {
#   const user = await User.findById(req.params.id);
#   res.json(user);
# });

# Python FastAPI:
from fastapi import FastAPI, HTTPException
from typing import Optional

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: str) -> dict:
    user = await User.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.dict()
""",
        "mongoose_model": """
# Mongoose model → SQLAlchemy model
# NodeJS:
# const userSchema = new mongoose.Schema({
#   name: String, email: { type: String, unique: true }, createdAt: Date
# });

# Python SQLAlchemy:
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
""",
        "redis_cache": """
# Redis cache pattern
import redis
import json
from functools import wraps

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def cache(ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            cached = r.get(key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            r.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

@cache(ttl=60)
async def get_user_data(user_id: str) -> dict:
    # Expensive DB call
    ...
""",
    }
    return templates.get(nodejs_pattern, f"No template for pattern: {nodejs_pattern}. Describe your use case for custom generation.")

@tool
def estimate_migration_effort(analysis_json: str) -> str:
    """
    Ước tính effort để migrate dựa trên analysis result.
    analysis_json: JSON string từ analyze_nodejs_patterns.
    Trả về: effort level (Small/Medium/Large), estimated hours, key risks.
    """
    import json
    try:
        analysis = json.loads(analysis_json)
        patterns = analysis.get("patterns_found", [])
        complexity = analysis.get("complexity_score", 5)

        hours = len(patterns) * 4 + complexity * 2
        level = "Small" if hours < 20 else "Medium" if hours < 80 else "Large"

        risks = []
        if "mongoose" in str(patterns):
            risks.append("Database schema migration: cần carefully map MongoDB → SQL models")
        if "socket.io" in str(patterns):
            risks.append("Real-time features: FastAPI WebSockets có API khác Socket.io")
        if "bull" in str(patterns) or "queue" in str(patterns).lower():
            risks.append("Job queues: Celery setup phức tạp hơn Bull")

        return json.dumps({
            "effort_level": level,
            "estimated_hours": hours,
            "risks": risks,
            "recommendation": f"{'Can do in a sprint' if level == 'Small' else 'Plan for a milestone' if level == 'Medium' else 'Multi-sprint project'}",
        }, indent=2)
    except:
        return "Cannot parse analysis JSON"
```

**Bước 2 — Migration Agent:**
```python
def create_migration_agent():
    """
    Agent với:
    - Custom system prompt cho migration expert persona (`prompt=...`)
    - All migration tools
    - Memory để nhớ context trong session
    - Structured final output
    """
    ...
```

**Bước 3 — Structured Report Generation:**
Sau khi agent finish, generate structured migration report:
```python
from pydantic import BaseModel

class MigrationReport(BaseModel):
    project_summary: str
    nodejs_patterns_identified: list
    python_tech_stack: dict  # {"web": "FastAPI", "db": "SQLAlchemy", ...}
    effort_estimate: str
    key_risks: list
    migration_steps: list  # Ordered list of steps
    code_snippets: dict  # {"category": "code"}
    overall_recommendation: str
```

**Bước 4 — Test với NodeJS project description:**
```python
nodejs_project = """
E-commerce REST API với NodeJS + TypeScript:
- Express.js REST API (20 routes)
- MongoDB với Mongoose (User, Product, Order models)
- Bull queue cho email sending và order processing
- Redis caching cho product listings
- JWT authentication với Passport.js
- Jest unit tests (150 tests)
- Winston logging
- PM2 process management
- Docker deployment
"""

result = migration_agent.invoke({
    "messages": [{"role": "user", "content": f"Phân tích project này và tạo migration plan sang Python:\n{nodejs_project}"}]
})
report = result["messages"][-1].content
```

**Expected output:**
```
=== NodeJS → Python Migration Analysis ===

Thinking: Tôi sẽ phân tích patterns trong project...
[Tool: analyze_nodejs_patterns] → Found: express, mongoose, bull, redis, passport, jest, winston
[Tool: find_python_equivalent_package x7] → Found equivalents for all packages
[Tool: estimate_migration_effort] → Large project, 120 hours estimated
[Tool: generate_python_migration_snippet] → Generated key snippets

=== MIGRATION REPORT ===

Tech Stack Mapping:
  Express.js      → FastAPI
  Mongoose        → SQLAlchemy + Alembic
  Bull Queue      → Celery + Redis
  Redis Cache     → redis-py với same caching pattern
  Passport JWT    → python-jose + fastapi-users
  Jest            → pytest + pytest-asyncio
  Winston         → loguru
  PM2             → systemd / supervisord / Docker

Effort: Large (~120 hours)

Key Risks:
  1. MongoDB → SQL migration: data shape changes
  2. Bull → Celery: different task definition patterns
  3. Passport → fastapi-users: auth flow changes

Migration Steps:
  1. Setup FastAPI project structure (4h)
  2. Setup SQLAlchemy models từ Mongoose schemas (16h)
  3. ...

Recommendation: Plan for 3 sprints (6 weeks with 1 developer)
```

**Bonus challenges:**
- Thêm tool để đọc actual file: `read_nodejs_file(filename)` và analyze real code
- Add LangSmith tracing để xem agent decision tree
- Generate Mermaid diagram cho architecture comparison

**Hint:**
- Agent cần nhiều iterations — set recursion/config limit theo docs của runtime bạn dùng
- Dùng `create_agent(..., system_prompt=system_prompt)` cho LangChain v1; dùng LangGraph khi bài giải cần state graph/checkpointing
- Sau khi agent returns, run một chain riêng để format final report thành `MigrationReport` Pydantic model

---

## 🔍 Gợi ý kiểm tra kết quả

### Smoke import trước khi làm bài
```bash
uv add "langchain>=1.0,<2.0" "langgraph>=1.0,<2.0" "langchain-openai>=1.0,<2.0"
uv run python - <<'PY'
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent
print("imports OK:", ChatOpenAI, tool, create_agent)
PY
```

### Verify Bài 1:
```python
# Test tools riêng biệt trước
assert "SyntaxError" in check_python_syntax.invoke({"code": "def bad syntax"})
assert "Valid" in check_python_syntax.invoke({"code": "def good(): pass"})
assert "any" in lookup_python_builtin.invoke({"function_name": "any"})
print("✓ All tools work independently")

# Test agent xử lý được queries
agent = create_migration_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Check: x = [1,2,"}]})
assert "SyntaxError" in result["messages"][-1].content
print("✓ Agent uses tools correctly")
```

### Verify Bài 2:
```python
# Chạy nhiều calls và check metrics được tracked
cost_tracker = CostTrackingCallback()
llm = ChatOpenAI(model="gpt-5", callbacks=[cost_tracker])

for i in range(5):
    llm.invoke(f"Say 'hello {i}' in one word")

assert len(cost_tracker.calls) == 5, "Phải track 5 calls"
print("✓ Tracked 5 calls; cost chỉ hiển thị nếu pricing config được inject")
```

### Verify Bài 3:
```python
# Verify agent dùng tools
from langsmith import Client
# Sau khi run agent, kiểm tra LangSmith traces
# Phải có tool calls trong trace
print("Check LangSmith dashboard for trace details")
print("URL: https://smith.langchain.com")
```

### Debug tips:
```python
# Enable verbose để xem agent thinking
import langchain
langchain.debug = True

# Hoặc print agent steps manually
for msg in result["messages"]:
    print(f"[{type(msg).__name__}]:", str(msg.content or msg.tool_calls)[:200])
```

# Bài Tập — Ngày 34: Project Thực Chiến — Agentic System

## Bài 1 — Build Basic LangGraph Agent (Cơ bản)

**Mô tả:** Build một agent đơn giản với LangGraph có thể dùng calculator và get_time tools.

**Yêu cầu:**
1. Define `AgentState` với `messages` và `iteration_count`
2. Implement 2 tools: `calculator(expression: str)` và `get_current_time()`
3. Build LangGraph graph với nodes: `agent`, `tools`
4. Add conditional edge: nếu LLM muốn dùng tool → `tools`, nếu không → `END`
5. Run agent với task: "Tính 15 * 23 + 100. Và cho tôi biết bây giờ là mấy giờ?"
6. Print tất cả messages trong state để xem reasoning process

**Expected output:**
```
=== Agent Run ===
Step 1 [LLM]: Tôi cần dùng calculator và get_time...
  → Calling tool: calculator("15 * 23 + 100")
  → Tool result: 445
  → Calling tool: get_current_time()
  → Tool result: 2024-01-15 10:30:00

Step 2 [LLM]: Kết quả tính toán là 445. Thời gian hiện tại là 10:30 AM.

Final answer: 15 * 23 + 100 = 445. Bây giờ là 10:30 AM ngày 15/01/2024.
Iterations: 2
```

**Hint:**
- `from langgraph.prebuilt import ToolNode` — xử lý tool execution tự động
- `bind_tools(tools)` trên ChatOpenAI để LLM biết có tools
- Check `last_message.tool_calls` để biết LLM muốn gọi tool không

---

## Bài 2 — Thêm Human-in-the-Loop Approval (Trung bình)

**Mô tả:** Mở rộng agent từ Bài 1, thêm approval flow cho dangerous tool.

**Yêu cầu:**
1. Thêm tool `delete_file(filename: str)` — tool "nguy hiểm"
2. Mark `delete_file` là tool cần approval
3. Thêm `human_review` node vào graph:
   - Hiển thị cho user xem tool nào sắp được gọi
   - Hỏi user có approve không (CLI input)
   - Nếu approve → execute tools, nếu không → end với message từ chối
4. Test với task: "Liệt kê files trong /tmp, rồi xóa file test.txt"
5. Khi agent muốn xóa file, hỏi user approve không

**Expected behavior:**
```
Task: "Liệt kê files trong /tmp, rồi xóa file test.txt"

[Agent] Listing files...
  → Tool: list_files() → "test.txt, data.csv, log.txt"

[Agent] Now wants to delete test.txt
  → PENDING APPROVAL: delete_file(filename="test.txt")

⚠️  Agent wants to execute: delete_file
   Arguments: {"filename": "test.txt"}
   Do you approve? (y/n): n

[System] Action rejected by user.
[Agent] The deletion was rejected. I cannot delete test.txt.
```

**Hint:**
- `interrupt()` từ `langgraph.types` để pause graph
- Persist checkpointer bắt buộc nếu muốn resume sau interrupt
- Resume bằng `graph.invoke(Command(resume={"approved": True}), config={"configurable": {"thread_id": same_thread_id}})`
- Không dùng `graph.update_state()`/`aupdate_state()` để "nhảy" qua interrupt; cách đó bỏ qua lifecycle của node đang pause

---

## Bài 3 — Thêm Custom Tool: Database Query Tool (Nâng cao / Challenge)

**Mô tả:** Implement một `DatabaseQueryTool` cho phép agent query PostgreSQL database an toàn.

**Yêu cầu:**
1. Implement tool `query_database(sql: str) -> str`:
   - Chỉ cho phép SELECT statements (parse SQL để verify)
   - Không cho phép INSERT, UPDATE, DELETE, DROP
   - Return kết quả dưới dạng formatted table
   - Giới hạn kết quả: max 100 rows
2. Thêm tool vào agent graph
3. Mark tool này là **safe** (không cần approval, chỉ readonly)
4. Create test database với sample data:
   ```sql
   CREATE TABLE products (id, name, price, stock);
   INSERT INTO products VALUES (1, 'Python Book', 29.99, 50);
   -- ... more rows
   ```
5. Test với tasks:
   - "Liệt kê tất cả products có giá < $50"
   - "Product nào có stock thấp nhất?"
   - "Tổng giá trị inventory là bao nhiêu?"
6. Verify agent không thể chạy DELETE hoặc DROP statements

**Expected behavior:**
```
Task: "Product nào có giá dưới $50?"

[Agent] I'll query the database to find products...
  → Tool: query_database("SELECT name, price FROM products WHERE price < 50")
  → Result:
    | name        | price |
    |-------------|-------|
    | Python Book | 29.99 |
    | Tutorial    | 19.99 |

[Agent] Có 2 sản phẩm có giá dưới $50: Python Book ($29.99) và Tutorial ($19.99).
```

**Security test:**
```
Task: "Xóa tất cả products"

[Agent] Running: query_database("DELETE FROM products")
  → Tool error: "Security Error: Only SELECT statements are allowed"

[Agent] I cannot execute DELETE statements for safety reasons.
```

**Bonus:**
- Thêm query timeout (5 seconds) để tránh slow queries
- Log tất cả queries vào audit table
- Add `explain_query(sql)` tool để xem query plan

## 🔍 Gợi ý kiểm tra kết quả

### Test graph structure
```python
from langgraph.graph import StateGraph

graph = build_graph()
compiled = graph.compile()

# Visualize graph (nếu có graphviz)
try:
    png = compiled.get_graph().draw_mermaid_png()
    with open("agent_graph.png", "wb") as f:
        f.write(png)
    print("Graph saved to agent_graph.png")
except Exception:
    # Print Mermaid diagram text
    print(compiled.get_graph().draw_mermaid())
```

### Test persistence
```python
import asyncio
from langchain_core.messages import HumanMessage

async def test_persistence():
    # Run 1: Start task, pause at human_review
    thread_id = "test-thread-001"
    result1 = await graph.ainvoke(
        {"messages": [HumanMessage("Delete test.txt")]},
        config={"configurable": {"thread_id": thread_id}},
    )
    print(f"Status after run 1: {result1.get('pending_tool_calls')}")

    # Simulate process restart... state vẫn còn trong PostgreSQL

    # Run 2: Resume đúng interrupt point với approval
    from langgraph.types import Command

    result2 = await graph.ainvoke(
        Command(resume={"approved": True}),
        config={"configurable": {"thread_id": thread_id}},
    )
    print(f"Final result: {result2['messages'][-1].content}")

asyncio.run(test_persistence())
```

### Benchmark agent speed
```python
import time
import asyncio

async def bench_agent(tasks: list[str], n_runs: int = 5):
    times = []
    for task in tasks[:n_runs]:
        start = time.perf_counter()
        await graph.ainvoke(...)
        times.append(time.perf_counter() - start)

    print(f"Avg latency: {sum(times)/len(times):.2f}s")
    print(f"Min: {min(times):.2f}s, Max: {max(times):.2f}s")
```

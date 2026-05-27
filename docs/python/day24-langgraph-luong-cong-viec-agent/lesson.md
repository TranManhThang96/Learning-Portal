# Ngày 24: LangGraph & Agentic Workflows

## 🎯 Mục tiêu học tập
- Hiểu tại sao state machines là foundation của reliable AI agents
- Implement LangGraph graphs với nodes, edges, và conditional routing
- Xây dựng human-in-the-loop workflows cho high-stakes operations
- Implement persistence và checkpointing để resume interrupted workflows
- Debug và monitor agent workflows với LangSmith integration

> **Version note:** Bài này dùng LangGraph Python hiện hành với `StateGraph`, `START`/`END`, checkpointer, `interrupt()`, và `Command(resume=...)`. Human-in-the-loop flow cần compile graph với checkpointer và resume bằng cùng `thread_id`; nếu thiếu một trong hai, workflow không thể tiếp tục từ đúng checkpoint. Một số docs/version trả interrupt qua `result.interrupts` khi gọi `version="v2"`, còn version cũ hơn có thể trả `result["__interrupt__"]`; smoke-test theo version pin.

## 🔄 So sánh với NodeJS

| Khái niệm LangGraph | Tương đương NodeJS | Ghi chú |
|--------------------|-------------------|---------|
| `StateGraph` | XState state machine / Redux | Quản lý state transitions |
| `State` (TypedDict) | Redux state shape / Zod schema | Định nghĩa data structure của workflow |
| `Node` | Middleware function trong Express | Nhận state, transform, trả về partial state |
| `Edge` | Route trong Express Router | Kết nối nodes |
| `Conditional Edge` | if/else trong route handler | Routing dựa trên state |
| `Checkpointer` | Redis session store | Persist state để resume |
| `Interrupt` | Webhook callback / human approval gate | Pause workflow, chờ input |
| `InMemorySaver` / `MemorySaver` | In-memory session store | Development checkpointing; tên alias phụ thuộc version |
| `Command` | Dispatch action trong Redux | Chuyển đổi state transitions |

**Analogy quan trọng:** LangGraph là như XState (state machine library) nhưng được thiết kế cho LLM workflows. Nếu bạn đã dùng Redux Saga hoặc XState, mental model rất quen thuộc: define states → define transitions → define effects (LLM calls).

**Tại sao không dùng LangChain chains thông thường?**
- LangChain chains: linear, không có loops, không có conditional branching phức tạp
- LangGraph: cyclic graphs, loops, conditional routing, state persistence — giống real-world workflows

## 📖 Lý thuyết

### Section 1: State Machines cho AI Agents — WHY

**WHY state machines thay vì sequential code?**

Hãy tưởng tượng một AI agent phải research và viết báo cáo:
1. Research topic
2. Nếu không đủ thông tin → search thêm (loop!)
3. Nếu đủ → draft report
4. Review draft — nếu kém → revise (loop!)
5. Nếu tốt → finalize

Code sequential không handle được loops. State machines handle điều này tự nhiên.

```python
# uv add langgraph langchain-openai

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, Sequence
import operator

# === STEP 1: Define State ===
# State là "Redux store" của workflow
# Mọi node đọc từ state và write partial updates về state

class WorkflowState(TypedDict):
    """
    State shape của workflow.
    TypedDict giống interface trong TypeScript.

    Annotated[list, add_messages] = messages được APPEND (không overwrite).
    Đây là pattern của LangGraph cho conversation history.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    research_notes: str           # Accumulated research
    draft: str                    # Current draft
    revision_count: int           # How many times we've revised
    is_approved: bool             # Final approval status
    next_step: str                # Control flow hint


# === STEP 2: Define Nodes ===
# Mỗi node là một function: state → partial state update
# Giống như reducer trong Redux nhưng chỉ update một phần

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def research_node(state: WorkflowState) -> dict:
    """
    Node: Thực hiện research dựa trên user question.
    Return: partial state update (chỉ các fields thay đổi)
    """
    question = state["messages"][-1].content

    research_response = llm.invoke([
        HumanMessage(content=f"""
Research the following topic and provide key facts:
Topic: {question}

Provide 5 key facts, recent developments, and relevant context.
Format: Numbered list with brief explanations.
""")
    ])

    research_text = research_response.content

    print(f"[Research Node] Gathered {len(research_text)} chars of research")

    return {
        "research_notes": research_text,
        "messages": [AIMessage(content=f"Research complete. Found key information about the topic.")],
    }


def draft_node(state: WorkflowState) -> dict:
    """Node: Tạo draft dựa trên research"""
    draft_response = llm.invoke([
        HumanMessage(content=f"""
Based on the following research notes, write a concise report:

RESEARCH NOTES:
{state['research_notes']}

ORIGINAL QUESTION:
{state['messages'][0].content}

Write a 3-paragraph report. Be factual and cite the research notes.
""")
    ])

    draft = draft_response.content
    print(f"[Draft Node] Draft created ({len(draft)} chars)")

    return {
        "draft": draft,
        "revision_count": state.get("revision_count", 0),
        "messages": [AIMessage(content="Draft created. Reviewing quality...")],
    }


def review_node(state: WorkflowState) -> dict:
    """Node: Review draft và quyết định approve hay revise"""
    review_response = llm.invoke([
        HumanMessage(content=f"""
Review this report draft and decide if it's ready to publish.

DRAFT:
{state['draft']}

Evaluate:
1. Is it factually grounded in the research?
2. Is it well-structured?
3. Is it comprehensive enough?

Response format:
DECISION: [APPROVE/REVISE]
REASON: [brief explanation]
IMPROVEMENTS: [if REVISE: what to improve]
""")
    ])

    review_text = review_response.content
    is_approved = "APPROVE" in review_text.upper()
    revision_count = state.get("revision_count", 0)

    print(f"[Review Node] Decision: {'APPROVE' if is_approved else 'REVISE'} "
          f"(revision #{revision_count})")

    return {
        "is_approved": is_approved,
        "revision_count": revision_count,
        "messages": [AIMessage(content=review_text)],
    }


def revise_node(state: WorkflowState) -> dict:
    """Node: Revise draft dựa trên review feedback"""
    last_review = state["messages"][-1].content
    current_count = state.get("revision_count", 0)

    revised_response = llm.invoke([
        HumanMessage(content=f"""
Revise this draft based on the review feedback:

CURRENT DRAFT:
{state['draft']}

REVIEW FEEDBACK:
{last_review}

Provide an improved version addressing all mentioned issues.
""")
    ])

    print(f"[Revise Node] Revision #{current_count + 1} complete")

    return {
        "draft": revised_response.content,
        "revision_count": current_count + 1,
        "messages": [AIMessage(content=f"Revision #{current_count + 1} complete.")],
    }


def finalize_node(state: WorkflowState) -> dict:
    """Node: Finalize và format final output"""
    print(f"[Finalize Node] Report finalized after {state.get('revision_count', 0)} revisions")

    return {
        "messages": [AIMessage(
            content=f"FINAL REPORT:\n\n{state['draft']}\n\n"
                    f"(Revised {state.get('revision_count', 0)} times)"
        )],
    }


# === STEP 3: Routing Logic ===
def should_revise(state: WorkflowState) -> str:
    """
    Conditional routing function.
    Nhận state → trả về tên node tiếp theo.

    Giống như switch statement trong route handler.
    """
    if state.get("is_approved", False):
        return "finalize"

    # Max 3 revisions để tránh infinite loop
    revision_count = state.get("revision_count", 0)
    if revision_count >= 3:
        print("[Router] Max revisions reached, force finalizing")
        return "finalize"

    return "revise"


# === STEP 4: Build Graph ===
workflow = StateGraph(WorkflowState)

# Add nodes
workflow.add_node("research", research_node)
workflow.add_node("draft", draft_node)
workflow.add_node("review", review_node)
workflow.add_node("revise", revise_node)
workflow.add_node("finalize", finalize_node)

# Add edges — linear flow
workflow.add_edge(START, "research")      # Start → Research
workflow.add_edge("research", "draft")    # Research → Draft
workflow.add_edge("draft", "review")      # Draft → Review

# Conditional edge — branching
workflow.add_conditional_edges(
    "review",           # From node
    should_revise,      # Function returns next node name
    {                   # Mapping: return value → node name
        "finalize": "finalize",
        "revise": "revise",
    }
)

workflow.add_edge("revise", "review")     # Revise → Review (loop!)
workflow.add_edge("finalize", END)        # Finalize → End

# Compile
app = workflow.compile()

# === STEP 5: Run ===
print("=== Starting Research Workflow ===\n")
initial_state = {
    "messages": [HumanMessage(content="What are the main benefits of Python for data science?")],
    "research_notes": "",
    "draft": "",
    "revision_count": 0,
    "is_approved": False,
    "next_step": "",
}

result = app.invoke(
    initial_state,
    config={"recursion_limit": 20},  # Guard runtime nếu routing loop bị lỗi
)

print("\n=== FINAL RESULT ===")
print(result["messages"][-1].content)
```

### Section 2: Human-in-the-Loop Patterns

**WHY Human-in-the-Loop?**

Không phải mọi AI decision đều an toàn để tự động hóa hoàn toàn. Ví dụ:
- Agent chuẩn bị execute SQL DELETE query
- Agent gửi email tới khách hàng
- Agent deploy code lên production

Những thao tác này cần human approval. LangGraph có `interrupt()` để pause workflow và chờ human input.

```python
from langgraph.graph import StateGraph, START, END
try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # Older LangGraph examples use MemorySaver
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
import json

# === State cho approval workflow ===
class ApprovalState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    action_plan: str          # Kế hoạch action của agent
    action_type: str          # Loại action: "safe", "risky", "dangerous"
    human_approved: bool      # Kết quả approval
    execution_result: str     # Kết quả sau execution


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def plan_action(state: ApprovalState) -> dict:
    """Node: Agent lên kế hoạch action"""
    user_request = state["messages"][-1].content

    plan_response = llm.invoke([
        HumanMessage(content=f"""
You are an AI assistant that helps with database operations.
User request: {user_request}

Analyze the request and create an action plan.
Classify the risk level: "safe" (read-only), "risky" (modifies data), or "dangerous" (deletes/irreversible)

Response format (JSON):
{{
  "action_description": "Detailed description of what will be done",
  "sql_query": "The SQL query to execute",
  "risk_level": "safe|risky|dangerous",
  "reason": "Why this risk level"
}}
""")
    ])

    try:
        plan = json.loads(plan_response.content)
    except json.JSONDecodeError:
        plan = {
            "action_description": plan_response.content,
            "sql_query": "N/A",
            "risk_level": "safe",
            "reason": "Could not parse plan"
        }

    print(f"[Plan Node] Action planned: {plan.get('risk_level', 'unknown')} risk")

    return {
        "action_plan": json.dumps(plan, indent=2),
        "action_type": plan.get("risk_level", "safe"),
        "messages": [AIMessage(content=f"Action planned:\n{json.dumps(plan, indent=2)}")],
    }


def human_approval_node(state: ApprovalState) -> dict:
    """
    Node: Yêu cầu human approval.

    interrupt() = pause execution tại đây, save state, chờ resume.
    Giống như Promise resolve bên ngoài — ai đó gọi resolve() sau.

    Khi resume, interrupt() trả về giá trị được pass vào Command(resume=...)
    """
    plan = json.loads(state["action_plan"])

    print(f"\n{'='*50}")
    print("⚠️  HUMAN APPROVAL REQUIRED")
    print(f"Action: {plan.get('action_description', 'N/A')}")
    print(f"SQL: {plan.get('sql_query', 'N/A')}")
    print(f"Risk: {plan.get('risk_level', 'N/A')}")
    print(f"{'='*50}")

    # interrupt() pauses execution và saves state
    # Giá trị pass vào interrupt() là message hiển thị cho user
    human_input = interrupt({
        "prompt": "Do you approve this action?",
        "action": plan.get("action_description"),
        "sql": plan.get("sql_query"),
        "risk": plan.get("risk_level"),
    })

    # Code dưới đây chỉ chạy SAU KHI được resume
    approved = human_input.get("approved", False)
    comment = human_input.get("comment", "")

    print(f"[Human Approval] Decision: {'APPROVED' if approved else 'REJECTED'}")
    if comment:
        print(f"[Human Approval] Comment: {comment}")

    return {
        "human_approved": approved,
        "messages": [
            AIMessage(content=f"Human decision: {'Approved' if approved else 'Rejected'}. {comment}")
        ],
    }


def execute_action(state: ApprovalState) -> dict:
    """Node: Execute action nếu được approve"""
    plan = json.loads(state["action_plan"])
    sql = plan.get("sql_query", "")

    # Simulate SQL execution (trong real app: thực sự execute)
    print(f"[Execute Node] Executing: {sql[:60]}...")

    # Simulate kết quả
    result = f"Query executed successfully: {sql[:80]}... | Rows affected: 5"

    return {
        "execution_result": result,
        "messages": [AIMessage(content=f"Execution complete: {result}")],
    }


def reject_action(state: ApprovalState) -> dict:
    """Node: Handle rejected action"""
    return {
        "execution_result": "Action rejected by human",
        "messages": [AIMessage(content="Action was rejected. No changes made.")],
    }


def route_after_approval(state: ApprovalState) -> str:
    """Routing sau approval node"""
    if state.get("human_approved", False):
        return "execute"
    return "reject"


def needs_approval(state: ApprovalState) -> str:
    """Routing: safe actions không cần approval"""
    if state.get("action_type") == "safe":
        print("[Router] Safe action, skipping human approval")
        return "execute"
    return "human_approval"


# Build graph với checkpointing
memory = InMemorySaver()  # In-memory checkpointer (dùng SQLite/Postgres cho persistence)

approval_workflow = StateGraph(ApprovalState)
approval_workflow.add_node("plan", plan_action)
approval_workflow.add_node("human_approval", human_approval_node)
approval_workflow.add_node("execute", execute_action)
approval_workflow.add_node("reject", reject_action)

approval_workflow.add_edge(START, "plan")
approval_workflow.add_conditional_edges("plan", needs_approval, {
    "human_approval": "human_approval",
    "execute": "execute",
})
approval_workflow.add_conditional_edges("human_approval", route_after_approval, {
    "execute": "execute",
    "reject": "reject",
})
approval_workflow.add_edge("execute", END)
approval_workflow.add_edge("reject", END)

# Compile VỚI checkpointer — bắt buộc cho interrupt() hoạt động
approval_app = approval_workflow.compile(checkpointer=memory)


# === Run với interrupt/resume flow ===
def run_with_approval(user_request: str):
    """
    Demo human-in-the-loop workflow.
    Thread ID là session identifier — giống user session trong Express.
    """
    thread_id = "thread_001"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"\n=== Starting workflow for: {user_request} ===\n")

    # Bước 1: Chạy cho đến khi gặp interrupt
    result = approval_app.invoke(
        {
            "messages": [HumanMessage(content=user_request)],
            "action_plan": "",
            "action_type": "",
            "human_approved": False,
            "execution_result": "",
        },
        config=config,
        version="v2",
    )

    # Kiểm tra xem có bị interrupt không.
    # LangGraph hiện hành có thể trả GraphOutput.interrupts (v2);
    # version cũ hơn trả dict với "__interrupt__".
    interrupts = getattr(result, "interrupts", None)
    if interrupts is None and isinstance(result, dict):
        interrupts = result.get("__interrupt__", [])

    if interrupts:
        print("\n[Workflow paused — awaiting human input]")
        print("State saved to checkpointer")
        print(f"Interrupt payload: {interrupts[0].value}")

        # Simulate human approval (trong real app: wait for user input từ UI)
        human_decision = {
            "approved": True,  # User clicks "Approve" trong UI
            "comment": "Looks good, proceed",
        }

        print(f"\n[Simulating human input]: {human_decision}")

        # Bước 2: Resume workflow với human decision
        # Command(resume=value) → LangGraph tiếp tục từ interrupt point
        final_result = approval_app.invoke(
            Command(resume=human_decision),
            config=config,
            version="v2",
        )

        print(f"\n=== Workflow complete ===")
        final_value = getattr(final_result, "value", final_result)
        print(f"Execution result: {final_value.get('execution_result', 'N/A')}")
        return final_result
    else:
        print(f"\n=== Workflow complete (no approval needed) ===")
        result_value = getattr(result, "value", result)
        print(f"Execution result: {result_value.get('execution_result', 'N/A')}")
        return result


# Test
# risky_result = run_with_approval("Delete all users who haven't logged in for 2 years")
# safe_result = run_with_approval("Show me all users created this month")
```

### Section 3: Persistence và Checkpointing

**WHY Checkpointing?**

Production workflows có thể:
- Chạy hàng giờ (research agent)
- Bị crash giữa chừng
- Cần human input sau nhiều giờ
- Cần audit trail

Checkpointing = save full state sau mỗi step → có thể resume từ bất kỳ điểm nào.

```python
try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
# uv add langgraph-checkpoint-postgres

# === Memory Checkpointer (Development) ===
memory_checkpointer = InMemorySaver()


# === PostgreSQL Checkpointer (Production) ===
def run_with_postgres_checkpointer(builder: StateGraph, inputs: dict, thread_id: str):
    """
    PostgreSQL checkpointer cho production.
    Tương tự như connect PostgreSQL cho session store trong Express.

    Lifecycle quan trọng: compile và invoke graph trong lúc checkpointer
    connection/pool còn mở. Đừng return checkpointer sau khi connection context đóng.
    """
    DB_URI = "postgresql://user:password@localhost:5432/langgraph_db"

    with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
        # Tạo tables cần thiết (chỉ cần chạy lần đầu)
        checkpointer.setup()
        app = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        return app.invoke(inputs, config=config)


# === Thread Management ===
# Mỗi "thread" = một conversation/workflow instance
# Thread ID giống session ID trong Express

def demonstrate_checkpointing():
    """Demo: Khởi tạo, pause, resume workflow"""

    # Build simple graph với checkpointing
    class SimpleState(TypedDict):
        messages: Annotated[list[BaseMessage], add_messages]
        step_count: int

    def increment_step(state: SimpleState) -> dict:
        count = state.get("step_count", 0) + 1
        print(f"[Step {count}] Processing...")
        return {
            "step_count": count,
            "messages": [AIMessage(content=f"Completed step {count}")],
        }

    def should_continue(state: SimpleState) -> str:
        if state.get("step_count", 0) >= 3:
            return "end"
        return "continue"

    graph = StateGraph(SimpleState)
    graph.add_node("process", increment_step)
    graph.add_conditional_edges("process", should_continue, {
        "continue": "process",  # Self-loop
        "end": END,
    })
    graph.add_edge(START, "process")

    checkpointed_app = graph.compile(checkpointer=InMemorySaver())

    # Thread 1 — Run steps
    config_1 = {"configurable": {"thread_id": "user_alice"}}
    config_2 = {"configurable": {"thread_id": "user_bob"}}

    # User Alice's workflow
    result_alice = checkpointed_app.invoke(
        {"messages": [HumanMessage(content="Start")], "step_count": 0},
        config=config_1,
    )
    print(f"\nAlice's steps: {result_alice['step_count']}")

    # User Bob's workflow (independent)
    result_bob = checkpointed_app.invoke(
        {"messages": [HumanMessage(content="Begin")], "step_count": 0},
        config=config_2,
    )
    print(f"Bob's steps: {result_bob['step_count']}")

    # === State Inspection ===
    alice_state = checkpointed_app.get_state(config_1)
    print(f"\nAlice's current state:")
    print(f"  Step count: {alice_state.values.get('step_count')}")
    print(f"  Messages: {len(alice_state.values.get('messages', []))}")

    # === State History ===
    # Xem tất cả state snapshots (audit trail)
    print("\nAlice's history:")
    for snapshot in checkpointed_app.get_state_history(config_1):
        print(f"  Checkpoint: step={snapshot.values.get('step_count', 0)} "
              f"| messages={len(snapshot.values.get('messages', []))} "
              f"| next={snapshot.next}")


demonstrate_checkpointing()


# === Time Travel — Rollback đến state trước ===
def demonstrate_time_travel(app, config: dict):
    """
    Time travel: rollback về state trước đó.
    Rất hữu ích cho debugging và cho phép user "undo" actions.

    Giống như git checkout <commit-hash> trong version control.
    """
    # Lấy tất cả checkpoints
    history = list(app.get_state_history(config))

    if len(history) < 2:
        print("Not enough history for time travel")
        return

    # Rollback về state 2 steps trước
    target_checkpoint = history[2]  # Index 0 = current, higher = older
    target_config = target_checkpoint.config

    print(f"\nTime traveling to: step={target_checkpoint.values.get('step_count')}")

    # Re-run từ checkpoint đó
    result = app.invoke(None, config=target_config)
    print(f"After time travel re-run: step={result.get('step_count')}")
```

### Section 4: Advanced Graph Patterns

#### 4.1 Parallel Node Execution (Fan-out / Fan-in)

```python
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END

# WHY parallel execution?
# Khi nhiều tasks độc lập có thể chạy song song.
# Giống như Promise.all() — chạy nhiều API calls cùng lúc.
# LangGraph không "đoán" mọi function độc lập trong arbitrary code; bạn biểu diễn
# fan-out bằng edges cùng step và dùng reducer an toàn để merge state.

class ParallelState(TypedDict):
    topic: str
    research_results: Annotated[list[str], operator.add]  # Accumulate results
    final_synthesis: str


def research_academic(state: ParallelState) -> dict:
    """Node: Research từ academic sources"""
    # Simulate academic research
    result = f"Academic perspective on '{state['topic']}': [academic findings...]"
    print(f"[Academic Research] Complete")
    return {"research_results": [f"ACADEMIC: {result}"]}


def research_industry(state: ParallelState) -> dict:
    """Node: Research từ industry sources"""
    result = f"Industry perspective on '{state['topic']}': [industry findings...]"
    print(f"[Industry Research] Complete")
    return {"research_results": [f"INDUSTRY: {result}"]}


def research_news(state: ParallelState) -> dict:
    """Node: Research từ news sources"""
    result = f"Recent news about '{state['topic']}': [news findings...]"
    print(f"[News Research] Complete")
    return {"research_results": [f"NEWS: {result}"]}


def synthesize_results(state: ParallelState) -> dict:
    """Fan-in node: Tổng hợp kết quả từ tất cả parallel branches"""
    all_results = state.get("research_results", [])
    print(f"[Synthesize] Combining {len(all_results)} research results")

    synthesis = f"Synthesis of {len(all_results)} sources:\n" + "\n".join(all_results)
    return {"final_synthesis": synthesis}


# Build parallel graph
parallel_graph = StateGraph(ParallelState)

# Thêm tất cả nodes
parallel_graph.add_node("academic", research_academic)
parallel_graph.add_node("industry", research_industry)
parallel_graph.add_node("news", research_news)
parallel_graph.add_node("synthesize", synthesize_results)

# Fan-out: START → 3 parallel nodes
parallel_graph.add_edge(START, "academic")
parallel_graph.add_edge(START, "industry")
parallel_graph.add_edge(START, "news")

# Fan-in: 3 parallel nodes → synthesize
parallel_graph.add_edge("academic", "synthesize")
parallel_graph.add_edge("industry", "synthesize")
parallel_graph.add_edge("news", "synthesize")

parallel_graph.add_edge("synthesize", END)

parallel_app = parallel_graph.compile()

result = parallel_app.invoke({"topic": "AI safety", "research_results": [], "final_synthesis": ""})
print(f"\nFinal synthesis preview: {result['final_synthesis'][:200]}")
```

#### 4.2 Subgraph — Modular Workflows

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# WHY subgraphs?
# Break complex workflows thành reusable modules.
# Giống như separate Express routers — /api/users, /api/products

# === Inner Graph (Subgraph) ===
class ValidationState(TypedDict):
    data: str
    validation_errors: list[str]
    is_valid: bool


def validate_format(state: ValidationState) -> dict:
    errors = []
    if len(state["data"]) < 10:
        errors.append("Data too short")
    if not state["data"].strip():
        errors.append("Data is empty")
    return {"validation_errors": errors}


def validate_content(state: ValidationState) -> dict:
    errors = state.get("validation_errors", [])
    if "invalid" in state["data"].lower():
        errors.append("Data contains invalid content")
    return {
        "validation_errors": errors,
        "is_valid": len(errors) == 0,
    }


# Build subgraph
validation_subgraph_builder = StateGraph(ValidationState)
validation_subgraph_builder.add_node("check_format", validate_format)
validation_subgraph_builder.add_node("check_content", validate_content)
validation_subgraph_builder.add_edge(START, "check_format")
validation_subgraph_builder.add_edge("check_format", "check_content")
validation_subgraph_builder.add_edge("check_content", END)
validation_subgraph = validation_subgraph_builder.compile()


# === Outer Graph sử dụng subgraph ===
class ProcessingState(TypedDict):
    user_input: str
    data: str                     # Mapped to subgraph's "data"
    validation_errors: list[str]  # Mapped from subgraph's output
    is_valid: bool
    processed_result: str


def prepare_data(state: ProcessingState) -> dict:
    """Prepare data trước khi validate"""
    return {"data": state["user_input"].strip()}


def process_valid_data(state: ProcessingState) -> dict:
    return {"processed_result": f"Processed: {state['data']}"}


def handle_invalid_data(state: ProcessingState) -> dict:
    errors = ", ".join(state.get("validation_errors", []))
    return {"processed_result": f"Failed validation: {errors}"}


def route_after_validation(state: ProcessingState) -> str:
    return "process" if state.get("is_valid") else "reject"


outer_graph = StateGraph(ProcessingState)
outer_graph.add_node("prepare", prepare_data)
outer_graph.add_node("validate", validation_subgraph)  # Subgraph như một node!
outer_graph.add_node("process", process_valid_data)
outer_graph.add_node("reject", handle_invalid_data)

outer_graph.add_edge(START, "prepare")
outer_graph.add_edge("prepare", "validate")
outer_graph.add_conditional_edges("validate", route_after_validation, {
    "process": "process",
    "reject": "reject",
})
outer_graph.add_edge("process", END)
outer_graph.add_edge("reject", END)

outer_app = outer_graph.compile()

# Test
valid_result = outer_app.invoke({
    "user_input": "This is valid input data that should pass validation",
    "data": "",
    "validation_errors": [],
    "is_valid": False,
    "processed_result": "",
})
print(f"Valid input result: {valid_result['processed_result']}")

invalid_result = outer_app.invoke({
    "user_input": "bad",  # Too short
    "data": "",
    "validation_errors": [],
    "is_valid": False,
    "processed_result": "",
})
print(f"Invalid input result: {invalid_result['processed_result']}")
```

#### 4.3 Streaming — Real-time Output

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated

class StreamingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def chat_node(state: StreamingState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


streaming_graph = StateGraph(StreamingState)
streaming_graph.add_node("chat", chat_node)
streaming_graph.add_edge(START, "chat")
streaming_graph.add_edge("chat", END)
streaming_app = streaming_graph.compile()

# === Streaming modes ===
# "values" — emit state sau mỗi step (full state)
# "updates" — emit chỉ state CHANGES sau mỗi step
# "messages" — emit từng token (LLM streaming)

# Stream tokens theo thời gian thực
print("=== Streaming output ===")
for chunk in streaming_app.stream(
    {"messages": [HumanMessage(content="Explain Python in 2 sentences")]},
    stream_mode="messages",  # Token-level streaming
):
    # chunk là tuple: (message_chunk, metadata)
    message_chunk, metadata = chunk
    if hasattr(message_chunk, 'content') and message_chunk.content:
        print(message_chunk.content, end="", flush=True)

print("\n")

# Stream state updates
print("=== State update streaming ===")
for state_update in streaming_app.stream(
    {"messages": [HumanMessage(content="What is TypeScript?")]},
    stream_mode="updates",  # State-level streaming
):
    print(f"Update from node: {list(state_update.keys())}")
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Không dùng `Annotated[list, add_messages]` cho messages | Messages bị overwrite thay vì append | Luôn dùng `add_messages` reducer |
| Không set `checkpointer` khi dùng `interrupt()` | Không resume được đúng checkpoint | Compile với `checkpointer=InMemorySaver()` cho dev hoặc SQLite/Postgres cho persistence |
| Không có termination condition trong cycle | Infinite loop | Luôn có max_iterations hoặc explicit END condition |
| Không có recursion/cost guard | Loop lỗi có thể tốn token/API cost rất nhanh | Set `recursion_limit`, max LLM calls, timeout, và token budget |
| Return full state thay vì partial update từ node | Performance kém, unexpected behavior | Node chỉ return fields nó thay đổi |
| Thread ID không consistent | Checkpointing không hoạt động, state bị mất | Dùng consistent thread ID (user ID, session ID) |
| Xử lý interrupt kết quả không đúng | Workflow không resume được | Check `Command(resume=...)` syntax |
| Parallel nodes với non-commutative state updates | Race condition | Dùng `Annotated[list, operator.add]` thay vì overwrite |

## ✅ Best Practices

- **State immutability:** Nodes chỉ return partial updates, không mutate state trực tiếp.
- **Explicit termination:** Luôn có điều kiện thoát khỏi cycles — counter, flag, hoặc max_iterations.
- **Runtime guard:** Dùng `recursion_limit`, max LLM/tool calls, request timeout, và token/cost budget cho mọi workflow có loop.
- **Thread IDs có ý nghĩa:** Dùng `user_id + conversation_id` thay vì random UUID để dễ debug.
- **PostgresSaver cho production:** MemorySaver chỉ cho development — data mất khi restart.
- **Checkpointer lifecycle:** Persistent checkpointer cần connection/pool sống trong suốt lúc graph invoke/resume; lưu `thread_id` ở DB/app state để resume sau interrupt.
- **Verbose logging:** `verbose=True` hoặc LangSmith tracing để debug graph execution.
- **Subgraphs cho modularity:** Break complex workflows thành reusable subgraphs.
- **Interrupt sparingly:** Interrupt points làm chậm workflow — chỉ interrupt khi thực sự cần human.
- **Test conditional routing:** Unit test các routing functions với mocked states.

## ⚖️ Trade-offs

| Pattern | Pros | Cons | Khi nào dùng |
|---------|------|------|--------------|
| Linear graph | Đơn giản, dễ debug | Không flexible | Simple pipelines |
| Cyclic graph | Handles loops tự nhiên | Cần careful termination | Iterative refinement |
| Parallel fan-out | Nhanh hơn sequential | Complex state merge | Independent tasks |
| Subgraphs | Modular, reusable | Overhead thêm | Complex workflows |
| Human-in-the-loop | Kiểm soát tốt | Chậm, cần UI | High-stakes decisions |
| InMemorySaver/MemorySaver | Simple, fast | Lost on restart | Dev/testing |
| PostgresSaver | Persistent, scalable | Setup phức tạp | Production |

## 🚀 Performance Notes

- **Parallel execution:** Các branch fan-out trong cùng superstep có thể chạy song song nếu state reducers merge được kết quả; không assume mọi node "independent-looking" sẽ tự parallelize.
- **Async nodes:** Implement `async def node_func(state) -> dict` cho I/O-bound operations.
- **Streaming cho UX:** Dùng `stream_mode="messages"` để user thấy output ngay lập tức.
- **Checkpoint frequency:** Mặc định checkpoint sau mỗi node — có thể reduce với custom checkpointer.
- **State size:** Tránh lưu large objects (binary data, images) vào state — dùng references thay thế.

## 📝 Tóm tắt

- **LangGraph = XState cho LLM:** State machine với nodes (processors), edges (transitions), conditional routing (guards)
- **State là nguồn sự thật duy nhất:** Mọi node đọc từ state, trả về partial updates — không dùng global variables
- **Interrupt + Checkpointing = Human-in-the-loop:** Pause tại bất kỳ điểm nào, save state, chờ human, resume seamlessly
- **Resume cần cùng thread:** `Command(resume=...)` phải dùng lại `configurable.thread_id` của lần invoke bị interrupt
- **PostgresSaver cho production:** MemorySaver tiện cho dev nhưng data mất khi restart — luôn dùng persistent checkpointer ở production
- **Parallel execution với fan-out/fan-in:** Chạy independent tasks song song như Promise.all(), merge kết quả với reducer
- **Subgraphs cho modularity:** Compose complex workflows từ reusable subgraphs, giống Express sub-routers
- **Streaming là UX best practice:** Token-level streaming với `stream_mode="messages"` cho real-time feedback

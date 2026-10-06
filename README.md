# BTTH#3: Flight Booking Agent & Harness Architecture

An automated flight booking agent system built with LangChain, LangGraph, and a 4-layer Harness control framework, following the core engineering principle:
$$\text{Agent} = \text{Model} + \text{Harness}$$

---

## 1. Project Structure

```text
SE373-BTTH-Buoi-3/
├── src/
│   ├── domain/          # Pydantic data schemas (Flight, Booking, FlightConstraints)
│   ├── tools/           # 5 mockup tools with structured JSON & semantic error hints
│   ├── harness/         # 4-layer Harness protection and failure mode sensors
│   │   ├── constraints.py   # Layer 1: Constraints as Data
│   │   ├── verification.py  # Layer 2: Computational Verification (code predicate)
│   │   ├── permission.py    # Layer 3: Permission Gatekeeper
│   │   ├── handoff.py       # Layer 4: Standardized Human Handoff (30s protocol)
│   │   ├── detectors.py     # LoopDetector & GroundingSensor
│   │   ├── budget.py        # ExecutionBudget (steps, tokens, timeout)
│   │   └── middleware.py    # HarnessMiddleware for LangChain tool interception
│   ├── agents/          # 3 Agent design patterns
│   │   ├── react_agent.py        # Pattern 1: ReAct Agent (create_agent)
│   │   ├── plan_execute_agent.py # Pattern 2: Plan-then-Execute (Pre-run review)
│   │   ├── hybrid_agent.py       # Pattern 3: Hybrid Agent (TodoList + Replan on drift)
│   │   └── model_provider.py     # LLM provider (Gemini / OpenAI / Offline Fallback)
│   └── benchmark/       # 5 standardized evaluation scenarios
│       ├── scenarios.py     # Scenarios SC1 through SC5
│       └── evaluator.py     # Benchmark runner & quantitative comparison matrix
├── tests/               # 22 standalone unit tests
├── main.py              # Unified CLI runner
├── requirements.txt     # Python package dependencies
├── .env.example         # Environment configuration template
└── 24521182_LeVuHoangNguyen_BTTH3.pdf # Official technical lab report
```

---

## 2. Installation & Setup

Prerequisites: **Python 3.10+**.

```bash
# Install dependencies
pip install -r requirements.txt
```

*(Optional)* Configure live LLM provider:
Create a `.env` file from `.env.example` with your API key (supports Google Gemini or OpenAI):
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest
```
*Note: If no API key is provided, the system automatically uses deterministic offline mock models to ensure tests run reliably without network or quota constraints.*

---

## 3. Usage

### 3.1. Run Full Unit Test Suite (22/22 tests)
```bash
python -m unittest discover tests -v
```

### 3.2. Run Individual Agent Architectures
```bash
# Pattern 1: ReAct Agent
python main.py --agent react

# Pattern 2: Plan-then-Execute Agent
python main.py --agent plan

# Pattern 3: Hybrid Agent
python main.py --agent hybrid
```

### 3.3. Run Permission Gate & Human Handoff Demonstration
```bash
python main.py --agent hybrid --require-approval
```

### 3.4. Run Quantitative Benchmark (All 3 Agents across 5 Scenarios)
```bash
python main.py --benchmark
```

---

## 4. Empirical Benchmark Summary

Measured across 5 standardized scenarios (SC1: Happy Path, SC2: Environmental Drift, SC3: Permission Gate, SC4: Impossible Budget, SC5: Pre-Execution Safety Rejection):

| Metric | Pattern 1: ReAct | Pattern 2: Plan-then-Execute | Pattern 3: Hybrid |
| :--- | :---: | :---: | :---: |
| **Success Rate (Booking)** | 20.0% (1/5) | 20.0% (1/5) | 20.0% (1/5) |
| **Average Steps** | 3.4 | 2.4 | 3.0 |
| **Average Tokens** | 12,700 | 1,440 | 3,900 |
| **Handoff / Approvals Triggered** | 4 times | 3 times | 4 times |
| **Drift Resilience (SC2)** | Moderate (Dynamic step) | Brittle (Static plan fails) | **High (Dynamic replanning)** |
| **Pre-execution Cost Control (SC5)** | None | **Absolute (Pre-run review)** | Roadmap-guided |

Full technical analysis, architecture diagrams, and execution proof screenshots are provided in `24521182_LeVuHoangNguyen_BTTH3.pdf`.

# DataAlchemy 

A **config-driven, multi-agent orchestration backend** for portfolio-level AI/ML systems.
This project enables dynamic, LLM-powered agents to collaborate across data pipelines, model training, evaluation, and reporting — all orchestrated through a declarative YAML configuration.

---

##  Overview

AgentML Backend is designed to power **portfolio-level AI systems**, where multiple projects run simultaneously and are coordinated by intelligent agents.

Instead of hardcoding workflows, this system:

* Uses **YAML-defined agents**
* Supports **dynamic task delegation**
* Enables **multi-agent reasoning**
* Streams **live updates to dashboards**
* Integrates with **Docker, databases, and reporting systems**

---

##  Project Structure

```
agentml-backend/
├─ app/
│  ├─ main.py                  # FastAPI entrypoint
│  ├─ api/                     # API routes (REST + WebSocket)
│  ├─ core/                    # Config, settings, logging
│  ├─ db/                      # Database models & session
│  ├─ engine/                  # Core agent orchestration logic
│  ├─ services/                # Business logic services
│  └─ utils/                   # Helpers (IDs, etc.)
├─ configs/
│  └─ agents.yaml              # Agent definitions (CORE of system)
├─ docker/
│  ├─ Dockerfile
│  └─ docker-compose.yml
├─ requirements.txt
└─ run.py                      # Local dev entrypoint
```

---

##  Core Concepts

### 1. Config-Driven Agents

All agents are defined in:

```
configs/agents.yaml
```

Each agent includes:

* model
* instruction
* sub-agents
* toolsets

Example:

```yaml
root:
  model: openai/gpt-5-mini
  description: Portfolio orchestrator
  sub_agents:
    - planner
    - ml_engineer
```

---

### 2. Orchestration Engine

The system revolves around:

```
app/engine/orchestrator.py
```

Responsibilities:

* Manage execution queue
* Delegate tasks between agents
* Track execution history
* Emit dashboard updates

---

### 3. Agent Runtime

```
app/engine/agent_runtime.py
```

* Loads agent config
* Resolves tools + sub-agents
* Calls LLM layer
* Returns structured results

---

### 4. LLM Layer

```
app/engine/llm_client.py
```

* Executes agent reasoning
* Returns structured `AgentResult`
* Drives dynamic decision-making


---

### 5. Execution Model

Each agent returns:

```json
{
  "status": "success",
  "summary": "...",
  "confidence": 0.9,
  "next_actions": [],
  "artifacts": [],
  "dashboard_update": {}
}
```

This enables:

* chaining agents dynamically
* real-time UI updates
* auditability

---

### 6. Real-Time Updates

WebSocket endpoint:

```
/ws/portfolio/{portfolio_id}
```

Streams:

* progress updates
* agent decisions
* system health

---

### 7. Persistence Layer

```
PostgreSQL
```

Stores:

* agent runs
* execution history
* project state

Model:

```
PortfolioRun
```

---

### 8. Tool System

```
app/engine/tool_executor.py
```

Supports:

* filesystem
* shell
* python execution
* HTTP requests
* (extensible for MCP, SQL, etc.)

---

### 9. Docker Integration

```
app/engine/docker_runtime.py
```

* Run agents in isolated containers
* Future: scale workloads dynamically
* Currently optional (stub mode supported)

---

### 10. Reporting Layer

```
app/services/report_service.py
```

* Generates structured reports
* Prepares Power BI-compatible exports

---

##  Getting Started

### 1. Clone the repo

```bash
git clone <your-repo>
cd agentml-backend
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run locally

```bash
python run.py
```

API available at:

```
http://localhost:8000
```

---

### 4. Run with Docker

```bash
cd docker
docker-compose up --build
```

---

## 📡 API Usage

### Execute Portfolio

**POST**

```
/api/portfolio/execute
```

Example:

```json
{
  "goal": "Build a churn prediction model",
  "portfolio_id": "portfolio_001",
  "project_id": "project_churn",
  "data_sources": ["s3://data/churn.csv"]
}
```

---

### Get Run History

**GET**

```
/api/portfolio/{portfolio_id}/runs
```

---

### WebSocket (Live Updates)

```
ws://localhost:8000/ws/portfolio/{portfolio_id}
```

---

##  Execution Flow

1. Request hits API
2. Planner builds payload
3. Root agent orchestrates
4. Tasks delegated to agents
5. Results stored in DB
6. Updates streamed via WebSocket
7. Final report generated

---

##  Agent System

### Default Agents

| Agent           | Role                    |
| --------------- | ----------------------- |
| root            | Portfolio orchestration |
| planner         | Workflow generation     |
| data_engineer   | Data pipelines          |
| ml_engineer     | Model training          |
| evaluator       | Validation              |
| project_manager | Project tracking        |
| reporter        | Reporting               |
| infra_ops       | Infrastructure          |

---

##  Development Notes

### Replace LLM Stub

Edit:

```
app/engine/llm_client.py
```

Add:

* OpenAI SDK
* Anthropic SDK
* structured JSON outputs

---

### Extend Tooling

Edit:

```
tool_executor.py
```

Add:

* SQL execution
* vector DB queries
* external APIs

---

### Improve Scaling

Future improvements:

* Redis queue (Celery / RQ)
* Kafka event streaming
* async worker pools
* distributed agent containers

---

##  Frontend Integration

The backend is designed for:

* dashboard cards
* progress bars
* project timelines
* KPI charts
* Power BI exports

---

##  Future Enhancements

* Auth & RBAC
* Multi-tenant portfolios
* Agent memory (vector DB)
* Self-improving agents
* Cost tracking
* Model selection optimization

---

##  Philosophy

AgentML is built on:

* **Config over code**
* **Dynamic reasoning over static pipelines**
* **Multi-agent collaboration**
* **Portfolio-level intelligence**


---

##  Author
Quan Do, Thuy Nguyen, Huan Tran.

---

## Final Note

This is not just a backend — it's a **framework for building autonomous AI systems at scale**.

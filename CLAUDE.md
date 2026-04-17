# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
cd DataAlchemy/backend

# Install dependencies
pip install -r requirements.txt

# Run dev server (FastAPI on :8000, hot-reload)
python run.py

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_model_training_agent.py

# Run a single test by name
pytest tests/test_data_quality_agent.py -k "test_missing_values"
```

### Frontend

```bash
cd DataAlchemy/frontend
npm i
npm run dev
```

## Architecture

DataAlchemy is a **multi-agent ML automation platform**. A user uploads a CSV and describes a goal in natural language; the system plans and executes the full data science workflow automatically.

### Request lifecycle

1. **Upload** — `POST /api/upload` saves the CSV and runs `schema_profiler.py` to build a JSON schema profile stored in SQLite (`uploads` table).
2. **Planning** — `POST /api/supervisor/start` calls `engine/supervisor.py`, which appends the schema profile to the system prompt and forces the LLM (GPT-4o) to call either `propose_plan` or `finalize_plan` via OpenAI function-calling (`engine/llm_client.py`).
3. **Refinement** — `POST /api/supervisor/message` iterates plan proposals until the user confirms.
4. **Execution** — On confirmation, `engine/coordinator.py` runs each plan step sequentially, calling `engine/agent_runtime.py:run_agent()` with `{dataset_id, step, agent, config, prior_results}`. Each step's full result is passed as `prior_results` to the next.
5. **Results** — Aggregated `{completed_steps, results, artifacts, dashboard_updates}` returned to the API caller.

### Agent system

All agent configs live in `configs/agents.yaml`. Each entry defines model settings, defaults, and the system prompt for LLM-driven agents.

**Implemented handlers** (registered in `engine/agent_runtime.py` at module load):

| Agent | Handler location | Role |
|---|---|---|
| `data_quality_agent` | `agents/data_quality_agent.py` | 8 quality checks (nulls, duplicates, outliers, imbalance, cardinality, zero-variance) → quality score + recommendations |
| `data_preprocessing_agent` | `agents/data_preprocessing_agent.py` | Dedup, imputation, encoding, scaling, date decomposition → writes `uploads/preprocessed_{dataset_id}.csv` |
| `model_training_agent` | `agents/model_training_agent.py` | Candidate model selection by dataset size, Optuna HPO, trains final model → writes `uploads/model_{dataset_id}.joblib` |

**Stub/missing agents** (fall back to `_default_handler`): `visualization_agent`, `evaluation_agent`, `report_agent`

### Adding a new agent

1. Add config block to `configs/agents.yaml` under `agents:` and list the name in `supervisor.available_agents`
2. Create `app/agents/<name>.py` with an `async def <name>_handler(payload: dict) -> dict` returning `{status, result, artifacts, dashboard_updates}`
3. Import and register at the bottom of `engine/agent_runtime.py`

### Agent handler payload contract

```python
payload = {
    "dataset_id": str,         # used to locate CSV in uploads/
    "step": str,               # step name from the plan
    "agent": str,              # agent name
    "config": dict,            # merged defaults + user overrides from supervisor
    "prior_results": list,     # all previous step results in execution order
}
```

### Key files

- `configs/agents.yaml` — single source of truth for agent configs, defaults, and supervisor system prompt
- `engine/coordinator.py` — sequential plan executor; structured for later parallelization
- `engine/agent_runtime.py` — handler registry; all real agent imports happen here
- `engine/supervisor.py` — LLM planning loop with propose/finalize workflow
- `engine/llm_client.py` — OpenAI wrapper with forced tool use
- `engine/registry.py` — YAML config loader with caching
- `db/models.py` — SQLite schema (single `uploads` table)
- `services/schema_profiler.py` — CSV analysis producing column stats, distributions, type inference

### What is not yet wired

- `app/api/routes_ws.py` — WebSocket skeleton exists but is empty; no real-time streaming
- `app/engine/docker_runtime.py` — Docker container execution stub, unused
- Frontend (`DataAlchemy/frontend/`) — React/MUI/Radix component scaffolding exists but is not connected to the backend APIs

# GitHub Copilot Instructions for SNA Evaluation Framework

## Project Overview

This is an Evaluation-as-a-Service framework that provides async API for testing AI agent responses using PyRIT with 6 specialized scorers.

**Key Context:**
- **Mode**: Async FastAPI service with batch evaluation support
- **Target**: Evaluates agents from commerce_agents app (runs on port 6000)
- **PyRIT**: Custom fork `albert-heijn-technology/PyRIT@cc729fcb959d146642bddd422453f46db94d632e`
- **Python**: 3.10, venv: `.venv-eval`
- **Port**: 8000

## Architecture

**Components:**
- `eval/api.py` - FastAPI service with 7 endpoints
- `eval/models.py` - Pydantic models (request/response validation)
- `eval/job_queue.py` - Thread-safe in-memory job queue
- `eval/worker.py` - Background worker for PyRIT execution
- `eval/unity_catalog.py` - Databricks UC integration (optional)

**Flow:**
1. Client POSTs batch evaluation → API returns 202 + job_id
2. Background worker executes PyRIT CLI → Generates reports
3. Client polls GET /evaluate/{job_id} for status
4. Client fetches GET /evaluate/{job_id}/results when complete

## Critical Configuration

### Azure OpenAI Endpoint
**MUST use full Azure-format URL:**
```
https://api-ai.digitaldev.nl/openai/deployments/gpt-5/chat/completions?api-version=2024-04-01-preview
```

Path is `/openai/deployments/`, NOT `/openai/v1/deployments/`

### Environment Variables (.env)
**Required:**
- `OPENAI_CHAT_ENDPOINT` - Azure OpenAI endpoint (full format)
- `OPENAI_API_KEY` - API key

**Optional (Unity Catalog):**
- `DATABRICKS_SERVER_HOSTNAME` - Databricks workspace
- `DATABRICKS_HTTP_PATH` - SQL warehouse path
- `DATABRICKS_TOKEN` - Access token
- `UNITY_CATALOG_ENABLED` - true/false (default: false until permissions granted)

### Temperature Setting
**REQUIRED:** `--scorer-temperature 1.0` in worker.py (gpt-5 doesn't support 0.0)

Temperature in YAML files is **ignored** - only CLI flag works.

Temperature in YAML files is **ignored** - only CLI flag works.

## File Structure

```
eval/
├── api.py                   # FastAPI app with 7 endpoints
├── models.py                # Pydantic models (JobStatus, EvaluationRequest, etc.)
├── job_queue.py             # Thread-safe in-memory job queue
├── worker.py                # Background worker for PyRIT CLI execution
├── unity_catalog.py         # Databricks UC writer (conditional)
├── config.yaml              # HTTP template for target API
└── scorers/
    ├── llm/*.yaml          # 5 LLM scorers
    └── programmatic/*.py   # 1 programmatic scorer

examples/
└── client_example.py        # Full API client with polling

scripts/
└── start_api.sh            # Start API service
```

## API Endpoints

1. `GET /` - Health check
2. `GET /health` - Detailed health with timestamp
3. `GET /scorers` - List 6 scorers with weights
4. `POST /evaluate` - Submit batch (returns 202 + job_id)
5. `GET /evaluate/{job_id}` - Poll status with progress
6. `GET /evaluate/{job_id}/results` - Get detailed results
7. `GET /jobs` - List all jobs

## Request/Response Format

**Request (POST /evaluate):**
```json
{
  "target_url": "http://localhost:6000/chat",
  "questions": [{
    "question": "What were total sales in Q3?",
    "expected_outcome": {
      "response": "€4.46B total sales",
      "agent": "merchandising_descriptives",
      "reason": "Sales aggregation query"
    }
  }]
}
```

**Response (GET /evaluate/{job_id}/results):**
```json
{
  "overall_score": 0.8,
  "questions_completed": 1,
  "question_results": [{
    "question": "...",
    "scorer_results": [{
      "scorer_name": "numerical_accuracy",
      "score": 0.8,
      "weight": 0.3,
      "weighted_score": 0.24,
      "rationale": "..."
    }]
  }],
  "report_json_path": "pyrit_reports/.../report.json",
  "report_html_path": "pyrit_reports/.../report.html"
}
```

## Scorer Configuration

6 scorers (3 required):
1. Numerical Accuracy (30%, required)
2. Data Methodology (30%, required)
3. Agent Routing (20%, required)
4. Completeness (10%)
5. Assumption Transparency (5%)
6. Error Handling (5%)

All LLM scorers use PyRIT Evaluator YAML format. NO temperature field in YAML - use CLI flag only.

## Common Issues

**Unity Catalog permission denied:**
- Set `UNITY_CATALOG_ENABLED=false` in .env
- Results still saved locally in pyrit_reports/
- Wait for CREATE SCHEMA permissions before enabling

**Port 8000 already in use:**
```bash
lsof -ti:8000 | xargs kill -9
```

**Connection refused port 6000:**
- Commerce agents API not running
- Start: `cd ~/ah-sa-commerce_agents_crew && python -m commerce_agents.main_langchain api`

**Worker not loading .env:**
- Lazy initialization pattern: worker created on first request, not import
- API loads .env with `load_dotenv()` before importing worker

## When Making Changes

**DO:**
- Use Pydantic models for all request/response validation
- Keep job queue operations thread-safe
- Make Unity Catalog writes conditional on UNITY_CATALOG_ENABLED
- Test with both UC enabled and disabled

**DON'T:**
- Instantiate worker at module level (breaks .env loading)
- Modify PyRIT CLI parameters without testing
- Remove error handling from UC writes (should gracefully degrade)

## Testing

**Start API:**
```bash
uvicorn eval.api:app --host 0.0.0.0 --port 8000
```

**Submit test request:**
```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"target_url":"http://localhost:6000/chat","questions":[...]}'
```

**Check status:**
```bash
curl http://localhost:8000/evaluate/{job_id}
```

All evaluation components match `eval/` directory in:
https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew

Refer to that repo's eval setup when in doubt.

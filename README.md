# SNA Evaluation Framework

Evaluation-as-a-Service framework for testing AI agents using PyRIT. Runs as an async API service with batch evaluation support.

## Quick Start

### 1. Setup

```bash
# Create virtual environment
python3 -m venv .venv-eval
source .venv-eval/bin/activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI and Databricks credentials
```

### 2. Start API Service

```bash
# Start the API server
uvicorn eval.api:app --host 0.0.0.0 --port 8000

# Or use the start script
./scripts/start_api.sh
```

The service will run on **http://localhost:8000** with interactive docs at **http://localhost:8000/docs**.

### 3. Submit Evaluation Request

**From your application (e.g., commerce_agents):**

```python
import requests

# Submit batch evaluation
response = requests.post("http://localhost:8000/evaluate", json={
    "target_url": "http://localhost:6000/chat",
    "questions": [
        {
            "question": "What were total sales in Q3 2024?",
            "expected_outcome": {
                "response": "Total sales in Q3 2024 were €4.46B",
                "agent": "merchandising_descriptives",
                "reason": "Simple aggregation query for sales metrics"
            }
        }
    ]
})

# Get job ID
job = response.json()
job_id = job["job_id"]

# Poll for completion
import time
while True:
    status = requests.get(f"http://localhost:8000/evaluate/{job_id}").json()
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(5)

# Get detailed results
results = requests.get(f"http://localhost:8000/evaluate/{job_id}/results").json()
print(f"Overall Score: {results['overall_score']}")
print(f"JSON Report: {results['report_json_path']}")
print(f"HTML Report: {results['report_html_path']}")
```

See [examples/client_example.py](examples/client_example.py) for a complete client implementation with error handling and progress tracking.

## API Endpoints

- **GET /** - Health check
- **GET /health** - Detailed health status
- **GET /scorers** - List available scorers with weights
- **POST /evaluate** - Submit batch evaluation (returns 202 + job_id)
- **GET /evaluate/{job_id}** - Poll job status with progress
- **GET /evaluate/{job_id}/results** - Get detailed results (when completed)
- **GET /jobs** - List all jobs

## Configuration

### Environment Variables (.env)

**Required:**
- `OPENAI_CHAT_ENDPOINT` - Azure OpenAI endpoint (full format with deployments path)
- `OPENAI_API_KEY` - Azure OpenAI API key

**Optional:**
- `DATABRICKS_SERVER_HOSTNAME` - Databricks workspace hostname
- `DATABRICKS_HTTP_PATH` - SQL warehouse HTTP path
- `DATABRICKS_TOKEN` - Databricks access token
- `UNITY_CATALOG_ENABLED` - Enable/disable Unity Catalog writes (true/false)

### Unity Catalog Integration

Results can be automatically stored in Databricks Unity Catalog:

- **Catalog**: `alh_preprd_spa_commerce`
- **Schema**: `conversational_analytics`
- **Table**: `eval_results` (denormalized - one row per question per scorer)
- **Volume**: `eval_reports` (stores JSON/HTML report files)

Set `UNITY_CATALOG_ENABLED=true` in .env to enable (requires CREATE SCHEMA permissions).

### Scorers (6 total)

**Required** (must pass):
1. **Numerical Accuracy** (30%) - All numbers match exactly
2. **Data Methodology** (30%) - SQL logic correct + sources cited
3. **Agent Routing** (20%) - Correct agent selected

**Optional**:
4. **Completeness** (10%) - All parts answered
5. **Assumption Transparency** (5%) - Assumptions stated
6. **Error Handling** (5%) - Graceful errors

## Project Structure

```
.
├── eval/
│   ├── api.py                         # FastAPI service
│   ├── models.py                      # Pydantic request/response models
│   ├── job_queue.py                   # In-memory job queue
│   ├── worker.py                      # Background evaluation worker
│   ├── unity_catalog.py               # Databricks UC integration
│   ├── config.yaml                    # HTTP request template
│   └── scorers/
│       ├── llm/                       # LLM-based scorers (5 files)
│       └── programmatic/              # Code-based scorers (1 file)
├── scripts/
│   └── start_api.sh                   # Start API service
├── examples/
│   └── client_example.py              # Example API client
├── pyrit_reports/                     # Evaluation reports (gitignored)
└── README.md
```

## Key Technical Details

- **Architecture**: Async FastAPI with background worker threads
- **Job Queue**: In-memory queue with thread-safe operations
- **PyRIT Integration**: Subprocess execution of PyRIT CLI
- **Response Format**: Structured JSON with per-scorer breakdown
- **Report Generation**: JSON + HTML reports saved to `pyrit_reports/`
- **Target Endpoint**: Configurable HTTP endpoint (default: localhost:6000)
- **Evaluation Time**: ~60 seconds per question (6 scorers × ~10s each)

## Troubleshooting

**Port already in use (8000)**
```bash
lsof -ti:8000 | xargs kill -9
```

**Connection refused on port 6000**
- Start commerce agents API: `cd ~/PycharmProjects/ah-sa-commerce_agents_crew && python -m commerce_agents.main_langchain api`

**Unity Catalog permission denied**
- Set `UNITY_CATALOG_ENABLED=false` in .env to disable UC writes
- Results will still be saved locally in `pyrit_reports/`

**No module 'pyrit'**
- Activate correct venv: `source .venv-eval/bin/activate`
- Verify PyRIT installed: `pip show pyrit`

## Development

**PyRIT Version:**
Uses custom fork: `albert-heijn-technology/PyRIT@cc729fcb959d146642bddd422453f46db94d632e`

**Testing:**
```bash
# Start API
uvicorn eval.api:app --host 0.0.0.0 --port 8000

# In another terminal, run client example
python examples/client_example.py
```

Source: [https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew](https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew)

This evaluation framework is designed to work with the agents in that repository.

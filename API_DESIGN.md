# API Design - SNA Evaluation Framework

## Overview

The evaluation framework provides Evaluation-as-a-Service for AI applications. 

**Architecture Flow:**

```
┌─────────────────────┐
│ Commerce Agents App │
│   (Port 6000)       │
└──────────┬──────────┘
           │ 1. POST /evaluate
           │    {target_url, question, expected_outcome}
           ▼
┌─────────────────────────────────────┐
│  SNA Evaluation Framework API       │
│       (Port 8000)                   │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ 2. Use PyRIT Library to:      │ │
│  │    - Send question to         │ │
│  │      target_url (port 6000)   │ │
│  │    - Get actual response      │ │
│  │    - Run 6 scorers           │ │
│  │    - Generate results         │ │
│  └───────────────────────────────┘ │
└──────────┬──────────────────────────┘
           │ 3. Write results
           │    (JSON + HTML reports)
           ▼
┌─────────────────────────────────────┐
│  Unity Catalog                      │
│  ca_workspace.sna_evaluation        │
│  .eval_results                      │
└─────────────────────────────────────┘
```

**Key Points:**
- Commerce Agents sends evaluation requests to this framework
- Framework uses PyRIT library internally (not an external service)
- PyRIT sends the question to commerce agents and evaluates the response
- Results (JSON/HTML) are written to Unity Catalog for persistence and analytics

## Request Format

### POST /evaluate (Async)

**Batch evaluation format matching PyRIT dataset structure:**

```json
{
  "target_url": "http://localhost:6000/chat",
  "questions": [
    {
      "question": "What were total sales in Q3 2024?",
      "expected_outcome": {
        "response": "Total sales in Q3 2024 were €4,459,017,155.65.",
        "agent": "merchandising_descriptives",
        "reason": "Simple aggregation query for sales metrics"
      }
    },
    {
      "question": "What was the average weekly customer count in Q2 2024?",
      "expected_outcome": {
        "response": "The average weekly customer count in Q2 2024 was 45,678 customers.",
        "agent": "customer_insights",
        "reason": "Average calculation over time period requires customer data"
      }
    },
    {
      "question": "What was the profit margin for Electronics category in 2024?",
      "expected_outcome": {
        "response": "The profit margin for Electronics in 2024 was 23.5%.",
        "agent": "merchandising_descriptives",
        "reason": "Profit margin calculation for specific category"
      }
    }
  ]
}
```

### Required Fields

- `target_url` (string) - URL of the application to evaluate (e.g., commerce agents API endpoint)
- `questions` (array) - List of questions to evaluate (matches in_scope_questions.yaml format)
  - `question` (string) - The user question (will be sent to target_url)
  - `expected_outcome` (object) - Expected response structure for evaluation
    - `response` (string) - The expected answer text (used by scorers for comparison)
    - `agent` (string) - Expected agent name (used by agent_routing scorer)
    - `reason` (string) - Why this agent should be chosen (used by agent_routing scorer)

**PyRIT Processing:**
1. Framework creates temporary YAML dataset file from `questions` array
2. Passes dataset to PyRIT via `--dataset-path` parameter
3. PyRIT sends each `question` to `target_url` 
4. Receives responses with fields: `response`, `agent_used`, `routing_reason` (from config.yaml field_defs)
5. Compares actual responses vs `expected_outcome` for all questions using all 6 scorers
6. Generates aggregated evaluation results

**Notes:**
- This matches the current PyRIT dataset format (`eval/datasets_sensitive/in_scope_questions_hydrated_json.yaml`)
- Supports batch evaluation of multiple questions in one API call
- Framework converts JSON request to YAML format for PyRIT compatibility
- Commerce agents responses are parsed according to `eval/config.yaml` field_defs

---

## Response Format

### Immediate Response (202 Accepted)

**Async job created - poll for results:**

```json
{
  "job_id": "eval_20260102_115043_a1b2c3",
  "status": "queued",
  "submitted_at": "2026-01-02T11:50:43Z",
  "target_url": "http://localhost:6000/chat",
  "total_questions": 3,
  "status_url": "/evaluate/eval_20260102_115043_a1b2c3",
  "estimated_completion_seconds": 90
}
```

---

### GET /evaluate/{job_id} - Check Status

**While Running (200 OK):**

```json
{
  "job_id": "eval_20260102_115043_a1b2c3",
  "status": "running",
  "submitted_at": "2026-01-02T11:50:43Z",
  "started_at": "2026-01-02T11:50:45Z",
  "target_url": "http://localhost:6000/chat",
  "total_questions": 3,
  "progress": {
    "questions_completed": 2,
    "questions_total": 3,
    "scorers_completed": 12,
    "scorers_total": 18,
    "percent": 67
  }
}
```

**Completed (200 OK):**

```json
{
  "job_id": "eval_20260102_115043_a1b2c3",
  "status": "completed",
  "submitted_at": "2026-01-02T11:50:43Z",
  "started_at": "2026-01-02T11:50:45Z",
  "completed_at": "2026-01-02T11:51:10Z",
  "duration_seconds": 25,
  "result": {
    "passed": true,
    "overall_score": 0.85,
    "scorer_results": [
      {
        "name": "numerical_accuracy",
        "score": 1.0,
        "passed": true,
        "weight": 0.3,
        "rationale": "All numerical values match expected answers exactly."
      },
      {
        "name": "data_methodology",
        "score": 0.9,
        "passed": true,
        "weight": 0.3,
        "rationale": "SQL query is correct. Data source cited."
      },
      {
        "name": "agent_routing",
        "score": 1.0,
        "passed": true,
        "weight": 0.2,
        "rationale": "Correct agent selected."
      }
    ],
    "summary": {
      "total_scorers": 6,
      "required_passed": 3,
      "required_failed": 0
    },
    "reports": {
      "json_path": "dbfs:/unity-catalog/ca_workspace/sna_evaluation/reports/eval_20260102_115043_a1b2c3.json",
      "html_path": "dbfs:/unity-catalog/ca_workspace/sna_evaluation/reports/eval_20260102_115043_a1b2c3.html"
    },
    "unity_catalog_table": "ca_workspace.sna_evaluation.eval_results"
  }
}
```

**Failed Evaluation (200 OK):**

```json
{
  "job_id": "eval_20260102_120000_d4e5f6",
  "status": "completed",
  "result": {
    "passed": false,
    "overall_score": 0.45,
    "critical_issues": [
      "FAILED: numerical_accuracy - Numbers don't match expected values",
      "FAILED: agent_routing - Wrong agent selected"
    ]
  }
}
```

**Job Error (200 OK):**

```json
{
  "job_id": "eval_20260102_120500_g7h8i9",
  "status": "failed",
  "error": {
    "code": "SCORER_ERROR",
    "message": "Failed to connect to Azure OpenAI",
    "details": "Connection timeout after 30s"
  }
}
```

---

## Design Decisions

### 1. Async-First Architecture
- POST /evaluate returns immediately with job_id (202 Accepted)
- Client polls GET /evaluate/{job_id} for results
- Evaluation runs in background (can take 30-60 seconds)
- Non-blocking for client applications

### 2. PyRIT-Compatible Request Format
- Matches existing PyRIT dataset structure exactly
- `question` + `expected_outcome` with fields: `response`, `agent`, `reason`
- Minimal transformation needed - can be passed directly to PyRIT
- Based on current implementation in `eval/datasets_sensitive/in_scope_questions_hydrated_json.yaml`

### 3. Config-Driven Target Communication
- `target_url` parameter specifies where to send questions
- `eval/config.yaml` defines HTTP request template and response parsing
- Current config extracts: `response`, `agent_used`, `routing_reason` from JSON
- Framework uses these extracted fields for scorer evaluation

### 4. Unity Catalog Storage
- All evaluation results written to Unity Catalog
- Table: `ca_workspace.sna_evaluation.eval_results`
- Stores both structured data (scores, status) and file references
- HTML and JSON reports stored as managed files in Unity Catalog
- Enables analytics and tracking over time
- Centralized storage for all commerce agents evaluations

### 5. PyRIT Integration
- PyRIT runs as a library within the evaluation framework
- Uses pyrit-eval CLI internally with these parameters:
  - `--config eval/config.yaml` (HTTP template + field extraction)
  - `--dataset-path` (dynamically created from API request)
  - `--target-endpoint` (from request's target_url)
  - `--scorer` (all 6 scorers with weights)
  - `--openai-*` (Azure credentials for LLM scorers)
  - `--scorer-temperature 1.0` (required for gpt-5)
- Sends question to target_url and receives actual response
- Runs all configured scorers (6 total: 3 required, 3 optional)
- Generates evaluation reports (JSON for data, HTML for viewing)
- Framework stores all outputs to Unity Catalog

### 4. Status Polling
- GET /evaluate/{job_id} returns current status
- Status values: `queued`, `running`, `completed`, `failed`
- Progress tracking shows completion percentage
- Results available immediately after completion

### 5. Report Storage
- JSON report: Structured evaluation data
- HTML report: Human-readable formatted results  
- Both stored in Unity Catalog managed storage
- Accessible via Unity Catalog file paths
- Long-term retention for audit and analysis

### 5. No Authentication (Phase 1)
- Open access for internal development
- Authentication layer can be added later
- Focus on core functionality first

---

---

## API Endpoints

### POST /evaluate
Submit evaluation job (async)
- Returns: 202 Accepted with job_id
- Background: Runs PyRIT evaluation
- Storage: Writes to Unity Catalog

### GET /evaluate/{job_id}
Check evaluation status
- Returns: Job status and results (if completed)
- Polling: Client should poll every 2-5 seconds

### GET /health
Health check endpoint
```json
{"status": "healthy", "version": "0.1.0"}
```

### GET /scorers
List available scorers
```json
{
  "scorers": [
    {
      "name": "numerical_accuracy",
      "type": "llm",
      "category": "required",
      "default_weight": 0.3
    }
  ]
}
```

---

## Unity Catalog Integration

### Table Schema: `ca_workspace.sna_evaluation.eval_results`

```sql
CREATE TABLE ca_workspace.sna_evaluation.eval_results (
  job_id STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  status STRING NOT NULL,  -- queued, running, completed, failed
  target_url STRING NOT NULL,
  question STRING NOT NULL,
  expected_response STRING,
  expected_agent STRING,
  overall_score DOUBLE,
  passed BOOLEAN,
  scorer_results ARRAY<STRUCT<
    name: STRING,
    score: DOUBLE,
    passed: BOOLEAN,
    weight: DOUBLE,
    rationale: STRING
  >>,
  required_passed INT,
  required_failed INT,
  total_scorers INT,
  error_message STRING,
  framework_version STRING,
  scorer_model STRING,
  json_report_path STRING,  -- Path to JSON report in Unity Catalog
  html_report_path STRING,  -- Path to HTML report in Unity Catalog
  PRIMARY KEY (job_id)
)
USING DELTA
PARTITIONED BY (DATE(submitted_at));
```

### Report Storage Structure
```
dbfs:/unity-catalog/ca_workspace/sna_evaluation/
├── reports/
│   ├── eval_20260102_115043_a1b2c3.json  ← Structured data
│   ├── eval_20260102_115043_a1b2c3.html  ← Formatted view
│   ├── eval_20260102_120000_d4e5f6.json
│   └── eval_20260102_120000_d4e5f6.html
```

### Write Pattern
- **On Job Creation**: Write row with status=queued
- **On Start**: Update status=running, add started_at timestamp
- **On Completion**: 
  - Update status=completed
  - Write JSON report to Unity Catalog managed storage
  - Write HTML report to Unity Catalog managed storage
  - Update table with report paths and evaluation results
- **On Failure**: Update status=failed, add error_message
- Enable time-series analytics and trend tracking
- Reports accessible via Unity Catalog file paths for long-term retention

---

## Questions for Discussion

~~1. **Response Detail Level**: Should we require structured response.details, or keep it optional?~~
✅ **Decided**: Simple format - just question + expected_outcome

~~2. **Expected Answer Format**: Should ground truth always be required, or optional?~~
✅ **Decided**: Required - part of expected_outcome

~~3. **Async vs Sync**: Should evaluations run synchronously (wait for result) or async (return job_id)?~~
✅ **Decided**: Async - return job_id immediately, client polls for results

~~4. **Result Storage**: Should we store evaluation results for later retrieval?~~
✅ **Decided**: Yes - write to Unity Catalog (ca_workspace.sna_evaluation.eval_results)

~~5. **Authentication**: Do we need API keys for access control?~~
✅ **Decided**: Not in Phase 1 - will be discussed later

~~6. **Rate Limiting**: Should we limit requests per client?~~
⏸️ **Deferred**: Address in Phase 2 if needed

---

## Next Steps

1. ✅ Review and approve this design
2. ⬜ Implement request validation schemas (Pydantic models)
3. ⬜ Implement async job queue (in-memory or Redis)
4. ⬜ Integrate with Unity Catalog (write results)
5. ⬜ Implement background worker for PyRIT evaluation
6. ⬜ Add status polling endpoint
7. ⬜ Update client example with async pattern
8. ⬜ Add job cleanup (remove old jobs after N days)

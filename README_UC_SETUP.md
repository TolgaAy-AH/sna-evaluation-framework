# Unity Catalog Setup

The evaluation framework writes results to Unity Catalog in the commerce agents workspace.

## Configuration

Set these environment variables in your `.env` file:

```bash
# Databricks Connection
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your-databricks-access-token
```

## Unity Catalog Resources

The framework will automatically create (if they don't exist):

### 1. Schema
- **Name**: `ca_workspace.sna_evaluation`
- **Purpose**: Container for evaluation artifacts

### 2. Table
- **Name**: `ca_workspace.sna_evaluation.eval_results`
- **Schema**:
  ```sql
  - job_id: STRING (unique job identifier)
  - submitted_at: TIMESTAMP (when job was submitted)
  - started_at: TIMESTAMP (when evaluation started)
  - completed_at: TIMESTAMP (when evaluation completed)
  - status: STRING (queued, running, completed, failed)
  - target_url: STRING (endpoint being evaluated)
  - total_questions: INT (number of questions in batch)
  - questions_completed: INT (number completed)
  - overall_score: DOUBLE (weighted average score 0.0-1.0)
  - question: STRING (the question text)
  - expected_response: STRING (expected response)
  - expected_agent: STRING (expected agent name)
  - expected_reason: STRING (expected routing reason)
  - actual_response: STRING (actual response from target)
  - actual_agent: STRING (actual agent that responded)
  - actual_routing_reason: STRING (actual routing reason)
  - scorer_name: STRING (numerical_accuracy, data_methodology, etc.)
  - scorer_score: DOUBLE (score from this scorer 0.0-1.0)
  - scorer_weight: DOUBLE (weight of this scorer)
  - scorer_weighted_score: DOUBLE (score * weight)
  - scorer_rationale: STRING (explanation from scorer)
  - report_json_path: STRING (path to JSON report in volume)
  - report_html_path: STRING (path to HTML report in volume)
  - error_message: STRING (error if failed)
  - created_at: TIMESTAMP (row creation time)
  ```
- **Partitioning**: Partitioned by `DATE(submitted_at)`
- **Structure**: One row per question per scorer (denormalized for analytics)

### 3. Volume
- **Name**: `ca_workspace.sna_evaluation.eval_reports`
- **Type**: MANAGED
- **Purpose**: Store JSON and HTML evaluation reports
- **Structure**: 
  ```
  /Volumes/ca_workspace/sna_evaluation/eval_reports/
    YYYYMMDD/
      eval_{timestamp}_{id}_json.json
      eval_{timestamp}_{id}_html.html
  ```

## Data Flow

1. **Job Submission**: Commerce agents sends batch evaluation request to API
2. **PyRIT Evaluation**: Framework runs PyRIT evaluation, generates JSON/HTML reports
3. **Upload Reports**: Reports uploaded to Unity Catalog volume
4. **Write Results**: Detailed results (one row per question per scorer) written to table
5. **Response**: API returns job_id, commerce agents polls for completion

## Querying Results

### Get overall scores for a job
```sql
SELECT 
  job_id,
  question,
  AVG(scorer_weighted_score) as overall_score
FROM ca_workspace.sna_evaluation.eval_results
WHERE job_id = 'eval_20260102_120000_abc123'
GROUP BY job_id, question
```

### Get scorer breakdown for a job
```sql
SELECT 
  question,
  scorer_name,
  scorer_score,
  scorer_weight,
  scorer_weighted_score,
  scorer_rationale
FROM ca_workspace.sna_evaluation.eval_results
WHERE job_id = 'eval_20260102_120000_abc123'
ORDER BY question, scorer_weight DESC
```

### Get recent evaluation summary
```sql
SELECT 
  job_id,
  submitted_at,
  completed_at,
  status,
  total_questions,
  AVG(scorer_weighted_score) as overall_score,
  report_json_path,
  report_html_path
FROM ca_workspace.sna_evaluation.eval_results
WHERE DATE(submitted_at) = CURRENT_DATE()
GROUP BY job_id, submitted_at, completed_at, status, total_questions, report_json_path, report_html_path
ORDER BY submitted_at DESC
```

## Permissions

The Databricks token must have:
- `USE CATALOG` on `ca_workspace`
- `USE SCHEMA` and `CREATE` on `ca_workspace.sna_evaluation`
- `SELECT`, `INSERT` on `ca_workspace.sna_evaluation.eval_results`
- `READ VOLUME`, `WRITE VOLUME` on `ca_workspace.sna_evaluation.eval_reports`

## Testing Without Unity Catalog

If Unity Catalog credentials are not configured, the framework will:
- Print a warning
- Skip UC writes
- Still store results in the in-memory job queue
- Results available via API endpoints

This allows local testing without Databricks access.

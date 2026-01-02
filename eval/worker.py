"""Background worker for processing evaluation jobs."""

import os
import yaml
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from eval.models import (
    JobStatus, EvaluationRequest, EvaluationResults, 
    QuestionResult, ScorerResult, ExpectedOutcome
)
from eval.job_queue import job_queue
from eval.unity_catalog import unity_catalog_writer


class EvaluationWorker:
    """Background worker for running PyRIT evaluations."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_path = self.base_dir / "eval" / "config.yaml"
        
        # Load OpenAI configuration from environment
        self.openai_endpoint = os.getenv("OPENAI_CHAT_ENDPOINT")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if not self.openai_endpoint or not self.openai_key:
            raise ValueError("OPENAI_CHAT_ENDPOINT and OPENAI_API_KEY must be set in .env")
        
        # Scorer configuration matching run_evaluation.sh format
        self.scorer_config = {
            "main": {
                "path": "eval/scorers/llm/numerical_accuracy_scorer.yaml",
                "weight": 0.3,
                "threshold": 1.0,
                "required": True
            },
            "auxiliary": [
                {
                    "path": "eval/scorers/llm/data_methodology_scorer.yaml",
                    "weight": 0.3,
                    "threshold": 1.0,
                    "required": True
                },
                {
                    "path": "eval/scorers/programmatic/agent_routing_scorer.py",
                    "callable": "AgentRoutingScorer",
                    "weight": 0.2,
                    "threshold": 1.0,
                    "required": True
                },
                {
                    "path": "eval/scorers/llm/completeness_scorer.yaml",
                    "weight": 0.1,
                    "threshold": 0.8
                },
                {
                    "path": "eval/scorers/llm/assumption_transparency_scorer.yaml",
                    "weight": 0.05,
                    "threshold": 0.8
                },
                {
                    "path": "eval/scorers/llm/error_handling_scorer.yaml",
                    "weight": 0.05,
                    "threshold": 0.8
                }
            ]
        }
        
        # Azure OpenAI configuration
        self.openai_endpoint = os.getenv(
            "OPENAI_CHAT_ENDPOINT",
            "https://api-ai.digitaldev.nl/openai/deployments/gpt-5/chat/completions?api-version=2024-04-01-preview"
        )
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
    
    def process_job(self, job_id: str) -> None:
        """Process a single evaluation job."""
        try:
            # Get job from queue
            job = job_queue.get_job(job_id)
            if not job:
                return
            
            request: EvaluationRequest = job["request"]
            
            # Update status to running
            job_queue.update_status(job_id, JobStatus.RUNNING)
            
            # Create temporary YAML dataset from request
            dataset_path = self._create_dataset_yaml(request)
            
            try:
                # Run PyRIT evaluation
                output_json, output_html = self._run_pyrit_evaluation(
                    dataset_path=dataset_path,
                    target_url=request.target_url,
                    job_id=job_id
                )
                
                # Parse results
                results = self._parse_results(
                    job_id=job_id,
                    request=request,
                    output_json=output_json,
                    output_html=output_html,
                    job_data=job
                )
                
                # Store results in job queue
                job_queue.set_results(job_id, results)
                job_queue.update_status(job_id, JobStatus.COMPLETED)
                
                # Write to Unity Catalog if enabled
                if os.getenv("UNITY_CATALOG_ENABLED", "false").lower() == "true":
                    try:
                        unity_catalog_writer.write_results(results)
                        print(f"Results written to Unity Catalog for job {job_id}")
                    except Exception as e:
                        print(f"Warning: Failed to write to Unity Catalog: {e}")
                else:
                    print(f"Unity Catalog disabled - results saved locally only")
                
            finally:
                # Cleanup temporary dataset file
                if dataset_path and os.path.exists(dataset_path):
                    os.remove(dataset_path)
        
        except Exception as e:
            error_msg = f"Evaluation failed: {str(e)}"
            job_queue.set_error(job_id, error_msg)
            print(f"Error processing job {job_id}: {error_msg}")
    
    def _create_dataset_yaml(self, request: EvaluationRequest) -> str:
        """Convert JSON request to YAML dataset file."""
        # Convert to PyRIT dataset format
        dataset = []
        for q in request.questions:
            # expected_outcome as JSON string (matching hydrated format)
            expected_json = json.dumps({
                "response": q.expected_outcome.response,
                "agent": q.expected_outcome.agent,
                "reason": q.expected_outcome.reason
            }, indent=2)
            
            dataset.append({
                "question": q.question,
                "expected_outcome": expected_json
            })
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.yaml',
            delete=False,
            dir=self.base_dir / "eval"
        ) as f:
            yaml.dump(dataset, f, default_flow_style=False, allow_unicode=True)
            return f.name
    
    def _run_pyrit_evaluation(
        self, 
        dataset_path: str, 
        target_url: str,
        job_id: str
    ) -> tuple[str, str]:
        """Run PyRIT evaluation CLI command."""
        # Build scorer JSON with proper format
        scorer_json = json.dumps(self.scorer_config)
        
        # Create output directory for reports
        output_dir = self.base_dir / "pyrit_reports" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build command (based on run_evaluation.sh)
        venv_python = self.base_dir / ".venv-eval" / "bin" / "python"
        
        # Get auth token for commerce agents (if needed)
        # Commerce agents doesn't require auth token currently
        auth_token = os.getenv("COMMERCE_AGENTS_AUTH_TOKEN", "not-used")
        
        cmd = [
            str(venv_python),
            "-m", "pyrit_eval_runner.cli",
            "run",
            "--config", str(self.config_path),
            "--dataset-path", dataset_path,
            "--scorer", scorer_json,
            "--target-endpoint", target_url,
            "--out", str(output_dir),
            "--auth-token", auth_token,
            "--openai-chat-endpoint", self.openai_endpoint,
            "--openai-api-key", self.openai_key,
            "--openai-chat-model", "gpt-5",
            "--scorer-temperature", "1.0"
        ]
        
        print(f"Running PyRIT evaluation for job {job_id}...")
        print(f"Command: {' '.join(cmd)}")
        
        # Run command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.base_dir)
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"PyRIT evaluation failed: {result.stderr}")
        
        print(f"PyRIT output:\n{result.stdout}")
        
        # Look for output files in the output directory
        output_json = None
        output_html = None
        
        # PyRIT creates files in the output directory
        json_files = list(output_dir.glob("*.json"))
        html_files = list(output_dir.glob("*.html"))
        
        if json_files:
            output_json = str(json_files[0])
        if html_files:
            output_html = str(html_files[0])
        
        return output_json, output_html
    
    def _parse_results(
        self,
        job_id: str,
        request: EvaluationRequest,
        output_json: str,
        output_html: str,
        job_data: Dict[str, Any]
    ) -> EvaluationResults:
        """Parse PyRIT results into structured format."""
        question_results = []
        overall_score = 0.0
        
        # If we have JSON output, parse it
        if output_json and os.path.exists(output_json):
            with open(output_json, 'r') as f:
                pyrit_results = json.load(f)
            
            # Parse each question's results
            # Note: PyRIT output format may vary, this is a simplified parser
            for idx, q in enumerate(request.questions):
                scorer_results = []
                question_score = 0.0
                
                # Extract scorer results for this question
                # Use scorer config to get names and weights
                all_scorers = [self.scorer_config["main"]] + self.scorer_config["auxiliary"]
                for scorer_cfg in all_scorers:
                    scorer_name = Path(scorer_cfg["path"]).stem.replace("_scorer", "")
                    weight = scorer_cfg["weight"]
                    
                    # Placeholder: actual parsing depends on PyRIT format
                    score = 0.8  # TODO: Parse from actual results
                    weighted_score = score * weight
                    question_score += weighted_score
                    
                    scorer_results.append(ScorerResult(
                        scorer_name=scorer_name,
                        score=score,
                        weight=weight,
                        weighted_score=weighted_score,
                        rationale=f"Evaluation for {scorer_name}"
                    ))
                
                question_results.append(QuestionResult(
                    question=q.question,
                    expected_outcome=q.expected_outcome,
                    actual_response="Response from target",  # TODO: Parse from results
                    actual_agent="agent_name",  # TODO: Parse from results
                    actual_routing_reason="Routing reason",  # TODO: Parse from results
                    scorer_results=scorer_results,
                    overall_score=question_score
                ))
                
                overall_score += question_score
        
        # Average score across questions
        if len(request.questions) > 0:
            overall_score = overall_score / len(request.questions)
        
        return EvaluationResults(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            submitted_at=job_data["submitted_at"],
            started_at=job_data["started_at"],
            completed_at=datetime.utcnow(),
            target_url=request.target_url,
            total_questions=len(request.questions),
            questions_completed=len(request.questions),
            overall_score=overall_score,
            question_results=question_results,
            report_json_path=output_json,
            report_html_path=output_html,
            error_message=None
        )


# Global worker instance (lazily initialized)
_worker = None

def _get_worker():
    """Get or create the global worker instance."""
    global _worker
    if _worker is None:
        _worker = EvaluationWorker()
    return _worker


def start_evaluation_async(job_id: str) -> None:
    """Start evaluation in background thread."""
    worker = _get_worker()
    thread = threading.Thread(target=worker.process_job, args=(job_id,))
    thread.daemon = True
    thread.start()

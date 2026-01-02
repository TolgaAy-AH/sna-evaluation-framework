"""In-memory job queue for managing evaluation jobs."""

import threading
from typing import Dict, Optional
from datetime import datetime
from eval.models import JobStatus, EvaluationRequest, EvaluationResults, ProgressInfo


class JobQueue:
    """Thread-safe in-memory job queue."""
    
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
        self._request_ids: Dict[str, str] = {}  # Maps request_id -> job_id
        self._lock = threading.Lock()
    
    def find_by_request_id(self, request_id: str) -> Optional[str]:
        """Find existing job_id by request_id."""
        with self._lock:
            return self._request_ids.get(request_id)
    
    def create_job(self, job_id: str, request: EvaluationRequest) -> None:
        """Create a new job."""
        with self._lock:
            # Track request_id if provided
            if request.request_id:
                self._request_ids[request.request_id] = job_id
            
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": JobStatus.QUEUED,
                "request": request,
                "submitted_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "results": None,
                "error": None,
                "progress": {
                    "questions_completed": 0,
                    "questions_total": len(request.questions),
                    "scorers_completed": 0,
                    "scorers_total": len(request.questions) * 6,  # 6 scorers per question
                    "percent": 0
                },
                "request_id": request.request_id
            }
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)
    
    def update_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status
                if status == JobStatus.RUNNING and not self._jobs[job_id]["started_at"]:
                    self._jobs[job_id]["started_at"] = datetime.utcnow()
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    self._jobs[job_id]["completed_at"] = datetime.utcnow()
    
    def update_progress(self, job_id: str, questions_completed: int, scorers_completed: int) -> None:
        """Update job progress."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job["progress"]["questions_completed"] = questions_completed
                job["progress"]["scorers_completed"] = scorers_completed
                
                # Calculate percentage
                total_scorers = job["progress"]["scorers_total"]
                if total_scorers > 0:
                    job["progress"]["percent"] = int((scorers_completed / total_scorers) * 100)
    
    def set_results(self, job_id: str, results: EvaluationResults) -> None:
        """Set job results."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["results"] = results
    
    def set_error(self, job_id: str, error: str) -> None:
        """Set job error."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["error"] = error
                self._jobs[job_id]["status"] = JobStatus.FAILED
    
    def list_jobs(self) -> list:
        """List all jobs."""
        with self._lock:
            return list(self._jobs.values())


# Global job queue instance
job_queue = JobQueue()

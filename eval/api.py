"""FastAPI service for the evaluation framework."""

from dotenv import load_dotenv
load_dotenv()  # Load .env before importing worker

from fastapi import FastAPI, HTTPException
from typing import List
from datetime import datetime
import uuid

from eval.models import (
    EvaluationRequest, EvaluationResponse, EvaluationResults,
    ScorerInfo, JobStatus, ProgressInfo
)
from eval.job_queue import job_queue
from eval.worker import start_evaluation_async

app = FastAPI(
    title="SNA Evaluation Framework API",
    description="API for evaluating AI agent responses using PyRIT",
    version="1.0.0"
)


@app.get("/")
async def root() -> dict:
    """Root endpoint - health check."""
    return {"status": "ok", "message": "SNA Evaluation Framework API"}


@app.get("/health")
async def health() -> dict:
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/scorers", response_model=List[ScorerInfo])
async def list_scorers() -> List[ScorerInfo]:
    """List available scorers with their weights."""
    return [
        ScorerInfo(
            name="numerical_accuracy",
            weight=0.3,
            description="Validates numerical precision and calculations"
        ),
        ScorerInfo(
            name="data_methodology",
            weight=0.3,
            description="Evaluates data source transparency and methodology"
        ),
        ScorerInfo(
            name="agent_routing",
            weight=0.2,
            description="Assesses correct agent selection and routing"
        ),
        ScorerInfo(
            name="completeness",
            weight=0.1,
            description="Checks response completeness"
        ),
        ScorerInfo(
            name="assumption_transparency",
            weight=0.05,
            description="Validates disclosure of assumptions and limitations"
        ),
        ScorerInfo(
            name="error_handling",
            weight=0.05,
            description="Evaluates error handling and recovery"
        )
    ]


@app.post("/evaluate", response_model=EvaluationResponse, status_code=202)
async def submit_evaluation(request: EvaluationRequest) -> EvaluationResponse:
    """
    Submit a batch evaluation job.
    
    Returns 202 Accepted with job_id for polling.
    If request_id is provided and matches an existing job, returns that job instead.
    """
    # Check for existing job with same request_id (deduplication)
    if request.request_id:
        existing_job_id = job_queue.find_by_request_id(request.request_id)
        if existing_job_id:
            job = job_queue.get_job(existing_job_id)
            if job:
                logger.info(f"Duplicate request_id '{request.request_id}' detected - returning existing job {existing_job_id}")
                return EvaluationResponse(
                    job_id=job["job_id"],
                    status=job["status"],
                    submitted_at=job["submitted_at"],
                    started_at=job.get("started_at"),
                    completed_at=job.get("completed_at"),
                    target_url=job["request"].target_url,
                    total_questions=len(job["request"].questions),
                    progress=ProgressInfo(**job["progress"]) if job.get("progress") else None,
                    message=f"Duplicate request_id detected. Returning existing job."
                )
    
    # Generate job ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    job_id = f"eval_{timestamp}_{uuid.uuid4().hex[:6]}"
    
    # Create job in queue
    job_queue.create_job(job_id, request)
    
    # Start background processing
    start_evaluation_async(job_id)
    
    # Return immediate response
    return EvaluationResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        submitted_at=datetime.utcnow(),
        started_at=None,
        completed_at=None,
        target_url=request.target_url,
        total_questions=len(request.questions),
        progress=None,
        message=None
    )


@app.get("/evaluate/{job_id}", response_model=EvaluationResponse)
async def get_evaluation_status(job_id: str) -> EvaluationResponse:
    """
    Get evaluation job status and results.
    
    Poll this endpoint to check job progress and retrieve results when completed.
    """
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Build progress info if running
    progress = None
    if job["status"] == JobStatus.RUNNING:
        progress = ProgressInfo(**job["progress"])
    
    return EvaluationResponse(
        job_id=job_id,
        status=job["status"],
        submitted_at=job["submitted_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        target_url=job["request"].target_url,
        total_questions=len(job["request"].questions),
        progress=progress
    )


@app.get("/evaluate/{job_id}/results", response_model=EvaluationResults)
async def get_evaluation_results(job_id: str) -> EvaluationResults:
    """
    Get detailed evaluation results.
    
    Only available when job status is 'completed'.
    """
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Results not available. Job status: {job['status']}"
        )
    
    if not job.get("results"):
        raise HTTPException(status_code=500, detail="Results not found in job data")
    
    return job["results"]


@app.get("/jobs")
async def list_jobs() -> dict:
    """List all evaluation jobs."""
    jobs = job_queue.list_jobs()
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "submitted_at": job["submitted_at"].isoformat(),
                "total_questions": len(job["request"].questions)
            }
            for job in jobs
        ]
    }

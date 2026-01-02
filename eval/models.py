"""Pydantic models for API request/response validation."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExpectedOutcome(BaseModel):
    """Expected outcome structure matching PyRIT dataset format."""
    response: str = Field(..., description="Expected response text")
    agent: str = Field(..., description="Expected agent that should handle the query")
    reason: str = Field(..., description="Reasoning for the expected agent selection")


class Question(BaseModel):
    """Single question with expected outcome."""
    question: str = Field(..., description="The question to evaluate")
    expected_outcome: ExpectedOutcome = Field(..., description="Expected outcome for validation")


class EvaluationRequest(BaseModel):
    """Request model for batch evaluation."""
    target_url: str = Field(..., description="Target endpoint URL to evaluate")
    questions: List[Question] = Field(..., min_items=1, description="List of questions to evaluate")

    class Config:
        json_schema_extra = {
            "example": {
                "target_url": "http://localhost:6000/chat",
                "questions": [
                    {
                        "question": "What were total sales in Q3 2024?",
                        "expected_outcome": {
                            "response": "Total sales in Q3 2024 were €4,459,017,155.65.",
                            "agent": "merchandising_descriptives",
                            "reason": "Simple aggregation query for sales metrics"
                        }
                    }
                ]
            }
        }


class ProgressInfo(BaseModel):
    """Progress information for running evaluation."""
    questions_completed: int = Field(0, description="Number of questions completed")
    questions_total: int = Field(..., description="Total number of questions")
    scorers_completed: int = Field(0, description="Number of scorer evaluations completed")
    scorers_total: int = Field(..., description="Total number of scorer evaluations (questions * 6)")
    percent: int = Field(0, ge=0, le=100, description="Overall completion percentage")


class EvaluationResponse(BaseModel):
    """Response model for evaluation submission."""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    submitted_at: datetime = Field(..., description="Job submission timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    target_url: str = Field(..., description="Target endpoint URL")
    total_questions: int = Field(..., description="Total number of questions in batch")
    progress: Optional[ProgressInfo] = Field(None, description="Progress information (only for running jobs)")


class ScorerResult(BaseModel):
    """Individual scorer result."""
    scorer_name: str
    score: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)
    weighted_score: float = Field(..., ge=0, le=1)
    rationale: Optional[str] = None


class QuestionResult(BaseModel):
    """Evaluation result for a single question."""
    question: str
    expected_outcome: ExpectedOutcome
    actual_response: Optional[str] = None
    actual_agent: Optional[str] = None
    actual_routing_reason: Optional[str] = None
    scorer_results: List[ScorerResult] = []
    overall_score: float = Field(0, ge=0, le=1)


class EvaluationResults(BaseModel):
    """Complete evaluation results."""
    job_id: str
    status: JobStatus
    submitted_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    target_url: str
    total_questions: int
    questions_completed: int
    overall_score: float = Field(0, ge=0, le=1)
    question_results: List[QuestionResult] = []
    report_json_path: Optional[str] = None
    report_html_path: Optional[str] = None
    error_message: Optional[str] = None


class ScorerInfo(BaseModel):
    """Information about a scorer."""
    name: str
    weight: float
    description: str

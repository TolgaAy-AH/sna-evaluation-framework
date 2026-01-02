"""Example client for the SNA Evaluation Framework API."""

import requests
import time
from typing import Dict, Any, List


class EvaluationClient:
    """Client for interacting with the evaluation API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def list_scorers(self) -> List[Dict[str, Any]]:
        """Get list of available scorers."""
        response = requests.get(f"{self.base_url}/scorers")
        response.raise_for_status()
        return response.json()
    
    def submit_evaluation(
        self,
        target_url: str,
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Submit a batch evaluation request.
        
        Args:
            target_url: URL of the target endpoint to evaluate
            questions: List of questions with expected outcomes
                Each question should have:
                - question: str
                - expected_outcome: dict with response, agent, reason
        
        Returns:
            Response with job_id for polling
        """
        payload = {
            "target_url": target_url,
            "questions": questions
        }
        
        response = requests.post(f"{self.base_url}/evaluate", json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get evaluation job status."""
        response = requests.get(f"{self.base_url}/evaluate/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def get_results(self, job_id: str) -> Dict[str, Any]:
        """Get detailed evaluation results (only when completed)."""
        response = requests.get(f"{self.base_url}/evaluate/{job_id}/results")
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(
        self, 
        job_id: str, 
        poll_interval: int = 5,
        max_wait: int = 600
    ) -> Dict[str, Any]:
        """
        Poll job status until completion.
        
        Args:
            job_id: Job ID to poll
            poll_interval: Seconds between polls
            max_wait: Maximum seconds to wait
        
        Returns:
            Final job status
        """
        elapsed = 0
        while elapsed < max_wait:
            status = self.get_status(job_id)
            
            if status["status"] in ["completed", "failed"]:
                return status
            
            if status["status"] == "running" and "progress" in status:
                progress = status["progress"]
                print(f"Progress: {progress['percent']}% "
                      f"({progress['questions_completed']}/{progress['questions_total']} questions)")
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        raise TimeoutError(f"Job {job_id} did not complete within {max_wait} seconds")


# Example usage
if __name__ == "__main__":
    client = EvaluationClient()
    
    # Health check
    print("=" * 60)
    print("Health check:")
    print(client.health_check())
    print()
    
    # List scorers
    print("=" * 60)
    print("Available scorers:")
    scorers = client.list_scorers()
    for scorer in scorers:
        print(f"  - {scorer['name']}: {scorer['weight']} - {scorer['description']}")
    print()
    
    # Submit batch evaluation
    print("=" * 60)
    print("Submitting batch evaluation...")
    
    questions = [
        {
            "question": "What were total sales in Q3 2024?",
            "expected_outcome": {
                "response": "Total sales in Q3 2024 were €4,459,017,155.65.",
                "agent": "merchandising_descriptives",
                "reason": "Simple aggregation query for sales metrics"
            }
        },
        {
            "question": "Which product category had the highest growth in Q2?",
            "expected_outcome": {
                "response": "Fresh Produce had the highest growth at 12.5% in Q2.",
                "agent": "merchandising_descriptives",
                "reason": "Comparative analysis across product categories"
            }
        },
        {
            "question": "What is the average basket size for this month?",
            "expected_outcome": {
                "response": "The average basket size for November 2024 is €28.45.",
                "agent": "merchandising_descriptives",
                "reason": "Simple metric calculation for current period"
            }
        }
    ]
    
    result = client.submit_evaluation(
        target_url="http://localhost:6000/chat",
        questions=questions
    )
    
    job_id = result["job_id"]
    print(f"Job submitted: {job_id}")
    print(f"Status: {result['status']}")
    print(f"Total questions: {result['total_questions']}")
    print()
    
    # Poll for completion
    print("=" * 60)
    print("Waiting for evaluation to complete...")
    try:
        final_status = client.wait_for_completion(job_id)
        print(f"\nJob completed with status: {final_status['status']}")
        
        if final_status["status"] == "completed":
            # Get detailed results
            results = client.get_results(job_id)
            print(f"\nOverall Score: {results['overall_score']:.2f}")
            print(f"Questions Evaluated: {results['questions_completed']}/{results['total_questions']}")
            
            if results.get("report_json_path"):
                print(f"JSON Report: {results['report_json_path']}")
            if results.get("report_html_path"):
                print(f"HTML Report: {results['report_html_path']}")
    
    except TimeoutError as e:
        print(f"Error: {e}")
    except requests.HTTPError as e:
        print(f"API Error: {e}")

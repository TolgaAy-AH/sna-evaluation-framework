"""
Agent Routing Scorer - Programmatic validation of agent selection.

Validates that the correct agent was selected for a given query without using LLM.
Fast, deterministic, and zero API cost.
"""

from pyrit.score import Scorer, ScorerPromptValidator
from pyrit.models.score import Score
from pyrit.models.message_piece import MessagePiece
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AgentRoutingScorer(Scorer):
    """
    Programmatic scorer that validates agent routing decisions.
    
    Checks if the correct agent was selected based on JSON expected outcome:
    {"response": "...", "agent": "agent_name", "reason": "..."}
    
    Scoring:
    - 1.0: Correct agent selected
    - 0.0: Wrong agent or missing metadata
    """
    
    def __init__(self):
        """Initialize the agent routing scorer."""
        # Create a simple validator that accepts text data types
        validator = ScorerPromptValidator(
            supported_data_types=["text"],
            is_objective_required=True
        )
        super().__init__(validator=validator)
        self._score_categories = ["agent_routing"]
        self.scorer_type = "float_scale"
    
    def get_identifier(self) -> dict:
        """Get scorer identifier."""
        return {"name": self.__class__.__name__}
    
    async def _score_piece_async(
        self, 
        message_piece: MessagePiece, 
        *, 
        objective: Optional[str] = None
    ) -> list[Score]:
        """
        Score the agent routing decision.
        
        Args:
            message_piece: The message piece containing expected_output and converted_value
            objective: Optional - not used, kept for compatibility
        
        Returns:
            List of Score objects
        
        Raises:
            ValueError: If expected_output is missing
        """
        # Get expected outcome from message_piece.expected_output (from YAML expected_outcome field)
        expected_output = getattr(message_piece, 'expected_output', None)
        if not expected_output:
            raise ValueError(
                "AgentRoutingScorer requires message_piece.expected_output. "
                "Ensure your dataset has 'expected_outcome' field with agent information."
            )
        
        # Extract expected agent from expected_output (handle both dict and JSON string)
        expected_agent = None
        try:
            # If already a dict, use directly
            if isinstance(expected_output, dict):
                expected_data = expected_output
            # If a string, parse as JSON
            elif isinstance(expected_output, str):
                expected_data = json.loads(expected_output)
            else:
                expected_data = {}
            
            expected_agent = expected_data.get('agent')
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            raise ValueError(f"Failed to parse expected_output: {e}")
        
        # Get actual outcome from message_piece.converted_value (API response)
        response_text = str(message_piece.converted_value)
        
        # Try to extract agent from response (format: "AgentUsed': 'agent_name")
        agent_match = re.search(r"'AgentUsed':\s*'(\w+)'", response_text)
        actual_agent = agent_match.group(1) if agent_match else None
        
        # Validate
        if not expected_agent:
            score_value = "0.0"
            rationale = "Expected agent not found in expected_outcome"
        elif not actual_agent:
            score_value = "0.0"
            rationale = "Agent information missing from response"
        elif actual_agent == expected_agent:
            score_value = "1.0"
            rationale = f"✓ Correct agent selected: {actual_agent}"
        else:
            score_value = "0.0"
            rationale = f"✗ Wrong agent: expected {expected_agent}, got {actual_agent}"
        
        return [Score(
            score_value=score_value,
            score_value_description=rationale,
            score_type="float_scale",
            score_category=self._score_categories,
            score_rationale=rationale,
            scorer_class_identifier=self.get_identifier(),
            message_piece_id=message_piece.id,
            objective=str(expected_output),
            score_metadata={"expected_agent": expected_agent, "actual_agent": actual_agent}
        )]
    
    def validate_return_scores(self, scores: list[Score]):
        """Validate that exactly one float_scale score is returned."""
        if len(scores) != 1:
            raise ValueError("AgentRoutingScorer should return exactly one score.")
        
        if scores[0].score_type != "float_scale":
            raise ValueError("AgentRoutingScorer score type must be float_scale.")
        
        try:
            score_val = float(scores[0].score_value)
        except (TypeError, ValueError):
            raise ValueError("AgentRoutingScorer score value must be a valid float.")

        if not (0.0 <= score_val <= 1.0):
            raise ValueError("AgentRoutingScorer score value must be between 0.0 and 1.0.")

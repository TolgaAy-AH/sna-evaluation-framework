#!/bin/bash
# Run PyRIT evaluation with all scorers

set -e

cd "$(dirname "$0")/.."

echo "🚀 Starting PyRIT Evaluation"
echo "======================================"
echo ""

# Activate virtual environment
source .venv-eval/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)
export OPENAI_CHAT_MODEL="gpt-5"

# Use JSON-formatted dataset if it exists, otherwise use original
if [ -f "eval/datasets_sensitive/in_scope_questions_hydrated_json.yaml" ]; then
    DATASET="eval/datasets_sensitive/in_scope_questions_hydrated_json.yaml"
    echo "📊 Using JSON-formatted dataset (3 questions for quick test)"
else
    DATASET="eval/datasets_sensitive/in_scope_questions_hydrated.yaml"
    echo "📊 Using original dataset"
fi

echo "🎯 Target: http://localhost:6000/chat"
echo "🤖 Model: $OPENAI_CHAT_MODEL"
echo "📝 Output: pyrit_reports/"
echo ""
echo "⏱️  This will take ~5-10 minutes..."
echo ""

# Run evaluation with all 6 scorers
pyrit-eval run \
    --config eval/config.yaml \
    --dataset-path "$DATASET" \
    --scorer '{
        "main": {
            "path": "eval/scorers/llm/numerical_accuracy_scorer.yaml",
            "weight": 0.3,
            "threshold": 1.0,
            "required": true
        },
        "auxiliary": [
            {
                "path": "eval/scorers/llm/data_methodology_scorer.yaml",
                "weight": 0.3,
                "threshold": 1.0,
                "required": true
            },
            {
                "path": "eval/scorers/programmatic/agent_routing_scorer.py",
                "callable": "AgentRoutingScorer",
                "weight": 0.2,
                "threshold": 1.0,
                "required": true
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
    }' \
    --out pyrit_reports \
    --target-endpoint "http://localhost:6000/chat" \
    --auth-token "not-used" \
    --openai-api-key "$OPENAI_API_KEY" \
    --openai-chat-endpoint "https://api-ai.digitaldev.nl/openai/deployments/gpt-5/chat/completions?api-version=2024-04-01-preview" \
    --openai-chat-model "gpt-5" \
    --scorer-temperature 1.0

echo ""
echo "======================================"
echo "✅ Evaluation complete!"
echo ""
echo "📊 View results:"
echo "   open pyrit_reports/dataset_report_*.html"
echo ""

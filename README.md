# SNA Evaluation Framework

Evaluation framework for testing AI agents using PyRIT. Extracted from the commerce agents repository to run as a standalone evaluation tool.

## Quick Start

### Prerequisites

- Python 3.10+
- Commerce agents API running on port 6000
- Azure OpenAI API access

### Setup

```bash
# 1. Install PyRIT
python3 -m venv .venv-eval
source .venv-eval/bin/activate
pip install git+https://github.com/albert-heijn-technology/PyRIT@7eb9201a2f5666aaf59df032d0bd4549e7ea268a

# 2. Configure environment
cp .env.template .env
# Edit .env with your Azure OpenAI credentials

# 3. Prepare test data
python eval/datasets/hydrate_test_data.py --template eval/datasets/in_scope_questions.yaml
```

### Run Evaluation

```bash
# Make sure commerce agents API is running on port 6000
# Then run:
./scripts/run_evaluation.sh
```

Results are saved to `pyrit_reports/dataset_report_*.html`

## Configuration

### Environment Variables

- `OPENAI_API_KEY` - Azure OpenAI API key
- `OPENAI_BASE_URL` - Azure OpenAI base URL
- `OPENAI_MODEL` - Model name (gpt-5)

### Evaluation Config

- **Dataset**: `eval/datasets_sensitive/in_scope_questions_hydrated_json.yaml` (3 test questions)
- **Target API**: `http://localhost:6000/chat` (commerce agents)
- **Scorer Model**: gpt-5 with temperature 1.0

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
│   ├── config.yaml                    # HTTP request template
│   ├── datasets/                      # Test question templates
│   │   ├── hydrate_test_data.py      # Hydration script
│   │   └── in_scope_questions.yaml   # Template with 12 questions
│   ├── datasets_sensitive/            # Hydrated data (gitignored)
│   │   └── in_scope_questions_hydrated_json.yaml
│   └── scorers/
│       ├── llm/                       # LLM-based scorers (5 files)
│       └── programmatic/              # Code-based scorers (1 file)
├── scripts/
│   └── run_evaluation.sh              # Main evaluation runner
├── .env                                # Credentials (gitignored)
└── README.md
```

## Key Notes

- This repo contains **only** the evaluation framework (extracted from `ah-sa-commerce_agents_crew`)
- The commerce agents app must be running separately on port 6000
- PyRIT uses a custom fork with specific commit hash
- Temperature must be set to 1.0 for gpt-5 (via `--scorer-temperature 1.0` CLI flag)
- Evaluation takes ~5-10 minutes for 3 questions

## Troubleshooting

**Connection refused on port 6000**
- Start commerce agents API: `cd ~/PycharmProjects/ah-sa-commerce_agents_crew && python -m commerce_agents.main_langchain api`

**Temperature error**
- Ensure `--scorer-temperature 1.0` is in run_evaluation.sh (required for gpt-5)

**No module 'pyrit'**
- Activate correct venv: `source .venv-eval/bin/activate`
- Verify PyRIT installed: `pip show pyrit`

## Original Repository

Source: [https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew](https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew)

This evaluation framework is designed to work with the agents in that repository.

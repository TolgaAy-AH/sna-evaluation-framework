# GitHub Copilot Instructions for SNA Evaluation Framework

## Project Overview

This is a standalone evaluation framework extracted from `ah-sa-commerce_agents_crew`. It tests AI agent responses using PyRIT with 6 specialized scorers.

**Key Context:**
- Evaluates agents from the commerce_agents app (runs separately on port 6000)
- Uses PyRIT custom fork: `albert-heijn-technology/PyRIT@cc729fcb959d146642bddd422453f46db94d632e`
- Python 3.10, venv: `.venv-eval`

## Critical Configuration

### Azure OpenAI Endpoint
**MUST use full Azure-format URL** (discovered from original repo):
```
https://api-ai.digitaldev.nl/openai/deployments/gpt-5/chat/completions?api-version=2024-04-01-preview
```

Path is `/openai/deployments/`, NOT `/openai/v1/deployments/`

### Temperature Setting
**REQUIRED:** `--scorer-temperature 1.0` in CLI command (gpt-5 doesn't support 0.0)

Temperature in YAML files is **ignored** - CLI flag overrides everything.

## File Structure

```
eval/
├── config.yaml              # HTTP template for target API
├── datasets/                # Question templates
├── datasets_sensitive/      # Hydrated data (gitignored)
└── scorers/
    ├── llm/*.yaml          # 5 LLM scorers
    └── programmatic/*.py   # 1 programmatic scorer

scripts/
└── run_evaluation.sh       # Main runner
```

## Key Commands

**Run evaluation:**
```bash
./scripts/run_evaluation.sh
```

**Hydrate test data:**
```bash
python eval/datasets/hydrate_test_data.py --template eval/datasets/in_scope_questions.yaml
```

## Scorer Configuration

All LLM scorers use PyRIT Evaluator format:
```yaml
category: <name>
evaluation_criteria: |
  <instructions>
true_description: <pass condition>
false_description: <fail condition>
# NO temperature field - use CLI flag
```

6 scorers (3 required):
1. Numerical Accuracy (30%, required)
2. Data Methodology (30%, required)
3. Agent Routing (20%, required)
4. Completeness (10%)
5. Assumption Transparency (5%)
6. Error Handling (5%)

## Common Issues

**Temperature 0.0 error:**
- Check `--scorer-temperature 1.0` in run_evaluation.sh
- YAML temperature fields don't work - CLI only

**Connection refused port 6000:**
- Commerce agents API not running
- Start: `cd ~/ah-sa-commerce_agents_crew && python -m commerce_agents.main_langchain api`

**404 from Azure endpoint:**
- Verify full Azure-format URL in command
- Must include `/deployments/gpt-5/` and `?api-version=` parameter

## When Making Changes

**DO:**
- Use CLI flags for runtime config (temperature, endpoints)
- Keep scorers in PyRIT Evaluator YAML format
- Test against commerce_agents on port 6000

**DON'T:**
- Set temperature in YAML files (ignored)
- Change PyRIT commit hash without testing
- Modify HTTP template in config.yaml without verifying field_defs match

## Original Repository

All evaluation components match `eval/` directory in:
https://github.com/RoyalAholdDelhaize/ah-sa-commerce_agents_crew

Refer to that repo's eval setup when in doubt.

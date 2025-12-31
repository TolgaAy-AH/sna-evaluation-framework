#!/usr/bin/env python3
"""
Hydrate Evaluation Data with Real Values

This script reads template YAML files containing {{PLACEHOLDER|format}} syntax,
executes SQL queries to fetch real values, and generates a hydrated YAML
file ready for evaluation.

Template Syntax:
    {{COLUMN_NAME|format}}
    
    Formats:
    - currency: €1,234,567 or $1,234,567
    - percentage: 45.3%
    - units: 1,234 units
    - number: 1,234,567

Usage:
    # Hydrate in-scope questions (auto-generates eval/datasets_sensitive/in_scope_questions_hydrated.yaml)
    python eval/datasets/hydrate_test_data.py \
        --template eval/datasets/in_scope_questions.yaml
    
    # Dry run to preview hydrated values
    python eval/datasets/hydrate_test_data.py \
        --template eval/datasets/in_scope_questions.yaml \
        --dry-run

Security: The hydrated file (e.g. eval/datasets_sensitive/in_scope_questions_hydrated.yaml)
         must be excluded from version control (see .gitignore). Only the
         template file (eval/datasets/in_scope_questions.yaml) is committed.
"""

import sys
import re
import yaml
import argparse
from pathlib import Path
from typing import Dict, Optional
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class TestDataHydrator:
    """Hydrates template evaluation files with real data from your database."""
    
    PLACEHOLDER_PATTERN = r'\{\{(\w+)\|(\w+)\}\}'
    
    def __init__(self, template_file: str, output_file: Optional[str] = None):
        """
        Initialize hydrator.
        
        Args:
            template_file: Path to template YAML with {{PLACEHOLDER}} syntax
            output_file: Path to write hydrated YAML (optional for dry-run)
        """
        self.template_file = Path(template_file)
        self.output_file = Path(output_file) if output_file else None
    
    def execute_query(self, sql: str) -> Optional[Dict[str, str]]:
        """
        Execute SQL query and return results as dict.
        
        TODO: Implement your database connection here.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Dict with column names as keys, values as strings
        """
        logger.warning("⚠️  Database connection not implemented - using mock data")
        
        # Mock data for demonstration
        # Replace this with your actual database connection
        mock_data = {
            'TotalSales': '1234567.89',
            'AvgCustomers': '45678',
            'ProfitMargin': '23.5',
            'TotalProfit': '287654.32',
            'TotalVolume': '9876',
            'TotalOrders': '12345',
            'Sales2024': '5678901.23',
            'Sales2023': '4567890.12',
            'GrowthRate': '24.3',
            'OnlineSales': '2345678.90',
            'StoreSales': '3456789.01',
            'OnlinePct': '40.3',
            'StorePct': '59.7',
            'BetterChannel': 'STORE',
            'YTDRevenue': '8765432.10',
            'CurrentYear': '2024',
            'LastQuarter': 'Q3',
            'PremiumSales': '987654.32',
            'UniqueCustomers': '78901',
            'TopCategory': 'Electronics',
            'CategorySales': '4567890.12'
        }
        
        return mock_data
    
    def format_value(self, value: str, format_type: str) -> str:
        """
        Format value according to format type.
        
        Args:
            value: Raw value from database
            format_type: One of: currency, percentage, units, number
            
        Returns:
            Formatted string
        """
        try:
            num_value = float(value.replace(',', ''))
            
            if format_type == 'currency':
                # Format as currency with thousands separator
                return f"€{num_value:,.2f}"
            elif format_type == 'percentage':
                # Format as percentage with 1 decimal
                return f"{num_value:.1f}%"
            elif format_type == 'units':
                # Format with thousands separator + " units"
                return f"{int(num_value):,} units"
            elif format_type == 'number':
                # Format with thousands separator
                return f"{int(num_value):,}"
            else:
                logger.warning(f"Unknown format type: {format_type}")
                return value
        except Exception as e:
            logger.warning(f"Failed to format value '{value}' as {format_type}: {e}")
            return value
    
    def hydrate_expected_outcome(self, outcome: str, query_result: Dict[str, str]) -> str:
        """
        Replace placeholders in expected_outcome with real values.
        
        Args:
            outcome: Expected outcome string with {{PLACEHOLDER}} syntax
            query_result: Dict with column values from SQL query
            
        Returns:
            Hydrated expected_outcome string
        """
        def replace_placeholder(match):
            column_name = match.group(1)
            format_type = match.group(2)
            
            if column_name in query_result:
                raw_value = query_result[column_name]
                return self.format_value(raw_value, format_type)
            else:
                logger.warning(f"Column '{column_name}' not found in query result. Available: {list(query_result.keys())}")
                return match.group(0)  # Keep placeholder if not found
        
        return re.sub(self.PLACEHOLDER_PATTERN, replace_placeholder, outcome)
    
    def hydrate_file(self, dry_run: bool = False) -> int:
        """
        Hydrate template file with real data.
        
        Args:
            dry_run: If True, print hydrated values without writing file
            
        Returns:
            Number of test cases hydrated
        """
        logger.info(f"Loading template: {self.template_file}")
        
        # Load template YAML
        with open(self.template_file, 'r') as f:
            template_content = f.read()
        
        # Parse YAML
        tests = yaml.safe_load(template_content)
        
        if not isinstance(tests, list):
            logger.error("Template file must contain a list of test cases")
            return 0
        
        hydrated_count = 0
        hydrated_tests = []
        
        for i, test in enumerate(tests, 1):
            question = test.get('question', '')
            expected_outcome = test.get('expected_outcome', '')
            sql_query = test.get('sql_query') or ''
            sql_query = sql_query.strip() if sql_query else ''
            
            # Skip tests without SQL queries or placeholders
            if not sql_query or '{{' not in expected_outcome:
                logger.info(f"[{i}/{len(tests)}] SKIPPED: {question[:50]}... (no placeholders or SQL)")
                # Preserve only question and expected_outcome
                hydrated_test = {
                    'question': test.get('question'),
                    'expected_outcome': test.get('expected_outcome')
                }
                hydrated_tests.append(hydrated_test)
                continue
            
            logger.info(f"[{i}/{len(tests)}] Processing: {question[:60]}...")
            
            # Execute query
            result = self.execute_query(sql_query)
            
            if result:
                # Hydrate placeholders
                hydrated_outcome = self.hydrate_expected_outcome(expected_outcome, result)
                
                if dry_run:
                    logger.info(f"  {expected_outcome[:80]} → {hydrated_outcome[:80]}")
                
                # Create hydrated test with only question and expected_outcome
                hydrated_test = {
                    'question': test.get('question'),
                    'expected_outcome': hydrated_outcome
                }
                hydrated_tests.append(hydrated_test)
                hydrated_count += 1
            else:
                logger.warning(f"  Query failed - keeping placeholders")
                hydrated_test = {
                    'question': test.get('question'),
                    'expected_outcome': test.get('expected_outcome')
                }
                hydrated_tests.append(hydrated_test)
        
        # Write hydrated file (unless dry-run)
        if not dry_run and self.output_file:
            self._write_hydrated_yaml(template_content, hydrated_tests)
        
        return hydrated_count
    
    def _write_hydrated_yaml(self, original_content: str, hydrated_tests: list):
        """
        Write hydrated YAML file with only question and expected_outcome fields.
        
        Args:
            original_content: Original template file content
            hydrated_tests: List of hydrated test dicts
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        header = f"""# ============================================================================
# HYDRATED EVALUATION DATASET - CONFIDENTIAL
# ============================================================================
# 🔒 AUTO-GENERATED FILE - DO NOT COMMIT TO VERSION CONTROL
#
# Generated: {timestamp}
# Source template: {self.template_file.name}
# Total test cases: {len(hydrated_tests)}
#
# This file contains real business data.
# All {{{{PLACEHOLDER|format}}}} tokens have been replaced with actual values.
#
# To regenerate this file:
#   python eval/datasets/hydrate_test_data.py --template {self.template_file}
#
# ⚠️  SECURITY WARNING: This file may contain sensitive metrics.
#     Never commit to git, share publicly, or store in unencrypted locations.
# ============================================================================

"""
        
        # Write file with custom formatting
        with open(self.output_file, 'w') as f:
            f.write(header)
            
            for i, test in enumerate(hydrated_tests):
                # Write each test with proper formatting
                question = test['question'].replace('"', '\\"')
                expected_outcome = test['expected_outcome'].replace('"', '\\"')
                
                f.write(f'- question: "{question}"\n')
                f.write(f'  expected_outcome: "{expected_outcome}"\n')
                
                # Add blank line between elements (except after last one)
                if i < len(hydrated_tests) - 1:
                    f.write("\n")
        
        logger.info(f"✅ Hydrated file written: {self.output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hydrate test template with real data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate hydrated file (auto-outputs to eval/datasets_sensitive/)
  python eval/datasets/hydrate_test_data.py \\
      --template eval/datasets/in_scope_questions.yaml
  
  # Preview hydrated values (dry-run)
  python eval/datasets/hydrate_test_data.py \\
      --template eval/datasets/in_scope_questions.yaml \\
      --dry-run
  
  # Custom filename (must still be in eval/datasets_sensitive/)
  python eval/datasets/hydrate_test_data.py \\
      --template eval/datasets/in_scope_questions.yaml \\
      --output eval/datasets_sensitive/custom_name.yaml
        """
    )
    parser.add_argument(
        '--template',
        required=True,
        help="Path to template YAML file with {{PLACEHOLDER}} syntax"
    )
    parser.add_argument(
        '--output',
        help="Path to write hydrated YAML file (must be in eval/datasets_sensitive/, defaults to eval/datasets_sensitive/<template>_hydrated.yaml)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Preview hydrated values without writing output file"
    )
    
    args = parser.parse_args()
    
    # Auto-derive output path if not provided
    if not args.dry_run and not args.output:
        template_path = Path(args.template)
        output_filename = template_path.stem + '_hydrated' + template_path.suffix
        # Always output to eval/datasets_sensitive/
        sensitive_dir = Path('eval/datasets_sensitive')
        args.output = str(sensitive_dir / output_filename)
        logger.info(f"No --output specified, auto-deriving: {args.output}")
    
    # Validate output path is in datasets_sensitive directory
    if not args.dry_run and args.output:
        output_path = Path(args.output).resolve()
        sensitive_dir = Path('eval/datasets_sensitive').resolve()
        try:
            output_path.relative_to(sensitive_dir)
        except ValueError:
            parser.error(f"Output path must be inside eval/datasets_sensitive/ directory. Got: {args.output}")
    
    try:
        # Ensure datasets_sensitive directory exists
        if not args.dry_run:
            Path('eval/datasets_sensitive').mkdir(parents=True, exist_ok=True)
        
        hydrator = TestDataHydrator(
            template_file=args.template,
            output_file=args.output
        )
        
        hydrated_count = hydrator.hydrate_file(dry_run=args.dry_run)
        
        if args.dry_run:
            logger.info(f"\n🔍 DRY RUN COMPLETE: {hydrated_count} test cases would be hydrated")
            logger.info("Run without --dry-run to generate the hydrated file")
        else:
            logger.info(f"\n✅ HYDRATION COMPLETE: {hydrated_count} test cases hydrated")
            logger.info(f"📁 Output: {args.output}")
            logger.info(f"\n⚠️  IMPORTANT: This file contains sensitive data - do NOT commit to git!")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

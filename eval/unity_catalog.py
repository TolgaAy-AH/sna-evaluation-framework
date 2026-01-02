"""Unity Catalog integration for storing evaluation results."""

import os
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import VolumeType

from eval.models import EvaluationResults, QuestionResult


class UnityCatalogWriter:
    """Write evaluation results to Unity Catalog."""
    
    def __init__(self):
        # Databricks connection settings
        self.catalog = "alh_preprd_spa_commerce"  # Commerce agents preprod catalog
        self.schema = "conversational_analytics"
        self.table = "eval_results"
        self.volume = "eval_reports"
        
        # Get credentials from environment
        self.server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
        self.http_path = os.getenv("DATABRICKS_HTTP_PATH")
        self.access_token = os.getenv("DATABRICKS_TOKEN")
        
        # Initialize Databricks SDK client
        self.workspace_client = None
        if self.access_token and self.server_hostname:
            try:
                self.workspace_client = WorkspaceClient(
                    host=f"https://{self.server_hostname}",
                    token=self.access_token
                )
            except Exception as e:
                print(f"Warning: Could not initialize Databricks workspace client: {e}")
    
    def _ensure_schema_exists(self):
        """Ensure the catalog and schema exist."""
        if not self._can_connect():
            print("Skipping schema creation - no connection")
            return
        
        try:
            # Try to create schema - will succeed if it doesn't exist, or fail gracefully if it does
            create_schema_sql = f"""
            CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.schema}
            COMMENT 'SNA Evaluation Framework results'
            """
            
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(create_schema_sql)
                    print(f"Schema {self.catalog}.{self.schema} ready")
        except Exception as e:
            print(f"Note: Schema may already exist or insufficient permissions: {e}")
    
    def _ensure_table_exists(self):
        """Ensure the results table exists."""
        if not self._can_connect():
            print("Skipping table creation - no connection")
            return
        
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.{self.table} (
            job_id STRING NOT NULL,
            submitted_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            status STRING NOT NULL,
            target_url STRING NOT NULL,
            total_questions INT NOT NULL,
            questions_completed INT NOT NULL,
            overall_score DOUBLE,
            question STRING,
            expected_response STRING,
            expected_agent STRING,
            expected_reason STRING,
            actual_response STRING,
            actual_agent STRING,
            actual_routing_reason STRING,
            scorer_name STRING,
            scorer_score DOUBLE,
            scorer_weight DOUBLE,
            scorer_weighted_score DOUBLE,
            scorer_rationale STRING,
            report_json_path STRING,
            report_html_path STRING,
            error_message STRING,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        )
        PARTITIONED BY (DATE(submitted_at))
        COMMENT 'SNA Evaluation Framework - Evaluation results with detailed scorer outputs'
        """
        
        try:
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(create_table_sql)
                    print(f"Table {self.catalog}.{self.schema}.{self.table} ready")
        except Exception as e:
            print(f"Warning: Could not ensure table exists: {e}")
    
    def _ensure_volume_exists(self):
        """Ensure the volume for storing reports exists."""
        if not self._can_connect():
            print("Skipping volume creation - no connection")
            return
        
        try:
            # Try to create volume using SQL - will succeed if it doesn't exist
            create_volume_sql = f"""
            CREATE VOLUME IF NOT EXISTS {self.catalog}.{self.schema}.{self.volume}
            COMMENT 'SNA Evaluation Framework - Evaluation reports (JSON and HTML)'
            """
            
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(create_volume_sql)
                    print(f"Volume {self.catalog}.{self.schema}.{self.volume} ready")
        except Exception as e:
            print(f"Note: Volume may already exist or insufficient permissions: {e}")
    
    def _can_connect(self) -> bool:
        """Check if we can connect to Unity Catalog."""
        return bool(self.server_hostname and self.http_path and self.access_token)
    
    def _upload_report_to_volume(self, local_path: str, report_type: str, job_id: str) -> Optional[str]:
        """Upload report file to Unity Catalog volume."""
        if not self.workspace_client or not local_path or not os.path.exists(local_path):
            return None
        
        try:
            # Volume path format: /Volumes/{catalog}/{schema}/{volume}/{path}
            timestamp = datetime.utcnow().strftime("%Y%m%d")
            filename = f"{job_id}_{report_type}.{report_type}"
            volume_path = f"/Volumes/{self.catalog}/{self.schema}/{self.volume}/{timestamp}/{filename}"
            
            # Read local file
            with open(local_path, 'rb') as f:
                content = f.read()
            
            # Upload to volume
            self.workspace_client.files.upload(volume_path, content, overwrite=True)
            print(f"Uploaded {report_type} report to {volume_path}")
            
            return volume_path
        except Exception as e:
            print(f"Warning: Could not upload {report_type} report: {e}")
            return local_path  # Return local path as fallback
    
    def write_results(self, results: EvaluationResults) -> bool:
        """
        Write evaluation results to Unity Catalog.
        
        Args:
            results: Evaluation results to write
            
        Returns:
            True if successful, False otherwise
        """
        # Ensure infrastructure exists
        self._ensure_schema_exists()
        self._ensure_volume_exists()
        self._ensure_table_exists()
        
        if not self._can_connect():
            print("Warning: Unity Catalog credentials not configured")
            print("Set DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN")
            print("Skipping Unity Catalog write")
            return False
        
        try:
            # Upload report files to volume
            json_path = None
            html_path = None
            
            if results.report_json_path:
                json_path = self._upload_report_to_volume(
                    results.report_json_path, 
                    "json", 
                    results.job_id
                )
            
            if results.report_html_path:
                html_path = self._upload_report_to_volume(
                    results.report_html_path,
                    "html",
                    results.job_id
                )
            
            # Write results to table (one row per question per scorer)
            insert_sql = f"""
            INSERT INTO {self.catalog}.{self.schema}.{self.table}
            (job_id, submitted_at, started_at, completed_at, status, target_url,
             total_questions, questions_completed, overall_score,
             question, expected_response, expected_agent, expected_reason,
             actual_response, actual_agent, actual_routing_reason,
             scorer_name, scorer_score, scorer_weight, scorer_weighted_score, scorer_rationale,
             report_json_path, report_html_path, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            with sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.access_token
            ) as connection:
                with connection.cursor() as cursor:
                    # Insert one row per question per scorer
                    for question_result in results.question_results:
                        for scorer_result in question_result.scorer_results:
                            cursor.execute(insert_sql, (
                                results.job_id,
                                results.submitted_at,
                                results.started_at,
                                results.completed_at,
                                results.status.value,
                                results.target_url,
                                results.total_questions,
                                results.questions_completed,
                                results.overall_score,
                                question_result.question,
                                question_result.expected_outcome.response,
                                question_result.expected_outcome.agent,
                                question_result.expected_outcome.reason,
                                question_result.actual_response,
                                question_result.actual_agent,
                                question_result.actual_routing_reason,
                                scorer_result.scorer_name,
                                scorer_result.score,
                                scorer_result.weight,
                                scorer_result.weighted_score,
                                scorer_result.rationale,
                                json_path,
                                html_path,
                                results.error_message
                            ))
                    
                    connection.commit()
            
            print(f"✓ Results written to Unity Catalog: {self.catalog}.{self.schema}.{self.table}")
            return True
        
        except Exception as e:
            print(f"Error writing to Unity Catalog: {e}")
            import traceback
            traceback.print_exc()
            return False


# Global instance
unity_catalog_writer = UnityCatalogWriter()

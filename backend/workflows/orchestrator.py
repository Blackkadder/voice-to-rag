"""
Workflow Orchestrator

Manages Databricks workflow lifecycle: create, run, monitor, and manage jobs.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime

from .definitions import (
    get_ingestion_workflow,
    get_embedding_workflow,
    get_indexing_workflow,
    get_full_rag_workflow,
    get_incremental_workflow
)


class WorkflowType(str, Enum):
    """Types of RAG workflows"""
    INGESTION = "ingestion"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    FULL_PIPELINE = "full_pipeline"
    INCREMENTAL = "incremental"


class RunStatus(str, Enum):
    """Workflow run statuses"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"
    SKIPPED = "SKIPPED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RunResultState(str, Enum):
    """Workflow run result states"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEDOUT = "TIMEDOUT"
    CANCELED = "CANCELED"


@dataclass
class WorkflowConfig:
    """Configuration for workflow creation"""
    catalog: str = "main"
    schema: str = "default"
    embedding_model: str = "databricks-gte-large-en"
    embedding_dimension: int = 1024
    vector_endpoint: Optional[str] = None
    cluster_size: str = "Medium"
    schedule: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=lambda: {"project": "voice-rag"})
    
    def to_dict(self) -> Dict:
        return {
            "catalog": self.catalog,
            "schema": self.schema,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "vector_endpoint": self.vector_endpoint,
            "cluster_size": self.cluster_size,
            "schedule": self.schedule,
            "tags": self.tags
        }


@dataclass
class WorkflowRun:
    """Information about a workflow run"""
    run_id: int
    job_id: int
    state: str
    result_state: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tasks: List[Dict] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        return self.state in [RunStatus.TERMINATED.value, RunStatus.SKIPPED.value, RunStatus.INTERNAL_ERROR.value]
    
    def is_successful(self) -> bool:
        return self.result_state == RunResultState.SUCCESS.value


class WorkflowOrchestrator:
    """
    Orchestrates Databricks workflows for the RAG pipeline.
    
    Provides methods to:
    - Create and manage workflows/jobs
    - Trigger workflow runs
    - Monitor run status
    - Retrieve run results
    """
    
    def __init__(self, config: Optional[WorkflowConfig] = None):
        """Initialize the orchestrator"""
        self.config = config or WorkflowConfig()
        self._client = None
        self._jobs_cache: Dict[str, int] = {}  # name -> job_id mapping
    
    def _get_client(self):
        """Get or create the Databricks client"""
        if self._client is None:
            from databricks.sdk import WorkspaceClient
            self._client = WorkspaceClient()
        return self._client
    
    def _get_workflow_definition(
        self,
        workflow_type: WorkflowType,
        workflow_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the workflow definition for a given type"""
        base_name = workflow_name or f"voice-rag-{workflow_type.value}"
        
        if workflow_type == WorkflowType.INGESTION:
            return get_ingestion_workflow(
                workflow_name=base_name,
                catalog=self.config.catalog,
                schema=self.config.schema,
                cluster_size=self.config.cluster_size,
                schedule=self.config.schedule,
                tags=self.config.tags
            )
        elif workflow_type == WorkflowType.EMBEDDING:
            return get_embedding_workflow(
                workflow_name=base_name,
                catalog=self.config.catalog,
                schema=self.config.schema,
                embedding_model=self.config.embedding_model,
                cluster_size=self.config.cluster_size,
                schedule=self.config.schedule,
                tags=self.config.tags
            )
        elif workflow_type == WorkflowType.INDEXING:
            return get_indexing_workflow(
                workflow_name=base_name,
                catalog=self.config.catalog,
                schema=self.config.schema,
                vector_endpoint=self.config.vector_endpoint,
                cluster_size="Small",  # Indexing needs less compute
                schedule=self.config.schedule,
                tags=self.config.tags
            )
        elif workflow_type == WorkflowType.FULL_PIPELINE:
            return get_full_rag_workflow(
                workflow_name=base_name,
                catalog=self.config.catalog,
                schema=self.config.schema,
                embedding_model=self.config.embedding_model,
                vector_endpoint=self.config.vector_endpoint,
                cluster_size=self.config.cluster_size,
                schedule=self.config.schedule,
                tags=self.config.tags
            )
        elif workflow_type == WorkflowType.INCREMENTAL:
            return get_incremental_workflow(
                workflow_name=base_name,
                catalog=self.config.catalog,
                schema=self.config.schema,
                embedding_model=self.config.embedding_model,
                cluster_size="Small",
                schedule=self.config.schedule or "0 */15 * * * ?",
                tags=self.config.tags
            )
        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
    
    def create_workflow(
        self,
        workflow_type: WorkflowType,
        workflow_name: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Create a Databricks job for the specified workflow type.
        
        Args:
            workflow_type: Type of workflow to create
            workflow_name: Optional custom name
            overwrite: If True, update existing job with same name
            
        Returns:
            Dict with job_id and status
        """
        client = self._get_client()
        
        workflow_def = self._get_workflow_definition(workflow_type, workflow_name)
        job_name = workflow_def["name"]
        
        # Check if job already exists
        existing_job = self._find_job_by_name(job_name)
        
        if existing_job:
            if overwrite:
                # Update existing job
                client.jobs.update(
                    job_id=existing_job,
                    new_settings=workflow_def
                )
                self._jobs_cache[job_name] = existing_job
                return {
                    "status": "updated",
                    "job_id": existing_job,
                    "job_name": job_name
                }
            else:
                return {
                    "status": "exists",
                    "job_id": existing_job,
                    "job_name": job_name
                }
        
        # Create new job
        job = client.jobs.create(**workflow_def)
        job_id = job.job_id
        
        self._jobs_cache[job_name] = job_id
        
        return {
            "status": "created",
            "job_id": job_id,
            "job_name": job_name
        }
    
    def _find_job_by_name(self, job_name: str) -> Optional[int]:
        """Find a job by name and return its ID"""
        # Check cache first
        if job_name in self._jobs_cache:
            return self._jobs_cache[job_name]
        
        client = self._get_client()
        
        # List jobs and find by name
        jobs = client.jobs.list(name=job_name)
        
        for job in jobs:
            if job.settings.name == job_name:
                self._jobs_cache[job_name] = job.job_id
                return job.job_id
        
        return None
    
    def run_workflow(
        self,
        workflow_type: Optional[WorkflowType] = None,
        job_id: Optional[int] = None,
        job_name: Optional[str] = None,
        parameters: Optional[Dict[str, str]] = None,
        wait: bool = False,
        timeout_seconds: int = 3600
    ) -> WorkflowRun:
        """
        Trigger a workflow run.
        
        Args:
            workflow_type: Type of workflow (used to find job if job_id not provided)
            job_id: Direct job ID
            job_name: Job name to look up
            parameters: Override parameters for the run
            wait: If True, wait for completion
            timeout_seconds: Timeout when waiting
            
        Returns:
            WorkflowRun with run information
        """
        client = self._get_client()
        
        # Determine job_id
        if job_id is None:
            if job_name:
                job_id = self._find_job_by_name(job_name)
            elif workflow_type:
                default_name = f"voice-rag-{workflow_type.value}"
                job_id = self._find_job_by_name(default_name)
            
            if job_id is None:
                raise ValueError("Could not find job. Provide job_id, job_name, or create the workflow first.")
        
        # Prepare run parameters
        run_params = {}
        if parameters:
            run_params["notebook_params"] = parameters
        
        # Trigger run
        run = client.jobs.run_now(job_id=job_id, **run_params)
        run_id = run.run_id
        
        workflow_run = WorkflowRun(
            run_id=run_id,
            job_id=job_id,
            state=RunStatus.PENDING.value
        )
        
        if wait:
            workflow_run = self.wait_for_run(run_id, timeout_seconds)
        
        return workflow_run
    
    def get_run_status(self, run_id: int) -> WorkflowRun:
        """Get the current status of a workflow run"""
        client = self._get_client()
        
        run = client.jobs.get_run(run_id=run_id)
        
        # Extract task information
        tasks = []
        if run.tasks:
            for task in run.tasks:
                tasks.append({
                    "task_key": task.task_key,
                    "state": task.state.life_cycle_state.value if task.state else None,
                    "result_state": task.state.result_state.value if task.state and task.state.result_state else None
                })
        
        return WorkflowRun(
            run_id=run_id,
            job_id=run.job_id,
            state=run.state.life_cycle_state.value if run.state else RunStatus.PENDING.value,
            result_state=run.state.result_state.value if run.state and run.state.result_state else None,
            start_time=datetime.fromtimestamp(run.start_time / 1000) if run.start_time else None,
            end_time=datetime.fromtimestamp(run.end_time / 1000) if run.end_time else None,
            tasks=tasks
        )
    
    def wait_for_run(
        self,
        run_id: int,
        timeout_seconds: int = 3600,
        poll_interval: int = 30
    ) -> WorkflowRun:
        """Wait for a workflow run to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            run_status = self.get_run_status(run_id)
            
            if run_status.is_complete():
                return run_status
            
            time.sleep(poll_interval)
        
        # Timeout reached
        run_status = self.get_run_status(run_id)
        if not run_status.is_complete():
            run_status.result_state = RunResultState.TIMEDOUT.value
        
        return run_status
    
    def cancel_run(self, run_id: int) -> Dict[str, Any]:
        """Cancel a running workflow"""
        client = self._get_client()
        
        client.jobs.cancel_run(run_id=run_id)
        
        return {"status": "cancelled", "run_id": run_id}
    
    def list_runs(
        self,
        job_id: Optional[int] = None,
        workflow_type: Optional[WorkflowType] = None,
        limit: int = 25
    ) -> List[WorkflowRun]:
        """List recent workflow runs"""
        client = self._get_client()
        
        # Determine job_id if not provided
        if job_id is None and workflow_type:
            default_name = f"voice-rag-{workflow_type.value}"
            job_id = self._find_job_by_name(default_name)
        
        runs = []
        
        if job_id:
            # List runs for specific job
            run_list = client.jobs.list_runs(job_id=job_id, limit=limit)
            for run in run_list:
                runs.append(WorkflowRun(
                    run_id=run.run_id,
                    job_id=run.job_id,
                    state=run.state.life_cycle_state.value if run.state else RunStatus.PENDING.value,
                    result_state=run.state.result_state.value if run.state and run.state.result_state else None,
                    start_time=datetime.fromtimestamp(run.start_time / 1000) if run.start_time else None,
                    end_time=datetime.fromtimestamp(run.end_time / 1000) if run.end_time else None
                ))
        
        return runs
    
    def delete_workflow(
        self,
        job_id: Optional[int] = None,
        job_name: Optional[str] = None,
        workflow_type: Optional[WorkflowType] = None
    ) -> Dict[str, Any]:
        """Delete a workflow/job"""
        client = self._get_client()
        
        # Determine job_id
        if job_id is None:
            if job_name:
                job_id = self._find_job_by_name(job_name)
            elif workflow_type:
                default_name = f"voice-rag-{workflow_type.value}"
                job_id = self._find_job_by_name(default_name)
        
        if job_id is None:
            return {"status": "not_found"}
        
        client.jobs.delete(job_id=job_id)
        
        # Clean up cache
        for name, cached_id in list(self._jobs_cache.items()):
            if cached_id == job_id:
                del self._jobs_cache[name]
        
        return {"status": "deleted", "job_id": job_id}
    
    def setup_all_workflows(self, overwrite: bool = False) -> Dict[str, Any]:
        """Create all RAG workflows"""
        results = {}
        
        for workflow_type in WorkflowType:
            try:
                result = self.create_workflow(workflow_type, overwrite=overwrite)
                results[workflow_type.value] = result
            except Exception as e:
                results[workflow_type.value] = {"status": "error", "message": str(e)}
        
        return results
    
    def run_full_pipeline(
        self,
        wait: bool = True,
        timeout_seconds: int = 7200
    ) -> Dict[str, Any]:
        """
        Run the full RAG pipeline.
        
        Creates the workflow if it doesn't exist, then runs it.
        """
        # Ensure workflow exists
        create_result = self.create_workflow(WorkflowType.FULL_PIPELINE)
        
        # Run the workflow
        run = self.run_workflow(
            workflow_type=WorkflowType.FULL_PIPELINE,
            wait=wait,
            timeout_seconds=timeout_seconds
        )
        
        return {
            "workflow": create_result,
            "run": {
                "run_id": run.run_id,
                "state": run.state,
                "result_state": run.result_state,
                "is_successful": run.is_successful() if run.is_complete() else None
            }
        }


def main():
    """CLI for workflow orchestration"""
    import sys
    
    # Parse command
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <command> [options]")
        print("Commands: setup, run, status, list, delete")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Parse options
    params = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key] = value
    
    # Initialize orchestrator
    config = WorkflowConfig(
        catalog=params.get("catalog", "main"),
        schema=params.get("schema", "default")
    )
    orchestrator = WorkflowOrchestrator(config)
    
    if command == "setup":
        results = orchestrator.setup_all_workflows(overwrite=params.get("overwrite", "false").lower() == "true")
        print(json.dumps(results, indent=2))
    
    elif command == "run":
        workflow_type = WorkflowType(params.get("type", "full_pipeline"))
        run = orchestrator.run_workflow(
            workflow_type=workflow_type,
            wait=params.get("wait", "false").lower() == "true"
        )
        print(f"Run ID: {run.run_id}")
        print(f"State: {run.state}")
    
    elif command == "status":
        run_id = int(params.get("run_id", 0))
        if run_id:
            status = orchestrator.get_run_status(run_id)
            print(f"Run ID: {status.run_id}")
            print(f"State: {status.state}")
            print(f"Result: {status.result_state}")
    
    elif command == "list":
        workflow_type = WorkflowType(params.get("type", "full_pipeline"))
        runs = orchestrator.list_runs(workflow_type=workflow_type)
        for run in runs:
            print(f"Run {run.run_id}: {run.state} - {run.result_state}")
    
    elif command == "delete":
        workflow_type = WorkflowType(params.get("type", "full_pipeline"))
        result = orchestrator.delete_workflow(workflow_type=workflow_type)
        print(json.dumps(result))
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()


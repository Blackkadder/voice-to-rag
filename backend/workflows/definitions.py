"""
Databricks Workflow Definitions

Contains workflow configurations for different RAG pipeline stages.
These can be used to create Databricks Jobs via the SDK.
"""

from typing import Dict, List, Optional, Any


def get_cluster_config(
    cluster_size: str = "Medium",
    min_workers: int = 1,
    max_workers: int = 4,
    spark_version: str = "14.3.x-scala2.12",
    node_type_id: str = "i3.xlarge"
) -> Dict[str, Any]:
    """Get cluster configuration for workflows"""
    
    # Map cluster sizes to configurations
    size_configs = {
        "Small": {"min_workers": 1, "max_workers": 2, "node_type_id": "i3.xlarge"},
        "Medium": {"min_workers": 1, "max_workers": 4, "node_type_id": "i3.xlarge"},
        "Large": {"min_workers": 2, "max_workers": 8, "node_type_id": "i3.2xlarge"},
        "XLarge": {"min_workers": 4, "max_workers": 16, "node_type_id": "i3.4xlarge"},
    }
    
    config = size_configs.get(cluster_size, size_configs["Medium"])
    
    return {
        "spark_version": spark_version,
        "node_type_id": config.get("node_type_id", node_type_id),
        "autoscale": {
            "min_workers": min_workers or config["min_workers"],
            "max_workers": max_workers or config["max_workers"]
        },
        "spark_conf": {
            "spark.databricks.delta.preview.enabled": "true",
            "spark.sql.shuffle.partitions": "auto"
        },
        "spark_env_vars": {
            "PYSPARK_PYTHON": "/databricks/python3/bin/python3"
        }
    }


def get_ingestion_task(
    catalog: str = "main",
    schema: str = "default",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    chunking_strategy: str = "recursive"
) -> Dict[str, Any]:
    """Get task definition for document ingestion"""
    return {
        "task_key": "document_ingestion",
        "description": "Ingest and chunk documents for RAG",
        "python_wheel_task": {
            "package_name": "voice_rag_backend",
            "entry_point": "ingestion",
            "parameters": [
                f"catalog={catalog}",
                f"schema={schema}",
                f"chunk_size={chunk_size}",
                f"chunk_overlap={chunk_overlap}",
                f"chunking_strategy={chunking_strategy}"
            ]
        },
        "libraries": [
            {"pypi": {"package": "databricks-sdk>=0.18.0"}},
            {"pypi": {"package": "pyyaml>=6.0"}}
        ]
    }


def get_embedding_task(
    catalog: str = "main",
    schema: str = "default",
    embedding_model: str = "databricks-gte-large-en",
    embedding_dimension: int = 1024,
    batch_size: int = 32,
    depends_on: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Get task definition for embedding generation"""
    task = {
        "task_key": "generate_embeddings",
        "description": "Generate vector embeddings for document chunks",
        "python_wheel_task": {
            "package_name": "voice_rag_backend",
            "entry_point": "embedding",
            "parameters": [
                f"catalog={catalog}",
                f"schema={schema}",
                f"embedding_model={embedding_model}",
                f"embedding_dimension={embedding_dimension}",
                f"batch_size={batch_size}"
            ]
        },
        "libraries": [
            {"pypi": {"package": "databricks-sdk>=0.18.0"}},
            {"pypi": {"package": "requests>=2.28.0"}}
        ]
    }
    
    if depends_on:
        task["depends_on"] = [{"task_key": dep} for dep in depends_on]
    
    return task


def get_indexing_task(
    catalog: str = "main",
    schema: str = "default",
    vector_endpoint: Optional[str] = None,
    vector_index: Optional[str] = None,
    embedding_dimension: int = 1024,
    index_type: str = "DELTA_SYNC",
    depends_on: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Get task definition for vector index management"""
    
    params = [
        f"catalog={catalog}",
        f"schema={schema}",
        f"embedding_dimension={embedding_dimension}",
        f"index_type={index_type}"
    ]
    
    if vector_endpoint:
        params.append(f"vector_endpoint={vector_endpoint}")
    if vector_index:
        params.append(f"vector_index={vector_index}")
    
    task = {
        "task_key": "manage_vector_index",
        "description": "Create and sync vector search index",
        "python_wheel_task": {
            "package_name": "voice_rag_backend",
            "entry_point": "indexing",
            "parameters": params
        },
        "libraries": [
            {"pypi": {"package": "databricks-sdk>=0.18.0"}},
            {"pypi": {"package": "databricks-vectorsearch>=0.22"}}
        ]
    }
    
    if depends_on:
        task["depends_on"] = [{"task_key": dep} for dep in depends_on]
    
    return task


def get_ingestion_workflow(
    workflow_name: str = "voice-rag-ingestion",
    catalog: str = "main",
    schema: str = "default",
    cluster_size: str = "Medium",
    schedule: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get complete workflow definition for document ingestion pipeline.
    
    This workflow:
    1. Reads new transcriptions/documents
    2. Chunks documents into smaller pieces
    3. Stores chunks in Delta table
    """
    workflow = {
        "name": workflow_name,
        "description": "Document ingestion pipeline for Voice RAG",
        "tags": tags or {"project": "voice-rag", "pipeline": "ingestion"},
        "job_clusters": [
            {
                "job_cluster_key": "ingestion_cluster",
                "new_cluster": get_cluster_config(cluster_size)
            }
        ],
        "tasks": [
            {
                **get_ingestion_task(catalog=catalog, schema=schema),
                "job_cluster_key": "ingestion_cluster"
            }
        ],
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK"
    }
    
    if schedule:
        workflow["schedule"] = {
            "quartz_cron_expression": schedule,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        }
    
    return workflow


def get_embedding_workflow(
    workflow_name: str = "voice-rag-embedding",
    catalog: str = "main",
    schema: str = "default",
    embedding_model: str = "databricks-gte-large-en",
    cluster_size: str = "Medium",
    schedule: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get complete workflow definition for embedding generation pipeline.
    
    This workflow:
    1. Reads document chunks without embeddings
    2. Generates embeddings using the specified model
    3. Updates chunks table with embeddings
    """
    workflow = {
        "name": workflow_name,
        "description": "Embedding generation pipeline for Voice RAG",
        "tags": tags or {"project": "voice-rag", "pipeline": "embedding"},
        "job_clusters": [
            {
                "job_cluster_key": "embedding_cluster",
                "new_cluster": get_cluster_config(cluster_size)
            }
        ],
        "tasks": [
            {
                **get_embedding_task(
                    catalog=catalog,
                    schema=schema,
                    embedding_model=embedding_model
                ),
                "job_cluster_key": "embedding_cluster"
            }
        ],
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK"
    }
    
    if schedule:
        workflow["schedule"] = {
            "quartz_cron_expression": schedule,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        }
    
    return workflow


def get_indexing_workflow(
    workflow_name: str = "voice-rag-indexing",
    catalog: str = "main",
    schema: str = "default",
    vector_endpoint: Optional[str] = None,
    cluster_size: str = "Small",
    schedule: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get complete workflow definition for vector index management.
    
    This workflow:
    1. Creates/updates vector search endpoint
    2. Creates/updates vector search index
    3. Triggers index sync
    """
    workflow = {
        "name": workflow_name,
        "description": "Vector index management pipeline for Voice RAG",
        "tags": tags or {"project": "voice-rag", "pipeline": "indexing"},
        "job_clusters": [
            {
                "job_cluster_key": "indexing_cluster",
                "new_cluster": get_cluster_config(cluster_size)
            }
        ],
        "tasks": [
            {
                **get_indexing_task(
                    catalog=catalog,
                    schema=schema,
                    vector_endpoint=vector_endpoint
                ),
                "job_cluster_key": "indexing_cluster"
            }
        ],
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK"
    }
    
    if schedule:
        workflow["schedule"] = {
            "quartz_cron_expression": schedule,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        }
    
    return workflow


def get_full_rag_workflow(
    workflow_name: str = "voice-rag-full-pipeline",
    catalog: str = "main",
    schema: str = "default",
    embedding_model: str = "databricks-gte-large-en",
    vector_endpoint: Optional[str] = None,
    cluster_size: str = "Medium",
    schedule: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get complete workflow definition for full RAG pipeline.
    
    This workflow runs all stages in sequence:
    1. Document ingestion
    2. Embedding generation
    3. Vector index sync
    
    Use this for scheduled batch processing of new documents.
    """
    workflow = {
        "name": workflow_name,
        "description": "Full RAG pipeline: ingestion → embedding → indexing",
        "tags": tags or {"project": "voice-rag", "pipeline": "full"},
        "job_clusters": [
            {
                "job_cluster_key": "rag_pipeline_cluster",
                "new_cluster": get_cluster_config(cluster_size)
            }
        ],
        "tasks": [
            # Task 1: Document Ingestion
            {
                **get_ingestion_task(catalog=catalog, schema=schema),
                "job_cluster_key": "rag_pipeline_cluster"
            },
            # Task 2: Embedding Generation (depends on ingestion)
            {
                **get_embedding_task(
                    catalog=catalog,
                    schema=schema,
                    embedding_model=embedding_model,
                    depends_on=["document_ingestion"]
                ),
                "job_cluster_key": "rag_pipeline_cluster"
            },
            # Task 3: Vector Index Sync (depends on embedding)
            {
                **get_indexing_task(
                    catalog=catalog,
                    schema=schema,
                    vector_endpoint=vector_endpoint,
                    depends_on=["generate_embeddings"]
                ),
                "job_cluster_key": "rag_pipeline_cluster"
            }
        ],
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK"
    }
    
    if schedule:
        workflow["schedule"] = {
            "quartz_cron_expression": schedule,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        }
    
    return workflow


def get_incremental_workflow(
    workflow_name: str = "voice-rag-incremental",
    catalog: str = "main",
    schema: str = "default",
    embedding_model: str = "databricks-gte-large-en",
    cluster_size: str = "Small",
    schedule: str = "0 */15 * * * ?",  # Every 15 minutes
    tags: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Get workflow for incremental/real-time processing.
    
    Optimized for frequent runs with smaller batch sizes.
    Suitable for near-real-time document indexing.
    """
    workflow = {
        "name": workflow_name,
        "description": "Incremental RAG pipeline for near-real-time processing",
        "tags": tags or {"project": "voice-rag", "pipeline": "incremental"},
        "job_clusters": [
            {
                "job_cluster_key": "incremental_cluster",
                "new_cluster": {
                    **get_cluster_config(cluster_size),
                    "autotermination_minutes": 10
                }
            }
        ],
        "tasks": [
            {
                "task_key": "incremental_ingestion",
                "description": "Ingest new documents incrementally",
                "notebook_task": {
                    "notebook_path": "/Repos/voice-rag/notebooks/incremental_ingestion",
                    "base_parameters": {
                        "catalog": catalog,
                        "schema": schema,
                        "batch_size": "100"
                    }
                },
                "job_cluster_key": "incremental_cluster"
            },
            {
                "task_key": "incremental_embedding",
                "description": "Generate embeddings for new chunks",
                "depends_on": [{"task_key": "incremental_ingestion"}],
                "notebook_task": {
                    "notebook_path": "/Repos/voice-rag/notebooks/incremental_embedding",
                    "base_parameters": {
                        "catalog": catalog,
                        "schema": schema,
                        "embedding_model": embedding_model
                    }
                },
                "job_cluster_key": "incremental_cluster"
            },
            {
                "task_key": "trigger_sync",
                "description": "Trigger vector index sync",
                "depends_on": [{"task_key": "incremental_embedding"}],
                "notebook_task": {
                    "notebook_path": "/Repos/voice-rag/notebooks/trigger_index_sync",
                    "base_parameters": {
                        "catalog": catalog,
                        "schema": schema
                    }
                },
                "job_cluster_key": "incremental_cluster"
            }
        ],
        "schedule": {
            "quartz_cron_expression": schedule,
            "timezone_id": "UTC",
            "pause_status": "UNPAUSED"
        },
        "max_concurrent_runs": 1,
        "format": "MULTI_TASK"
    }
    
    return workflow


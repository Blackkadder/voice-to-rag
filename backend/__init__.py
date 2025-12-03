"""
Backend package for voice-to-rag graph RAG pipeline.

This package provides:
- Configuration management for RAG pipelines
- Document ingestion and chunking
- Embedding generation
- Vector search indexing
- Retrieval and generation pipelines
- Databricks workflow orchestration
"""

from .config import (
    PipelineConfig,
    UnityConfigConfig,
    AudioProcessingConfig,
    GraphRAGConfig,
    RetrievalConfig,
    DatabricksConfig,
    get_config,
    load_config_from_file,
    save_config_to_file,
)

# Pipeline imports
from .pipelines import (
    DocumentIngestionPipeline,
    EmbeddingPipeline,
    VectorIndexPipeline,
    VectorRetrievalPipeline,
    RAGGenerationPipeline,
)

# Workflow imports
from .workflows import (
    WorkflowOrchestrator,
    WorkflowConfig,
    get_ingestion_workflow,
    get_embedding_workflow,
    get_indexing_workflow,
    get_full_rag_workflow,
)

# Task utilities
from .tasks import (
    DeltaTableManager,
    TaskLogger,
    DataValidator,
    ValidationResult,
)

__all__ = [
    # Config
    "PipelineConfig",
    "UnityConfigConfig",
    "AudioProcessingConfig",
    "GraphRAGConfig",
    "RetrievalConfig",
    "DatabricksConfig",
    "get_config",
    "load_config_from_file",
    "save_config_to_file",
    # Pipelines
    "DocumentIngestionPipeline",
    "EmbeddingPipeline",
    "VectorIndexPipeline",
    "VectorRetrievalPipeline",
    "RAGGenerationPipeline",
    # Workflows
    "WorkflowOrchestrator",
    "WorkflowConfig",
    "get_ingestion_workflow",
    "get_embedding_workflow",
    "get_indexing_workflow",
    "get_full_rag_workflow",
    # Tasks
    "DeltaTableManager",
    "TaskLogger",
    "DataValidator",
    "ValidationResult",
]

__version__ = "0.2.0"

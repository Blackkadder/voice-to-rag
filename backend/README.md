# Backend - Vector Search RAG Pipeline

This directory contains the complete implementation of vector search RAG (Retrieval-Augmented Generation) pipelines as Databricks workflows.

## Overview

The backend provides a full RAG pipeline system including:

- **Document Ingestion**: Chunk documents/transcriptions for processing
- **Embedding Generation**: Create vector embeddings using Databricks Foundation Models
- **Vector Indexing**: Manage Databricks Vector Search indexes
- **Retrieval**: Semantic and hybrid search for relevant context
- **Generation**: RAG response generation with LLMs
- **Workflow Orchestration**: Databricks Jobs/Workflows management

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Databricks Workflows                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │  Ingestion   │──▶│  Embedding   │──▶│   Indexing   │        │
│  │   Pipeline   │   │   Pipeline   │   │   Pipeline   │        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Unity Catalog Delta Tables              │      │
│  │  • transcriptions  • document_chunks  • embeddings   │      │
│  └──────────────────────────────────────────────────────┘      │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────┐      │
│  │            Databricks Vector Search Index            │      │
│  └──────────────────────────────────────────────────────┘      │
│                              │                                  │
│         ┌────────────────────┴────────────────────┐            │
│         ▼                                         ▼            │
│  ┌──────────────┐                         ┌──────────────┐     │
│  │  Retrieval   │                         │  Generation  │     │
│  │   Pipeline   │────────────────────────▶│   Pipeline   │     │
│  └──────────────┘                         └──────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
backend/
├── __init__.py              # Package exports
├── config.py                # Configuration management
├── config.example.json      # Example configuration
├── requirements.txt         # Python dependencies
├── README.md                # This file
│
├── pipelines/               # Core pipeline modules
│   ├── __init__.py
│   ├── ingestion.py         # Document ingestion & chunking
│   ├── embedding.py         # Embedding generation
│   ├── indexing.py          # Vector index management
│   ├── retrieval.py         # Vector search retrieval
│   └── generation.py        # RAG response generation
│
├── workflows/               # Databricks workflow definitions
│   ├── __init__.py
│   ├── definitions.py       # Workflow task definitions
│   ├── orchestrator.py      # Workflow lifecycle management
│   ├── rag_pipeline.yaml    # Full pipeline YAML definition
│   └── incremental_pipeline.yaml  # Incremental processing
│
└── tasks/                   # Task utilities
    ├── __init__.py
    ├── delta_utils.py       # Delta table management
    ├── logging_utils.py     # Structured logging
    └── validation.py        # Data validation
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Set required environment variables:

```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token"
export UC_CATALOG="main"
export UC_SCHEMA="default"
```

### 3. Set Up Tables

```python
from backend.tasks import DeltaTableManager

# Initialize table manager
tables = DeltaTableManager(catalog="main", schema="default")

# Create all required tables
tables.setup_all_tables()
```

### 4. Create Workflows

```python
from backend.workflows import WorkflowOrchestrator, WorkflowConfig

# Configure
config = WorkflowConfig(
    catalog="main",
    schema="default",
    embedding_model="databricks-gte-large-en"
)

# Initialize orchestrator
orchestrator = WorkflowOrchestrator(config)

# Create all workflows
orchestrator.setup_all_workflows()
```

### 5. Run the Pipeline

```python
# Run the full RAG pipeline
result = orchestrator.run_full_pipeline(wait=True)
print(f"Pipeline result: {result}")
```

## Pipelines

### Document Ingestion Pipeline

Processes documents/transcriptions into chunks suitable for embedding.

```python
from backend.pipelines import DocumentIngestionPipeline

pipeline = DocumentIngestionPipeline({
    "catalog": "main",
    "schema": "default",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "chunking_strategy": "recursive"  # or "sentence", "fixed"
})

# Process a transcription
chunks = pipeline.ingest_transcription(
    transcription_text="Your transcription text here...",
    audio_file_path="/path/to/audio.mp3",
    metadata={"speaker": "John", "date": "2024-01-15"}
)
```

### Embedding Pipeline

Generates vector embeddings for document chunks.

```python
from backend.pipelines import EmbeddingPipeline

pipeline = EmbeddingPipeline({
    "catalog": "main",
    "schema": "default",
    "embedding_model": "databricks-gte-large-en",
    "embedding_dimension": 1024,
    "batch_size": 32
})

# Embed a single text (for queries)
embedding = pipeline.embed_text("What was discussed in the meeting?")

# Run as Spark job (for batch processing)
result = pipeline.run_spark(spark)
```

### Vector Index Pipeline

Manages Databricks Vector Search indexes.

```python
from backend.pipelines import VectorIndexPipeline

pipeline = VectorIndexPipeline({
    "catalog": "main",
    "schema": "default",
    "vector_endpoint": "voice-rag-endpoint",
    "vector_index": "main.default.voice_embeddings_index",
    "index_type": "DELTA_SYNC"
})

# Setup index
result = pipeline.setup_index()

# Sync index
pipeline.sync_index()
```

### Retrieval Pipeline

Performs vector similarity search with optional hybrid retrieval.

```python
from backend.pipelines import VectorRetrievalPipeline

pipeline = VectorRetrievalPipeline({
    "catalog": "main",
    "schema": "default",
    "top_k": 10,
    "use_hybrid_search": True,
    "similarity_threshold": 0.7
})

# Search
results = pipeline.search("What decisions were made about the budget?")

for result in results:
    print(f"Score: {result.score:.4f}")
    print(f"Content: {result.content[:200]}...")
```

### RAG Generation Pipeline

End-to-end RAG with retrieval and generation.

```python
from backend.pipelines import RAGGenerationPipeline

pipeline = RAGGenerationPipeline({
    "catalog": "main",
    "schema": "default",
    "generation_model": "databricks-llama-3-70b-instruct",
    "top_k": 10,
    "temperature": 0.7
})

# Answer a question
response = pipeline.answer("Summarize the key action items from the meeting")

print(f"Response: {response.response}")
print(f"Sources: {len(response.sources)}")
print(f"Generation time: {response.generation_time_ms:.2f}ms")
```

## Workflows

### Available Workflow Types

| Workflow | Description | Use Case |
|----------|-------------|----------|
| `ingestion` | Document ingestion only | Testing chunking |
| `embedding` | Embedding generation only | Reprocess embeddings |
| `indexing` | Vector index management | Index maintenance |
| `full_pipeline` | Complete pipeline | Batch processing |
| `incremental` | Incremental updates | Near-real-time |

### Running Workflows

```python
from backend.workflows import WorkflowOrchestrator, WorkflowType

orchestrator = WorkflowOrchestrator(config)

# Run specific workflow
run = orchestrator.run_workflow(
    workflow_type=WorkflowType.FULL_PIPELINE,
    wait=True,
    timeout_seconds=3600
)

# Check status
status = orchestrator.get_run_status(run.run_id)
print(f"Status: {status.state}, Result: {status.result_state}")

# List recent runs
runs = orchestrator.list_runs(workflow_type=WorkflowType.FULL_PIPELINE)
```

### YAML Workflow Definitions

Workflows can also be deployed using Databricks Asset Bundles:

```yaml
# databricks.yml
bundle:
  name: voice-rag

include:
  - ./backend/workflows/*.yaml

targets:
  development:
    workspace:
      host: https://dev.cloud.databricks.com
  production:
    workspace:
      host: https://prod.cloud.databricks.com
```

Deploy with:

```bash
databricks bundle deploy -t production
```

## Configuration

### Pipeline Configuration

```python
from backend.config import PipelineConfig

config = PipelineConfig()

# Access nested configs
print(config.graph_rag.chunk_size)  # 512
print(config.retrieval.top_k)       # 10
print(config.databricks.model_serving_endpoint)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Workspace URL | - |
| `DATABRICKS_TOKEN` | API token | - |
| `UC_CATALOG` | Unity Catalog name | `main` |
| `UC_SCHEMA` | Schema name | `default` |
| `UC_VOLUME` | Volume for data | `voice_data` |

## Task Utilities

### Delta Table Management

```python
from backend.tasks import DeltaTableManager

tables = DeltaTableManager(catalog="main", schema="default")

# Get table statistics
stats = tables.get_table_stats("document_chunks")
print(f"Rows: {stats['row_count']}")

# Optimize table
tables.optimize_table("document_chunks", zorder_columns=["document_id"])

# Vacuum old files
tables.vacuum_table("document_chunks", retention_hours=168)
```

### Task Logging

```python
from backend.tasks import TaskLogger, task_context

# Using context manager
with task_context("my_task") as logger:
    logger.info("Starting processing...")
    
    with logger.timed_operation("embedding_generation"):
        # Do work...
        pass
    
    logger.record_processed(100)
    logger.metric("custom_metric", 42)

# Direct logger usage
logger = TaskLogger("embedding_task", log_to_table=True)
logger.start()
try:
    # Do work...
    logger.complete()
except Exception as e:
    logger.fail(e)
```

### Data Validation

```python
from backend.tasks import DataValidator, validate_rag_data

# Validate data quality
results = validate_rag_data(
    spark,
    chunks_table="main.default.document_chunks",
    sample_size=1000
)

print(f"Chunks valid: {results['chunks'].is_valid}")
print(f"Embeddings valid: {results['embeddings'].is_valid}")

# Custom validation
validator = DataValidator({"embedding_dimension": 1024})
issues = validator.validate_embedding(my_embedding)
```

## Testing

```python
# Test retrieval pipeline locally
from backend.pipelines import VectorRetrievalPipeline

pipeline = VectorRetrievalPipeline({
    "catalog": "main",
    "schema": "default"
})

results = pipeline.search("test query")
assert len(results) > 0
```

## Monitoring

### Job Run Monitoring

```python
from backend.workflows import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator(config)

# Get recent runs
runs = orchestrator.list_runs(limit=10)

for run in runs:
    print(f"Run {run.run_id}: {run.state} - {run.result_state}")
    if run.duration_seconds:
        print(f"  Duration: {run.duration_seconds}s")
```

### Metrics Tables

Task metrics are logged to Delta tables when enabled:

```sql
-- Query task metrics
SELECT 
    task_name,
    status,
    records_processed,
    duration_seconds,
    run_timestamp
FROM main.default.task_logs
WHERE run_timestamp > current_date() - 7
ORDER BY run_timestamp DESC
```

## Troubleshooting

### Common Issues

**1. Embedding generation fails**
- Check that the embedding endpoint is accessible
- Verify API token has correct permissions
- Check rate limits on the endpoint

**2. Index sync stuck**
- Check Vector Search endpoint status
- Verify source table has embeddings
- Check for schema mismatches

**3. Workflow timeout**
- Increase `timeout_seconds` in task definition
- Check cluster autoscaling limits
- Review data volume

### Debug Mode

```python
import logging
logging.getLogger("voice_rag").setLevel(logging.DEBUG)
```

## Contributing

1. Follow existing code patterns
2. Add tests for new functionality
3. Update documentation
4. Use type hints

## Related Documentation

- [Frontend README](../frontend/README.md)
- [Databricks Vector Search](https://docs.databricks.com/generative-ai/vector-search.html)
- [Databricks Workflows](https://docs.databricks.com/workflows/index.html)
- [Unity Catalog](https://docs.databricks.com/unity-catalog/index.html)

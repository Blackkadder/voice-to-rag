# Backend - Graph RAG Pipeline Configuration

This directory contains configuration files and utilities for the Graph RAG (Retrieval-Augmented Generation) pipeline.

## Overview

The backend configuration system provides a comprehensive set of parameters to control all aspects of the voice-to-graph-RAG pipeline, including:

- Unity Catalog storage settings
- Audio processing parameters
- Graph construction and entity extraction
- Retrieval and generation settings
- Databricks service integration

## Files

- `config.py` - Main configuration module with dataclass-based configuration system
- `config.example.json` - Example configuration file in JSON format

## Configuration Components

### 1. Unity Catalog Configuration

Controls where voice data is stored in Databricks Unity Catalog:

```python
unity_catalog = UnityConfigConfig(
    catalog="main",
    schema="default",
    volume="voice_data"
)
```

### 2. Audio Processing Configuration

Parameters for audio transcription and processing:

```python
audio_processing = AudioProcessingConfig(
    sample_rate=16000,
    transcription_model="whisper-large-v3",
    enable_noise_reduction=True,
    chunk_length_seconds=30
)
```

### 3. Graph RAG Configuration

Settings for entity extraction and graph construction:

```python
graph_rag = GraphRAGConfig(
    entity_extraction_model="llama-3-70b-instruct",
    entity_types=["PERSON", "ORGANIZATION", "LOCATION", ...],
    min_entity_confidence=0.7,
    embedding_model="gte-large-en-v1.5",
    vector_index_name="main.default.voice_embeddings"
)
```

### 4. Retrieval Configuration

Parameters for querying and generating responses:

```python
retrieval = RetrievalConfig(
    top_k=10,
    similarity_threshold=0.7,
    generation_model="llama-3-70b-instruct",
    use_hybrid_search=True
)
```

### 5. Databricks Configuration

Integration settings for Databricks services:

```python
databricks = DatabricksConfig(
    model_serving_endpoint="voice-rag-endpoint",
    graph_data_table="main.default.graph_data",
    cluster_size="Medium"
)
```

## Usage

### Using Default Configuration

```python
from backend.config import get_config

config = get_config()
print(config.graph_rag.entity_extraction_model)
```

### Loading from JSON File

```python
from backend.config import load_config_from_file

config = load_config_from_file("config.json")
```

### Saving Configuration

```python
from backend.config import PipelineConfig, save_config_to_file

config = PipelineConfig()
config.graph_rag.entity_extraction_model = "custom-model"
save_config_to_file(config, "my_config.json")
```

### Converting to Dictionary

```python
from backend.config import get_config

config = get_config()
config_dict = config.to_dict()
```

### Environment Variable Override

Unity Catalog settings can be overridden with environment variables:

```bash
export UC_CATALOG="production"
export UC_SCHEMA="voice_data"
export UC_VOLUME="recordings"
export DATABRICKS_HOST="https://workspace.cloud.databricks.com"
```

## Configuration Parameters

### Audio Processing

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_rate` | int | 16000 | Audio sample rate in Hz |
| `channels` | int | 1 | Number of audio channels |
| `transcription_model` | str | "whisper-large-v3" | Model for speech-to-text |
| `enable_noise_reduction` | bool | true | Enable audio denoising |
| `chunk_length_seconds` | int | 30 | Length of audio chunks |

### Graph RAG

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_extraction_model` | str | "llama-3-70b-instruct" | LLM for entity extraction |
| `min_entity_confidence` | float | 0.7 | Minimum confidence for entities |
| `chunk_size` | int | 512 | Text chunk size for processing |
| `embedding_model` | str | "gte-large-en-v1.5" | Model for embeddings |
| `embedding_dimension` | int | 1024 | Embedding vector dimension |

### Retrieval

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `top_k` | int | 10 | Number of results to retrieve |
| `similarity_threshold` | float | 0.7 | Minimum similarity score |
| `generation_model` | str | "llama-3-70b-instruct" | LLM for response generation |
| `temperature` | float | 0.7 | Generation temperature |
| `use_hybrid_search` | bool | true | Enable hybrid keyword+semantic search |

## Integration with Frontend

The frontend application reads configuration from environment variables. Key mappings:

- `UC_CATALOG` → `unity_catalog.catalog`
- `UC_SCHEMA` → `unity_catalog.schema`
- `UC_VOLUME` → `unity_catalog.volume`
- `MODEL_ENDPOINT` → `databricks.model_serving_endpoint`
- `DELTA_TABLE` → `databricks.graph_data_table`

## Example Pipeline Usage

```python
from backend.config import PipelineConfig

# Load configuration
config = PipelineConfig()

# Use in pipeline
def process_audio(audio_path: str):
    # Transcribe with configured model
    transcription = transcribe_audio(
        audio_path,
        model=config.audio_processing.transcription_model,
        sample_rate=config.audio_processing.sample_rate
    )
    
    # Extract entities
    entities = extract_entities(
        transcription,
        model=config.graph_rag.entity_extraction_model,
        min_confidence=config.graph_rag.min_entity_confidence
    )
    
    # Build graph
    graph = build_graph(
        entities,
        max_hop_distance=config.graph_rag.max_hop_distance
    )
    
    return graph
```

## Extending Configuration

To add new configuration parameters:

1. Add fields to the appropriate dataclass in `config.py`
2. Update the `to_dict()` method to include new fields
3. Update `config.example.json` with example values
4. Document new parameters in this README

Example:

```python
@dataclass
class GraphRAGConfig:
    # ... existing fields ...
    
    # New field
    enable_coreference_resolution: bool = field(default=False)
```

## Best Practices

1. **Use Environment Variables**: For sensitive data (tokens, URLs) and deployment-specific settings
2. **Version Configuration Files**: Keep configuration files in version control
3. **Document Changes**: Update the example config and README when adding parameters
4. **Validate Values**: Add validation logic for critical parameters
5. **Use Defaults Wisely**: Set sensible defaults that work for most use cases

## Troubleshooting

### Configuration Not Loading

- Check file path is correct
- Verify JSON/YAML syntax is valid
- Ensure required fields are present

### Environment Variables Not Working

- Verify variable names match expected format
- Check variables are exported in the current shell
- Ensure application has access to read environment

### Type Errors

- Verify all numeric values are numbers, not strings in JSON
- Check boolean values are `true/false` not `"true"/"false"`
- Ensure lists are properly formatted

## Related Documentation

- [Frontend README](../frontend/README.md)
- [Databricks Unity Catalog](https://docs.databricks.com/unity-catalog/index.html)
- [Databricks Model Serving](https://docs.databricks.com/machine-learning/model-serving/index.html)

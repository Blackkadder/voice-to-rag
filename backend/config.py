"""
Graph RAG Pipeline Configuration

This module defines configuration parameters for the graph RAG pipeline.
It can be imported by backend processing scripts to maintain consistent settings.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import os


@dataclass
class UnityConfigConfig:
    """Configuration for Unity Catalog storage"""
    catalog: str = field(default="main")
    schema: str = field(default="default")
    volume: str = field(default="voice_data")
    
    @property
    def volume_path(self) -> str:
        """Get the full Unity Catalog volume path"""
        return f"/Volumes/{self.catalog}/{self.schema}/{self.volume}"
    
    def __post_init__(self):
        # Override with environment variables if present
        self.catalog = os.getenv("UC_CATALOG", self.catalog)
        self.schema = os.getenv("UC_SCHEMA", self.schema)
        self.volume = os.getenv("UC_VOLUME", self.volume)


@dataclass
class AudioProcessingConfig:
    """Configuration for audio processing pipeline"""
    # Audio format settings
    sample_rate: int = field(default=16000)
    channels: int = field(default=1)
    bit_depth: int = field(default=16)
    
    # Transcription settings
    transcription_model: str = field(default="whisper-large-v3")
    language: Optional[str] = field(default=None)  # Auto-detect if None
    
    # Processing options
    enable_noise_reduction: bool = field(default=True)
    enable_speaker_diarization: bool = field(default=False)
    chunk_length_seconds: int = field(default=30)


@dataclass
class GraphRAGConfig:
    """Configuration for Graph RAG pipeline"""
    # Graph construction
    entity_extraction_model: str = field(default="llama-3-70b-instruct")
    relationship_extraction_model: str = field(default="llama-3-70b-instruct")
    
    # Entity recognition
    entity_types: List[str] = field(default_factory=lambda: [
        "PERSON", "ORGANIZATION", "LOCATION", "DATE", "EVENT", "CONCEPT"
    ])
    
    # Graph parameters
    min_entity_confidence: float = field(default=0.7)
    min_relationship_confidence: float = field(default=0.6)
    max_hop_distance: int = field(default=3)
    
    # Chunking strategy
    chunk_size: int = field(default=512)
    chunk_overlap: int = field(default=50)
    
    # Embedding settings
    embedding_model: str = field(default="gte-large-en-v1.5")
    embedding_dimension: int = field(default=1024)
    
    # Vector store
    vector_store_type: str = field(default="databricks-vector-search")
    vector_index_name: str = field(default="main.default.voice_embeddings")


@dataclass
class RetrievalConfig:
    """Configuration for retrieval and generation"""
    # Retrieval parameters
    top_k: int = field(default=10)
    similarity_threshold: float = field(default=0.7)
    rerank_model: Optional[str] = field(default="bge-reranker-v2-m3")
    
    # Generation parameters
    generation_model: str = field(default="llama-3-70b-instruct")
    temperature: float = field(default=0.7)
    max_tokens: int = field(default=1024)
    
    # Context window
    max_context_tokens: int = field(default=4096)
    
    # Hybrid search
    use_hybrid_search: bool = field(default=True)
    keyword_weight: float = field(default=0.3)
    semantic_weight: float = field(default=0.7)


@dataclass
class DatabricksConfig:
    """Configuration for Databricks services"""
    # Workspace
    workspace_url: str = field(default_factory=lambda: os.getenv("DATABRICKS_HOST", ""))
    
    # Model serving
    model_serving_endpoint: str = field(default="voice-rag-endpoint")
    
    # Delta tables
    graph_data_table: str = field(default="main.default.graph_data")
    transcription_table: str = field(default="main.default.transcriptions")
    metadata_table: str = field(default="main.default.audio_metadata")
    
    # Job configuration
    cluster_size: str = field(default="Medium")
    min_workers: int = field(default=1)
    max_workers: int = field(default=4)


@dataclass
class PipelineConfig:
    """Main pipeline configuration combining all components"""
    unity_catalog: UnityConfigConfig = field(default_factory=UnityConfigConfig)
    audio_processing: AudioProcessingConfig = field(default_factory=AudioProcessingConfig)
    graph_rag: GraphRAGConfig = field(default_factory=GraphRAGConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    databricks: DatabricksConfig = field(default_factory=DatabricksConfig)
    
    # Pipeline execution
    enable_parallel_processing: bool = field(default=True)
    batch_size: int = field(default=10)
    retry_attempts: int = field(default=3)
    retry_delay_seconds: int = field(default=5)
    
    def to_dict(self) -> Dict:
        """Convert configuration to dictionary"""
        return {
            "unity_catalog": {
                "catalog": self.unity_catalog.catalog,
                "schema": self.unity_catalog.schema,
                "volume": self.unity_catalog.volume,
                "volume_path": self.unity_catalog.volume_path,
            },
            "audio_processing": {
                "sample_rate": self.audio_processing.sample_rate,
                "channels": self.audio_processing.channels,
                "bit_depth": self.audio_processing.bit_depth,
                "transcription_model": self.audio_processing.transcription_model,
                "language": self.audio_processing.language,
                "enable_noise_reduction": self.audio_processing.enable_noise_reduction,
                "enable_speaker_diarization": self.audio_processing.enable_speaker_diarization,
                "chunk_length_seconds": self.audio_processing.chunk_length_seconds,
            },
            "graph_rag": {
                "entity_extraction_model": self.graph_rag.entity_extraction_model,
                "relationship_extraction_model": self.graph_rag.relationship_extraction_model,
                "entity_types": self.graph_rag.entity_types,
                "min_entity_confidence": self.graph_rag.min_entity_confidence,
                "min_relationship_confidence": self.graph_rag.min_relationship_confidence,
                "max_hop_distance": self.graph_rag.max_hop_distance,
                "chunk_size": self.graph_rag.chunk_size,
                "chunk_overlap": self.graph_rag.chunk_overlap,
                "embedding_model": self.graph_rag.embedding_model,
                "embedding_dimension": self.graph_rag.embedding_dimension,
                "vector_store_type": self.graph_rag.vector_store_type,
                "vector_index_name": self.graph_rag.vector_index_name,
            },
            "retrieval": {
                "top_k": self.retrieval.top_k,
                "similarity_threshold": self.retrieval.similarity_threshold,
                "rerank_model": self.retrieval.rerank_model,
                "generation_model": self.retrieval.generation_model,
                "temperature": self.retrieval.temperature,
                "max_tokens": self.retrieval.max_tokens,
                "max_context_tokens": self.retrieval.max_context_tokens,
                "use_hybrid_search": self.retrieval.use_hybrid_search,
                "keyword_weight": self.retrieval.keyword_weight,
                "semantic_weight": self.retrieval.semantic_weight,
            },
            "databricks": {
                "workspace_url": self.databricks.workspace_url,
                "model_serving_endpoint": self.databricks.model_serving_endpoint,
                "graph_data_table": self.databricks.graph_data_table,
                "transcription_table": self.databricks.transcription_table,
                "metadata_table": self.databricks.metadata_table,
                "cluster_size": self.databricks.cluster_size,
                "min_workers": self.databricks.min_workers,
                "max_workers": self.databricks.max_workers,
            },
            "pipeline": {
                "enable_parallel_processing": self.enable_parallel_processing,
                "batch_size": self.batch_size,
                "retry_attempts": self.retry_attempts,
                "retry_delay_seconds": self.retry_delay_seconds,
            }
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict) -> "PipelineConfig":
        """Create configuration from dictionary"""
        return cls(
            unity_catalog=UnityConfigConfig(**config_dict.get("unity_catalog", {})),
            audio_processing=AudioProcessingConfig(**config_dict.get("audio_processing", {})),
            graph_rag=GraphRAGConfig(**config_dict.get("graph_rag", {})),
            retrieval=RetrievalConfig(**config_dict.get("retrieval", {})),
            databricks=DatabricksConfig(**config_dict.get("databricks", {})),
            **config_dict.get("pipeline", {})
        )


# Default configuration instance
default_config = PipelineConfig()


def get_config() -> PipelineConfig:
    """Get the default pipeline configuration"""
    return default_config


def load_config_from_file(filepath: str) -> PipelineConfig:
    """Load configuration from a JSON or YAML file"""
    import json
    
    with open(filepath, 'r') as f:
        if filepath.endswith('.json'):
            config_dict = json.load(f)
        elif filepath.endswith(('.yaml', '.yml')):
            import yaml
            config_dict = yaml.safe_load(f)
        else:
            raise ValueError("Unsupported file format. Use .json or .yaml")
    
    return PipelineConfig.from_dict(config_dict)


def save_config_to_file(config: PipelineConfig, filepath: str):
    """Save configuration to a JSON or YAML file"""
    import json
    
    config_dict = config.to_dict()
    
    with open(filepath, 'w') as f:
        if filepath.endswith('.json'):
            json.dump(config_dict, f, indent=2)
        elif filepath.endswith(('.yaml', '.yml')):
            import yaml
            yaml.dump(config_dict, f, default_flow_style=False)
        else:
            raise ValueError("Unsupported file format. Use .json or .yaml")

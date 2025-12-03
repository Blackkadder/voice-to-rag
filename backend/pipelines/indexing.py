"""
Vector Index Pipeline

Manages Databricks Vector Search indexes for RAG retrieval.
Handles index creation, syncing, and management.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime


class IndexType(str, Enum):
    """Vector search index types"""
    DELTA_SYNC = "DELTA_SYNC"  # Auto-sync with Delta table
    DIRECT_ACCESS = "DIRECT_ACCESS"  # Direct vector operations


class EmbeddingSourceType(str, Enum):
    """Source of embeddings for the index"""
    PRECOMPUTED = "precomputed"  # Embeddings stored in source table
    COMPUTE = "compute"  # Compute embeddings on indexing


@dataclass
class VectorIndexConfig:
    """Configuration for a vector search index"""
    index_name: str
    endpoint_name: str
    source_table: str
    primary_key: str = "chunk_id"
    embedding_column: str = "embedding"
    text_column: str = "content"
    embedding_dimension: int = 1024
    index_type: IndexType = IndexType.DELTA_SYNC
    embedding_source: EmbeddingSourceType = EmbeddingSourceType.PRECOMPUTED
    embedding_model_endpoint: Optional[str] = None
    sync_columns: List[str] = field(default_factory=lambda: ["content", "metadata", "document_id"])
    
    def to_dict(self) -> Dict:
        return {
            "index_name": self.index_name,
            "endpoint_name": self.endpoint_name,
            "source_table": self.source_table,
            "primary_key": self.primary_key,
            "embedding_column": self.embedding_column,
            "text_column": self.text_column,
            "embedding_dimension": self.embedding_dimension,
            "index_type": self.index_type.value,
            "embedding_source": self.embedding_source.value,
            "embedding_model_endpoint": self.embedding_model_endpoint,
            "sync_columns": self.sync_columns
        }


class VectorSearchClient:
    """Client for interacting with Databricks Vector Search"""
    
    def __init__(self):
        self._client = None
        self._vs_client = None
    
    def _get_workspace_client(self):
        """Get or create the Databricks workspace client"""
        if self._client is None:
            from databricks.sdk import WorkspaceClient
            self._client = WorkspaceClient()
        return self._client
    
    def _get_vs_client(self):
        """Get or create the Vector Search client"""
        if self._vs_client is None:
            from databricks.vector_search.client import VectorSearchClient as VSClient
            self._vs_client = VSClient()
        return self._vs_client
    
    def create_endpoint(self, endpoint_name: str) -> Dict[str, Any]:
        """Create a vector search endpoint if it doesn't exist"""
        vs_client = self._get_vs_client()
        
        try:
            # Check if endpoint exists
            endpoint = vs_client.get_endpoint(endpoint_name)
            return {"status": "exists", "endpoint": endpoint}
        except Exception:
            pass
        
        # Create new endpoint
        endpoint = vs_client.create_endpoint(
            name=endpoint_name,
            endpoint_type="STANDARD"
        )
        
        return {"status": "created", "endpoint": endpoint}
    
    def create_delta_sync_index(self, config: VectorIndexConfig) -> Dict[str, Any]:
        """Create a Delta Sync vector search index"""
        vs_client = self._get_vs_client()
        
        # Build index specification
        if config.embedding_source == EmbeddingSourceType.PRECOMPUTED:
            # Use pre-computed embeddings from source table
            index_spec = {
                "source_table": config.source_table,
                "primary_key": config.primary_key,
                "embedding_vector_column": config.embedding_column,
                "embedding_dimension": config.embedding_dimension,
                "columns_to_sync": config.sync_columns
            }
            
            index = vs_client.create_delta_sync_index(
                endpoint_name=config.endpoint_name,
                index_name=config.index_name,
                source_table_name=config.source_table,
                primary_key=config.primary_key,
                embedding_dimension=config.embedding_dimension,
                embedding_vector_column=config.embedding_column,
                pipeline_type="TRIGGERED"  # Manual sync triggers
            )
        else:
            # Compute embeddings during indexing
            index = vs_client.create_delta_sync_index(
                endpoint_name=config.endpoint_name,
                index_name=config.index_name,
                source_table_name=config.source_table,
                primary_key=config.primary_key,
                embedding_source_column=config.text_column,
                embedding_model_endpoint_name=config.embedding_model_endpoint,
                pipeline_type="TRIGGERED"
            )
        
        return {"status": "created", "index": config.index_name}
    
    def create_direct_access_index(self, config: VectorIndexConfig) -> Dict[str, Any]:
        """Create a Direct Access vector search index"""
        vs_client = self._get_vs_client()
        
        index = vs_client.create_direct_access_index(
            endpoint_name=config.endpoint_name,
            index_name=config.index_name,
            primary_key=config.primary_key,
            embedding_dimension=config.embedding_dimension,
            embedding_vector_column=config.embedding_column,
            schema={
                config.primary_key: "string",
                config.text_column: "string",
                "metadata": "string",
                "document_id": "string",
                config.embedding_column: f"array<float>"
            }
        )
        
        return {"status": "created", "index": config.index_name}
    
    def get_index(self, endpoint_name: str, index_name: str) -> Optional[Any]:
        """Get an existing index"""
        vs_client = self._get_vs_client()
        
        try:
            return vs_client.get_index(
                endpoint_name=endpoint_name,
                index_name=index_name
            )
        except Exception:
            return None
    
    def sync_index(self, endpoint_name: str, index_name: str) -> Dict[str, Any]:
        """Trigger a sync for a Delta Sync index"""
        vs_client = self._get_vs_client()
        
        index = vs_client.get_index(
            endpoint_name=endpoint_name,
            index_name=index_name
        )
        
        # Trigger sync
        index.sync()
        
        return {"status": "sync_triggered", "index": index_name}
    
    def wait_for_index_ready(
        self,
        endpoint_name: str,
        index_name: str,
        timeout_seconds: int = 600,
        poll_interval: int = 30
    ) -> Dict[str, Any]:
        """Wait for an index to be ready"""
        vs_client = self._get_vs_client()
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                index = vs_client.get_index(
                    endpoint_name=endpoint_name,
                    index_name=index_name
                )
                
                status = index.describe()
                
                if status.get("status", {}).get("ready", False):
                    return {"status": "ready", "index": index_name}
                
                if status.get("status", {}).get("message"):
                    print(f"Index status: {status['status']['message']}")
                
            except Exception as e:
                print(f"Error checking index status: {e}")
            
            time.sleep(poll_interval)
        
        return {"status": "timeout", "index": index_name}
    
    def delete_index(self, endpoint_name: str, index_name: str) -> Dict[str, Any]:
        """Delete a vector search index"""
        vs_client = self._get_vs_client()
        
        vs_client.delete_index(
            endpoint_name=endpoint_name,
            index_name=index_name
        )
        
        return {"status": "deleted", "index": index_name}


class VectorIndexPipeline:
    """
    Main pipeline for managing vector search indexes.
    Handles index lifecycle and synchronization.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the indexing pipeline"""
        self.config = config or {}
        
        # Unity Catalog configuration
        self.catalog = self.config.get("catalog", "main")
        self.schema = self.config.get("schema", "default")
        
        # Index configuration
        self.endpoint_name = self.config.get("vector_endpoint", f"{self.catalog}_{self.schema}_endpoint")
        self.index_name = self.config.get("vector_index", f"{self.catalog}.{self.schema}.voice_embeddings_index")
        self.source_table = self.config.get("chunks_table", f"{self.catalog}.{self.schema}.document_chunks")
        
        # Embedding configuration
        self.embedding_dimension = self.config.get("embedding_dimension", 1024)
        self.embedding_column = self.config.get("embedding_column", "embedding")
        self.primary_key = self.config.get("primary_key", "chunk_id")
        
        # Index type
        index_type_str = self.config.get("index_type", "DELTA_SYNC")
        self.index_type = IndexType(index_type_str) if isinstance(index_type_str, str) else index_type_str
        
        # Embedding source
        embedding_source_str = self.config.get("embedding_source", "precomputed")
        self.embedding_source = EmbeddingSourceType(embedding_source_str)
        
        self.embedding_model_endpoint = self.config.get("embedding_model_endpoint")
        
        # Columns to sync
        self.sync_columns = self.config.get("sync_columns", [
            "content", "metadata", "document_id", "chunk_index"
        ])
        
        # Initialize client
        self.client = VectorSearchClient()
    
    def get_index_config(self) -> VectorIndexConfig:
        """Get the current index configuration"""
        return VectorIndexConfig(
            index_name=self.index_name,
            endpoint_name=self.endpoint_name,
            source_table=self.source_table,
            primary_key=self.primary_key,
            embedding_column=self.embedding_column,
            text_column="content",
            embedding_dimension=self.embedding_dimension,
            index_type=self.index_type,
            embedding_source=self.embedding_source,
            embedding_model_endpoint=self.embedding_model_endpoint,
            sync_columns=self.sync_columns
        )
    
    def setup_index(self) -> Dict[str, Any]:
        """Set up the vector search endpoint and index"""
        results = {}
        
        # Create endpoint if needed
        endpoint_result = self.client.create_endpoint(self.endpoint_name)
        results["endpoint"] = endpoint_result
        
        # Check if index exists
        existing_index = self.client.get_index(self.endpoint_name, self.index_name)
        
        if existing_index is not None:
            results["index"] = {"status": "exists", "index": self.index_name}
            return results
        
        # Create index based on type
        index_config = self.get_index_config()
        
        if self.index_type == IndexType.DELTA_SYNC:
            index_result = self.client.create_delta_sync_index(index_config)
        else:
            index_result = self.client.create_direct_access_index(index_config)
        
        results["index"] = index_result
        
        # Wait for index to be ready
        ready_result = self.client.wait_for_index_ready(
            self.endpoint_name,
            self.index_name,
            timeout_seconds=self.config.get("setup_timeout", 600)
        )
        results["ready"] = ready_result
        
        return results
    
    def sync_index(self) -> Dict[str, Any]:
        """Trigger index synchronization"""
        return self.client.sync_index(self.endpoint_name, self.index_name)
    
    def run_spark(self, spark) -> Dict[str, Any]:
        """
        Run indexing pipeline as a Spark job.
        Sets up index and triggers sync.
        
        Args:
            spark: SparkSession instance
            
        Returns:
            Dict with indexing results
        """
        results = {}
        
        # Verify source table exists and has data
        try:
            chunks_df = spark.table(self.source_table)
            chunk_count = chunks_df.count()
            
            if chunk_count == 0:
                return {"status": "no_data", "message": "Source table is empty"}
            
            # Check for embeddings
            from pyspark.sql import functions as F
            embedded_count = chunks_df.filter(
                F.col(self.embedding_column).isNotNull() & 
                (F.size(F.col(self.embedding_column)) > 0)
            ).count()
            
            results["source_stats"] = {
                "total_chunks": chunk_count,
                "embedded_chunks": embedded_count
            }
            
            if embedded_count == 0 and self.embedding_source == EmbeddingSourceType.PRECOMPUTED:
                return {
                    "status": "no_embeddings",
                    "message": "No embeddings found. Run embedding pipeline first."
                }
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to read source table: {e}"}
        
        # Set up index
        setup_results = self.setup_index()
        results.update(setup_results)
        
        # Trigger sync if Delta Sync index
        if self.index_type == IndexType.DELTA_SYNC:
            sync_result = self.sync_index()
            results["sync"] = sync_result
        
        results["status"] = "success"
        return results
    
    def get_index_status(self) -> Dict[str, Any]:
        """Get the current status of the index"""
        index = self.client.get_index(self.endpoint_name, self.index_name)
        
        if index is None:
            return {"status": "not_found"}
        
        try:
            description = index.describe()
            return {
                "status": "found",
                "details": description
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


def main():
    """Entry point for Databricks job"""
    from pyspark.sql import SparkSession
    import sys
    
    # Parse job parameters
    params = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key] = value
    
    # Create Spark session
    spark = SparkSession.builder.appName("VectorIndexPipeline").getOrCreate()
    
    # Initialize pipeline with parameters
    config = {
        "catalog": params.get("catalog", "main"),
        "schema": params.get("schema", "default"),
        "vector_endpoint": params.get("vector_endpoint"),
        "vector_index": params.get("vector_index"),
        "embedding_dimension": int(params.get("embedding_dimension", "1024")),
        "index_type": params.get("index_type", "DELTA_SYNC"),
        "embedding_source": params.get("embedding_source", "precomputed"),
    }
    
    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}
    
    pipeline = VectorIndexPipeline(config)
    result = pipeline.run_spark(spark)
    
    print(f"Indexing complete: {result}")
    
    # Set task values for downstream tasks
    dbutils = spark.sparkContext._jvm.com.databricks.dbutils_v1.DBUtilsHolder.dbutils()
    dbutils.jobs().taskValues().set("indexing_result", json.dumps(result))


if __name__ == "__main__":
    main()


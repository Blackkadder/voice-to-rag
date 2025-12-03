"""
Embedding Pipeline

Generates vector embeddings for document chunks using Databricks Model Serving
or Foundation Model APIs.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import json
import time
from datetime import datetime


@dataclass
class EmbeddingResult:
    """Result from embedding generation"""
    chunk_id: str
    embedding: List[float]
    model: str
    token_count: int
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()


class EmbeddingClient:
    """Client for generating embeddings via Databricks APIs"""
    
    def __init__(
        self,
        model_name: str = "databricks-gte-large-en",
        endpoint_name: Optional[str] = None,
        batch_size: int = 32,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.model_name = model_name
        self.endpoint_name = endpoint_name or model_name
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = None
    
    def _get_client(self):
        """Get or create the Databricks client"""
        if self._client is None:
            try:
                from databricks.sdk import WorkspaceClient
                self._client = WorkspaceClient()
            except ImportError:
                raise ImportError(
                    "databricks-sdk is required. Install with: pip install databricks-sdk"
                )
        return self._client
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        if not texts:
            return []
        
        client = self._get_client()
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = self._embed_batch_with_retry(client, batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def _embed_batch_with_retry(self, client, texts: List[str]) -> List[List[float]]:
        """Embed a batch with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return self._embed_batch(client, texts)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        raise RuntimeError(f"Failed to embed batch after {self.max_retries} attempts: {last_error}")
    
    def _embed_batch(self, client, texts: List[str]) -> List[List[float]]:
        """Embed a single batch of texts"""
        # Try Foundation Model API first
        try:
            response = client.serving_endpoints.query(
                name=self.endpoint_name,
                dataframe_records=[{"text": text} for text in texts]
            )
            
            # Extract embeddings from response
            if hasattr(response, 'predictions'):
                return response.predictions
            elif hasattr(response, 'data'):
                return [item.embedding for item in response.data]
            else:
                raise ValueError("Unexpected response format")
        
        except Exception as e:
            # Fall back to direct API call
            return self._embed_via_serving_endpoint(client, texts)
    
    def _embed_via_serving_endpoint(self, client, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via model serving endpoint"""
        import requests
        
        workspace_url = client.config.host
        token = client.config.token
        
        url = f"{workspace_url}/serving-endpoints/{self.endpoint_name}/invocations"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": texts
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if "data" in result:
            return [item["embedding"] for item in result["data"]]
        elif "predictions" in result:
            return result["predictions"]
        else:
            raise ValueError(f"Unexpected response format: {result}")
    
    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []


class EmbeddingPipeline:
    """
    Main pipeline for generating embeddings.
    Processes document chunks and adds vector embeddings.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the embedding pipeline"""
        self.config = config or {}
        
        # Model configuration
        self.model_name = self.config.get("embedding_model", "databricks-gte-large-en")
        self.endpoint_name = self.config.get("embedding_endpoint", self.model_name)
        self.embedding_dimension = self.config.get("embedding_dimension", 1024)
        self.batch_size = self.config.get("batch_size", 32)
        
        # Unity Catalog configuration
        self.catalog = self.config.get("catalog", "main")
        self.schema = self.config.get("schema", "default")
        self.chunks_table = self.config.get("chunks_table", f"{self.catalog}.{self.schema}.document_chunks")
        
        # Initialize embedding client
        self.client = EmbeddingClient(
            model_name=self.model_name,
            endpoint_name=self.endpoint_name,
            batch_size=self.batch_size,
            max_retries=self.config.get("max_retries", 3),
            retry_delay=self.config.get("retry_delay", 1.0)
        )
    
    def embed_chunks(self, chunks: List[Dict]) -> List[EmbeddingResult]:
        """Generate embeddings for a list of chunk dictionaries"""
        if not chunks:
            return []
        
        texts = [chunk.get("content", "") for chunk in chunks]
        chunk_ids = [chunk.get("chunk_id", str(i)) for i, chunk in enumerate(chunks)]
        
        embeddings = self.client.embed_texts(texts)
        
        results = []
        for chunk_id, embedding, text in zip(chunk_ids, embeddings, texts):
            results.append(EmbeddingResult(
                chunk_id=chunk_id,
                embedding=embedding,
                model=self.model_name,
                token_count=len(text.split())  # Approximate token count
            ))
        
        return results
    
    def run_spark(self, spark) -> Dict[str, Any]:
        """
        Run embedding pipeline as a Spark job.
        Reads chunks without embeddings and adds them.
        
        Args:
            spark: SparkSession instance
            
        Returns:
            Dict with processing statistics
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import ArrayType, FloatType
        
        # Read chunks without embeddings
        try:
            chunks_df = spark.table(self.chunks_table)
        except Exception as e:
            return {"status": "error", "message": f"Failed to read chunks table: {e}"}
        
        # Filter to chunks without embeddings
        chunks_to_embed = chunks_df.filter(
            F.col("embedding").isNull() | (F.size(F.col("embedding")) == 0)
        )
        
        chunks_count = chunks_to_embed.count()
        if chunks_count == 0:
            return {"status": "no_new_chunks", "chunks_embedded": 0}
        
        # Collect chunks for embedding (for smaller datasets)
        # For large datasets, use Pandas UDF with batch processing
        if chunks_count <= 10000:
            return self._embed_small_batch(spark, chunks_to_embed)
        else:
            return self._embed_large_batch(spark, chunks_to_embed)
    
    def _embed_small_batch(self, spark, chunks_df) -> Dict[str, Any]:
        """Embed a small batch of chunks by collecting to driver"""
        from pyspark.sql import functions as F
        
        # Collect chunks
        chunks_data = chunks_df.select("chunk_id", "content").collect()
        
        # Generate embeddings
        chunk_ids = [row.chunk_id for row in chunks_data]
        texts = [row.content for row in chunks_data]
        
        embeddings = self.client.embed_texts(texts)
        
        # Create DataFrame with embeddings
        embedding_data = [
            (chunk_id, embedding)
            for chunk_id, embedding in zip(chunk_ids, embeddings)
        ]
        
        embeddings_df = spark.createDataFrame(
            embedding_data,
            ["chunk_id", "new_embedding"]
        )
        
        # Update the chunks table
        chunks_df_full = spark.table(self.chunks_table)
        
        updated_df = chunks_df_full.join(
            embeddings_df,
            on="chunk_id",
            how="left"
        ).withColumn(
            "embedding",
            F.coalesce(F.col("new_embedding"), F.col("embedding"))
        ).drop("new_embedding")
        
        # Overwrite the table with updated embeddings
        updated_df.write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(self.chunks_table)
        
        return {
            "status": "success",
            "chunks_embedded": len(chunk_ids),
            "model": self.model_name,
            "chunks_table": self.chunks_table
        }
    
    def _embed_large_batch(self, spark, chunks_df) -> Dict[str, Any]:
        """Embed a large batch using Pandas UDF for distributed processing"""
        from pyspark.sql import functions as F
        from pyspark.sql.types import ArrayType, FloatType
        import pandas as pd
        
        # Create a broadcast variable for the endpoint configuration
        endpoint_config = spark.sparkContext.broadcast({
            "model_name": self.model_name,
            "endpoint_name": self.endpoint_name,
            "batch_size": self.batch_size
        })
        
        @F.pandas_udf(ArrayType(FloatType()))
        def embed_batch_udf(texts: pd.Series) -> pd.Series:
            """Pandas UDF to embed texts in batches"""
            from databricks.sdk import WorkspaceClient
            import requests
            
            config = endpoint_config.value
            client = WorkspaceClient()
            
            workspace_url = client.config.host
            token = client.config.token
            
            url = f"{workspace_url}/serving-endpoints/{config['endpoint_name']}/invocations"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            results = []
            text_list = texts.tolist()
            batch_size = config["batch_size"]
            
            for i in range(0, len(text_list), batch_size):
                batch = text_list[i:i + batch_size]
                
                payload = {"input": batch}
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                if "data" in result:
                    batch_embeddings = [item["embedding"] for item in result["data"]]
                else:
                    batch_embeddings = result.get("predictions", [])
                
                results.extend(batch_embeddings)
            
            return pd.Series(results)
        
        # Apply the UDF
        embedded_df = chunks_df.withColumn(
            "new_embedding",
            embed_batch_udf(F.col("content"))
        )
        
        # Update the full table
        chunks_df_full = spark.table(self.chunks_table)
        chunks_count = chunks_df.count()
        
        updated_df = chunks_df_full.join(
            embedded_df.select("chunk_id", "new_embedding"),
            on="chunk_id",
            how="left"
        ).withColumn(
            "embedding",
            F.coalesce(F.col("new_embedding"), F.col("embedding"))
        ).drop("new_embedding")
        
        # Write back
        updated_df.write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(self.chunks_table)
        
        return {
            "status": "success",
            "chunks_embedded": chunks_count,
            "model": self.model_name,
            "chunks_table": self.chunks_table,
            "processing_mode": "distributed"
        }
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text (for real-time queries)"""
        return self.client.embed_single(text)


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
    spark = SparkSession.builder.appName("EmbeddingPipeline").getOrCreate()
    
    # Initialize pipeline with parameters
    config = {
        "catalog": params.get("catalog", "main"),
        "schema": params.get("schema", "default"),
        "embedding_model": params.get("embedding_model", "databricks-gte-large-en"),
        "embedding_endpoint": params.get("embedding_endpoint", "databricks-gte-large-en"),
        "embedding_dimension": int(params.get("embedding_dimension", "1024")),
        "batch_size": int(params.get("batch_size", "32")),
    }
    
    pipeline = EmbeddingPipeline(config)
    result = pipeline.run_spark(spark)
    
    print(f"Embedding complete: {result}")
    
    # Set task values for downstream tasks
    dbutils = spark.sparkContext._jvm.com.databricks.dbutils_v1.DBUtilsHolder.dbutils()
    dbutils.jobs().taskValues().set("embedding_result", json.dumps(result))


if __name__ == "__main__":
    main()


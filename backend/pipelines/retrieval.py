"""
Vector Retrieval Pipeline

Handles vector similarity search and hybrid retrieval for RAG.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
import json
from datetime import datetime


@dataclass
class RetrievalResult:
    """Result from vector search retrieval"""
    chunk_id: str
    content: str
    score: float
    document_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "document_id": self.document_id,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index
        }


@dataclass
class RetrievalRequest:
    """Request for vector retrieval"""
    query: str
    top_k: int = 10
    filters: Optional[Dict[str, Any]] = None
    similarity_threshold: float = 0.0
    include_metadata: bool = True
    use_hybrid: bool = False
    keyword_weight: float = 0.3
    semantic_weight: float = 0.7


class VectorRetrievalClient:
    """Client for vector search retrieval"""
    
    def __init__(
        self,
        endpoint_name: str,
        index_name: str,
        embedding_model: str = "databricks-gte-large-en"
    ):
        self.endpoint_name = endpoint_name
        self.index_name = index_name
        self.embedding_model = embedding_model
        self._vs_client = None
        self._embedding_client = None
    
    def _get_vs_client(self):
        """Get the Vector Search client"""
        if self._vs_client is None:
            from databricks.vector_search.client import VectorSearchClient
            self._vs_client = VectorSearchClient()
        return self._vs_client
    
    def _get_index(self):
        """Get the vector search index"""
        vs_client = self._get_vs_client()
        return vs_client.get_index(
            endpoint_name=self.endpoint_name,
            index_name=self.index_name
        )
    
    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for the query"""
        if self._embedding_client is None:
            from .embedding import EmbeddingClient
            self._embedding_client = EmbeddingClient(
                model_name=self.embedding_model,
                endpoint_name=self.embedding_model
            )
        
        return self._embedding_client.embed_single(query)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
        columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        index = self._get_index()
        
        # Default columns to retrieve
        if columns is None:
            columns = ["chunk_id", "content", "document_id", "metadata", "chunk_index"]
        
        # Search using query text (index will handle embedding)
        try:
            results = index.similarity_search(
                query_text=query,
                num_results=top_k,
                columns=columns,
                filters=filters
            )
        except Exception:
            # Fall back to embedding the query manually
            query_embedding = self._embed_query(query)
            results = index.similarity_search(
                query_vector=query_embedding,
                num_results=top_k,
                columns=columns,
                filters=filters
            )
        
        return results.get("result", {}).get("data_array", [])
    
    def search_with_score(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Search and return results with similarity scores"""
        results = self.search(query, top_k, filters)
        
        # Results include score as the last column
        scored_results = []
        for row in results:
            if len(row) >= 2:
                # Last element is typically the score
                score = row[-1] if isinstance(row[-1], (int, float)) else 0.0
                data = {
                    "chunk_id": row[0] if len(row) > 0 else "",
                    "content": row[1] if len(row) > 1 else "",
                    "document_id": row[2] if len(row) > 2 else "",
                    "metadata": row[3] if len(row) > 3 else {},
                    "chunk_index": row[4] if len(row) > 4 else 0,
                }
                scored_results.append((data, score))
        
        return scored_results


class HybridSearchClient:
    """Client for hybrid keyword + semantic search"""
    
    def __init__(
        self,
        vector_client: VectorRetrievalClient,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7
    ):
        self.vector_client = vector_client
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Perform hybrid search combining keyword and semantic search"""
        # Get semantic results
        semantic_results = self.vector_client.search_with_score(
            query=query,
            top_k=top_k * 2,  # Get more results for reranking
            filters=filters
        )
        
        # Perform keyword matching
        query_terms = set(query.lower().split())
        
        # Score and combine results
        combined_scores = {}
        
        for data, semantic_score in semantic_results:
            chunk_id = data.get("chunk_id", "")
            content = data.get("content", "").lower()
            
            # Calculate keyword score
            content_terms = set(content.split())
            keyword_overlap = len(query_terms.intersection(content_terms))
            keyword_score = keyword_overlap / max(len(query_terms), 1)
            
            # Combine scores
            combined_score = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score
            )
            
            combined_scores[chunk_id] = (data, combined_score)
        
        # Sort by combined score
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        return sorted_results


class VectorRetrievalPipeline:
    """
    Main pipeline for vector search retrieval.
    Handles both simple and hybrid retrieval strategies.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the retrieval pipeline"""
        self.config = config or {}
        
        # Unity Catalog configuration
        self.catalog = self.config.get("catalog", "main")
        self.schema = self.config.get("schema", "default")
        
        # Index configuration
        self.endpoint_name = self.config.get(
            "vector_endpoint",
            f"{self.catalog}_{self.schema}_endpoint"
        )
        self.index_name = self.config.get(
            "vector_index",
            f"{self.catalog}.{self.schema}.voice_embeddings_index"
        )
        
        # Retrieval configuration
        self.top_k = self.config.get("top_k", 10)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.7)
        self.use_hybrid = self.config.get("use_hybrid_search", True)
        self.keyword_weight = self.config.get("keyword_weight", 0.3)
        self.semantic_weight = self.config.get("semantic_weight", 0.7)
        
        # Embedding model
        self.embedding_model = self.config.get("embedding_model", "databricks-gte-large-en")
        
        # Reranking configuration
        self.use_reranking = self.config.get("use_reranking", False)
        self.rerank_model = self.config.get("rerank_model")
        
        # Initialize clients
        self.vector_client = VectorRetrievalClient(
            endpoint_name=self.endpoint_name,
            index_name=self.index_name,
            embedding_model=self.embedding_model
        )
        
        if self.use_hybrid:
            self.hybrid_client = HybridSearchClient(
                vector_client=self.vector_client,
                keyword_weight=self.keyword_weight,
                semantic_weight=self.semantic_weight
            )
        else:
            self.hybrid_client = None
    
    def retrieve(self, request: RetrievalRequest) -> List[RetrievalResult]:
        """Execute retrieval based on request"""
        # Determine search method
        if request.use_hybrid and self.hybrid_client:
            raw_results = self.hybrid_client.search(
                query=request.query,
                top_k=request.top_k,
                filters=request.filters
            )
        else:
            raw_results = self.vector_client.search_with_score(
                query=request.query,
                top_k=request.top_k,
                filters=request.filters
            )
        
        # Convert to RetrievalResult objects
        results = []
        for data, score in raw_results:
            if score >= request.similarity_threshold:
                # Parse metadata if it's a string
                metadata = data.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                
                result = RetrievalResult(
                    chunk_id=data.get("chunk_id", ""),
                    content=data.get("content", ""),
                    score=score,
                    document_id=data.get("document_id", ""),
                    metadata=metadata if request.include_metadata else {},
                    chunk_index=data.get("chunk_index", 0)
                )
                results.append(result)
        
        # Apply reranking if configured
        if self.use_reranking and self.rerank_model and len(results) > 0:
            results = self._rerank_results(request.query, results)
        
        return results
    
    def _rerank_results(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Rerank results using a reranking model"""
        try:
            from databricks.sdk import WorkspaceClient
            import requests
            
            client = WorkspaceClient()
            workspace_url = client.config.host
            token = client.config.token
            
            url = f"{workspace_url}/serving-endpoints/{self.rerank_model}/invocations"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Prepare reranking request
            documents = [r.content for r in results]
            payload = {
                "query": query,
                "documents": documents
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            rerank_scores = response.json().get("scores", [])
            
            # Update scores and re-sort
            for i, score in enumerate(rerank_scores):
                if i < len(results):
                    results[i].score = score
            
            results.sort(key=lambda x: x.score, reverse=True)
            
        except Exception as e:
            print(f"Reranking failed, using original scores: {e}")
        
        return results
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[RetrievalResult]:
        """Simplified search interface"""
        request = RetrievalRequest(
            query=query,
            top_k=top_k or self.top_k,
            filters=filters,
            similarity_threshold=similarity_threshold or self.similarity_threshold,
            use_hybrid=self.use_hybrid
        )
        
        return self.retrieve(request)
    
    def get_context_for_generation(
        self,
        query: str,
        max_tokens: int = 4096,
        top_k: Optional[int] = None
    ) -> Tuple[str, List[RetrievalResult]]:
        """
        Retrieve and format context for RAG generation.
        Returns formatted context string and source results.
        """
        results = self.search(query, top_k=top_k or self.top_k)
        
        # Build context string, respecting token limit
        context_parts = []
        estimated_tokens = 0
        included_results = []
        
        for result in results:
            # Rough token estimation (4 chars ≈ 1 token)
            content_tokens = len(result.content) // 4
            
            if estimated_tokens + content_tokens > max_tokens:
                break
            
            context_parts.append(f"[Source: {result.document_id}]\n{result.content}")
            estimated_tokens += content_tokens
            included_results.append(result)
        
        context = "\n\n---\n\n".join(context_parts)
        
        return context, included_results
    
    def run_batch_retrieval(
        self,
        queries: List[str],
        top_k: Optional[int] = None
    ) -> Dict[str, List[RetrievalResult]]:
        """Run retrieval for multiple queries"""
        results = {}
        
        for query in queries:
            results[query] = self.search(query, top_k=top_k)
        
        return results


def main():
    """Entry point for testing retrieval pipeline"""
    import sys
    
    # Parse parameters
    params = {}
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key] = value
    
    config = {
        "catalog": params.get("catalog", "main"),
        "schema": params.get("schema", "default"),
        "top_k": int(params.get("top_k", "10")),
        "use_hybrid_search": params.get("use_hybrid", "true").lower() == "true",
    }
    
    pipeline = VectorRetrievalPipeline(config)
    
    # Test query
    query = params.get("query", "What was discussed in the meeting?")
    results = pipeline.search(query)
    
    print(f"Query: {query}")
    print(f"Results: {len(results)}")
    for i, result in enumerate(results):
        print(f"\n{i+1}. Score: {result.score:.4f}")
        print(f"   Content: {result.content[:200]}...")


if __name__ == "__main__":
    main()


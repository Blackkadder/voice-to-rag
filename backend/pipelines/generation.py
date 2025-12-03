"""
RAG Generation Pipeline

Handles response generation using retrieved context.
Integrates with Databricks Foundation Models and Model Serving.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
import json
from datetime import datetime

from .retrieval import VectorRetrievalPipeline, RetrievalResult, RetrievalRequest


@dataclass
class GenerationRequest:
    """Request for RAG generation"""
    query: str
    system_prompt: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7
    top_k_retrieval: int = 10
    include_sources: bool = True
    filters: Optional[Dict[str, Any]] = None


@dataclass
class GenerationResponse:
    """Response from RAG generation"""
    query: str
    response: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    context_used: str = ""
    model: str = ""
    tokens_used: int = 0
    retrieval_time_ms: float = 0
    generation_time_ms: float = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "response": self.response,
            "sources": self.sources,
            "context_used": self.context_used,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "retrieval_time_ms": self.retrieval_time_ms,
            "generation_time_ms": self.generation_time_ms,
            "created_at": self.created_at
        }


class LLMClient:
    """Client for LLM generation via Databricks"""
    
    def __init__(
        self,
        model_name: str = "databricks-llama-3-70b-instruct",
        endpoint_name: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 60
    ):
        self.model_name = model_name
        self.endpoint_name = endpoint_name or model_name
        self.max_retries = max_retries
        self.timeout = timeout
        self._client = None
    
    def _get_client(self):
        """Get the Databricks client"""
        if self._client is None:
            from databricks.sdk import WorkspaceClient
            self._client = WorkspaceClient()
        return self._client
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate text using the LLM"""
        import time
        
        client = self._get_client()
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        start_time = time.time()
        
        # Try Foundation Model API
        try:
            response = self._call_foundation_model(
                client, messages, max_tokens, temperature, stop_sequences
            )
        except Exception:
            # Fall back to serving endpoint
            response = self._call_serving_endpoint(
                client, messages, max_tokens, temperature, stop_sequences
            )
        
        generation_time = (time.time() - start_time) * 1000
        response["generation_time_ms"] = generation_time
        
        return response
    
    def _call_foundation_model(
        self,
        client,
        messages: List[Dict],
        max_tokens: int,
        temperature: float,
        stop_sequences: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Call Databricks Foundation Model API"""
        response = client.serving_endpoints.query(
            name=self.endpoint_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop_sequences
        )
        
        # Extract response
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
            tokens = getattr(response, 'usage', {})
            return {
                "content": content,
                "tokens_used": getattr(tokens, 'total_tokens', 0),
                "model": self.model_name
            }
        
        raise ValueError("Unexpected response format")
    
    def _call_serving_endpoint(
        self,
        client,
        messages: List[Dict],
        max_tokens: int,
        temperature: float,
        stop_sequences: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Call model serving endpoint directly"""
        import requests
        
        workspace_url = client.config.host
        token = client.config.token
        
        url = f"{workspace_url}/serving-endpoints/{self.endpoint_name}/invocations"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        if stop_sequences:
            payload["stop"] = stop_sequences
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Handle different response formats
        if "choices" in result and result["choices"]:
            content = result["choices"][0].get("message", {}).get("content", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
        elif "predictions" in result:
            content = result["predictions"][0] if result["predictions"] else ""
            tokens = 0
        else:
            content = result.get("output", result.get("response", ""))
            tokens = 0
        
        return {
            "content": content,
            "tokens_used": tokens,
            "model": self.model_name
        }
    
    def generate_with_context(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate response with retrieved context"""
        # Build the RAG prompt
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
        
        user_prompt = self._build_rag_prompt(query, context)
        
        return self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
    
    def _get_default_system_prompt(self) -> str:
        """Get the default RAG system prompt"""
        return """You are a helpful AI assistant that answers questions based on the provided context.

Instructions:
- Answer the question using ONLY the information provided in the context
- If the context doesn't contain enough information to answer, say so clearly
- Be concise and accurate
- When appropriate, cite the source documents
- Do not make up information that is not in the context"""
    
    def _build_rag_prompt(self, query: str, context: str) -> str:
        """Build the RAG prompt with context"""
        return f"""Context:
{context}

Question: {query}

Please answer the question based on the context provided above."""


class RAGGenerationPipeline:
    """
    Main pipeline for RAG generation.
    Combines retrieval and generation for end-to-end RAG.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the RAG generation pipeline"""
        self.config = config or {}
        
        # Unity Catalog configuration
        self.catalog = self.config.get("catalog", "main")
        self.schema = self.config.get("schema", "default")
        
        # Generation configuration
        self.generation_model = self.config.get(
            "generation_model",
            "databricks-llama-3-70b-instruct"
        )
        self.generation_endpoint = self.config.get(
            "generation_endpoint",
            self.generation_model
        )
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 1024)
        self.max_context_tokens = self.config.get("max_context_tokens", 4096)
        
        # Retrieval configuration
        self.top_k = self.config.get("top_k", 10)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.7)
        
        # System prompt
        self.system_prompt = self.config.get("system_prompt")
        
        # Initialize clients
        self.retrieval_pipeline = VectorRetrievalPipeline(self.config)
        self.llm_client = LLMClient(
            model_name=self.generation_model,
            endpoint_name=self.generation_endpoint
        )
    
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute full RAG pipeline: retrieve and generate"""
        import time
        
        # Step 1: Retrieve relevant context
        retrieval_start = time.time()
        
        context, retrieved_results = self.retrieval_pipeline.get_context_for_generation(
            query=request.query,
            max_tokens=self.max_context_tokens,
            top_k=request.top_k_retrieval
        )
        
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # Step 2: Generate response
        generation_start = time.time()
        
        generation_result = self.llm_client.generate_with_context(
            query=request.query,
            context=context,
            system_prompt=request.system_prompt or self.system_prompt,
            max_tokens=request.max_tokens,
            temperature=self.temperature
        )
        
        generation_time = generation_result.get("generation_time_ms", 0)
        if generation_time == 0:
            generation_time = (time.time() - generation_start) * 1000
        
        # Build sources list
        sources = []
        if request.include_sources:
            for result in retrieved_results:
                sources.append({
                    "chunk_id": result.chunk_id,
                    "document_id": result.document_id,
                    "score": result.score,
                    "content_preview": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                    "metadata": result.metadata
                })
        
        return GenerationResponse(
            query=request.query,
            response=generation_result.get("content", ""),
            sources=sources,
            context_used=context,
            model=generation_result.get("model", self.generation_model),
            tokens_used=generation_result.get("tokens_used", 0),
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time
        )
    
    def answer(
        self,
        query: str,
        top_k: Optional[int] = None,
        include_sources: bool = True
    ) -> GenerationResponse:
        """Simplified interface for RAG Q&A"""
        request = GenerationRequest(
            query=query,
            top_k_retrieval=top_k or self.top_k,
            include_sources=include_sources,
            max_tokens=self.max_tokens
        )
        
        return self.generate(request)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        top_k: Optional[int] = None
    ) -> GenerationResponse:
        """
        Multi-turn chat with RAG context.
        Retrieves context based on the last user message.
        """
        # Get the last user message for retrieval
        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if not last_user_message:
            raise ValueError("No user message found in chat history")
        
        # Retrieve context
        context, retrieved_results = self.retrieval_pipeline.get_context_for_generation(
            query=last_user_message,
            max_tokens=self.max_context_tokens,
            top_k=top_k or self.top_k
        )
        
        # Build chat prompt with context
        system_prompt = self.system_prompt or self.llm_client._get_default_system_prompt()
        system_prompt += f"\n\nRelevant Context:\n{context}"
        
        # Format conversation
        conversation = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                conversation += f"\nUser: {content}"
            elif role == "assistant":
                conversation += f"\nAssistant: {content}"
        
        conversation += "\nAssistant:"
        
        # Generate
        result = self.llm_client.generate(
            prompt=conversation,
            system_prompt=system_prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        
        sources = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "score": r.score
            }
            for r in retrieved_results
        ]
        
        return GenerationResponse(
            query=last_user_message,
            response=result.get("content", ""),
            sources=sources,
            context_used=context,
            model=result.get("model", self.generation_model),
            tokens_used=result.get("tokens_used", 0),
            generation_time_ms=result.get("generation_time_ms", 0)
        )
    
    def run_spark_batch(self, spark, queries_table: str, output_table: str) -> Dict[str, Any]:
        """
        Run batch RAG generation as a Spark job.
        
        Args:
            spark: SparkSession instance
            queries_table: Table containing queries to process
            output_table: Table to write responses to
            
        Returns:
            Dict with processing statistics
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType
        
        # Read queries
        queries_df = spark.table(queries_table)
        
        # Process each query (collect for small batches, use UDF for large)
        queries = queries_df.select("query_id", "query_text").collect()
        
        results = []
        for row in queries:
            query_id = row.query_id
            query_text = row.query_text
            
            try:
                response = self.answer(query_text)
                results.append({
                    "query_id": query_id,
                    "query_text": query_text,
                    "response": response.response,
                    "sources": json.dumps(response.sources),
                    "model": response.model,
                    "tokens_used": response.tokens_used,
                    "retrieval_time_ms": response.retrieval_time_ms,
                    "generation_time_ms": response.generation_time_ms,
                    "created_at": response.created_at,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "query_id": query_id,
                    "query_text": query_text,
                    "response": "",
                    "sources": "[]",
                    "model": self.generation_model,
                    "tokens_used": 0,
                    "retrieval_time_ms": 0,
                    "generation_time_ms": 0,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": f"error: {str(e)}"
                })
        
        # Create results DataFrame
        results_df = spark.createDataFrame(results)
        
        # Write to output table
        results_df.write.format("delta").mode("append").saveAsTable(output_table)
        
        return {
            "status": "success",
            "queries_processed": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] != "success"),
            "output_table": output_table
        }


def main():
    """Entry point for testing RAG generation"""
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
        "generation_model": params.get("generation_model", "databricks-llama-3-70b-instruct"),
        "top_k": int(params.get("top_k", "10")),
        "temperature": float(params.get("temperature", "0.7")),
    }
    
    pipeline = RAGGenerationPipeline(config)
    
    # Test query
    query = params.get("query", "What was discussed in the meeting?")
    response = pipeline.answer(query)
    
    print(f"Query: {query}")
    print(f"\nResponse: {response.response}")
    print(f"\nSources: {len(response.sources)}")
    print(f"Retrieval time: {response.retrieval_time_ms:.2f}ms")
    print(f"Generation time: {response.generation_time_ms:.2f}ms")


if __name__ == "__main__":
    main()


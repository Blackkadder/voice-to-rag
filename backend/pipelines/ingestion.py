"""
Document Ingestion Pipeline

Handles document loading, chunking, and preparation for embedding.
Designed to run as a Databricks workflow task.
"""

from typing import Dict, List, Optional, Iterator, Any
from dataclasses import dataclass, field
import hashlib
import json
from datetime import datetime


@dataclass
class DocumentChunk:
    """Represents a chunk of text from a document"""
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Document:
    """Represents a source document"""
    document_id: str
    source_path: str
    content: str
    doc_type: str  # 'transcription', 'text', 'pdf', etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TextChunker:
    """Handles text chunking with various strategies"""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        strategy: str = "recursive"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        
        # Sentence-ending patterns for intelligent chunking
        self.sentence_endings = ['. ', '! ', '? ', '\n\n', '\n']
        self.word_separators = [' ', '\n', '\t']
    
    def chunk_text(self, text: str, document_id: str) -> List[DocumentChunk]:
        """Split text into chunks using the configured strategy"""
        if self.strategy == "recursive":
            return self._recursive_chunk(text, document_id)
        elif self.strategy == "sentence":
            return self._sentence_chunk(text, document_id)
        elif self.strategy == "fixed":
            return self._fixed_chunk(text, document_id)
        else:
            return self._recursive_chunk(text, document_id)
    
    def _generate_chunk_id(self, document_id: str, chunk_index: int, content: str) -> str:
        """Generate a deterministic chunk ID"""
        hash_input = f"{document_id}:{chunk_index}:{content[:100]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _recursive_chunk(self, text: str, document_id: str) -> List[DocumentChunk]:
        """Recursively split text, preserving semantic boundaries"""
        chunks = []
        separators = self.sentence_endings + self.word_separators
        
        def split_recursive(text: str, sep_index: int = 0) -> List[str]:
            if len(text) <= self.chunk_size:
                return [text] if text.strip() else []
            
            if sep_index >= len(separators):
                # Fall back to character-level split
                return self._hard_split(text)
            
            separator = separators[sep_index]
            parts = text.split(separator)
            
            result = []
            current = ""
            
            for part in parts:
                candidate = current + (separator if current else "") + part
                
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        result.append(current)
                    if len(part) > self.chunk_size:
                        result.extend(split_recursive(part, sep_index + 1))
                    else:
                        current = part
            
            if current:
                result.append(current)
            
            return result
        
        raw_chunks = split_recursive(text)
        
        # Apply overlap
        char_position = 0
        for i, chunk_content in enumerate(raw_chunks):
            chunk_content = chunk_content.strip()
            if not chunk_content:
                continue
            
            # Find actual position in original text
            start_char = text.find(chunk_content, max(0, char_position - self.chunk_overlap))
            if start_char == -1:
                start_char = char_position
            end_char = start_char + len(chunk_content)
            
            chunk = DocumentChunk(
                chunk_id=self._generate_chunk_id(document_id, len(chunks), chunk_content),
                document_id=document_id,
                content=chunk_content,
                chunk_index=len(chunks),
                start_char=start_char,
                end_char=end_char,
            )
            chunks.append(chunk)
            char_position = end_char
        
        return chunks
    
    def _sentence_chunk(self, text: str, document_id: str) -> List[DocumentChunk]:
        """Split text by sentences, grouping to reach target size"""
        import re
        
        # Split by sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        char_position = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk = (current_chunk + " " + sentence).strip()
            else:
                if current_chunk:
                    start_char = text.find(current_chunk, max(0, char_position - self.chunk_overlap))
                    if start_char == -1:
                        start_char = char_position
                    
                    chunk = DocumentChunk(
                        chunk_id=self._generate_chunk_id(document_id, len(chunks), current_chunk),
                        document_id=document_id,
                        content=current_chunk,
                        chunk_index=len(chunks),
                        start_char=start_char,
                        end_char=start_char + len(current_chunk),
                    )
                    chunks.append(chunk)
                    char_position = start_char + len(current_chunk)
                
                current_chunk = sentence
        
        # Don't forget the last chunk
        if current_chunk:
            start_char = text.find(current_chunk, max(0, char_position - self.chunk_overlap))
            if start_char == -1:
                start_char = char_position
            
            chunk = DocumentChunk(
                chunk_id=self._generate_chunk_id(document_id, len(chunks), current_chunk),
                document_id=document_id,
                content=current_chunk,
                chunk_index=len(chunks),
                start_char=start_char,
                end_char=start_char + len(current_chunk),
            )
            chunks.append(chunk)
        
        return chunks
    
    def _fixed_chunk(self, text: str, document_id: str) -> List[DocumentChunk]:
        """Split text into fixed-size chunks with overlap"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_content = text[start:end].strip()
            
            if chunk_content:
                chunk = DocumentChunk(
                    chunk_id=self._generate_chunk_id(document_id, len(chunks), chunk_content),
                    document_id=document_id,
                    content=chunk_content,
                    chunk_index=len(chunks),
                    start_char=start,
                    end_char=end,
                )
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break
        
        return chunks
    
    def _hard_split(self, text: str) -> List[str]:
        """Hard split when no separators work"""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks


class DocumentIngestionPipeline:
    """
    Main pipeline for document ingestion.
    Orchestrates loading, chunking, and storing documents.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the ingestion pipeline"""
        self.config = config or {}
        
        # Chunking configuration
        chunk_size = self.config.get("chunk_size", 512)
        chunk_overlap = self.config.get("chunk_overlap", 50)
        chunking_strategy = self.config.get("chunking_strategy", "recursive")
        
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=chunking_strategy
        )
        
        # Unity Catalog configuration
        self.catalog = self.config.get("catalog", "main")
        self.schema = self.config.get("schema", "default")
        self.chunks_table = self.config.get("chunks_table", f"{self.catalog}.{self.schema}.document_chunks")
        self.documents_table = self.config.get("documents_table", f"{self.catalog}.{self.schema}.documents")
    
    def ingest_document(self, document: Document) -> List[DocumentChunk]:
        """Process a single document into chunks"""
        chunks = self.chunker.chunk_text(document.content, document.document_id)
        
        # Add document metadata to each chunk
        for chunk in chunks:
            chunk.metadata.update({
                "source_path": document.source_path,
                "doc_type": document.doc_type,
                **document.metadata
            })
        
        return chunks
    
    def ingest_transcription(
        self,
        transcription_text: str,
        audio_file_path: str,
        metadata: Optional[Dict] = None
    ) -> List[DocumentChunk]:
        """Ingest a transcription from audio processing"""
        doc_id = hashlib.sha256(audio_file_path.encode()).hexdigest()[:16]
        
        document = Document(
            document_id=doc_id,
            source_path=audio_file_path,
            content=transcription_text,
            doc_type="transcription",
            metadata=metadata or {}
        )
        
        return self.ingest_document(document)
    
    def run_spark(self, spark) -> Dict[str, Any]:
        """
        Run ingestion pipeline as a Spark job.
        Reads from source tables and writes chunked documents.
        
        Args:
            spark: SparkSession instance
            
        Returns:
            Dict with processing statistics
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, 
            MapType, ArrayType
        )
        
        # Read transcriptions that haven't been chunked yet
        transcriptions_table = self.config.get(
            "transcriptions_table", 
            f"{self.catalog}.{self.schema}.transcriptions"
        )
        
        # Check for new transcriptions
        try:
            transcriptions_df = spark.table(transcriptions_table)
        except Exception:
            return {"status": "no_data", "documents_processed": 0, "chunks_created": 0}
        
        # Check if chunks table exists and get processed document IDs
        try:
            existing_chunks = spark.table(self.chunks_table)
            processed_ids = existing_chunks.select("document_id").distinct()
            
            # Filter to only unprocessed transcriptions
            new_transcriptions = transcriptions_df.join(
                processed_ids,
                transcriptions_df["transcription_id"] == processed_ids["document_id"],
                "left_anti"
            )
        except Exception:
            new_transcriptions = transcriptions_df
        
        if new_transcriptions.count() == 0:
            return {"status": "no_new_data", "documents_processed": 0, "chunks_created": 0}
        
        # Define UDF for chunking
        chunker = self.chunker
        
        def chunk_document(doc_id: str, content: str, source_path: str, doc_type: str, metadata_json: str):
            """UDF to chunk a document"""
            chunks = chunker.chunk_text(content, doc_id)
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            result = []
            for chunk in chunks:
                chunk.metadata.update({
                    "source_path": source_path,
                    "doc_type": doc_type,
                    **metadata
                })
                result.append({
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": json.dumps(chunk.metadata),
                    "created_at": chunk.created_at
                })
            return result
        
        # Register UDF
        chunk_schema = ArrayType(StructType([
            StructField("chunk_id", StringType(), False),
            StructField("document_id", StringType(), False),
            StructField("content", StringType(), False),
            StructField("chunk_index", IntegerType(), False),
            StructField("start_char", IntegerType(), False),
            StructField("end_char", IntegerType(), False),
            StructField("metadata", StringType(), True),
            StructField("created_at", StringType(), False),
        ]))
        
        chunk_udf = F.udf(chunk_document, chunk_schema)
        
        # Process transcriptions
        chunks_df = new_transcriptions.withColumn(
            "chunks",
            chunk_udf(
                F.col("transcription_id"),
                F.col("text"),
                F.col("audio_file_path"),
                F.lit("transcription"),
                F.to_json(F.col("metadata")) if "metadata" in new_transcriptions.columns else F.lit("{}")
            )
        ).select(F.explode("chunks").alias("chunk"))
        
        # Flatten the struct
        final_chunks_df = chunks_df.select(
            F.col("chunk.chunk_id").alias("chunk_id"),
            F.col("chunk.document_id").alias("document_id"),
            F.col("chunk.content").alias("content"),
            F.col("chunk.chunk_index").alias("chunk_index"),
            F.col("chunk.start_char").alias("start_char"),
            F.col("chunk.end_char").alias("end_char"),
            F.col("chunk.metadata").alias("metadata"),
            F.col("chunk.created_at").alias("created_at"),
            F.lit(None).cast("array<float>").alias("embedding")  # Placeholder for embeddings
        )
        
        # Write to Delta table
        docs_processed = new_transcriptions.count()
        chunks_created = final_chunks_df.count()
        
        final_chunks_df.write.format("delta").mode("append").saveAsTable(self.chunks_table)
        
        return {
            "status": "success",
            "documents_processed": docs_processed,
            "chunks_created": chunks_created,
            "chunks_table": self.chunks_table
        }
    
    def run_batch(self, documents: List[Document]) -> List[DocumentChunk]:
        """Process a batch of documents (non-Spark mode)"""
        all_chunks = []
        for doc in documents:
            chunks = self.ingest_document(doc)
            all_chunks.extend(chunks)
        return all_chunks


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
    spark = SparkSession.builder.appName("DocumentIngestionPipeline").getOrCreate()
    
    # Initialize pipeline with parameters
    config = {
        "catalog": params.get("catalog", "main"),
        "schema": params.get("schema", "default"),
        "chunk_size": int(params.get("chunk_size", "512")),
        "chunk_overlap": int(params.get("chunk_overlap", "50")),
        "chunking_strategy": params.get("chunking_strategy", "recursive"),
    }
    
    pipeline = DocumentIngestionPipeline(config)
    result = pipeline.run_spark(spark)
    
    print(f"Ingestion complete: {result}")
    
    # Set task values for downstream tasks
    dbutils = spark.sparkContext._jvm.com.databricks.dbutils_v1.DBUtilsHolder.dbutils()
    dbutils.jobs().taskValues().set("ingestion_result", json.dumps(result))


if __name__ == "__main__":
    main()


"""
Data Validation Utilities

Validators for RAG pipeline data quality.
"""

from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ValidationLevel(str, Enum):
    """Validation severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A validation issue found in data"""
    level: ValidationLevel
    field: str
    message: str
    value: Optional[Any] = None
    row_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "field": self.field,
            "message": self.message,
            "value": str(self.value) if self.value is not None else None,
            "row_id": self.row_id
        }


@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    
    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue"""
        self.issues.append(issue)
        
        # Update summary
        key = f"{issue.level.value}_{issue.field}"
        self.summary[key] = self.summary.get(key, 0) + 1
        
        # Update validity
        if issue.level == ValidationLevel.ERROR:
            self.is_valid = False
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "issue_count": len(self.issues),
            "issues": [i.to_dict() for i in self.issues[:100]],  # Limit issues in output
            "summary": self.summary
        }
    
    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues"""
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]
    
    def get_warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues"""
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]


class DataValidator:
    """
    Validates data for RAG pipeline quality.
    
    Supports validation of:
    - Document chunks
    - Embeddings
    - Transcriptions
    - Query/response data
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Validation thresholds
        self.min_chunk_length = self.config.get("min_chunk_length", 10)
        self.max_chunk_length = self.config.get("max_chunk_length", 10000)
        self.embedding_dimension = self.config.get("embedding_dimension", 1024)
        self.min_embedding_norm = self.config.get("min_embedding_norm", 0.1)
        self.max_embedding_norm = self.config.get("max_embedding_norm", 100.0)
    
    def validate_chunk(self, chunk: Dict, row_id: Optional[str] = None) -> List[ValidationIssue]:
        """Validate a single document chunk"""
        issues = []
        row_id = row_id or chunk.get("chunk_id", "unknown")
        
        # Required fields
        required_fields = ["chunk_id", "document_id", "content"]
        for field in required_fields:
            if not chunk.get(field):
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field=field,
                    message=f"Missing required field: {field}",
                    row_id=row_id
                ))
        
        # Content validation
        content = chunk.get("content", "")
        if content:
            if len(content) < self.min_chunk_length:
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    field="content",
                    message=f"Content too short ({len(content)} chars)",
                    value=len(content),
                    row_id=row_id
                ))
            
            if len(content) > self.max_chunk_length:
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    field="content",
                    message=f"Content too long ({len(content)} chars)",
                    value=len(content),
                    row_id=row_id
                ))
            
            # Check for empty or whitespace-only content
            if not content.strip():
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field="content",
                    message="Content is empty or whitespace-only",
                    row_id=row_id
                ))
        
        # Chunk index validation
        chunk_index = chunk.get("chunk_index")
        if chunk_index is not None and chunk_index < 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="chunk_index",
                message="Chunk index cannot be negative",
                value=chunk_index,
                row_id=row_id
            ))
        
        return issues
    
    def validate_embedding(
        self,
        embedding: Union[List[float], None],
        row_id: Optional[str] = None
    ) -> List[ValidationIssue]:
        """Validate an embedding vector"""
        issues = []
        
        if embedding is None or len(embedding) == 0:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="embedding",
                message="Embedding is null or empty",
                row_id=row_id
            ))
            return issues
        
        # Dimension check
        if len(embedding) != self.embedding_dimension:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="embedding",
                message=f"Wrong embedding dimension: {len(embedding)}, expected {self.embedding_dimension}",
                value=len(embedding),
                row_id=row_id
            ))
        
        # Norm check (detect zero or abnormal vectors)
        import math
        norm = math.sqrt(sum(x * x for x in embedding))
        
        if norm < self.min_embedding_norm:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="embedding",
                message=f"Embedding norm too small: {norm:.4f}",
                value=norm,
                row_id=row_id
            ))
        
        if norm > self.max_embedding_norm:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="embedding",
                message=f"Embedding norm too large: {norm:.4f}",
                value=norm,
                row_id=row_id
            ))
        
        # NaN/Inf check
        if any(math.isnan(x) or math.isinf(x) for x in embedding):
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                field="embedding",
                message="Embedding contains NaN or Inf values",
                row_id=row_id
            ))
        
        return issues
    
    def validate_transcription(
        self,
        transcription: Dict,
        row_id: Optional[str] = None
    ) -> List[ValidationIssue]:
        """Validate a transcription record"""
        issues = []
        row_id = row_id or transcription.get("transcription_id", "unknown")
        
        # Required fields
        required_fields = ["transcription_id", "text"]
        for field in required_fields:
            if not transcription.get(field):
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field=field,
                    message=f"Missing required field: {field}",
                    row_id=row_id
                ))
        
        # Text validation
        text = transcription.get("text", "")
        if text and len(text) < 10:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                field="text",
                message="Transcription text is very short",
                value=len(text),
                row_id=row_id
            ))
        
        # Duration validation
        duration = transcription.get("duration_seconds")
        if duration is not None:
            if duration <= 0:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    field="duration_seconds",
                    message="Duration must be positive",
                    value=duration,
                    row_id=row_id
                ))
            elif duration > 36000:  # 10 hours
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    field="duration_seconds",
                    message="Duration unusually long",
                    value=duration,
                    row_id=row_id
                ))
        
        return issues
    
    def validate_chunks_dataframe(self, df, sample_size: int = 1000) -> ValidationResult:
        """Validate a DataFrame of document chunks"""
        result = ValidationResult(is_valid=True)
        
        total_count = df.count()
        result.total_records = total_count
        
        # Sample for validation
        if total_count > sample_size:
            sample_df = df.sample(fraction=sample_size / total_count, seed=42)
        else:
            sample_df = df
        
        # Collect sample for validation
        records = sample_df.collect()
        
        valid_count = 0
        for row in records:
            row_dict = row.asDict()
            chunk_issues = self.validate_chunk(row_dict)
            
            # Validate embedding if present
            embedding = row_dict.get("embedding")
            if embedding:
                embedding_issues = self.validate_embedding(
                    list(embedding) if embedding else None,
                    row_id=row_dict.get("chunk_id")
                )
                chunk_issues.extend(embedding_issues)
            
            for issue in chunk_issues:
                result.add_issue(issue)
            
            if not any(i.level == ValidationLevel.ERROR for i in chunk_issues):
                valid_count += 1
        
        # Extrapolate results
        sample_valid_ratio = valid_count / len(records) if records else 1.0
        result.valid_records = int(total_count * sample_valid_ratio)
        result.invalid_records = total_count - result.valid_records
        
        return result
    
    def validate_embeddings_dataframe(
        self,
        df,
        embedding_column: str = "embedding",
        sample_size: int = 1000
    ) -> ValidationResult:
        """Validate embeddings in a DataFrame"""
        from pyspark.sql import functions as F
        
        result = ValidationResult(is_valid=True)
        
        # Filter to rows with embeddings
        with_embeddings = df.filter(
            F.col(embedding_column).isNotNull() & 
            (F.size(F.col(embedding_column)) > 0)
        )
        
        total_count = df.count()
        embedded_count = with_embeddings.count()
        
        result.total_records = total_count
        
        # Check embedding coverage
        coverage = embedded_count / total_count if total_count > 0 else 0
        if coverage < 0.9:
            result.add_issue(ValidationIssue(
                level=ValidationLevel.WARNING,
                field=embedding_column,
                message=f"Only {coverage:.1%} of records have embeddings"
            ))
        
        # Sample and validate
        if embedded_count > sample_size:
            sample_df = with_embeddings.sample(fraction=sample_size / embedded_count, seed=42)
        else:
            sample_df = with_embeddings
        
        records = sample_df.select("chunk_id", embedding_column).collect()
        
        valid_count = 0
        for row in records:
            embedding = row[embedding_column]
            chunk_id = row["chunk_id"]
            
            issues = self.validate_embedding(
                list(embedding) if embedding else None,
                row_id=chunk_id
            )
            
            for issue in issues:
                result.add_issue(issue)
            
            if not any(i.level == ValidationLevel.ERROR for i in issues):
                valid_count += 1
        
        # Extrapolate
        sample_valid_ratio = valid_count / len(records) if records else 1.0
        result.valid_records = int(embedded_count * sample_valid_ratio)
        result.invalid_records = embedded_count - result.valid_records
        
        return result


def validate_rag_data(
    spark,
    chunks_table: str,
    embedding_column: str = "embedding",
    sample_size: int = 1000
) -> Dict[str, ValidationResult]:
    """
    Convenience function to validate RAG data quality.
    
    Returns validation results for chunks and embeddings.
    """
    validator = DataValidator()
    
    df = spark.table(chunks_table)
    
    results = {
        "chunks": validator.validate_chunks_dataframe(df, sample_size),
        "embeddings": validator.validate_embeddings_dataframe(df, embedding_column, sample_size)
    }
    
    return results


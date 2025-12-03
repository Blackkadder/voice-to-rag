"""
Delta Table Utilities

Helpers for managing Delta tables in Unity Catalog.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TableSchema:
    """Schema definition for a Delta table"""
    columns: List[Dict[str, str]]
    partition_columns: Optional[List[str]] = None
    
    def to_spark_schema(self):
        """Convert to PySpark StructType"""
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, 
            FloatType, BooleanType, ArrayType, MapType, TimestampType
        )
        
        type_mapping = {
            "string": StringType(),
            "int": IntegerType(),
            "integer": IntegerType(),
            "float": FloatType(),
            "double": FloatType(),
            "boolean": BooleanType(),
            "bool": BooleanType(),
            "timestamp": TimestampType(),
            "array<float>": ArrayType(FloatType()),
            "array<string>": ArrayType(StringType()),
            "map<string,string>": MapType(StringType(), StringType()),
        }
        
        fields = []
        for col in self.columns:
            col_type = type_mapping.get(col["type"].lower(), StringType())
            nullable = col.get("nullable", True)
            fields.append(StructField(col["name"], col_type, nullable))
        
        return StructType(fields)


# Predefined schemas for RAG tables
DOCUMENT_CHUNKS_SCHEMA = TableSchema(
    columns=[
        {"name": "chunk_id", "type": "string", "nullable": False},
        {"name": "document_id", "type": "string", "nullable": False},
        {"name": "content", "type": "string", "nullable": False},
        {"name": "chunk_index", "type": "integer", "nullable": False},
        {"name": "start_char", "type": "integer", "nullable": True},
        {"name": "end_char", "type": "integer", "nullable": True},
        {"name": "metadata", "type": "string", "nullable": True},
        {"name": "embedding", "type": "array<float>", "nullable": True},
        {"name": "created_at", "type": "timestamp", "nullable": False},
    ]
)

TRANSCRIPTIONS_SCHEMA = TableSchema(
    columns=[
        {"name": "transcription_id", "type": "string", "nullable": False},
        {"name": "audio_file_path", "type": "string", "nullable": False},
        {"name": "text", "type": "string", "nullable": False},
        {"name": "duration_seconds", "type": "float", "nullable": True},
        {"name": "language", "type": "string", "nullable": True},
        {"name": "model", "type": "string", "nullable": True},
        {"name": "metadata", "type": "string", "nullable": True},
        {"name": "created_at", "type": "timestamp", "nullable": False},
    ]
)

RAG_RESPONSES_SCHEMA = TableSchema(
    columns=[
        {"name": "response_id", "type": "string", "nullable": False},
        {"name": "query_id", "type": "string", "nullable": True},
        {"name": "query_text", "type": "string", "nullable": False},
        {"name": "response", "type": "string", "nullable": False},
        {"name": "sources", "type": "string", "nullable": True},
        {"name": "model", "type": "string", "nullable": True},
        {"name": "tokens_used", "type": "integer", "nullable": True},
        {"name": "retrieval_time_ms", "type": "float", "nullable": True},
        {"name": "generation_time_ms", "type": "float", "nullable": True},
        {"name": "created_at", "type": "timestamp", "nullable": False},
    ]
)


class DeltaTableManager:
    """
    Manages Delta tables for the RAG pipeline.
    
    Handles:
    - Table creation with proper schemas
    - Table optimization (OPTIMIZE, VACUUM)
    - Schema evolution
    - Data validation
    """
    
    def __init__(
        self,
        catalog: str = "main",
        schema: str = "default",
        spark=None
    ):
        self.catalog = catalog
        self.schema = schema
        self._spark = spark
    
    def _get_spark(self):
        """Get or create SparkSession"""
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.builder.getOrCreate()
        return self._spark
    
    def get_full_table_name(self, table_name: str) -> str:
        """Get fully qualified table name"""
        if "." in table_name:
            return table_name
        return f"{self.catalog}.{self.schema}.{table_name}"
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        try:
            spark.table(full_name)
            return True
        except Exception:
            return False
    
    def create_table(
        self,
        table_name: str,
        table_schema: TableSchema,
        comment: Optional[str] = None,
        properties: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a Delta table if it doesn't exist"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        if self.table_exists(table_name):
            return {"status": "exists", "table": full_name}
        
        # Build CREATE TABLE SQL
        columns_sql = []
        for col in table_schema.columns:
            nullable = "NOT NULL" if not col.get("nullable", True) else ""
            columns_sql.append(f"`{col['name']}` {col['type'].upper()} {nullable}".strip())
        
        columns_str = ",\n  ".join(columns_sql)
        
        sql = f"CREATE TABLE IF NOT EXISTS {full_name} (\n  {columns_str}\n)"
        sql += " USING DELTA"
        
        if table_schema.partition_columns:
            partitions = ", ".join(table_schema.partition_columns)
            sql += f" PARTITIONED BY ({partitions})"
        
        if comment:
            sql += f" COMMENT '{comment}'"
        
        if properties:
            props = ", ".join([f"'{k}'='{v}'" for k, v in properties.items()])
            sql += f" TBLPROPERTIES ({props})"
        
        spark.sql(sql)
        
        return {"status": "created", "table": full_name}
    
    def create_chunks_table(self, table_name: str = "document_chunks") -> Dict[str, Any]:
        """Create the document chunks table"""
        return self.create_table(
            table_name=table_name,
            table_schema=DOCUMENT_CHUNKS_SCHEMA,
            comment="Document chunks with embeddings for RAG",
            properties={
                "delta.enableChangeDataFeed": "true",
                "delta.autoOptimize.optimizeWrite": "true"
            }
        )
    
    def create_transcriptions_table(self, table_name: str = "transcriptions") -> Dict[str, Any]:
        """Create the transcriptions table"""
        return self.create_table(
            table_name=table_name,
            table_schema=TRANSCRIPTIONS_SCHEMA,
            comment="Audio transcriptions for RAG processing"
        )
    
    def create_responses_table(self, table_name: str = "rag_responses") -> Dict[str, Any]:
        """Create the RAG responses table"""
        return self.create_table(
            table_name=table_name,
            table_schema=RAG_RESPONSES_SCHEMA,
            comment="RAG query responses and metrics"
        )
    
    def setup_all_tables(self) -> Dict[str, Any]:
        """Create all required tables"""
        results = {}
        
        results["transcriptions"] = self.create_transcriptions_table()
        results["document_chunks"] = self.create_chunks_table()
        results["rag_responses"] = self.create_responses_table()
        
        return results
    
    def optimize_table(
        self,
        table_name: str,
        zorder_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run OPTIMIZE on a Delta table"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        sql = f"OPTIMIZE {full_name}"
        
        if zorder_columns:
            columns = ", ".join(zorder_columns)
            sql += f" ZORDER BY ({columns})"
        
        result = spark.sql(sql)
        
        return {
            "status": "optimized",
            "table": full_name,
            "zorder_columns": zorder_columns
        }
    
    def vacuum_table(
        self,
        table_name: str,
        retention_hours: int = 168  # 7 days default
    ) -> Dict[str, Any]:
        """Run VACUUM on a Delta table"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        # Enable retention check override if needed
        spark.sql("SET spark.databricks.delta.retentionDurationCheck.enabled = false")
        
        spark.sql(f"VACUUM {full_name} RETAIN {retention_hours} HOURS")
        
        return {
            "status": "vacuumed",
            "table": full_name,
            "retention_hours": retention_hours
        }
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get statistics about a Delta table"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        if not self.table_exists(table_name):
            return {"status": "not_found", "table": full_name}
        
        # Get row count
        count = spark.table(full_name).count()
        
        # Get table details
        details = spark.sql(f"DESCRIBE DETAIL {full_name}").collect()[0]
        
        # Get history
        history = spark.sql(f"DESCRIBE HISTORY {full_name} LIMIT 5").collect()
        
        return {
            "table": full_name,
            "row_count": count,
            "size_bytes": details.sizeInBytes if hasattr(details, 'sizeInBytes') else None,
            "num_files": details.numFiles if hasattr(details, 'numFiles') else None,
            "created_at": str(details.createdAt) if hasattr(details, 'createdAt') else None,
            "last_modified": str(details.lastModified) if hasattr(details, 'lastModified') else None,
            "recent_operations": [
                {
                    "version": h.version,
                    "operation": h.operation,
                    "timestamp": str(h.timestamp)
                }
                for h in history
            ]
        }
    
    def merge_data(
        self,
        table_name: str,
        source_df,
        merge_key: str,
        update_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Merge data into a Delta table (upsert)"""
        from delta.tables import DeltaTable
        
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        delta_table = DeltaTable.forName(spark, full_name)
        
        # Build merge condition
        merge_condition = f"target.{merge_key} = source.{merge_key}"
        
        # Build update set
        if update_columns:
            update_set = {col: f"source.{col}" for col in update_columns}
        else:
            # Update all columns except merge key
            source_columns = source_df.columns
            update_set = {col: f"source.{col}" for col in source_columns if col != merge_key}
        
        # Perform merge
        merge_result = (
            delta_table.alias("target")
            .merge(source_df.alias("source"), merge_condition)
            .whenMatchedUpdate(set=update_set)
            .whenNotMatchedInsertAll()
            .execute()
        )
        
        return {"status": "merged", "table": full_name}
    
    def drop_table(self, table_name: str) -> Dict[str, Any]:
        """Drop a Delta table"""
        spark = self._get_spark()
        full_name = self.get_full_table_name(table_name)
        
        if not self.table_exists(table_name):
            return {"status": "not_found", "table": full_name}
        
        spark.sql(f"DROP TABLE {full_name}")
        
        return {"status": "dropped", "table": full_name}


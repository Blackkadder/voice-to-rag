"""
Logging Utilities for Databricks Tasks

Provides structured logging and metrics tracking for workflow tasks.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import time
from contextlib import contextmanager


@dataclass
class TaskMetrics:
    """Metrics collected during task execution"""
    task_name: str
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    records_processed: int = 0
    records_failed: int = 0
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    error_message: Optional[str] = None
    
    def complete(self, status: str = "success"):
        """Mark the task as complete"""
        self.end_time = datetime.utcnow()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = status
    
    def fail(self, error: str):
        """Mark the task as failed"""
        self.complete(status="failed")
        self.error_message = error
    
    def to_dict(self) -> Dict:
        return {
            "task_name": self.task_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "records_processed": self.records_processed,
            "records_failed": self.records_failed,
            "custom_metrics": self.custom_metrics,
            "status": self.status,
            "error_message": self.error_message
        }


class TaskLogger:
    """
    Structured logger for Databricks workflow tasks.
    
    Provides:
    - Structured JSON logging
    - Metrics collection
    - Integration with Databricks logging
    """
    
    def __init__(
        self,
        task_name: str,
        log_level: str = "INFO",
        log_to_table: bool = False,
        log_table: Optional[str] = None
    ):
        self.task_name = task_name
        self.log_level = log_level
        self.log_to_table = log_to_table
        self.log_table = log_table
        
        self.metrics = TaskMetrics(task_name=task_name)
        self._logs: List[Dict] = []
        
        # Initialize standard Python logger
        import logging
        self._logger = logging.getLogger(f"voice_rag.{task_name}")
        self._logger.setLevel(getattr(logging, log_level.upper()))
        
        # Add console handler if not present
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self._logger.addHandler(handler)
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task": self.task_name,
            "level": level,
            "message": message,
            **kwargs
        }
        
        self._logs.append(log_entry)
        
        # Log to Python logger
        log_method = getattr(self._logger, level.lower())
        if kwargs:
            log_method(f"{message} | {json.dumps(kwargs)}")
        else:
            log_method(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log("ERROR", message, **kwargs)
    
    def metric(self, name: str, value: Any):
        """Record a custom metric"""
        self.metrics.custom_metrics[name] = value
        self.debug(f"Metric: {name}={value}")
    
    def increment(self, counter: str, amount: int = 1):
        """Increment a counter metric"""
        current = self.metrics.custom_metrics.get(counter, 0)
        self.metrics.custom_metrics[counter] = current + amount
    
    def record_processed(self, count: int = 1):
        """Record processed records"""
        self.metrics.records_processed += count
    
    def record_failed(self, count: int = 1):
        """Record failed records"""
        self.metrics.records_failed += count
    
    @contextmanager
    def timed_operation(self, operation_name: str):
        """Context manager for timing an operation"""
        start = time.time()
        self.debug(f"Starting: {operation_name}")
        
        try:
            yield
            duration = time.time() - start
            self.info(f"Completed: {operation_name}", duration_seconds=duration)
            self.metric(f"{operation_name}_duration_seconds", duration)
        except Exception as e:
            duration = time.time() - start
            self.error(f"Failed: {operation_name}", duration_seconds=duration, error=str(e))
            raise
    
    def start(self):
        """Mark task start"""
        self.info(f"Task started: {self.task_name}")
    
    def complete(self, status: str = "success"):
        """Mark task complete and finalize metrics"""
        self.metrics.complete(status)
        self.info(
            f"Task completed: {self.task_name}",
            status=status,
            duration_seconds=self.metrics.duration_seconds,
            records_processed=self.metrics.records_processed,
            records_failed=self.metrics.records_failed
        )
        
        # Write to log table if configured
        if self.log_to_table and self.log_table:
            self._write_to_table()
    
    def fail(self, error: Union[str, Exception]):
        """Mark task as failed"""
        error_msg = str(error)
        self.metrics.fail(error_msg)
        self.error(
            f"Task failed: {self.task_name}",
            error=error_msg,
            duration_seconds=self.metrics.duration_seconds
        )
        
        if self.log_to_table and self.log_table:
            self._write_to_table()
    
    def _write_to_table(self):
        """Write logs and metrics to Delta table"""
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            
            # Create log record
            log_record = [{
                "task_name": self.task_name,
                "run_timestamp": self.metrics.start_time.isoformat(),
                "duration_seconds": self.metrics.duration_seconds,
                "status": self.metrics.status,
                "records_processed": self.metrics.records_processed,
                "records_failed": self.metrics.records_failed,
                "metrics": json.dumps(self.metrics.custom_metrics),
                "error_message": self.metrics.error_message,
                "logs": json.dumps(self._logs[-100:])  # Keep last 100 logs
            }]
            
            df = spark.createDataFrame(log_record)
            df.write.format("delta").mode("append").saveAsTable(self.log_table)
            
        except Exception as e:
            self._logger.error(f"Failed to write logs to table: {e}")
    
    def get_metrics(self) -> TaskMetrics:
        """Get collected metrics"""
        return self.metrics
    
    def get_logs(self) -> List[Dict]:
        """Get collected logs"""
        return self._logs


def log_task_metrics(
    task_name: str,
    metrics: Dict[str, Any],
    spark=None,
    table_name: Optional[str] = None
):
    """
    Quick utility to log task metrics.
    
    Can be used to log metrics without full TaskLogger.
    """
    log_entry = {
        "task_name": task_name,
        "timestamp": datetime.utcnow().isoformat(),
        **metrics
    }
    
    # Print to console
    print(f"[METRICS] {task_name}: {json.dumps(metrics)}")
    
    # Write to table if provided
    if spark and table_name:
        try:
            df = spark.createDataFrame([log_entry])
            df.write.format("delta").mode("append").saveAsTable(table_name)
        except Exception as e:
            print(f"Failed to write metrics to table: {e}")
    
    return log_entry


@contextmanager
def task_context(task_name: str, log_to_table: bool = False, log_table: Optional[str] = None):
    """
    Context manager for task execution with automatic logging.
    
    Usage:
        with task_context("my_task") as logger:
            logger.info("Processing...")
            # do work
            logger.record_processed(100)
    """
    logger = TaskLogger(
        task_name=task_name,
        log_to_table=log_to_table,
        log_table=log_table
    )
    
    logger.start()
    
    try:
        yield logger
        logger.complete()
    except Exception as e:
        logger.fail(e)
        raise


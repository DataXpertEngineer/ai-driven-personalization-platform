"""Structured logging and pipeline observability."""
import structlog
import time
from typing import Any
from contextlib import contextmanager

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if False else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


def log_pipeline_stage(stage: str, run_id: str, **kwargs: Any) -> None:
    """Log pipeline stage with lineage context."""
    logger.info("pipeline_stage", stage=stage, run_id=run_id, **kwargs)


def log_latency(operation: str, latency_ms: float, **kwargs: Any) -> None:
    """Log latency for observability."""
    logger.info("latency", operation=operation, latency_ms=round(latency_ms, 2), **kwargs)


def log_anomaly(anomaly_type: str, details: str, **kwargs: Any) -> None:
    """Log detected anomaly."""
    logger.warning("anomaly", anomaly_type=anomaly_type, details=details, **kwargs)


@contextmanager
def measure_latency(operation: str, **context: Any):
    """Context manager to measure and log latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        log_latency(operation, latency_ms, **context)

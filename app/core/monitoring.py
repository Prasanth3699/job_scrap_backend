"""
Comprehensive monitoring system for the job scraper microservice.
Provides metrics collection, request tracing, and performance monitoring.
"""

import time
import uuid
import asyncio
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import threading

from ..core.logger import logger


@dataclass
class RequestMetrics:
    """Metrics for individual requests"""

    request_id: str
    method: str
    path: str
    status_code: int
    response_time_ms: float
    timestamp: datetime
    user_id: Optional[int] = None
    service_name: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class SystemMetrics:
    """System-level metrics"""

    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_usage_mb: float
    disk_usage_percent: float
    active_connections: int
    total_requests: int
    error_rate_percent: float
    avg_response_time_ms: float


@dataclass
class EndpointStats:
    """Statistics for individual endpoints"""

    endpoint: str
    total_requests: int = 0
    total_errors: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    last_accessed: Optional[datetime] = None
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))


def endpoint_stats_factory(endpoint: str) -> EndpointStats:
    return EndpointStats(endpoint=endpoint)


class MetricsCollector:
    """Collects and stores application metrics"""

    def __init__(self, max_requests_history: int = 10000):
        self.max_requests_history = max_requests_history
        self.request_history: deque = deque(maxlen=max_requests_history)
        self.endpoint_stats: Dict[str, EndpointStats] = {}
        self.system_metrics_history: deque = deque(maxlen=1000)

        # Counters
        self.total_requests = 0
        self.total_errors = 0
        self.active_requests = 0

        # Performance tracking
        self.response_times: deque = deque(maxlen=1000)
        self.error_counts = defaultdict(int)

        # System info
        self.start_time = datetime.now()
        self.last_system_check = datetime.now()

        # Thread safety
        self._lock = threading.Lock()

        # Start background metrics collection
        self._start_background_collection()

    def record_request(self, metrics: RequestMetrics):
        """Record a request's metrics"""
        with self._lock:
            # Add to history
            self.request_history.append(metrics)

            # Update counters
            self.total_requests += 1
            if metrics.status_code >= 400:
                self.total_errors += 1
                self.error_counts[metrics.status_code] += 1

            # Update response times
            self.response_times.append(metrics.response_time_ms)

            # Update endpoint stats
            endpoint_key = f"{metrics.method} {metrics.path}"
            stats = self.endpoint_stats[endpoint_key]

            if not stats.endpoint:
                stats.endpoint = endpoint_key

            stats.total_requests += 1
            if metrics.status_code >= 400:
                stats.total_errors += 1

            stats.response_times.append(metrics.response_time_ms)
            stats.last_accessed = metrics.timestamp

            # Update response time stats
            if metrics.response_time_ms < stats.min_response_time:
                stats.min_response_time = metrics.response_time_ms
            if metrics.response_time_ms > stats.max_response_time:
                stats.max_response_time = metrics.response_time_ms

            # Calculate average response time
            if stats.response_times:
                stats.avg_response_time = sum(stats.response_times) / len(
                    stats.response_times
                )

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current application metrics"""
        with self._lock:
            now = datetime.now()
            uptime_seconds = (now - self.start_time).total_seconds()

            # Calculate error rate
            error_rate = (
                (self.total_errors / self.total_requests * 100)
                if self.total_requests > 0
                else 0
            )

            # Calculate average response time
            avg_response_time = (
                sum(self.response_times) / len(self.response_times)
                if self.response_times
                else 0
            )

            # Get recent requests (last 5 minutes)
            five_minutes_ago = now - timedelta(minutes=5)
            recent_requests = [
                r for r in self.request_history if r.timestamp >= five_minutes_ago
            ]
            recent_errors = [r for r in recent_requests if r.status_code >= 400]

            return {
                "timestamp": now.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "requests": {
                    "total": self.total_requests,
                    "total_errors": self.total_errors,
                    "active": self.active_requests,
                    "recent_5min": len(recent_requests),
                    "recent_errors_5min": len(recent_errors),
                    "error_rate_percent": round(error_rate, 2),
                    "requests_per_second": (
                        round(len(recent_requests) / 300, 2) if recent_requests else 0
                    ),
                },
                "performance": {
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "min_response_time_ms": (
                        min(self.response_times) if self.response_times else 0
                    ),
                    "max_response_time_ms": (
                        max(self.response_times) if self.response_times else 0
                    ),
                    "p95_response_time_ms": self._calculate_percentile(
                        self.response_times, 95
                    ),
                    "p99_response_time_ms": self._calculate_percentile(
                        self.response_times, 99
                    ),
                },
                "errors": dict(self.error_counts),
                "system": self._get_system_metrics(),
            }

    def get_endpoint_statistics(self) -> Dict[str, Any]:
        """Get statistics for all endpoints"""
        with self._lock:
            stats = {}

            for endpoint, endpoint_stats in self.endpoint_stats.items():
                error_rate = (
                    (endpoint_stats.total_errors / endpoint_stats.total_requests * 100)
                    if endpoint_stats.total_requests > 0
                    else 0
                )

                stats[endpoint] = {
                    "total_requests": endpoint_stats.total_requests,
                    "total_errors": endpoint_stats.total_errors,
                    "error_rate_percent": round(error_rate, 2),
                    "avg_response_time_ms": round(endpoint_stats.avg_response_time, 2),
                    "min_response_time_ms": (
                        endpoint_stats.min_response_time
                        if endpoint_stats.min_response_time != float("inf")
                        else 0
                    ),
                    "max_response_time_ms": endpoint_stats.max_response_time,
                    "last_accessed": (
                        endpoint_stats.last_accessed.isoformat()
                        if endpoint_stats.last_accessed
                        else None
                    ),
                    "p95_response_time_ms": self._calculate_percentile(
                        endpoint_stats.response_times, 95
                    ),
                    "p99_response_time_ms": self._calculate_percentile(
                        endpoint_stats.response_times, 99
                    ),
                }

            return stats

    def get_request_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent request history"""
        with self._lock:
            recent_requests = list(self.request_history)[-limit:]

            return [
                {
                    "request_id": req.request_id,
                    "method": req.method,
                    "path": req.path,
                    "status_code": req.status_code,
                    "response_time_ms": req.response_time_ms,
                    "timestamp": req.timestamp.isoformat(),
                    "user_id": req.user_id,
                    "service_name": req.service_name,
                    "error_message": req.error_message,
                }
                for req in recent_requests
            ]

    def increment_active_requests(self):
        """Increment active request counter"""
        with self._lock:
            self.active_requests += 1

    def decrement_active_requests(self):
        """Decrement active request counter"""
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)

    def _calculate_percentile(self, values: deque, percentile: int) -> float:
        """Calculate percentile from values"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return round(sorted_values[min(index, len(sorted_values) - 1)], 2)

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info()

            return {
                "cpu_usage_percent": round(cpu_percent, 2),
                "memory_usage_percent": round(memory.percent, 2),
                "memory_available_mb": round(memory.available / (1024 * 1024), 2),
                "disk_usage_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "process_memory_mb": round(process_memory.rss / (1024 * 1024), 2),
                "process_threads": process.num_threads(),
                "load_average": (
                    psutil.getloadavg() if hasattr(psutil, "getloadavg") else [0, 0, 0]
                ),
            }
        except Exception as e:
            logger.warning(f"Error getting system metrics: {str(e)}")
            return {"error": str(e)}

    def _start_background_collection(self):
        """Start background thread for periodic metrics collection"""

        def collect_system_metrics():
            while True:
                try:
                    system_metrics = SystemMetrics(
                        timestamp=datetime.now(),
                        cpu_usage_percent=psutil.cpu_percent(),
                        memory_usage_percent=psutil.virtual_memory().percent,
                        memory_usage_mb=psutil.virtual_memory().used / (1024 * 1024),
                        disk_usage_percent=psutil.disk_usage("/").percent,
                        active_connections=self.active_requests,
                        total_requests=self.total_requests,
                        error_rate_percent=(
                            (self.total_errors / self.total_requests * 100)
                            if self.total_requests > 0
                            else 0
                        ),
                        avg_response_time_ms=(
                            sum(self.response_times) / len(self.response_times)
                            if self.response_times
                            else 0
                        ),
                    )

                    with self._lock:
                        self.system_metrics_history.append(system_metrics)

                    time.sleep(30)  # Collect every 30 seconds

                except Exception as e:
                    logger.error(f"Error in background metrics collection: {str(e)}")
                    time.sleep(60)  # Wait longer on error

        # Start background thread
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
        logger.info("Background metrics collection started")


class RequestTracer:
    """Handles request tracing and correlation IDs"""

    def __init__(self):
        self.active_traces: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start_trace(
        self, request_id: str, method: str, path: str, headers: Dict[str, str] = None
    ) -> str:
        """Start a new trace for a request"""
        trace_data = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "start_time": datetime.now(),
            "headers": headers or {},
            "spans": [],
            "metadata": {},
        }

        with self._lock:
            self.active_traces[request_id] = trace_data

        return request_id

    def add_span(
        self,
        request_id: str,
        span_name: str,
        start_time: datetime,
        duration_ms: float,
        metadata: Dict[str, Any] = None,
    ):
        """Add a span to an existing trace"""
        with self._lock:
            if request_id in self.active_traces:
                span = {
                    "name": span_name,
                    "start_time": start_time.isoformat(),
                    "duration_ms": duration_ms,
                    "metadata": metadata or {},
                }
                self.active_traces[request_id]["spans"].append(span)

    def finish_trace(
        self, request_id: str, status_code: int, response_time_ms: float
    ) -> Optional[Dict[str, Any]]:
        """Finish a trace and return the trace data"""
        with self._lock:
            if request_id in self.active_traces:
                trace_data = self.active_traces.pop(request_id)
                trace_data["end_time"] = datetime.now()
                trace_data["status_code"] = status_code
                trace_data["total_duration_ms"] = response_time_ms
                return trace_data

        return None

    def get_active_traces(self) -> List[Dict[str, Any]]:
        """Get all currently active traces"""
        with self._lock:
            return [
                {
                    "request_id": trace_id,
                    "method": trace_data["method"],
                    "path": trace_data["path"],
                    "start_time": trace_data["start_time"].isoformat(),
                    "duration_so_far": (
                        datetime.now() - trace_data["start_time"]
                    ).total_seconds()
                    * 1000,
                    "spans_count": len(trace_data["spans"]),
                }
                for trace_id, trace_data in self.active_traces.items()
            ]


# Global instances
metrics_collector = MetricsCollector()
request_tracer = RequestTracer()


@asynccontextmanager
async def trace_request(
    request_id: str, method: str, path: str, headers: Dict[str, str] = None
):
    """Context manager for request tracing"""
    start_time = time.time()

    try:
        # Start trace
        request_tracer.start_trace(request_id, method, path, headers)
        metrics_collector.increment_active_requests()

        yield request_id

    finally:
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Finish trace
        request_tracer.finish_trace(request_id, 200, response_time_ms)
        metrics_collector.decrement_active_requests()


@asynccontextmanager
async def trace_span(request_id: str, span_name: str, metadata: Dict[str, Any] = None):
    """Context manager for tracing individual spans within a request"""
    start_time = datetime.now()
    span_start = time.time()

    try:
        yield
    finally:
        duration_ms = (time.time() - span_start) * 1000
        request_tracer.add_span(
            request_id, span_name, start_time, duration_ms, metadata
        )


def record_request_metrics(
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    response_time_ms: float,
    user_id: Optional[int] = None,
    service_name: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Record metrics for a completed request"""
    metrics = RequestMetrics(
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        response_time_ms=response_time_ms,
        timestamp=datetime.now(),
        user_id=user_id,
        service_name=service_name,
        error_message=error_message,
    )

    metrics_collector.record_request(metrics)


def get_monitoring_data() -> Dict[str, Any]:
    """Get comprehensive monitoring data"""
    return {
        "metrics": metrics_collector.get_current_metrics(),
        "endpoints": metrics_collector.get_endpoint_statistics(),
        "active_traces": request_tracer.get_active_traces(),
        "request_history": metrics_collector.get_request_history(50),
    }


# Prometheus-style metrics export
def export_prometheus_metrics() -> str:
    """Export metrics in Prometheus format"""
    metrics = metrics_collector.get_current_metrics()
    lines = []

    # Request metrics
    lines.append("# HELP http_requests_total Total number of HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    lines.append(f"http_requests_total {metrics['requests']['total']}")

    lines.append("# HELP http_request_errors_total Total number of HTTP request errors")
    lines.append("# TYPE http_request_errors_total counter")
    lines.append(f"http_request_errors_total {metrics['requests']['total_errors']}")

    lines.append(
        "# HELP http_request_duration_ms HTTP request duration in milliseconds"
    )
    lines.append("# TYPE http_request_duration_ms histogram")
    lines.append(
        f"http_request_duration_ms_avg {metrics['performance']['avg_response_time_ms']}"
    )
    lines.append(
        f"http_request_duration_ms_p95 {metrics['performance']['p95_response_time_ms']}"
    )
    lines.append(
        f"http_request_duration_ms_p99 {metrics['performance']['p99_response_time_ms']}"
    )

    # System metrics
    if "system" in metrics and "error" not in metrics["system"]:
        system = metrics["system"]
        lines.append("# HELP system_cpu_usage_percent CPU usage percentage")
        lines.append("# TYPE system_cpu_usage_percent gauge")
        lines.append(f"system_cpu_usage_percent {system['cpu_usage_percent']}")

        lines.append("# HELP system_memory_usage_percent Memory usage percentage")
        lines.append("# TYPE system_memory_usage_percent gauge")
        lines.append(f"system_memory_usage_percent {system['memory_usage_percent']}")

        lines.append("# HELP system_process_memory_mb Process memory usage in MB")
        lines.append("# TYPE system_process_memory_mb gauge")
        lines.append(f"system_process_memory_mb {system['process_memory_mb']}")

    return "\n".join(lines)


# Health check integration
def get_monitoring_health() -> Dict[str, Any]:
    """Get monitoring system health status"""
    try:
        metrics = metrics_collector.get_current_metrics()
        active_traces_count = len(request_tracer.get_active_traces())

        # Determine health based on metrics
        health_status = "healthy"
        issues = []

        # Check error rate
        error_rate = metrics["requests"]["error_rate_percent"]
        if error_rate > 10:  # More than 10% errors
            health_status = "degraded"
            issues.append(f"High error rate: {error_rate}%")

        # Check response time
        avg_response_time = metrics["performance"]["avg_response_time_ms"]
        if avg_response_time > 2000:  # More than 2 seconds
            health_status = "degraded"
            issues.append(f"High response time: {avg_response_time}ms")

        # Check system resources
        if "system" in metrics and "error" not in metrics["system"]:
            cpu_usage = metrics["system"]["cpu_usage_percent"]
            memory_usage = metrics["system"]["memory_usage_percent"]

            if cpu_usage > 80:
                health_status = "degraded"
                issues.append(f"High CPU usage: {cpu_usage}%")

            if memory_usage > 85:
                health_status = "degraded"
                issues.append(f"High memory usage: {memory_usage}%")

        return {
            "status": health_status,
            "total_requests": metrics["requests"]["total"],
            "active_requests": metrics["requests"]["active"],
            "active_traces": active_traces_count,
            "uptime_seconds": metrics["uptime_seconds"],
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

"""
Monitoring and metrics endpoints for observability.
Provides real-time metrics, traces, and system health information.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ...core.monitoring import (
    metrics_collector,
    request_tracer,
    get_monitoring_data,
    export_prometheus_metrics,
    get_monitoring_health
)
from ...core.service_auth import ServiceAuth, verify_service_auth
from ...core.logger import logger

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics", response_model=Dict[str, Any])
async def get_application_metrics(
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get comprehensive application metrics.
    Requires service authentication.
    """
    try:
        return metrics_collector.get_current_metrics()
    except Exception as e:
        logger.error(f"Error getting application metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/endpoints", response_model=Dict[str, Any])
async def get_endpoint_statistics(
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get detailed statistics for all API endpoints.
    Shows request counts, error rates, and response times per endpoint.
    """
    try:
        return metrics_collector.get_endpoint_statistics()
    except Exception as e:
        logger.error(f"Error getting endpoint statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve endpoint statistics")


@router.get("/traces", response_model=List[Dict[str, Any]])
async def get_active_traces(
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get currently active request traces.
    Shows requests that are still being processed.
    """
    try:
        return request_tracer.get_active_traces()
    except Exception as e:
        logger.error(f"Error getting active traces: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve traces")


@router.get("/requests", response_model=List[Dict[str, Any]])
async def get_recent_requests(
    limit: int = Query(100, ge=1, le=1000),
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get recent request history with details.
    Useful for debugging and monitoring recent activity.
    """
    try:
        return metrics_collector.get_request_history(limit)
    except Exception as e:
        logger.error(f"Error getting request history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve request history")


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_monitoring_dashboard(
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get comprehensive monitoring data for dashboard.
    Combines metrics, endpoint stats, and traces in one response.
    """
    try:
        return get_monitoring_data()
    except Exception as e:
        logger.error(f"Error getting monitoring dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")


@router.get("/health", response_model=Dict[str, Any])
async def get_monitoring_health_status():
    """
    Get monitoring system health status.
    This endpoint doesn't require authentication as it's used by health checks.
    """
    try:
        return get_monitoring_health()
    except Exception as e:
        logger.error(f"Error getting monitoring health: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve monitoring health")


@router.get("/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Export metrics in Prometheus format.
    Compatible with Prometheus scraping and Grafana dashboards.
    """
    try:
        return export_prometheus_metrics()
    except Exception as e:
        logger.error(f"Error exporting Prometheus metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_system_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, error, critical"),
    hours: int = Query(24, ge=1, le=168, description="Look back period in hours"),
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get system alerts and anomalies.
    Analyzes metrics to identify potential issues.
    """
    try:
        alerts = []
        metrics = metrics_collector.get_current_metrics()
        
        # Check error rate alerts
        error_rate = metrics['requests']['error_rate_percent']
        if error_rate > 5:
            alert_severity = "warning" if error_rate < 10 else "error" if error_rate < 20 else "critical"
            if not severity or severity == alert_severity:
                alerts.append({
                    "type": "high_error_rate",
                    "severity": alert_severity,
                    "message": f"Error rate is {error_rate}% (threshold: 5%)",
                    "value": error_rate,
                    "threshold": 5,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Check response time alerts
        avg_response_time = metrics['performance']['avg_response_time_ms']
        if avg_response_time > 1000:
            alert_severity = "warning" if avg_response_time < 2000 else "error" if avg_response_time < 5000 else "critical"
            if not severity or severity == alert_severity:
                alerts.append({
                    "type": "high_response_time",
                    "severity": alert_severity,
                    "message": f"Average response time is {avg_response_time}ms (threshold: 1000ms)",
                    "value": avg_response_time,
                    "threshold": 1000,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Check system resource alerts
        if 'system' in metrics and 'error' not in metrics['system']:
            system = metrics['system']
            
            # CPU alert
            cpu_usage = system['cpu_usage_percent']
            if cpu_usage > 70:
                alert_severity = "warning" if cpu_usage < 85 else "error" if cpu_usage < 95 else "critical"
                if not severity or severity == alert_severity:
                    alerts.append({
                        "type": "high_cpu_usage",
                        "severity": alert_severity,
                        "message": f"CPU usage is {cpu_usage}% (threshold: 70%)",
                        "value": cpu_usage,
                        "threshold": 70,
                        "timestamp": datetime.now().isoformat()
                    })
            
            # Memory alert
            memory_usage = system['memory_usage_percent']
            if memory_usage > 80:
                alert_severity = "warning" if memory_usage < 90 else "error" if memory_usage < 95 else "critical"
                if not severity or severity == alert_severity:
                    alerts.append({
                        "type": "high_memory_usage",
                        "severity": alert_severity,
                        "message": f"Memory usage is {memory_usage}% (threshold: 80%)",
                        "value": memory_usage,
                        "threshold": 80,
                        "timestamp": datetime.now().isoformat()
                    })
            
            # Disk alert
            disk_usage = system['disk_usage_percent']
            if disk_usage > 85:
                alert_severity = "warning" if disk_usage < 90 else "error" if disk_usage < 95 else "critical"
                if not severity or severity == alert_severity:
                    alerts.append({
                        "type": "high_disk_usage",
                        "severity": alert_severity,
                        "message": f"Disk usage is {disk_usage}% (threshold: 85%)",
                        "value": disk_usage,
                        "threshold": 85,
                        "timestamp": datetime.now().isoformat()
                    })
        
        # Check for stuck requests (active traces older than 5 minutes)
        active_traces = request_tracer.get_active_traces()
        stuck_requests = [
            trace for trace in active_traces 
            if trace['duration_so_far'] > 300000  # 5 minutes in ms
        ]
        
        if stuck_requests and (not severity or severity in ['warning', 'error']):
            alerts.append({
                "type": "stuck_requests",
                "severity": "warning",
                "message": f"{len(stuck_requests)} requests have been processing for over 5 minutes",
                "value": len(stuck_requests),
                "threshold": 0,
                "details": stuck_requests,
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting system alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_summary(
    time_range: str = Query("1h", description="Time range: 5m, 15m, 1h, 6h, 24h"),
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Get performance summary for specified time range.
    Analyzes trends and provides insights.
    """
    try:
        # Parse time range
        time_ranges = {
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24)
        }
        
        if time_range not in time_ranges:
            raise HTTPException(status_code=400, detail="Invalid time range")
        
        delta = time_ranges[time_range]
        cutoff_time = datetime.now() - delta
        
        # Filter requests in time range
        all_requests = metrics_collector.get_request_history(10000)  # Get more history
        filtered_requests = [
            req for req in all_requests 
            if datetime.fromisoformat(req['timestamp']) >= cutoff_time
        ]
        
        if not filtered_requests:
            return {
                "time_range": time_range,
                "message": "No requests in specified time range",
                "summary": {}
            }
        
        # Calculate performance metrics
        response_times = [req['response_time_ms'] for req in filtered_requests]
        error_requests = [req for req in filtered_requests if req['status_code'] >= 400]
        
        # Group by endpoint
        endpoint_performance = {}
        for req in filtered_requests:
            endpoint = f"{req['method']} {req['path']}"
            if endpoint not in endpoint_performance:
                endpoint_performance[endpoint] = {
                    "requests": 0,
                    "errors": 0,
                    "response_times": []
                }
            
            endpoint_performance[endpoint]["requests"] += 1
            endpoint_performance[endpoint]["response_times"].append(req['response_time_ms'])
            if req['status_code'] >= 400:
                endpoint_performance[endpoint]["errors"] += 1
        
        # Calculate summary stats
        for endpoint in endpoint_performance:
            perf = endpoint_performance[endpoint]
            times = perf["response_times"]
            
            perf["avg_response_time"] = sum(times) / len(times)
            perf["min_response_time"] = min(times)
            perf["max_response_time"] = max(times)
            perf["error_rate"] = (perf["errors"] / perf["requests"]) * 100
            
            # Remove raw response times to reduce payload size
            del perf["response_times"]
        
        summary = {
            "time_range": time_range,
            "total_requests": len(filtered_requests),
            "total_errors": len(error_requests),
            "error_rate_percent": (len(error_requests) / len(filtered_requests)) * 100,
            "avg_response_time_ms": sum(response_times) / len(response_times),
            "min_response_time_ms": min(response_times),
            "max_response_time_ms": max(response_times),
            "requests_per_minute": len(filtered_requests) / (delta.total_seconds() / 60),
            "endpoint_performance": endpoint_performance,
            "timestamp": datetime.now().isoformat()
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance summary")


@router.post("/reset", response_model=Dict[str, str])
async def reset_metrics(
    confirm: bool = Query(False, description="Confirm reset operation"),
    service_auth: ServiceAuth = Depends(verify_service_auth)
):
    """
    Reset all collected metrics and traces.
    WARNING: This will clear all monitoring data.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Reset operation requires confirmation. Add ?confirm=true to proceed."
        )
    
    try:
        # Reset metrics collector
        global metrics_collector, request_tracer
        from ...core.monitoring import MetricsCollector, RequestTracer
        
        metrics_collector = MetricsCollector()
        request_tracer = RequestTracer()
        
        logger.warning("Monitoring metrics have been reset")
        
        return {
            "status": "success",
            "message": "All monitoring data has been reset",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")
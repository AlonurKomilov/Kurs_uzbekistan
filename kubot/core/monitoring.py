"""
Monitoring and alerting utilities for collectors.
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sentry_sdk

logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN")


class CollectorMonitor:
    """Monitor collector operations and report metrics."""
    
    def __init__(self, collector_name: str):
        self.collector_name = collector_name
        self.start_time: Optional[float] = None
        self.metrics: Dict[str, Any] = {}
    
    def start(self):
        """Start monitoring session."""
        self.start_time = time.time()
        logger.info(f"🚀 Starting {self.collector_name} collector")
    
    def record_success(self, count: int = 1):
        """Record successful operations."""
        self.metrics['success'] = self.metrics.get('success', 0) + count
    
    def record_failure(self, count: int = 1, error: Optional[Exception] = None):
        """Record failed operations."""
        self.metrics['failures'] = self.metrics.get('failures', 0) + count
        
        if error:
            logger.error(f"❌ {self.collector_name} error: {error}", exc_info=True)
            
            # Send to Sentry if configured
            if SENTRY_DSN:
                sentry_sdk.capture_exception(error)
    
    def record_metric(self, key: str, value: Any):
        """Record custom metric."""
        self.metrics[key] = value
    
    def finish(self, alert_on_failure: bool = True) -> Dict[str, Any]:
        """
        Finish monitoring and return metrics.
        
        Args:
            alert_on_failure: Whether to send alert if failures exceed threshold
        
        Returns:
            Dictionary of metrics
        """
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics['duration_seconds'] = round(duration, 2)
        
        self.metrics['timestamp'] = datetime.utcnow().isoformat()
        self.metrics['collector'] = self.collector_name
        
        # Calculate success rate
        total = self.metrics.get('success', 0) + self.metrics.get('failures', 0)
        if total > 0:
            success_rate = (self.metrics.get('success', 0) / total) * 100
            self.metrics['success_rate'] = round(success_rate, 2)
        
        # Log summary
        logger.info(
            f"✅ {self.collector_name} completed: "
            f"Success: {self.metrics.get('success', 0)}, "
            f"Failures: {self.metrics.get('failures', 0)}, "
            f"Duration: {self.metrics.get('duration_seconds', 0)}s"
        )
        
        # Check if we should alert on failures
        if alert_on_failure and self.should_alert():
            self.send_alert()
        
        return self.metrics
    
    def should_alert(self) -> bool:
        """Determine if we should send an alert based on metrics."""
        failures = self.metrics.get('failures', 0)
        success = self.metrics.get('success', 0)
        total = failures + success
        
        # Alert if:
        # 1. All operations failed (and we had some operations)
        # 2. More than 50% failed and we had at least 5 operations
        if total == 0:
            return False
        
        if failures == total:
            return True
        
        if total >= 5 and (failures / total) > 0.5:
            return True
        
        return False
    
    def send_alert(self):
        """Send alert about collector failures."""
        alert_message = (
            f"🚨 ALERT: {self.collector_name} collector has high failure rate!\n"
            f"Success: {self.metrics.get('success', 0)}\n"
            f"Failures: {self.metrics.get('failures', 0)}\n"
            f"Success Rate: {self.metrics.get('success_rate', 0):.2f}%\n"
            f"Duration: {self.metrics.get('duration_seconds', 0)}s\n"
            f"Time: {self.metrics.get('timestamp', 'N/A')}"
        )
        
        logger.error(alert_message)
        
        # Send to Sentry with high severity
        if SENTRY_DSN:
            sentry_sdk.capture_message(
                alert_message,
                level='error',
                extras=self.metrics
            )


def monitor_collector(collector_name: str):
    """
    Decorator to monitor collector functions.
    
    Usage:
        @monitor_collector("CBU Rates")
        async def collect_cbu_rates():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitor = CollectorMonitor(collector_name)
            monitor.start()
            
            try:
                result = await func(*args, **kwargs)
                monitor.record_success()
                return result
            except Exception as e:
                monitor.record_failure(error=e)
                raise
            finally:
                monitor.finish()
        
        return wrapper
    return decorator

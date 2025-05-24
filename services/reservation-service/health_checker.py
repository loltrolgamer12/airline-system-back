import asyncio
import httpx
import time
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session

class HealthChecker:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.start_time = datetime.utcnow()
        self.health_history = []
        self.max_history = 100
    
    def check_database(self, db_session_factory) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        start_time = time.time()
        try:
            db = db_session_factory()
            db.execute(text("SELECT 1"))
            db.close()
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "connection": "active"
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "connection": "failed",
                "error": str(e)
            }
    
    async def check_service_dependency(self, service_url: str, service_name: str) -> Dict[str, Any]:
        """Check external service dependency"""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{service_url}/health")
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "response_time_ms": round(response_time, 2),
                        "service_name": service_name,
                        "service_url": service_url
                    }
                else:
                    return {
                        "status": "degraded",
                        "response_time_ms": round(response_time, 2),
                        "service_name": service_name,
                        "service_url": service_url,
                        "http_status": response.status_code
                    }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "service_name": service_name,
                "service_url": service_url,
                "error": str(e)
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information and uptime"""
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        uptime_hours = uptime_seconds / 3600
        
        return {
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_hours": round(uptime_hours, 2),
            "status": "running"
        }
    
    def add_health_check_result(self, result: Dict[str, Any]):
        """Add health check result to history"""
        result["timestamp"] = datetime.utcnow().isoformat()
        self.health_history.append(result)
        
        # Keep only last N results
        if len(self.health_history) > self.max_history:
            self.health_history = self.health_history[-self.max_history:]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of recent health checks"""
        if not self.health_history:
            return {"status": "no_data", "total_checks": 0}
        
        total_checks = len(self.health_history)
        healthy_checks = len([h for h in self.health_history if h.get("overall_status") == "healthy"])
        
        success_rate = (healthy_checks / total_checks) * 100 if total_checks > 0 else 0
        
        return {
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "success_rate_percentage": round(success_rate, 2),
            "last_check": self.health_history[-1] if self.health_history else None
        }

# Instancia global
health_checker = HealthChecker("reservation-service")

import time
from typing import Dict, Callable, Any, Optional
from enum import Enum
import asyncio
import httpx

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, 
                 failure_threshold: int = 5, 
                 recovery_timeout: int = 60,
                 expected_exception: Exception = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.success_count = 0
        self.total_requests = 0
        
        print(f"🛡️ Circuit Breaker inicializado - Threshold: {failure_threshold}, Timeout: {recovery_timeout}s")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        self.total_requests += 1
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                print("🔄 Circuit Breaker: CLOSED → HALF_OPEN")
            else:
                raise Exception(f"🚫 Circuit breaker is OPEN. Service temporarily unavailable.")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""
        self.total_requests += 1
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                print("🔄 Circuit Breaker: CLOSED → HALF_OPEN")
            else:
                raise Exception(f"🚫 Circuit breaker is OPEN. Service temporarily unavailable.")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        return (time.time() - self.last_failure_time) > self.recovery_timeout
    
    def _on_success(self):
        self.failure_count = 0
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            print("✅ Circuit Breaker: HALF_OPEN → CLOSED (Service recovered)")
        
        # Log successful recovery
        if self.success_count % 10 == 0:
            print(f"✅ Circuit Breaker: {self.success_count} successful calls")
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                print(f"🔴 Circuit Breaker: → OPEN (Failure threshold reached: {self.failure_count})")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        uptime_percentage = (self.success_count / self.total_requests * 100) if self.total_requests > 0 else 100
        
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "uptime_percentage": round(uptime_percentage, 2),
            "last_failure_time": self.last_failure_time
        }

# Circuit breakers para diferentes servicios
database_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
service_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

# Circuit breaker específico para HTTP requests
class HTTPCircuitBreaker(CircuitBreaker):
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        super().__init__(failure_threshold, recovery_timeout, httpx.HTTPError)
    
    async def http_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with circuit breaker protection"""
        async def make_request():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url, **kwargs)
                if response.status_code >= 400:
                    raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                return response
        
        return await self.async_call(make_request)

# Instancias globales
http_circuit_breaker = HTTPCircuitBreaker(failure_threshold=3, recovery_timeout=45)

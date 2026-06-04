from typing import Dict, Any, Callable, Awaitable
from datetime import datetime
from pydantic import BaseModel, Field
from plasmaagent.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from plasmaagent.reliability.degradation import (
    GracefulDegradation,
    DegradationConfig,
    DegradationLevel,
)
from plasmaagent.reliability.backoff import RetryPolicy, BackoffConfig
import threading


class ResilienceConfig(BaseModel):
    health_check_interval_seconds: float = Field(ge=1.0, le=3600.0, default=30.0)
    auto_degrade_on_failure: bool = True
    circuit_breaker_enabled: bool = True
    degradation_enabled: bool = True
    max_consecutive_failures: int = Field(ge=1, le=100, default=3)


class ServiceHealth(BaseModel):
    name: str
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    circuit_state: str = "closed"
    degradation_level: str = "full"
    last_check: datetime | None = None
    consecutive_failures: int = 0
    message: str = ""


class ResilienceManager:
    def __init__(self, config: ResilienceConfig | None = None):
        self._config = config or ResilienceConfig()
        self._services: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._start_time = datetime.now()

    def register_service(
        self,
        name: str,
        health_check: Callable[[], Awaitable[bool]] | None = None,
        circuit_config: CircuitBreakerConfig | None = None,
        degradation_config: DegradationConfig | None = None,
    ) -> None:
        with self._lock:
            entry: Dict[str, Any] = {
                "health_check": health_check,
                "consecutive_failures": 0,
                "last_check": None,
                "last_status": "healthy",
            }

            if self._config.circuit_breaker_enabled:
                entry["circuit_breaker"] = CircuitBreaker(
                    name=f"{name}-cb",
                    config=circuit_config or CircuitBreakerConfig(),
                )

            if self._config.degradation_enabled:
                entry["degradation"] = GracefulDegradation(
                    name=name,
                    config=degradation_config or DegradationConfig(),
                )

            self._services[name] = entry

    def unregister_service(self, name: str) -> bool:
        with self._lock:
            if name in self._services:
                del self._services[name]
                return True
            return False

    def get_service_names(self) -> list[str]:
        with self._lock:
            return list(self._services.keys())

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        with self._lock:
            entry = self._services.get(name)
            if entry:
                return entry.get("circuit_breaker")
            return None

    def get_degradation(self, name: str) -> GracefulDegradation | None:
        with self._lock:
            entry = self._services.get(name)
            if entry:
                return entry.get("degradation")
            return None

    def record_success(self, name: str, latency_ms: float = 0.0) -> None:
        with self._lock:
            entry = self._services.get(name)
            if not entry:
                return
            entry["consecutive_failures"] = 0
            entry["last_check"] = datetime.now()
            entry["last_status"] = "healthy"
            cb = entry.get("circuit_breaker")
            if cb:
                cb.record_success()
            gd = entry.get("degradation")
            if gd:
                gd.record_request(True, latency_ms)

    def record_failure(self, name: str, error: Exception | None = None) -> None:
        with self._lock:
            entry = self._services.get(name)
            if not entry:
                return
            entry["consecutive_failures"] += 1
            entry["last_check"] = datetime.now()
            entry["last_status"] = "unhealthy"
            cb = entry.get("circuit_breaker")
            if cb:
                cb.record_failure(error)
            gd = entry.get("degradation")
            if gd:
                gd.record_request(False, 0.0)
            if (
                self._config.auto_degrade_on_failure
                and entry["consecutive_failures"]
                >= self._config.max_consecutive_failures
            ):
                if gd:
                    gd.degrade_manually(DegradationLevel.PARTIAL)

    async def run_health_check(self, name: str) -> ServiceHealth:
        with self._lock:
            entry = self._services.get(name)
            if not entry:
                return ServiceHealth(
                    name=name,
                    status="unhealthy",
                    message="Service not registered",
                )

        health_check = entry.get("health_check")
        if health_check:
            try:
                is_healthy = await health_check()
                if is_healthy:
                    self.record_success(name)
                else:
                    self.record_failure(name)
            except Exception as e:
                self.record_failure(name, e)

        return self.get_service_health(name)

    async def run_all_health_checks(self) -> Dict[str, ServiceHealth]:
        results: Dict[str, ServiceHealth] = {}
        for name in self.get_service_names():
            results[name] = await self.run_health_check(name)
        return results

    def get_service_health(self, name: str) -> ServiceHealth:
        with self._lock:
            entry = self._services.get(name)
            if not entry:
                return ServiceHealth(
                    name=name,
                    status="unhealthy",
                    message="Service not registered",
                )

            cb = entry.get("circuit_breaker")
            gd = entry.get("degradation")

            circuit_state = cb.state.value if cb else "closed"
            degradation_level = gd.level.value if gd else "full"

            if circuit_state == "open" or degradation_level in ("minimal", "none"):
                status = "unhealthy"
            elif (
                circuit_state == "half_open"
                or degradation_level == "partial"
                or entry["consecutive_failures"] > 0
            ):
                status = "degraded"
            else:
                status = "healthy"

            return ServiceHealth(
                name=name,
                status=status,
                circuit_state=circuit_state,
                degradation_level=degradation_level,
                last_check=entry.get("last_check"),
                consecutive_failures=entry.get("consecutive_failures", 0),
                message=entry.get("last_status", ""),
            )

    def get_overall_health(self) -> Dict[str, Any]:
        results: Dict[str, ServiceHealth] = {}
        for name in self.get_service_names():
            results[name] = self.get_service_health(name)

        unhealthy = sum(1 for r in results.values() if r.status == "unhealthy")
        degraded = sum(1 for r in results.values() if r.status == "degraded")
        total = len(results)

        if unhealthy > 0:
            overall = "unhealthy"
        elif degraded > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        uptime = (datetime.now() - self._start_time).total_seconds()

        return {
            "status": overall,
            "uptime_seconds": uptime,
            "total_services": total,
            "healthy": total - unhealthy - degraded,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "services": {
                name: health.model_dump() for name, health in results.items()
            },
        }

    async def execute_with_resilience(
        self,
        service_name: str,
        func: Callable,
        fallback: Callable | None = None,
    ) -> Any:
        with self._lock:
            entry = self._services.get(service_name)
            if not entry:
                raise ValueError(f"Service '{service_name}' not registered")

        cb = entry.get("circuit_breaker")
        gd = entry.get("degradation")

        if cb:
            try:
                result = await cb.execute_async(func, fallback)
                self.record_success(service_name)
                return result
            except Exception as e:
                self.record_failure(service_name, e)
                raise

        if gd:
            try:
                result = await gd.execute_async(func, fallback)
                self.record_success(service_name)
                return result
            except Exception as e:
                self.record_failure(service_name, e)
                raise

        try:
            result = await func()
            self.record_success(service_name)
            return result
        except Exception as e:
            self.record_failure(service_name, e)
            raise

    def get_resilience_stats(self) -> Dict[str, Any]:
        with self._lock:
            services_stats: Dict[str, Any] = {}
            for name, entry in self._services.items():
                cb = entry.get("circuit_breaker")
                gd = entry.get("degradation")
                services_stats[name] = {
                    "consecutive_failures": entry.get("consecutive_failures", 0),
                    "last_check": (
                        entry["last_check"].isoformat()
                        if entry.get("last_check")
                        else None
                    ),
                    "last_status": entry.get("last_status", "unknown"),
                    "circuit_breaker": cb.get_stats() if cb else None,
                    "degradation": gd.get_stats() if gd else None,
                }

            return {
                "overall": self.get_overall_health(),
                "services": services_stats,
                "config": self._config.model_dump(),
            }

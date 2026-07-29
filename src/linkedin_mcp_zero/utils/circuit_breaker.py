from __future__ import annotations

import time

import structlog

from linkedin_mcp_zero.utils.errors import UpstreamError

logger = structlog.get_logger()


class CircuitBreaker:
    """Circuit Breaker pattern to protect against upstream rate-limiting and service outages."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()
        # HALF-OPEN must probe with a single request; without this flag every
        # queued request rushes through the moment the cooldown expires and
        # hits a still-unhealthy upstream at full concurrency.
        self._probe_in_flight = False

    def record_success(self) -> None:
        if self.state != "CLOSED":
            logger.info("Circuit breaker closed (recovered)", state=self.state)
        self.failure_count = 0
        self.state = "CLOSED"
        self._probe_in_flight = False

    def record_failure(self) -> None:
        self._probe_in_flight = False
        self.failure_count += 1
        logger.warning(
            "Circuit breaker recorded failure",
            count=self.failure_count,
            threshold=self.failure_threshold,
            state=self.state,
        )
        if self.state == "HALF-OPEN":
            # A failed probe means the upstream is still unhealthy: reopen
            # immediately instead of waiting for more (expensive) failures.
            self.state = "OPEN"
            self.last_state_change = time.time()
            logger.error("Circuit breaker re-opened after failed probe", recovery_timeout=self.recovery_timeout)
            return
        if self.failure_count >= self.failure_threshold and self.state != "OPEN":
            self.state = "OPEN"
            self.last_state_change = time.time()
            logger.error("Circuit breaker tripped to OPEN state", recovery_timeout=self.recovery_timeout)

    def allow_request(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change > self.recovery_timeout:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker entered HALF-OPEN state (cooldown expired)")
                return self._try_start_probe()
            return False
        if self.state == "HALF-OPEN":
            return self._try_start_probe()
        return True

    def _try_start_probe(self) -> bool:
        if self._probe_in_flight:
            return False
        self._probe_in_flight = True
        return True

    def check(self) -> None:
        if not self.allow_request():
            logger.warning("Request rejected by circuit breaker", state=self.state)
            raise UpstreamError(
                "Upstream request rejected by circuit breaker. "
                "LinkedIn guest service is temporarily failing or rate-limited. "
                "Please try again in a few seconds."
            )

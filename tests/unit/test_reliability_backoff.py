import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from plasmaagent.reliability import (
    ExponentialBackoff,
    BackoffConfig,
    RetryPolicy,
    RetryResult,
    retry_with_backoff,
)
from plasmaagent.reliability.backoff import (
    BackoffStrategy,
    retry_with_backoff_sync,
)


class TestBackoffStrategy:
    def test_strategies_exist(self):
        assert BackoffStrategy.EXPONENTIAL == "exponential"
        assert BackoffStrategy.LINEAR == "linear"
        assert BackoffStrategy.CONSTANT == "constant"
        assert BackoffStrategy.FIBONACCI == "fibonacci"


class TestBackoffConfig:
    def test_default_values(self):
        config = BackoffConfig()
        assert config.base_delay_ms == 100
        assert config.max_delay_ms == 30000
        assert config.multiplier == 2.0
        assert config.jitter is True
        assert config.strategy == BackoffStrategy.EXPONENTIAL

    def test_custom_values(self):
        config = BackoffConfig(
            base_delay_ms=200,
            max_delay_ms=60000,
            multiplier=3.0,
            jitter=False,
            strategy=BackoffStrategy.LINEAR,
        )
        assert config.base_delay_ms == 200
        assert config.max_delay_ms == 60000
        assert config.multiplier == 3.0
        assert config.jitter is False
        assert config.strategy == BackoffStrategy.LINEAR

    def test_negative_base_delay_raises(self):
        with pytest.raises(ValueError, match="base_delay_ms"):
            BackoffConfig(base_delay_ms=-1)

    def test_max_less_than_base_raises(self):
        with pytest.raises(ValueError, match="max_delay_ms"):
            BackoffConfig(base_delay_ms=100, max_delay_ms=50)

    def test_multiplier_below_one_raises(self):
        with pytest.raises(ValueError, match="multiplier"):
            BackoffConfig(multiplier=0.5)

    def test_zero_base_delay_valid(self):
        config = BackoffConfig(base_delay_ms=0, max_delay_ms=0)
        assert config.base_delay_ms == 0

    def test_frozen_dataclass(self):
        config = BackoffConfig()
        with pytest.raises(Exception):
            config.base_delay_ms = 200


class TestRetryPolicy:
    def test_default_values(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert isinstance(policy.backoff, BackoffConfig)
        assert policy.retryable_exceptions == (Exception,)

    def test_custom_values(self):
        config = BackoffConfig(base_delay_ms=50)
        policy = RetryPolicy(
            max_retries=5,
            backoff=config,
            retryable_exceptions=(ValueError, TypeError),
        )
        assert policy.max_retries == 5
        assert policy.backoff.base_delay_ms == 50
        assert ValueError in policy.retryable_exceptions

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError, match="max_retries"):
            RetryPolicy(max_retries=-1)

    def test_max_retries_too_high_raises(self):
        with pytest.raises(ValueError, match="max_retries"):
            RetryPolicy(max_retries=21)

    def test_max_retries_boundary_20(self):
        policy = RetryPolicy(max_retries=20)
        assert policy.max_retries == 20

    def test_zero_max_retries(self):
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0

    def test_frozen_dataclass(self):
        policy = RetryPolicy()
        with pytest.raises(Exception):
            policy.max_retries = 5


class TestRetryResult:
    def test_success_result(self):
        result = RetryResult(
            success=True,
            value=42,
            attempts=1,
            total_duration_ms=10.0,
        )
        assert result.success is True
        assert result.value == 42
        assert result.attempts == 1

    def test_failure_result(self):
        error = ValueError("oops")
        result = RetryResult(
            success=False,
            attempts=3,
            total_duration_ms=100.0,
            last_error=error,
            delays_ms=[100, 200, 400],
        )
        assert result.success is False
        assert result.last_error == error
        assert len(result.delays_ms) == 3

    def test_default_values(self):
        result = RetryResult(success=True)
        assert result.value is None
        assert result.attempts == 0
        assert result.total_duration_ms == 0.0
        assert result.last_error is None
        assert result.delays_ms == []


class TestExponentialBackoffCalculation:
    def test_exponential_strategy(self):
        config = BackoffConfig(
            base_delay_ms=100,
            multiplier=2.0,
            jitter=False,
            strategy=BackoffStrategy.EXPONENTIAL,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 100
        assert backoff.calculate_delay_ms(1) == 200
        assert backoff.calculate_delay_ms(2) == 400
        assert backoff.calculate_delay_ms(3) == 800

    def test_linear_strategy(self):
        config = BackoffConfig(
            base_delay_ms=100,
            multiplier=1.0,
            jitter=False,
            strategy=BackoffStrategy.LINEAR,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 100
        assert backoff.calculate_delay_ms(1) == 200
        assert backoff.calculate_delay_ms(2) == 300

    def test_constant_strategy(self):
        config = BackoffConfig(
            base_delay_ms=100,
            jitter=False,
            strategy=BackoffStrategy.CONSTANT,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 100
        assert backoff.calculate_delay_ms(1) == 100
        assert backoff.calculate_delay_ms(5) == 100

    def test_fibonacci_strategy(self):
        config = BackoffConfig(
            base_delay_ms=100,
            jitter=False,
            strategy=BackoffStrategy.FIBONACCI,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 100
        assert backoff.calculate_delay_ms(1) == 200
        assert backoff.calculate_delay_ms(2) == 300
        assert backoff.calculate_delay_ms(3) == 500
        assert backoff.calculate_delay_ms(4) == 800

    def test_max_delay_cap(self):
        config = BackoffConfig(
            base_delay_ms=1000,
            max_delay_ms=5000,
            multiplier=10.0,
            jitter=False,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 1000
        assert backoff.calculate_delay_ms(1) == 5000
        assert backoff.calculate_delay_ms(2) == 5000

    def test_jitter_applied(self):
        config = BackoffConfig(
            base_delay_ms=1000,
            jitter=True,
            strategy=BackoffStrategy.CONSTANT,
        )
        backoff = ExponentialBackoff(config)
        delays = [backoff.calculate_delay_ms(0) for _ in range(20)]
        assert min(delays) < 1000
        assert max(delays) > 1000 or min(delays) < 1000

    def test_jitter_not_exceed_max(self):
        config = BackoffConfig(
            base_delay_ms=100,
            max_delay_ms=1000,
            multiplier=2.0,
            jitter=True,
        )
        backoff = ExponentialBackoff(config)
        for _ in range(50):
            delay = backoff.calculate_delay_ms(10)
            assert delay <= 1250

    def test_negative_attempt_raises(self):
        backoff = ExponentialBackoff()
        with pytest.raises(ValueError, match="attempt"):
            backoff.calculate_delay_ms(-1)

    def test_zero_base_delay(self):
        config = BackoffConfig(base_delay_ms=0, max_delay_ms=0, jitter=False)
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 0
        assert backoff.calculate_delay_ms(5) == 0


class TestExponentialBackoffWait:
    @pytest.mark.asyncio
    async def test_wait_async(self):
        config = BackoffConfig(
            base_delay_ms=10,
            jitter=False,
            strategy=BackoffStrategy.CONSTANT,
        )
        backoff = ExponentialBackoff(config)
        start = time.time()
        delay = await backoff.wait(0)
        elapsed = time.time() - start
        assert delay == 10
        assert 0.005 <= elapsed <= 0.05

    def test_wait_sync(self):
        config = BackoffConfig(
            base_delay_ms=10,
            jitter=False,
            strategy=BackoffStrategy.CONSTANT,
        )
        backoff = ExponentialBackoff(config)
        start = time.time()
        delay = backoff.wait_sync(0)
        elapsed = time.time() - start
        assert delay == 10
        assert 0.005 <= elapsed <= 0.05


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return 42

        result = await retry_with_backoff(func)
        assert result.success is True
        assert result.value == 42
        assert result.attempts == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return 42

        policy = RetryPolicy(
            max_retries=5,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = await retry_with_backoff(func, policy)
        assert result.success is True
        assert result.value == 42
        assert result.attempts == 3
        assert len(result.delays_ms) == 2

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        policy = RetryPolicy(
            max_retries=2,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = await retry_with_backoff(func, policy)
        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.last_error, ValueError)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        async def func():
            raise TypeError("not retryable")

        policy = RetryPolicy(
            max_retries=5,
            retryable_exceptions=(ValueError,),
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = await retry_with_backoff(func, policy)
        assert result.success is False
        assert result.attempts == 1
        assert isinstance(result.last_error, TypeError)

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        callbacks = []

        async def func():
            if len(callbacks) < 2:
                raise ValueError("fail")
            return 42

        def on_retry(attempt, error, delay_ms):
            callbacks.append((attempt, str(error), delay_ms))

        policy = RetryPolicy(
            max_retries=5,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = await retry_with_backoff(func, policy, on_retry=on_retry)
        assert result.success is True
        assert len(callbacks) == 2

    @pytest.mark.asyncio
    async def test_zero_max_retries(self):
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        policy = RetryPolicy(
            max_retries=0,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = await retry_with_backoff(func, policy)
        assert result.success is False
        assert result.attempts == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_duration_tracking(self):
        async def func():
            await asyncio.sleep(0.01)
            return 42

        result = await retry_with_backoff(func)
        assert result.total_duration_ms >= 10


class TestRetryWithBackoffSync:
    def test_success_first_attempt(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return 42

        result = retry_with_backoff_sync(func)
        assert result.success is True
        assert result.value == 42
        assert call_count == 1

    def test_success_after_retries(self):
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return 42

        policy = RetryPolicy(
            max_retries=5,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = retry_with_backoff_sync(func, policy)
        assert result.success is True
        assert result.attempts == 3

    def test_failure_after_max_retries(self):
        def func():
            raise ValueError("always fail")

        policy = RetryPolicy(
            max_retries=2,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
        )
        result = retry_with_backoff_sync(func, policy)
        assert result.success is False
        assert result.attempts == 3


class TestBackoffEdgeCases:
    def test_large_attempt_number(self):
        config = BackoffConfig(
            base_delay_ms=100,
            max_delay_ms=5000,
            jitter=False,
        )
        backoff = ExponentialBackoff(config)
        delay = backoff.calculate_delay_ms(100)
        assert delay <= 5000

    def test_fibonacci_large_attempt(self):
        config = BackoffConfig(
            base_delay_ms=1,
            max_delay_ms=1000000,
            jitter=False,
            strategy=BackoffStrategy.FIBONACCI,
        )
        backoff = ExponentialBackoff(config)
        delay = backoff.calculate_delay_ms(20)
        assert delay > 0

    def test_retry_result_delays_tracking(self):
        result = RetryResult(
            success=False,
            attempts=4,
            delays_ms=[100, 200, 400],
        )
        assert len(result.delays_ms) == 3
        assert sum(result.delays_ms) == 700

    @pytest.mark.asyncio
    async def test_retry_with_none_policy(self):
        async def func():
            return 42

        result = await retry_with_backoff(func, None)
        assert result.success is True

    def test_sync_retry_with_none_policy(self):
        result = retry_with_backoff_sync(lambda: 42, None)
        assert result.success is True

    def test_multiplier_exactly_one(self):
        config = BackoffConfig(
            base_delay_ms=100,
            multiplier=1.0,
            jitter=False,
            strategy=BackoffStrategy.EXPONENTIAL,
        )
        backoff = ExponentialBackoff(config)
        assert backoff.calculate_delay_ms(0) == 100
        assert backoff.calculate_delay_ms(1) == 100
        assert backoff.calculate_delay_ms(5) == 100

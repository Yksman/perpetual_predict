"""Tests for retry decorator."""

import pytest

from perpetual_predict.utils.retry import retry, retry_sync


class TestRetryDecorator:
    """Tests for async retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        """Test successful call doesn't retry."""
        call_count = 0

        @retry(max_retries=3)
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self) -> None:
        """Test retry on failure, then success."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self) -> None:
        """Test exception raised when max retries exceeded."""
        call_count = 0

        @retry(max_retries=2, base_delay=0.01)
        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await always_fail()

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_specific_exception_retry(self) -> None:
        """Test only specified exceptions are retried."""
        call_count = 0

        @retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        async def raise_type_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError):
            await raise_type_error()

        assert call_count == 1  # No retry for TypeError

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test exponential backoff calculation."""
        import time

        call_times: list[float] = []

        @retry(max_retries=2, base_delay=0.05, exponential_base=2.0)
        async def track_time() -> None:
            call_times.append(time.time())
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await track_time()

        # Check delays are roughly exponential
        # First delay: 0.05s, second delay: 0.1s
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.03 <= delay1 <= 0.15  # Allow some tolerance

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert delay2 > delay1  # Second delay should be longer

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test max delay cap is respected."""
        import time

        call_times: list[float] = []

        @retry(
            max_retries=2, base_delay=1.0, max_delay=0.05, exponential_base=10.0
        )
        async def track_time() -> None:
            call_times.append(time.time())
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await track_time()

        # With max_delay=0.05, delays should be capped
        if len(call_times) >= 2:
            delay = call_times[1] - call_times[0]
            assert delay <= 0.1  # Should be around max_delay


class TestRetrySyncDecorator:
    """Tests for sync retry decorator."""

    def test_success_no_retry(self) -> None:
        """Test successful call doesn't retry."""
        call_count = 0

        @retry_sync(max_retries=3)
        def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_then_success(self) -> None:
        """Test retry on failure, then success."""
        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01)
        def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self) -> None:
        """Test exception raised when max retries exceeded."""
        call_count = 0

        @retry_sync(max_retries=2, base_delay=0.01)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fail()

        assert call_count == 3  # Initial + 2 retries

    def test_specific_exception_retry(self) -> None:
        """Test only specified exceptions are retried."""
        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def raise_type_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError):
            raise_type_error()

        assert call_count == 1

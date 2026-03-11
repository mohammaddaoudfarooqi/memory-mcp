"""Tests for RateLimiter."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_mcp.core.config import MCPConfig
from memory_mcp.services.rate_limiter import RateLimiter


def _make_config(**overrides) -> MCPConfig:
    defaults = {"mongodb_connection_string": "mongodb://localhost:27017"}
    defaults.update(overrides)
    return MCPConfig(**defaults, _env_file=None)


def _make_collection():
    col = MagicMock()
    col.count_documents = AsyncMock(return_value=0)
    col.insert_one = AsyncMock()
    return col


class TestRateLimiterCheck:
    """check_rate_limit enforces sliding window limits."""

    async def test_within_limit(self):
        col = _make_collection()
        config = _make_config(rate_limit_enabled=True, rate_limit_max_requests=100)
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=5)

        result = await limiter.check_rate_limit("user1", "store_memory")
        assert result is True
        col.insert_one.assert_called_once()

    async def test_exceeds_limit(self):
        col = _make_collection()
        config = _make_config(rate_limit_enabled=True, rate_limit_max_requests=10)
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=10)

        result = await limiter.check_rate_limit("user1", "store_memory")
        assert result is False
        col.insert_one.assert_not_called()

    async def test_disabled_always_allows(self):
        col = _make_collection()
        config = _make_config(rate_limit_enabled=False)
        limiter = RateLimiter(col, config)

        result = await limiter.check_rate_limit("user1", "store_memory")
        assert result is True
        col.count_documents.assert_not_called()
        col.insert_one.assert_not_called()

    async def test_records_operation(self):
        col = _make_collection()
        config = _make_config(rate_limit_enabled=True, rate_limit_max_requests=100)
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=0)

        await limiter.check_rate_limit("user1", "recall_memory")

        insert_doc = col.insert_one.call_args[0][0]
        assert insert_doc["user_id"] == "user1"
        assert insert_doc["operation"] == "recall_memory"
        assert "timestamp" in insert_doc

    async def test_sliding_window_query(self):
        col = _make_collection()
        config = _make_config(
            rate_limit_enabled=True,
            rate_limit_max_requests=100,
            rate_limit_window_seconds=3600,
        )
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=0)

        await limiter.check_rate_limit("user1", "store_memory")

        query = col.count_documents.call_args[0][0]
        assert query["user_id"] == "user1"
        assert query["operation"] == "store_memory"
        assert "$gte" in query["timestamp"]


class TestRateLimiterBoundary:
    """Boundary tests for rate limiter."""

    async def test_at_exact_limit(self):
        """At exactly max_requests, should be denied."""
        col = _make_collection()
        config = _make_config(rate_limit_enabled=True, rate_limit_max_requests=50)
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=50)

        result = await limiter.check_rate_limit("user1", "store_memory")
        assert result is False

    async def test_just_below_limit(self):
        """At max_requests - 1, should be allowed."""
        col = _make_collection()
        config = _make_config(rate_limit_enabled=True, rate_limit_max_requests=50)
        limiter = RateLimiter(col, config)

        col.count_documents = AsyncMock(return_value=49)

        result = await limiter.check_rate_limit("user1", "store_memory")
        assert result is True

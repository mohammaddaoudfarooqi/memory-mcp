"""Tests for DecisionService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory_mcp.core.config import MCPConfig
from memory_mcp.services.decision import DecisionService


def _make_config(**overrides) -> MCPConfig:
    defaults = {"mongodb_connection_string": "mongodb://localhost:27017"}
    defaults.update(overrides)
    return MCPConfig(**defaults, _env_file=None)


def _make_collection():
    col = MagicMock()
    col.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id"))
    col.find_one = AsyncMock(return_value=None)
    return col


class TestDecisionStore:
    """store() creates or updates decisions."""

    async def test_store_new_decision(self):
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        col.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id"))

        result = await svc.store("user1", "editor", "vim")
        assert result == "stored"
        col.update_one.assert_called_once()

        call_args = col.update_one.call_args
        assert call_args[0][0] == {"user_id": "user1", "key": "editor"}
        assert call_args[1]["upsert"] is True

    async def test_store_upsert_updates(self):
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        col.update_one = AsyncMock(return_value=MagicMock(upserted_id=None))

        result = await svc.store("user1", "editor", "emacs")
        assert result == "updated"

    async def test_store_custom_ttl(self):
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        col.update_one = AsyncMock(return_value=MagicMock(upserted_id="new"))

        await svc.store("user1", "theme", "dark", ttl_days=7)

        update_doc = col.update_one.call_args[0][1]
        expires_at = update_doc["$set"]["expires_at"]
        now = datetime.now(timezone.utc)
        # TTL should be roughly 7 days from now
        delta = expires_at - now
        assert 6 <= delta.days <= 7

    async def test_store_default_ttl(self):
        col = _make_collection()
        config = _make_config(decision_default_ttl_days=30)
        svc = DecisionService(col, config)

        col.update_one = AsyncMock(return_value=MagicMock(upserted_id="new"))

        await svc.store("user1", "theme", "dark")

        update_doc = col.update_one.call_args[0][1]
        expires_at = update_doc["$set"]["expires_at"]
        now = datetime.now(timezone.utc)
        delta = expires_at - now
        assert 29 <= delta.days <= 30


class TestDecisionRecall:
    """recall() retrieves decisions by key."""

    async def test_recall_found(self):
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        now = datetime.now(timezone.utc)
        col.find_one = AsyncMock(return_value={
            "key": "editor",
            "value": "vim",
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(days=30),
        })

        result = await svc.recall("user1", "editor")
        assert result is not None
        assert result["key"] == "editor"
        assert result["value"] == "vim"

    async def test_recall_not_found(self):
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        col.find_one = AsyncMock(return_value=None)

        result = await svc.recall("user1", "nonexistent")
        assert result is None

    async def test_recall_filters_expired(self):
        """recall query filters for expires_at > now."""
        col = _make_collection()
        config = _make_config()
        svc = DecisionService(col, config)

        col.find_one = AsyncMock(return_value=None)

        await svc.recall("user1", "expired_key")

        query = col.find_one.call_args[0][0]
        assert query["user_id"] == "user1"
        assert query["key"] == "expired_key"
        assert "$gt" in query["expires_at"]

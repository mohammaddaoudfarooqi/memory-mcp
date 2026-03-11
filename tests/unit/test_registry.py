"""Tests for ServiceRegistry singleton."""

import pytest
from unittest.mock import MagicMock

from memory_mcp.core.registry import ServiceRegistry


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset ServiceRegistry singleton between tests."""
    ServiceRegistry._instance = None
    yield
    ServiceRegistry._instance = None


class TestServiceRegistryInitialize:
    """TC-038: ServiceRegistry initializes and holds services."""

    def test_initialize_stores_services(self):
        config = MagicMock()
        memory_svc = MagicMock()
        cache_svc = MagicMock()
        audit_svc = MagicMock()
        providers = MagicMock()

        registry = ServiceRegistry.initialize(
            config=config,
            memory_service=memory_svc,
            cache_service=cache_svc,
            audit_service=audit_svc,
            providers=providers,
        )

        assert registry.config is config
        assert registry.memory_service is memory_svc
        assert registry.cache_service is cache_svc
        assert registry.audit_service is audit_svc
        assert registry.providers is providers


class TestServiceRegistryGet:
    """TC-039: get() returns singleton or raises."""

    def test_get_before_init_raises(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            ServiceRegistry.get()

    def test_get_after_init_returns_same(self):
        ServiceRegistry.initialize(
            config=MagicMock(),
            memory_service=MagicMock(),
            cache_service=MagicMock(),
            audit_service=MagicMock(),
            providers=MagicMock(),
        )

        reg1 = ServiceRegistry.get()
        reg2 = ServiceRegistry.get()
        assert reg1 is reg2

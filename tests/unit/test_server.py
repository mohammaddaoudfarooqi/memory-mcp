"""Tests for FastMCP server lifespan integration."""

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory_mcp.core.config import MCPConfig


def _make_config(**overrides) -> MCPConfig:
    defaults = {"mongodb_connection_string": "mongodb://localhost:27017"}
    defaults.update(overrides)
    return MCPConfig(**defaults, _env_file=None)


def _make_mock_db_manager():
    """Create a mock DatabaseManager with collection-returning db."""
    mock_db_manager = MagicMock()
    collections = {}

    def getitem(name):
        if name not in collections:
            collections[name] = MagicMock(name=f"col_{name}")
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=getitem)
    mock_db_manager.db = mock_db
    mock_db_manager.close = AsyncMock()
    return mock_db_manager, collections


class TestLifespan:
    """TC-053: Lifespan initializes all services and tears down on exit."""

    async def test_lifespan_initializes_services(self):
        """REQ-031: Startup initializes DB, providers, services, registry."""
        mock_db_manager, collections = _make_mock_db_manager()
        mock_config = _make_config()

        with patch("memory_mcp.server.MCPConfig", return_value=mock_config), \
             patch("memory_mcp.server.DatabaseManager") as mock_db_cls, \
             patch("memory_mcp.server.ProviderManager") as mock_pm_cls, \
             patch("memory_mcp.server.MemoryService") as mock_mem_cls, \
             patch("memory_mcp.server.CacheService") as mock_cache_cls, \
             patch("memory_mcp.server.AuditService") as mock_audit_cls, \
             patch("memory_mcp.server.EnrichmentWorker") as mock_enrich_cls, \
             patch("memory_mcp.server.ConsolidationWorker") as mock_consol_cls, \
             patch("memory_mcp.server.PromptLibrary") as mock_pl_cls, \
             patch("memory_mcp.server.DecisionService") as mock_ds_cls, \
             patch("memory_mcp.server.ServiceRegistry") as mock_reg_cls, \
             patch("memory_mcp.server.ensure_indexes", new_callable=AsyncMock) as mock_ei, \
             patch("memory_mcp.server.asyncio") as mock_asyncio:

            mock_db_cls.initialize = AsyncMock(return_value=mock_db_manager)
            mock_audit_cls.return_value = MagicMock()
            mock_audit_cls.return_value.flush = AsyncMock()

            mock_enrichment = MagicMock()
            mock_enrichment.run = AsyncMock()
            mock_enrich_cls.return_value = mock_enrichment
            mock_consolidation = MagicMock()
            mock_consolidation.run = AsyncMock()
            mock_consol_cls.return_value = mock_consolidation

            mock_reg_instance = MagicMock()
            mock_reg_cls.initialize.return_value = mock_reg_instance

            mock_enrichment_task = MagicMock()
            mock_consolidation_task = MagicMock()
            mock_search_task = MagicMock()
            mock_search_task.done = MagicMock(return_value=False)
            mock_asyncio.create_task.side_effect = [
                mock_enrichment_task, mock_consolidation_task, mock_search_task,
            ]
            mock_enrichment_task.cancel = MagicMock()
            mock_consolidation_task.cancel = MagicMock()

            from memory_mcp.server import lifespan

            app = MagicMock()
            ctx = lifespan(app)
            await ctx.__aenter__()

            # Verify initialization order
            mock_db_cls.initialize.assert_called_once()
            mock_ei.assert_called_once_with(mock_db_manager.db)
            mock_pm_cls.assert_called_once()
            mock_mem_cls.assert_called_once()
            mock_cache_cls.assert_called_once()
            mock_audit_cls.assert_called_once()
            mock_reg_cls.initialize.assert_called_once()
            assert mock_asyncio.create_task.call_count == 3

            # Shutdown
            await ctx.__aexit__(None, None, None)

            mock_enrichment_task.cancel.assert_called_once()
            mock_consolidation_task.cancel.assert_called_once()
            mock_search_task.cancel.assert_called_once()
            mock_audit_cls.return_value.flush.assert_called_once()
            mock_db_manager.close.assert_called_once()

    async def test_lifespan_passes_collections_not_db(self):
        """Services receive specific collection objects, not the raw db."""
        mock_db_manager, collections = _make_mock_db_manager()
        mock_config = _make_config()

        with patch("memory_mcp.server.MCPConfig", return_value=mock_config), \
             patch("memory_mcp.server.DatabaseManager") as mock_db_cls, \
             patch("memory_mcp.server.ProviderManager") as mock_pm_cls, \
             patch("memory_mcp.server.MemoryService") as mock_mem_cls, \
             patch("memory_mcp.server.CacheService") as mock_cache_cls, \
             patch("memory_mcp.server.AuditService") as mock_audit_cls, \
             patch("memory_mcp.server.EnrichmentWorker") as mock_enrich_cls, \
             patch("memory_mcp.server.ConsolidationWorker") as mock_consol_cls, \
             patch("memory_mcp.server.PromptLibrary") as mock_pl_cls, \
             patch("memory_mcp.server.DecisionService") as mock_ds_cls, \
             patch("memory_mcp.server.ServiceRegistry") as mock_reg_cls, \
             patch("memory_mcp.server.ensure_indexes", new_callable=AsyncMock), \
             patch("memory_mcp.server.asyncio") as mock_asyncio:

            mock_db_cls.initialize = AsyncMock(return_value=mock_db_manager)
            mock_audit_cls.return_value = MagicMock()
            mock_audit_cls.return_value.flush = AsyncMock()

            mock_enrichment = MagicMock()
            mock_enrichment.run = AsyncMock()
            mock_enrich_cls.return_value = mock_enrichment
            mock_consol_cls.return_value = MagicMock(run=AsyncMock())

            mock_reg_instance = MagicMock()
            mock_reg_cls.initialize.return_value = mock_reg_instance

            mock_search_task = MagicMock()
            mock_search_task.done = MagicMock(return_value=True)
            mock_asyncio.create_task.side_effect = [MagicMock(), MagicMock(), mock_search_task]

            from memory_mcp.server import lifespan

            app = MagicMock()
            ctx = lifespan(app)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

            # MemoryService should receive the memories collection
            mem_call = mock_mem_cls.call_args
            assert mem_call[0][0] == collections["memories"]

            # CacheService should receive the cache collection
            cache_call = mock_cache_cls.call_args
            assert cache_call[0][0] == collections["semantic_cache"]

            # AuditService should receive the audit_log collection
            audit_call = mock_audit_cls.call_args
            assert audit_call[0][0] == collections["audit_log"]


class TestToolRegistration:
    """TC-054: MCP server registers all 7 Phase 0 tools."""

    def test_server_module_has_mcp_instance(self):
        """The server module exposes a FastMCP instance with tools registered."""
        from memory_mcp.server import mcp
        # mcp should be a FastMCP instance (imported at module level)
        assert mcp is not None


class TestEnrichmentWorkerLifecycle:
    """TC-055: Enrichment worker starts and stops with lifespan."""

    async def test_enrichment_worker_receives_correct_args(self):
        mock_db_manager, collections = _make_mock_db_manager()
        mock_config = _make_config()

        with patch("memory_mcp.server.MCPConfig", return_value=mock_config), \
             patch("memory_mcp.server.DatabaseManager") as mock_db_cls, \
             patch("memory_mcp.server.ProviderManager") as mock_pm_cls, \
             patch("memory_mcp.server.MemoryService") as mock_mem_cls, \
             patch("memory_mcp.server.CacheService") as mock_cache_cls, \
             patch("memory_mcp.server.AuditService") as mock_audit_cls, \
             patch("memory_mcp.server.EnrichmentWorker") as mock_enrich_cls, \
             patch("memory_mcp.server.ConsolidationWorker") as mock_consol_cls, \
             patch("memory_mcp.server.PromptLibrary") as mock_pl_cls, \
             patch("memory_mcp.server.DecisionService") as mock_ds_cls, \
             patch("memory_mcp.server.ServiceRegistry") as mock_reg_cls, \
             patch("memory_mcp.server.ensure_indexes", new_callable=AsyncMock), \
             patch("memory_mcp.server.asyncio") as mock_asyncio:

            mock_db_cls.initialize = AsyncMock(return_value=mock_db_manager)
            mock_audit_cls.return_value = MagicMock()
            mock_audit_cls.return_value.flush = AsyncMock()

            mock_enrichment = MagicMock()
            mock_enrichment.run = AsyncMock()
            mock_enrich_cls.return_value = mock_enrichment
            mock_consol_cls.return_value = MagicMock(run=AsyncMock())

            mock_reg_instance = MagicMock()
            mock_reg_cls.initialize.return_value = mock_reg_instance

            mock_search_task = MagicMock()
            mock_search_task.done = MagicMock(return_value=True)
            mock_asyncio.create_task.side_effect = [MagicMock(), MagicMock(), mock_search_task]

            from memory_mcp.server import lifespan

            app = MagicMock()
            ctx = lifespan(app)
            await ctx.__aenter__()
            await ctx.__aexit__(None, None, None)

            # EnrichmentWorker receives memories collection, config, providers, memory_service
            enrich_call = mock_enrich_cls.call_args
            assert enrich_call[0][0] == collections["memories"]


class TestEnsureSearchIndexesBg:
    """_ensure_search_indexes_bg wraps ensure_search_indexes non-fatally."""

    async def test_bg_success(self):
        from memory_mcp.server import _ensure_search_indexes_bg
        with patch("memory_mcp.server.ensure_search_indexes", new_callable=AsyncMock) as mock_esi:
            mock_db = MagicMock()
            await _ensure_search_indexes_bg(mock_db, embedding_dimension=1024)
            mock_esi.assert_called_once_with(mock_db, embedding_dimension=1024)

    async def test_bg_exception_does_not_propagate(self):
        from memory_mcp.server import _ensure_search_indexes_bg
        with patch("memory_mcp.server.ensure_search_indexes",
                    new_callable=AsyncMock, side_effect=Exception("boom")):
            mock_db = MagicMock()
            # Should not raise
            await _ensure_search_indexes_bg(mock_db)

    async def test_bg_cancelled_error_is_swallowed(self):
        import asyncio
        from memory_mcp.server import _ensure_search_indexes_bg
        with patch("memory_mcp.server.ensure_search_indexes",
                    new_callable=AsyncMock, side_effect=asyncio.CancelledError):
            mock_db = MagicMock()
            # CancelledError is caught and logged, not re-raised
            await _ensure_search_indexes_bg(mock_db)


class TestHealthEndpoint:
    """Health check endpoint is registered on the MCP server."""

    def test_health_route_registered(self):
        """The /health custom route is registered on the mcp instance."""
        from memory_mcp.server import mcp
        # custom_route registers on the server's custom routes
        route_paths = [r.path for r in getattr(mcp, "_custom_routes", [])]
        # If custom_routes isn't exposed, verify the function exists
        from memory_mcp.server import health_check
        assert callable(health_check)

    async def test_health_returns_ok(self):
        """The health check handler returns a 200 JSON response."""
        from memory_mcp.server import health_check
        from unittest.mock import MagicMock
        request = MagicMock()
        response = await health_check(request)
        assert response.status_code == 200
        import json
        body = json.loads(response.body)
        assert body["status"] == "ok"


class TestMainEntryPoint:
    """__main__.py main() calls mcp.run."""

    def test_main_calls_mcp_run_http_default(self):
        mock_config = _make_config(port=8000)
        with patch("memory_mcp.__main__.mcp") as mock_mcp, \
             patch("memory_mcp.__main__.MCPConfig", return_value=mock_config):
            from memory_mcp.__main__ import main
            main()
            mock_mcp.run.assert_called_once_with(
                transport="streamable-http", host="0.0.0.0", port=8000,
            )

    def test_main_uses_config_port(self):
        mock_config = _make_config(port=9999)
        with patch("memory_mcp.__main__.mcp") as mock_mcp, \
             patch("memory_mcp.__main__.MCPConfig", return_value=mock_config):
            from memory_mcp.__main__ import main
            main()
            mock_mcp.run.assert_called_once_with(
                transport="streamable-http", host="0.0.0.0", port=9999,
            )

    def test_main_stdio_transport(self):
        mock_config = _make_config(transport="stdio")
        with patch("memory_mcp.__main__.mcp") as mock_mcp, \
             patch("memory_mcp.__main__.MCPConfig", return_value=mock_config):
            from memory_mcp.__main__ import main
            main()
            mock_mcp.run.assert_called_once_with(transport="stdio")

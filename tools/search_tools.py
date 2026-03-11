"""MCP Search Tools — hybrid search and web search."""

import asyncio
import time

from memory_mcp.core.registry import ServiceRegistry


def register_search_tools(mcp):
    """Register search MCP tools on the FastMCP server."""

    @mcp.tool(
        name="hybrid_search",
        description=(
            "Combined vector + full-text search over memories using "
            "Reciprocal Rank Fusion (RRF)."
        ),
    )
    async def hybrid_search(
        user_id: str,
        query: str,
        tier: list[str] | None = None,
        limit: int = 10,
        memory_type: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        svc = ServiceRegistry.get()
        config = svc.config
        start = time.time()

        try:
            limit = min(limit, config.max_results_per_query)
            tiers = tier or ["stm", "ltm"]
            query_embedding = await svc.providers.embedding.generate_embedding(query)

            # Pipeline 1: Vector search
            vs_filter = {"user_id": user_id, "deleted_at": None, "tier": {"$in": tiers}}
            if memory_type:
                vs_filter["memory_type"] = memory_type
            if tags:
                vs_filter["tags"] = {"$all": tags}

            vector_pipeline = [
                {
                    "$vectorSearch": {
                        "index": "memories_vector_index",
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 100,
                        "limit": 20,
                        "filter": vs_filter,
                    }
                },
                {"$addFields": {"vs_score": {"$meta": "vectorSearchScore"}}},
            ]

            # Pipeline 2: Full-text search
            fts_filter_clauses = [
                {"equals": {"path": "user_id", "value": user_id}},
                {"equals": {"path": "is_deleted", "value": False}},
            ]
            if tiers:
                fts_filter_clauses.append(
                    {"in": {"path": "tier", "value": tiers}}
                )

            fts_pipeline = [
                {
                    "$search": {
                        "index": "memories_fts_index",
                        "compound": {
                            "must": [
                                {"text": {"query": query, "path": ["content", "summary"]}}
                            ],
                            "filter": fts_filter_clauses,
                        },
                    }
                },
                {"$limit": 20},
                {"$addFields": {"fts_score": {"$meta": "searchScore"}}},
            ]

            # Execute concurrently
            memories_col = (await _get_db())["memories"]

            async def _run_pipeline(collection, pipeline):
                cursor = await collection.aggregate(pipeline)
                return await cursor.to_list(None)

            vector_results, fts_results = await asyncio.gather(
                _run_pipeline(memories_col, vector_pipeline),
                _run_pipeline(memories_col, fts_pipeline),
            )

            # Application-side RRF merge
            merged = _rrf_merge(
                vector_results, fts_results,
                rrf_k=config.rrf_k,
                vector_weight=config.rrf_vector_weight,
                text_weight=config.rrf_text_weight,
                limit=limit,
            )

            # Strip embeddings and sanitize BSON types for JSON serialization
            for r in merged:
                r.pop("embedding", None)
                r.pop("vs_score", None)
                r.pop("fts_score", None)
                _sanitize_doc(r)

            duration_ms = int((time.time() - start) * 1000)
            await svc.audit_service.log(
                user_id, "search", "hybrid_search", "success", duration_ms,
                query=query, result_count=len(merged),
            )
            return {"results": merged, "count": len(merged)}
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            await svc.audit_service.log(
                user_id, "search", "hybrid_search", "error", duration_ms,
                error=str(e),
            )
            raise

    @mcp.tool(
        name="search_web",
        description="Web search via Tavily API. Requires user_id for audit logging.",
    )
    async def search_web(user_id: str, query: str) -> dict:
        svc = ServiceRegistry.get()
        start = time.time()

        if not svc.config.tavily_api_key:
            await svc.audit_service.log(
                user_id, "search", "search_web", "error", 0,
                error="Tavily API key not configured",
            )
            return {"error": "Web search service unavailable: Tavily API key not configured"}

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=svc.config.tavily_api_key)
            response = await asyncio.to_thread(client.search, query)

            duration_ms = int((time.time() - start) * 1000)
            await svc.audit_service.log(
                user_id, "search", "search_web", "success", duration_ms,
                query=query,
            )
            return {"results": response.get("results", []), "query": query}
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            await svc.audit_service.log(
                user_id, "search", "search_web", "error", duration_ms,
                error=str(e),
            )
            raise


async def _get_db():
    """Get the DatabaseManager instance."""
    from memory_mcp.core.database import DatabaseManager

    return (await DatabaseManager.get_instance()).db


def _rrf_merge(
    vector_results: list[dict],
    fts_results: list[dict],
    rrf_k: int = 60,
    vector_weight: float = 1.0,
    text_weight: float = 0.7,
    limit: int = 10,
) -> list[dict]:
    """Merge two ranked result lists using Reciprocal Rank Fusion."""
    scores: dict = {}
    docs: dict = {}

    for rank, doc in enumerate(vector_results):
        doc_id = doc["_id"]
        rrf_score = vector_weight / (rrf_k + rank + 1)
        importance_boost = 1 + doc.get("importance", 0.5) * 0.1
        scores[doc_id] = scores.get(doc_id, 0) + rrf_score * importance_boost
        docs[doc_id] = doc

    for rank, doc in enumerate(fts_results):
        doc_id = doc["_id"]
        rrf_score = text_weight / (rrf_k + rank + 1)
        importance_boost = 1 + doc.get("importance", 0.5) * 0.1
        scores[doc_id] = scores.get(doc_id, 0) + rrf_score * importance_boost
        docs[doc_id] = doc

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [docs[doc_id] for doc_id in sorted_ids[:limit]]


def _sanitize_doc(doc: dict) -> None:
    """Convert BSON types (ObjectId, datetime) to JSON-safe strings in place."""
    from bson import ObjectId
    from datetime import datetime

    for key, val in list(doc.items()):
        if isinstance(val, ObjectId):
            doc[key] = str(val)
        elif isinstance(val, datetime):
            doc[key] = val.isoformat()
        elif isinstance(val, dict):
            _sanitize_doc(val)

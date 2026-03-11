# API Reference

Memory-MCP exposes tools over the Model Context Protocol (MCP) using Streamable HTTP transport on port 8000. Tools are called by MCP clients, not via REST endpoints.

## Transport

- **Protocol**: MCP (Model Context Protocol)
- **Transport**: Streamable HTTP
- **Host**: `0.0.0.0`
- **Port**: `8000`

## Memory Tools

Defined in `tools/memory_tools.py`.

### `store_memory`

Store conversation messages as short-term memories. For human messages longer than 30 characters, also creates long-term memory candidates queued for background enrichment.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier for multi-tenant isolation |
| `conversation_id` | string | Yes | — | Conversation identifier for grouping messages |
| `messages` | list[dict] | Yes | — | List of message objects to store |

Each message in `messages` should contain:

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | Message role: `"human"` or `"ai"` |
| `content` | string | Message text content |

**Returns:**

```json
{
  "stm_ids": ["67a1b2c3d4e5f6a7b8c9d0e1", "67a1b2c3d4e5f6a7b8c9d0e2"],
  "count": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `stm_ids` | list[string] | MongoDB ObjectId strings for created STM documents |
| `count` | integer | Number of STM documents created |

**Behavior:**
- Creates one STM document per message with a 24-hour TTL (configurable via `STM_TTL_HOURS`)
- Human messages >30 characters also produce an LTM candidate with `enrichment_status: "pending"`
- LTM candidate IDs are not returned (they are internal)
- Each message is embedded using the configured embedding provider

---

### `recall_memory`

Semantically search stored memories. Returns results ranked by a calibrated formula combining recency, importance, and vector similarity.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier |
| `query` | string | Yes | — | Natural language search query |
| `memory_type` | string \| null | No | `null` | Filter by memory type classification |
| `tags` | list[string] \| null | No | `null` | Filter by tags (all must match) |
| `limit` | integer | No | `10` | Maximum results to return (capped at `MAX_RESULTS_PER_QUERY`) |
| `tier` | list[string] \| null | No | `null` | Filter by tier: `["stm"]`, `["ltm"]`, or `["stm", "ltm"]` |

**Returns:**

```json
{
  "results": [
    {
      "_id": "67a1b2c3d4e5f6a7b8c9d0e1",
      "user_id": "user-123",
      "tier": "ltm",
      "content": "The user prefers dark mode interfaces.",
      "summary": "User preference for dark mode UI.",
      "importance": 0.7,
      "access_count": 3,
      "created_at": "2025-01-15T10:30:00",
      "final_score": 0.82
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results` | list[dict] | Ranked memory documents (embeddings stripped) |
| `count` | integer | Number of results returned |

**Behavior:**
- Generates an embedding for the query and runs a vector search on the `memories` collection
- Deduplicates STM/LTM pairs (keeps the higher-scoring result)
- Applies ranking: `score = α·recency + β·importance_boost + γ·relevance`
- Increments `access_count` and updates `last_accessed` on returned documents
- Excludes soft-deleted documents

---

### `delete_memory`

Soft-delete memories by ID, tags, or time range. Bulk deletes require explicit confirmation. Supports dry-run mode.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier |
| `memory_id` | string \| null | No | `null` | Specific memory ID to delete |
| `tags` | list[string] \| null | No | `null` | Delete memories matching all specified tags |
| `time_range` | dict \| null | No | `null` | Delete memories within time range (`{"start": "ISO8601", "end": "ISO8601"}`) |
| `confirm` | boolean | No | `false` | Required for bulk deletes (by tags or time range) |
| `dry_run` | boolean | No | `false` | Preview deletion count without modifying data |

**Returns:**

```json
{
  "deleted_count": 5,
  "dry_run": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `deleted_count` | integer | Number of documents (soft-)deleted or that would be deleted |
| `dry_run` | boolean | Present when `dry_run=true` |

**Behavior:**
- Single delete by `memory_id` does not require `confirm`
- Bulk deletes (by `tags` or `time_range`) require `confirm=true` or the operation is rejected
- Sets `deleted_at` timestamp and `is_deleted=true` on matched documents
- Soft-deleted documents are purged after `SOFT_DELETE_PURGE_DAYS` (default: 30)

---

## Cache Tools

Defined in `tools/cache_tools.py`.

### `check_cache`

Check the semantic cache for a previously cached response to a similar query.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier |
| `query` | string | Yes | — | Query to check against cached entries |
| `similarity_threshold` | float \| null | No | `null` | Minimum similarity for a cache hit (defaults to `CACHE_SIMILARITY_THRESHOLD`: 0.95) |

**Returns (cache hit):**

```json
{
  "cache_hit": true,
  "query": "What is the project deadline?",
  "response": "The project deadline is March 31, 2025.",
  "score": 0.97
}
```

**Returns (cache miss):**

```json
{
  "cache_hit": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cache_hit` | boolean | Whether a cached response was found |
| `query` | string | Original cached query (on hit) |
| `response` | string | Cached response text (on hit) |
| `score` | float | Similarity score (on hit) |

---

### `store_cache`

Cache a query-response pair for future similarity lookups.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier |
| `query` | string | Yes | — | Query text to cache |
| `response` | string | Yes | — | Response text to cache |

**Returns:**

```json
{
  "cache_id": "67a1b2c3d4e5f6a7b8c9d0e3"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cache_id` | string | MongoDB ObjectId of the created cache entry |

**Behavior:**
- Generates an embedding for the query
- Stores with a TTL of `CACHE_TTL_SECONDS` (default: 3600)
- Expired entries are automatically purged by MongoDB TTL index

---

## Search Tools

Defined in `tools/search_tools.py`.

### `hybrid_search`

Combined vector and full-text search over memories using Reciprocal Rank Fusion (RRF). Requires MongoDB Atlas with both `memories_vector_index` and `memories_fts_index` configured.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier |
| `query` | string | Yes | — | Search query |
| `tier` | list[string] \| null | No | `null` | Filter by tier (defaults to `["stm", "ltm"]`) |
| `limit` | integer | No | `10` | Maximum results (capped at `MAX_RESULTS_PER_QUERY`) |
| `memory_type` | string \| null | No | `null` | Filter by memory type |
| `tags` | list[string] \| null | No | `null` | Filter by tags (all must match) |

**Returns:**

```json
{
  "results": [
    {
      "_id": "67a1b2c3d4e5f6a7b8c9d0e1",
      "user_id": "user-123",
      "tier": "ltm",
      "content": "Discussed project architecture decisions.",
      "importance": 0.8,
      "rrf_score": 0.034
    }
  ],
  "count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results` | list[dict] | Merged and ranked memory documents (embeddings stripped) |
| `count` | integer | Number of results |

**Behavior:**
- Executes two concurrent MongoDB aggregation pipelines:
  1. `$vectorSearch` on the `embedding` field
  2. `$search` on `content` and `summary` fields
- Merges results using RRF: `score = vector_weight/(k+rank+1) + text_weight/(k+rank+1)` with importance boost
- Configurable via `RRF_K`, `RRF_VECTOR_WEIGHT`, `RRF_TEXT_WEIGHT`
- Excludes soft-deleted documents

---

### `search_web`

Web search via the Tavily API. Requires `TAVILY_API_KEY` to be configured.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `user_id` | string | Yes | — | User identifier (used for audit logging) |
| `query` | string | Yes | — | Search query |

**Returns (success):**

```json
{
  "results": [
    {
      "title": "Example Result",
      "url": "https://example.com",
      "content": "Result snippet..."
    }
  ],
  "query": "search terms"
}
```

**Returns (no API key):**

```json
{
  "error": "Web search service unavailable: Tavily API key not configured"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results` | list[dict] | Tavily search results |
| `query` | string | Original query |
| `error` | string | Error message (when Tavily is not configured) |

## Audit Logging

Every tool call generates an audit log entry with:

| Field | Description |
|-------|-------------|
| `user_id` | User who made the call |
| `operation` | Operation type (e.g., `memory:write`, `cache:read`, `search`) |
| `tool_name` | Tool function name (e.g., `store_memory`, `check_cache`) |
| `status` | `success` or `error` |
| `duration_ms` | Execution time in milliseconds |
| `timestamp` | ISO 8601 timestamp |
| `metadata` | Tool-specific context (query, result count, error message, etc.) |

Audit entries are buffered and flushed to the `audit_log` MongoDB collection. See [configuration.md](configuration.md) for audit buffer settings.

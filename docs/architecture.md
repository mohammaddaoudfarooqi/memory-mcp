# Architecture

## System Overview

Memory-MCP is an MCP (Model Context Protocol) server that provides AI applications with persistent memory, semantic caching, and hybrid search capabilities. It runs as a single Python process using FastMCP and stores all data in MongoDB Atlas.

The server targets AI agents and LLM-based applications that need to remember past conversations, retrieve relevant context, and cache repeated queries.

## System Context

### Users / Actors

- **AI Agent (MCP Client)**: Calls MCP tools to store, recall, and search memories. Each agent identifies itself via a `user_id` parameter.

### External Systems

- **MongoDB Atlas**: Stores memories, cache entries, and audit logs. Provides vector search (`$vectorSearch`), full-text search (`$search`), and TTL-based expiration.
- **AWS Bedrock**: Generates text embeddings (Titan Embed) and runs LLM inference (Claude) for enrichment tasks (importance scoring, summarization, memory merging).
- **Voyage AI** (optional): Alternative embedding provider. Used when `EMBEDDING_PROVIDER=voyage`.
- **Tavily API** (optional): Web search provider for the `search_web` tool. Requires `TAVILY_API_KEY`.

## Containers

| Container | Technology | Responsibility |
|-----------|-----------|----------------|
| Memory-MCP Server | Python 3.11, FastMCP | Hosts MCP tools, manages service lifecycle, runs enrichment worker |
| MongoDB Atlas | MongoDB 7.0+ | Persists memories, cache, and audit logs; provides search indexes |
| AWS Bedrock | Amazon Titan, Claude | Generates embeddings and LLM responses for enrichment |

## Component Details

### Core Layer (`core/`)

**`MCPConfig`** (`core/config.py`)
- Centralized configuration via Pydantic BaseSettings
- Loads from `.env` file or environment variables
- Validates types and provides defaults for 50+ settings
- Single required field: `MONGODB_CONNECTION_STRING`

**`DatabaseManager`** (`core/database.py`)
- Async-safe MongoDB connection pool singleton
- Double-checked locking with `asyncio.Lock`
- Configurable pool sizes (min 2, max 20)
- Initialized once during server startup, closed on shutdown

**`ServiceRegistry`** (`core/registry.py`)
- Module-level singleton holding all initialized services
- Tools call `ServiceRegistry.get()` to access services
- Initialized after all services are created during lifespan startup

**`Collections and Indexes`** (`core/collections.py`, `core/migrations.py`)
- Defines three collections: `memories`, `semantic_cache`, `audit_log`
- Two-stage index creation:
  - Stage 1 (blocking): Standard B-tree indexes for queries and TTL expiration
  - Stage 2 (background): Atlas Search indexes for vector and full-text search
- Non-Atlas deployments degrade gracefully (no vector/FTS search)

### Provider Layer (`providers/`)

**`ProviderManager`** (`providers/manager.py`)
- Factory that creates embedding and LLM providers based on configuration
- Exposes `.embedding` (EmbeddingProvider) and `.llm` (LLMProvider) attributes

**`BedrockEmbeddingProvider`** (`providers/bedrock.py`)
- Uses `boto3` with `bedrock-runtime` client
- Model: `amazon.titan-embed-text-v1` (1536 dimensions)
- Runs blocking boto3 calls via `asyncio.to_thread()`

**`BedrockLLMProvider`** (`providers/bedrock.py`)
- Uses the Bedrock `converse()` API with Claude
- Provides `assess_importance()` (returns 0.1–1.0) and `generate_summary()` methods

**`VoyageEmbeddingProvider`** (`providers/voyage.py`)
- Uses `httpx.AsyncClient` for the Voyage AI REST API
- Model: `voyage-3` (default)
- Batches requests at 128 texts per API call

### Service Layer (`services/`)

**`MemoryService`** (`services/memory.py`)
- **Store**: Creates STM documents with embeddings. Auto-creates LTM candidates for human messages >30 characters.
- **Recall**: Vector search with deduplication of STM/LTM pairs, calibrated 3-component ranking, and access counter updates.
- **Delete**: Soft-delete by ID, tags, or time range. Bulk deletes require `confirm=true`. Supports dry-run preview.
- **Evolve**: Detects similar memories and either reinforces (>0.85 similarity), queues merge (0.70–0.85), or creates new.

**`CacheService`** (`services/cache.py`)
- **Check**: Vector search on cached embeddings; returns hit if similarity >= threshold (default 0.95).
- **Store**: Inserts query-response pair with embedding and TTL.
- **Invalidate**: Bulk or pattern-based hard-delete of cache entries.

**`AuditService`** (`services/audit.py`)
- Buffers audit entries in memory.
- Flushes to MongoDB on buffer full, timer elapsed, or write-through mode.
- Falls back to local `audit_fallback.jsonl` file if MongoDB write fails.

**`EnrichmentWorker`** (`services/enrichment.py`)
- Runs as an `asyncio.Task` within the server process.
- Polls for pending LTM memories every 30 seconds (configurable).
- Processes in batches of 50 with concurrency limit of 5.
- For each memory: assesses importance via LLM, generates summary, runs evolution check.
- Retries up to 3 times on failure; marks as failed on exhaustion.

### Tool Layer (`tools/`)

Seven MCP tools organized into three modules:

- `tools/memory_tools.py`: `store_memory`, `recall_memory`, `delete_memory`
- `tools/cache_tools.py`: `check_cache`, `store_cache`
- `tools/search_tools.py`: `hybrid_search`, `search_web`

Each tool delegates to its service via `ServiceRegistry.get()` and logs the operation through `AuditService`.

## Data Flow

### Store Memory

```
MCP Client
  → store_memory(user_id, conversation_id, messages)
    → MemoryService.store_stm()
      → EmbeddingProvider.generate_embeddings_batch(messages)
      → MongoDB insert: STM documents (tier="stm", expires_at=now+24h)
      → MongoDB insert: LTM candidates (tier="ltm", enrichment_status="pending")
    → AuditService.log(operation="memory:write")
  ← {stm_ids: [...], count: N}
```

### Recall Memory

```
MCP Client
  → recall_memory(user_id, query, limit=10)
    → MemoryService.recall()
      → EmbeddingProvider.generate_embedding(query)
      → MongoDB $vectorSearch (memories collection)
      → Deduplicate STM/LTM pairs (keep higher score)
      → Calibrated ranking: score = α·recency + β·importance + γ·relevance
      → MongoDB update: increment access_count, set last_accessed
    → AuditService.log(operation="memory:read")
  ← {results: [...], count: N}
```

### Hybrid Search

```
MCP Client
  → hybrid_search(user_id, query, limit=10)
    → Concurrent execution:
      → Pipeline 1: MongoDB $vectorSearch on embedding
      → Pipeline 2: MongoDB $search on content + summary
    → RRF merge: score = vector_weight/(k+rank) + text_weight/(k+rank)
      with importance boost: × (1 + importance × 0.1)
    → AuditService.log(operation="search")
  ← {results: [...], count: N}
```

### Background Enrichment

```
EnrichmentWorker (continuous loop, every 30s)
  → Query: find memories where enrichment_status="pending", limit 50
  → For each memory (concurrency=5):
    → LLM: assess_importance(content) → float (0.1–1.0)
    → LLM: generate_summary(content) → string (≤100 words)
    → MemoryService.evolve_memory(user_id, content, embedding)
      → Vector search for similar LTM
      → >0.85 similarity: reinforce (boost importance 1.1×)
      → 0.70–0.85: queue merge (enrichment_status="merge_pending")
      → <0.70: create new memory
    → MongoDB update: enrichment_status="complete", importance, summary
```

## Key Design Decisions

### Single-process architecture

**Context:** Phase 0 requires a working system with minimal operational complexity.
**Decision:** Run everything — MCP server, enrichment worker, audit flushing — in a single FastMCP process.
**Rationale:** Eliminates inter-service communication, shared-nothing coordination, and deployment of multiple containers. The enrichment worker runs as an `asyncio.Task`, sharing the event loop.
**Trade-offs:** Vertical scaling only. The enrichment worker competes for CPU with request handling. Acceptable at Phase 0 scale.

### Two-tier memory model (STM/LTM)

**Context:** AI agents produce many messages, but not all are worth keeping permanently.
**Decision:** Store all messages as short-term memories with a 24-hour TTL. Automatically promote human messages >30 characters to long-term memory candidates for enrichment.
**Rationale:** TTL-based STM auto-purges via MongoDB index. LTM undergoes quality assessment before becoming permanent. Deduplication during recall prevents showing both STM and LTM versions of the same content.

### Calibrated ranking formula

**Context:** Raw vector similarity alone does not reflect how useful a memory is in context.
**Decision:** Rank results using `score = α·recency + β·importance + γ·relevance` where α=0.2, β=0.3, γ=0.5.
**Rationale:** Recency uses exponential decay (half-life ~30 days). Importance incorporates LLM-assessed value boosted by access frequency. Relevance is the vector similarity score. Weights are configurable.

### Soft-delete with TTL purge

**Context:** Hard-deleting memories makes audit trails incomplete and prevents accidental deletion recovery.
**Decision:** Delete operations set `deleted_at` and `is_deleted=true`. A TTL index on `deleted_at` purges soft-deleted documents after 30 days.
**Rationale:** All query filters exclude soft-deleted documents. Audit logs reference the original memory IDs. Recovery is possible within the purge window.

### Non-blocking Atlas Search index creation

**Context:** Atlas Search index creation can take minutes and may fail on non-Atlas deployments.
**Decision:** Standard B-tree indexes are created synchronously at startup (Stage 1). Atlas Search indexes are created in a background task (Stage 2) that polls for readiness with a 120-second timeout.
**Rationale:** The server becomes available after Stage 1 completes. If Stage 2 fails, the server runs without vector/FTS search — tools degrade but do not crash.

## Security Considerations

- **Multi-tenant isolation**: Every service method injects `user_id` into MongoDB query filters via `_base_filter()`. No cross-user data leakage is possible through the service layer.
- **Soft-delete filtering**: All queries include `deleted_at: null` to exclude soft-deleted documents.
- **No authentication (Phase 0)**: The server trusts the `user_id` parameter provided by the MCP client. Authentication and authorization are planned for Phase 2 (JWT-based, with RBAC).
- **Credential management**: AWS credentials and API keys are loaded from environment variables, not hardcoded.

## Collections

| Collection | Purpose | TTL |
|------------|---------|-----|
| `memories` | STM and LTM storage | `expires_at` (STM: 24h), `deleted_at` (soft-delete: 30d) |
| `semantic_cache` | Query-response cache | `created_at` (default: 3600s) |
| `audit_log` | Operation audit trail | `timestamp` (365 days) |

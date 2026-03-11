# Configuration Reference

All configuration is managed through environment variables, loaded from a `.env` file or the process environment. Variables are case-insensitive.

The configuration class is `MCPConfig` in `core/config.py`, built on Pydantic BaseSettings.

## Environment Variables

### Server

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `APP_NAME` | string | No | `memory-mcp` | Application name |
| `APP_VERSION` | string | No | `3.2.0` | Application version |
| `PORT` | integer | No | `8080` | Defined in config but **not used** — the server always listens on port 8000 (hardcoded in `__main__.py`) |
| `DEBUG` | boolean | No | `false` | Debug mode |

### MongoDB

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MONGODB_CONNECTION_STRING` | string | **Yes** | — | MongoDB Atlas connection URI (e.g., `mongodb+srv://user:pass@cluster.mongodb.net/db`) |
| `MONGODB_DATABASE_NAME` | string | No | `memory_mcp` | Database name |
| `MONGODB_MAX_POOL_SIZE` | integer | No | `20` | Maximum connection pool size |
| `MONGODB_MIN_POOL_SIZE` | integer | No | `2` | Minimum connection pool size |

### Embedding Provider

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | string | No | `bedrock` | Embedding provider: `bedrock` or `voyage` |
| `EMBEDDING_MODEL` | string | No | `amazon.titan-embed-text-v1` | Embedding model identifier |
| `EMBEDDING_DIMENSION` | integer | No | `1536` | Embedding vector dimension |

### LLM Provider

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `LLM_PROVIDER` | string | No | `bedrock` | LLM provider (only `bedrock` supported in Phase 0) |
| `LLM_MODEL` | string | No | `us.anthropic.claude-sonnet-4-20250514-v1:0` | LLM model identifier for enrichment tasks |

### AWS Bedrock

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `AWS_REGION` | string | No | `us-east-1` | AWS region for Bedrock API calls |
| `AWS_ACCESS_KEY_ID` | string | No | — | AWS access key (falls back to default AWS credential chain if unset) |
| `AWS_SECRET_ACCESS_KEY` | string | No | — | AWS secret key (falls back to default AWS credential chain if unset) |

### Voyage AI

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `VOYAGE_API_KEY` | string | Conditional | — | Required when `EMBEDDING_PROVIDER=voyage` |
| `VOYAGE_BASE_URL` | string | No | `https://api.voyageai.com/v1/embeddings` | Voyage AI API endpoint |
| `VOYAGE_MODEL` | string | No | `voyage-3` | Voyage embedding model |

### Tavily

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `TAVILY_API_KEY` | string | No | — | Enables the `search_web` tool. Without this key, `search_web` returns an error. |

### Memory Lifecycle

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `STM_TTL_HOURS` | integer | No | `24` | Short-term memory time-to-live in hours |
| `LTM_RETENTION_CRITICAL_DAYS` | integer | No | `365` | Retention for critical-tier LTM |
| `LTM_RETENTION_REFERENCE_DAYS` | integer | No | `180` | Retention for reference-tier LTM |
| `LTM_RETENTION_STANDARD_DAYS` | integer | No | `90` | Retention for standard-tier LTM |
| `LTM_RETENTION_TEMPORARY_DAYS` | integer | No | `7` | Retention for temporary-tier LTM |

### Memory Evolution

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `REINFORCE_THRESHOLD` | float | No | `0.85` | Similarity threshold above which existing memory is reinforced |
| `MERGE_THRESHOLD` | float | No | `0.70` | Similarity threshold above which memories are queued for merge |

### Retrieval Ranking

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `RANKING_ALPHA` | float | No | `0.2` | Weight for recency component in ranking formula |
| `RANKING_BETA` | float | No | `0.3` | Weight for importance component |
| `RANKING_GAMMA` | float | No | `0.5` | Weight for relevance (vector similarity) component |

The ranking formula: `score = α·recency + β·importance_boost + γ·relevance`

### Reciprocal Rank Fusion (RRF)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `RRF_K` | integer | No | `60` | RRF smoothing constant |
| `RRF_VECTOR_WEIGHT` | float | No | `1.0` | Weight for vector search results in RRF |
| `RRF_TEXT_WEIGHT` | float | No | `0.7` | Weight for full-text search results in RRF |
| `RRF_SINGLE_PIPELINE` | boolean | No | `false` | Use single pipeline mode (skip dual-pipeline RRF) |

### Query Limits

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MAX_RESULTS_PER_QUERY` | integer | No | `100` | Maximum results returned per query |
| `MAX_RESPONSE_BYTES` | integer | No | `16777216` | Maximum response size in bytes (16 MB) |

### Cache

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | integer | No | `3600` | Cache entry time-to-live (1 hour) |
| `CACHE_SIMILARITY_THRESHOLD` | float | No | `0.95` | Minimum similarity for cache hit |

### Enrichment Worker

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ENRICHMENT_INTERVAL_SECONDS` | integer | No | `30` | Polling interval for pending memories |
| `ENRICHMENT_BATCH_SIZE` | integer | No | `50` | Maximum memories processed per poll cycle |
| `ENRICHMENT_CONCURRENCY` | integer | No | `5` | Maximum concurrent enrichment tasks |
| `ENRICHMENT_MAX_RETRIES` | integer | No | `3` | Maximum retry attempts before marking as failed |

### Audit

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `AUDIT_BUFFER_SIZE` | integer | No | `10` | Number of entries buffered before flush |
| `AUDIT_FLUSH_INTERVAL_SECONDS` | integer | No | `60` | Maximum seconds between flushes |
| `AUDIT_FLUSH_ON_WRITE` | boolean | No | `false` | Flush after every audit entry (compliance mode) |
| `AUDIT_RETENTION_DAYS` | integer | No | `365` | TTL for audit log entries |

### Soft Delete

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `SOFT_DELETE_PURGE_DAYS` | integer | No | `30` | Days before soft-deleted documents are purged |

### Consolidation (Phase 1)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `CONSOLIDATION_INTERVAL_HOURS` | integer | No | `24` | Consolidation cycle interval |
| `STM_COMPRESSION_AGE_HOURS` | integer | No | `24` | Age threshold for STM compression |
| `FORGETTING_SCORE_THRESHOLD` | float | No | `0.1` | Score below which memories may be forgotten |
| `PROMOTION_IMPORTANCE_THRESHOLD` | float | No | `0.6` | Minimum importance for STM-to-LTM promotion |
| `PROMOTION_ACCESS_THRESHOLD` | integer | No | `2` | Minimum access count for promotion |
| `PROMOTION_AGE_MINUTES` | integer | No | `60` | Minimum age in minutes for promotion |

### Feature Flags

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `USE_NEW_MEMORY_SERVICE` | boolean | No | `true` | Use v3.2 memory service |
| `USE_NEW_CACHE_SERVICE` | boolean | No | `true` | Use v3.2 cache service |
| `USE_NEW_SEARCH_SERVICE` | boolean | No | `true` | Use v3.2 search service |

### Identity and Auth (Phase 2)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `AUTH_ENABLED` | boolean | No | `false` | Enable JWT authentication |
| `AUTH_TOKEN_HEADER` | string | No | `Authorization` | HTTP header for auth token |
| `AUTH_JWKS_URL` | string | No | — | JWKS endpoint for token validation |
| `AUTH_USER_ID_CLAIM` | string | No | `sub` | JWT claim for user ID |
| `AUTH_ROLE_CLAIM` | string | No | `role` | JWT claim for user role |
| `AUTH_DEFAULT_ROLE` | string | No | `end_user` | Role assigned when no role claim present |

### Governance (Phase 2)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `GOVERNANCE_ENABLED` | boolean | No | `false` | Enable governance policies |
| `GOVERNANCE_DEFAULT_PROFILE` | string | No | `default` | Default governance profile name |
| `GOVERNANCE_CACHE_TTL_SECONDS` | integer | No | `300` | TTL for governance policy cache |
| `RATE_LIMIT_ENABLED` | boolean | No | `false` | Enable rate limiting |
| `RATE_LIMIT_WINDOW_SECONDS` | integer | No | `60` | Rate limit window duration |

### Experimental (Phase 2)

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `PROMPT_EXPERIMENT_ENABLED` | boolean | No | `false` | Enable prompt library experimentation |
| `DECISION_STICKINESS_ENABLED` | boolean | No | `false` | Enable decision stickiness |
| `DECISION_DEFAULT_TTL_DAYS` | integer | No | `90` | Default TTL for sticky decisions |

## Example `.env` File

```bash
# Required
MONGODB_CONNECTION_STRING=mongodb+srv://user:password@cluster.mongodb.net/memory_mcp

# AWS Bedrock (required for default providers)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Optional: switch to Voyage AI embeddings
# EMBEDDING_PROVIDER=voyage
# VOYAGE_API_KEY=your-voyage-api-key

# Optional: enable web search
# TAVILY_API_KEY=your-tavily-api-key
```

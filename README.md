# Memory-MCP

MongoDB Atlas-backed MCP server for AI memory management with semantic caching, hybrid search, and background enrichment.

## Installation

```bash
pip install memory-mcp
```

Or install from source:

```bash
git clone https://github.com/mongodb-partners/memory-mcp.git
cd memory-mcp
pip install .
```

## Quick Start

1. Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

2. Set the required variables in `.env`:

```bash
MONGODB_CONNECTION_STRING=mongodb+srv://user:password@cluster.mongodb.net/memory_mcp
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

3. Start the server:

```bash
memory-mcp
```

The server listens on `http://0.0.0.0:8000` using the Streamable HTTP MCP transport.

## Features

- **Memory storage and recall**: Store conversation messages as short-term memories (STM) with automatic long-term memory (LTM) candidate creation
- **Semantic search**: Vector similarity search over stored memories using configurable embedding providers (AWS Bedrock, Voyage AI)
- **Hybrid search**: Combined vector and full-text search with Reciprocal Rank Fusion (RRF) ranking
- **Semantic caching**: Cache query-response pairs and retrieve them by similarity threshold
- **Background enrichment**: Async worker that assesses memory importance and generates summaries via LLM
- **Memory evolution**: Automatic reinforcement of similar memories and merge detection
- **Calibrated ranking**: Three-component scoring combining recency, importance, and relevance
- **Audit logging**: Buffered audit trail for all operations with configurable flush strategies
- **Web search**: Optional Tavily API integration for web search
- **Multi-tenant isolation**: All queries scoped by `user_id`

## MCP Tools

Memory-MCP exposes 7 tools over the Model Context Protocol:

| Tool | Description |
|------|-------------|
| `store_memory` | Store conversation messages as short-term memories |
| `recall_memory` | Semantically search stored memories with ranked results |
| `delete_memory` | Soft-delete memories by ID, tags, or time range |
| `check_cache` | Check semantic cache for a similar previous query |
| `store_cache` | Cache a query-response pair for future lookups |
| `hybrid_search` | Combined vector + full-text search with RRF merging |
| `search_web` | Web search via Tavily API |

See [docs/api-reference.md](docs/api-reference.md) for full tool signatures and parameters.

## Architecture

Memory-MCP runs as a single FastMCP process with four internal services:

- **MemoryService** — STM/LTM storage, recall with calibrated ranking, soft-delete
- **CacheService** — Semantic cache with vector similarity lookup
- **AuditService** — Buffered audit logging with MongoDB persistence and local file fallback
- **EnrichmentWorker** — Background async task for LTM importance assessment, summarization, and memory evolution

Embedding and LLM operations are handled by pluggable providers (AWS Bedrock, Voyage AI). MongoDB Atlas provides vector search, full-text search, and TTL-based document expiration.

See [docs/architecture.md](docs/architecture.md) for data flow diagrams and design decisions.

## Configuration

Configuration is managed through environment variables loaded from a `.env` file. Key variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_CONNECTION_STRING` | Yes | — | MongoDB Atlas connection URI |
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS credentials for Bedrock |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS credentials for Bedrock |
| `AWS_REGION` | No | `us-east-1` | AWS region for Bedrock |
| `EMBEDDING_PROVIDER` | No | `bedrock` | `bedrock` or `voyage` |
| `TAVILY_API_KEY` | No | — | Enables `search_web` tool |

See [docs/configuration.md](docs/configuration.md) for the complete reference of 50+ configuration variables.

## Development

```bash
git clone https://github.com/mongodb-partners/memory-mcp.git
cd memory-mcp
pip install -e ".[dev]"
pytest
```

See [docs/developer-guide.md](docs/developer-guide.md) for project structure, conventions, and common tasks.

## Deployment

```bash
docker compose up -d
```

See [docs/deployment.md](docs/deployment.md) for Docker configuration, health checks, and production settings.

## License

See the LICENSE file for details.

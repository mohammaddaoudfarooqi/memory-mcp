"""Entry point: python -m memory_mcp."""

from memory_mcp.server import mcp


def main():
    """CLI entry point for ``memory-mcp`` script."""
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

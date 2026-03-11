FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata and source so pip install works
COPY pyproject.toml .
COPY __init__.py .
COPY __main__.py .
COPY server.py .
COPY core/ core/
COPY providers/ providers/
COPY services/ services/
COPY tools/ tools/
COPY utils/ utils/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["memory-mcp"]

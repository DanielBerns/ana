FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# Install Firefox/Geckodriver for the SeleniumExtractor
RUN apt-get update && apt-get install -y firefox-esr wget && \
    wget https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-linux64.tar.gz && \
    tar -zxf geckodriver-v0.34.0-linux64.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    rm geckodriver-v0.34.0-linux64.tar.gz

# Copy the entire workspace (monorepo) structure
COPY pyproject.toml uv.lock README.md ./
COPY packages/shared packages/shared
# COPY apps/edge/etl apps/edge/etl
COPY apps apps

# Sync the entire workspace with frozen lockfile
RUN uv sync --frozen --no-cache --all-packages

# ENV PATH="/app/.venv/bin:$PATH"
# ENV PYTHONPATH="/app/apps/edge/etl/src:/app/packages/shared/src"

# Run with proper module path - use the package name 'etl'
CMD ["uv", "run", "--package", "etl", "faststream", "run", "etl.main:app"]

FROM python:3.14-slim

# Install uv directly from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy the workspace configuration and lockfile
COPY pyproject.toml uv.lock ./

# Copy the source code for the entire monorepo
COPY packages/ packages/
COPY apps/ apps/

# Sync the ENTIRE workspace into the container (production mode)
RUN uv sync --frozen --no-dev --all-packages

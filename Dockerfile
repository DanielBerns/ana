FROM python:3.14-slim

# Install uv directly from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy the workspace configuration and lockfile
COPY pyproject.toml uv.lock ./

# Copy the source code for the entire monorepo
COPY packages/ packages/
COPY apps/ apps/

# Sync the entire workspace into the container (production mode)
RUN uv sync --frozen --no-dev

# We don't set a CMD here because docker-compose will override it
# depending on which microservice it is spinning up.

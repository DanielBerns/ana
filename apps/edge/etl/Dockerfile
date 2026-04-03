FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# Install Firefox/Geckodriver for the SeleniumExtractor
RUN apt-get update && apt-get install -y firefox-esr wget && \
    wget https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-linux64.tar.gz && \
    tar -zxf geckodriver-v0.34.0-linux64.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    rm geckodriver-v0.34.0-linux64.tar.gz

COPY pyproject.toml uv.lock ./
COPY packages/shared packages/shared
COPY apps/edge/etl apps/edge/etl

RUN uv sync --frozen --no-cache
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/edge/etl/src:/app/packages/shared/src"

CMD ["uv", "run", "faststream", "run", "etl.main:app"]

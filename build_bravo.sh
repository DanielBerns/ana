#!/usr/bin/env bash

# Initialize the project (creates pyproject.toml and .python-version)
uv init --app

# Add core runtime dependencies
uv add faststream[rabbit] edgedb aiofiles rocketry pydantic pydantic-settings typer pyyaml

# Add development and testing dependencies
uv add --dev pytest pytest-asyncio ruff testcontainers

warning: The package `faststream==0.6.7` does not have an extra named `rabbitmq`
hint: This error likely indicates that you need to install a library that provides "Python.h" for `edgedb@2.2.0`

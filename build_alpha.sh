#!/usr/bin/env bash

# Initialize the project directories
mkdir -p src/{domain,adapters,ports,agents}
mkdir -p cli
mkdir -p tests/{unit,integration,e2e}
mkdir -p config
mkdir -p storage/local_repo  # For aiofiles local storage

# Create empty init files for Python packages
touch src/__init__.py src/domain/__init__.py src/adapters/__init__.py src/ports/__init__.py src/agents/__init__.py
touch cli/__init__.py tests/__init__.py

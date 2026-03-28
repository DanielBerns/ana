ana/
├── pyproject.toml            # The root workspace configuration
├── uv.lock                   # The single, unified lockfile for the whole system
├── docker-compose.yml        # To spin up RabbitMQ and your databases locally
├── packages/
│   └── shared/               # Pure Python! Pydantic models, event schemas, logging setup
│       ├── pyproject.toml
│       └── src/shared/
└── apps/
    ├── configurator/         # Dynamic config server
    ├── store/                # Blob storage with TTL
    ├── interface/            # Sensory boundary & Chat Bridge
    ├── controller/           # Decision engine
    ├── actor/                # Execution engine
    ├── memory/               # Context and records database
    └── inspector/            # inspector dashboard

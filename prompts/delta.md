# Ana: Autonomous Event-Driven Agent

## Context

Ana is an event-driven, microservice-based AI system built with Hexagonal Architecture. It autonomously scrapes web data, processes RSS feeds, archives artifacts, and features a conversational AI loop, all orchestrated through a RabbitMQ event bus and backed by PostgreSQL.

The system is designed for complete environment isolation. You can run multiple separate "instances" (e.g., `devel`, `testing`, `prod`) on the same machine, each with its own dedicated database, RabbitMQ virtual host, and configuration files.

## Petition

Review the system:
1. look for typos, coding bad practices, and dead code
2. analyze the system architecture, and compare with the stated context
3. Suggest possible refactorings for review before doing changes.
4. Suggest improvements and new features.

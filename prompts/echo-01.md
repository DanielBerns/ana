# Ana: Autonomous Event-Driven Agent

## Context

Ana is an event-driven, microservice-based AI system built with Hexagonal Architecture. It autonomously scrapes web data, processes RSS feeds, archives artifacts, and features a conversational AI loop, all orchestrated through a RabbitMQ event bus and backed by PostgreSQL.

The system is designed for complete environment isolation. You can run multiple separate "instances" (e.g., `devel`, `testing`, `prod`) on the same machine, each with its own dedicated database, RabbitMQ virtual host, and configuration files.

## Petition

There are some credentials in the docker-compose.yml. For example, it would be nice the following fix

### Example Docker Credential Fix:
```yaml
# docker-compose.yml
rabbitmq:
  environment:
    RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASS:-guest}
```

a) Is it possible to move those credentials to an .env file located at ~/ana/.env?
b) Is it possible to make some changes to the makefile, adding targets for creating .env files and validating configurations?


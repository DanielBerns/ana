#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

INSTANCE=$1

if [ -z "$INSTANCE" ]; then
  echo "Error: You must provide an instance name."
  echo "Usage: ./provision.sh <instance_name>"
  exit 1
fi

echo "=========================================="
echo " Provisioning Infrastructure for: $INSTANCE"
echo "=========================================="

# Variables updated to match your docker-compose.yml exactly
PG_SERVICE="postgres"
PG_USER="ana_admin"
PG_DEFAULT_DB="ana_db"
RMQ_SERVICE="rabbitmq"
RMQ_USER="guest"

# 1. Provision PostgreSQL Database
DB_NAME="ana_${INSTANCE}"
echo "[1/2] Creating PostgreSQL Database: $DB_NAME..."
# Connect to the default ana_db to execute the creation command
docker compose exec -T $PG_SERVICE psql -U $PG_USER -d $PG_DEFAULT_DB -c "CREATE DATABASE $DB_NAME;" || true

# 2. Provision RabbitMQ Virtual Host
echo "[2/2] Creating RabbitMQ vhost: $INSTANCE..."
docker compose exec -T $RMQ_SERVICE rabbitmqctl add_vhost $INSTANCE || true
docker compose exec -T $RMQ_SERVICE rabbitmqctl set_permissions -p $INSTANCE $RMQ_USER ".*" ".*" ".*"

echo "=========================================="
echo " Success! $INSTANCE is ready to roll."
echo "=========================================="

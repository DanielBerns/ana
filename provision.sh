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

# Variables (Adjust these if your docker-compose.yml uses different service names)
PG_SERVICE="postgres"
PG_USER="admin"
RMQ_SERVICE="rabbitmq"
RMQ_USER="guest"

# 1. Provision PostgreSQL Database
DB_NAME="ana_${INSTANCE}"
echo "[1/2] Creating PostgreSQL Database: $DB_NAME..."
# We use '|| true' so the script doesn't crash if the database already exists
docker compose exec -T $PG_SERVICE psql -U $PG_USER -c "CREATE DATABASE $DB_NAME;" || true

# 2. Provision RabbitMQ Virtual Host
echo "[2/2] Creating RabbitMQ vhost: $INSTANCE..."
# Create the vhost
docker compose exec -T $RMQ_SERVICE rabbitmqctl add_vhost $INSTANCE || true
# Grant the guest user full permissions to the new vhost
docker compose exec -T $RMQ_SERVICE rabbitmqctl set_permissions -p $INSTANCE $RMQ_USER ".*" ".*" ".*"

echo "=========================================="
echo " Success! $INSTANCE is ready to roll."
echo "=========================================="

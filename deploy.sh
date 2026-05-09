#!/bin/bash
# Run this script ON the Timeweb server after first setup
set -e

echo "==> Pulling latest code..."
git pull origin main

echo "==> Rebuilding Docker image..."
docker compose build --no-cache

echo "==> Restarting bot..."
docker compose down
docker compose up -d

echo "==> Done! Logs:"
docker compose logs --tail=20

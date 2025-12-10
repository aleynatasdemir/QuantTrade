#!/bin/bash
# QuantTrade Deployment Script
# Usage: ./scripts/deploy.sh

set -e

echo "======================================"
echo "QuantTrade Docker Deployment"
echo "======================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Copy .env.docker to .env and fill in the values"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Pull latest code (if git repo)
if [ -d .git ]; then
    echo ">> Pulling latest code..."
    git pull origin main
fi

# Build and start services
echo ">> Building Docker images..."
docker-compose build --no-cache

echo ">> Starting services..."
docker-compose up -d

# Wait for services to be ready
echo ">> Waiting for services to start..."
sleep 10

# Health check
echo ">> Checking service health..."
docker-compose ps

# Show logs
echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "Services:"
echo "  Frontend: http://$(hostname -I | awk '{print $1}')"
echo "  Backend:  http://$(hostname -I | awk '{print $1}'):8000"
echo "  Database: localhost:5432"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f          # View all logs"
echo "  docker-compose logs -f backend  # View backend logs"
echo "  docker-compose logs -f telegram # View telegram logs"
echo "  docker-compose restart          # Restart all services"
echo "  docker-compose down             # Stop all services"
echo ""

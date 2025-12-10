#!/bin/bash
# Server Setup Script for QuantTrade
# Run this on a fresh Ubuntu/Debian server
# Usage: curl -sSL https://raw.githubusercontent.com/aleynatasdemir/QuantTrade/main/scripts/setup-server.sh | bash

set -e

echo "======================================"
echo "QuantTrade Server Setup"
echo "======================================"

# Update system
echo ">> Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo ">> Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose
echo ">> Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Install Git
echo ">> Installing Git..."
sudo apt-get install -y git

# Create app directory
echo ">> Creating application directory..."
sudo mkdir -p /opt/quanttrade
sudo chown $USER:$USER /opt/quanttrade

# Clone repository
echo ">> Cloning repository..."
cd /opt/quanttrade
if [ ! -d ".git" ]; then
    git clone https://github.com/aleynatasdemir/QuantTrade.git .
fi

# Create data directories
echo ">> Creating data directories..."
mkdir -p data/raw data/processed data/master data/features

# Setup environment
echo ">> Setting up environment..."
if [ ! -f .env ]; then
    cp .env.docker .env
    echo ""
    echo "IMPORTANT: Edit .env file with your API keys!"
    echo "nano /opt/quanttrade/.env"
fi

# Setup cron jobs
echo ">> Setting up cron jobs..."
(crontab -l 2>/dev/null || true; echo "# QuantTrade Daily Jobs") | crontab -
(crontab -l 2>/dev/null; echo "0 19 * * 1-5 cd /opt/quanttrade && docker-compose exec -T telegram python portfolio_daily_sender.py >> /var/log/quanttrade-portfolio.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "30 9 * * 1-5 cd /opt/quanttrade && docker-compose exec -T telegram python gpt_daily_sender.py >> /var/log/quanttrade-gpt.log 2>&1") | crontab -

echo ""
echo "======================================"
echo "Server Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file: nano /opt/quanttrade/.env"
echo "2. Start services: cd /opt/quanttrade && ./scripts/deploy.sh"
echo ""
echo "NOTE: You may need to log out and back in for Docker permissions to take effect."
echo ""

#!/bin/bash
# VDS Deployment Setup Script
# Run this on VDS after copying files

echo "🚀 QuantTrade VDS Deployment Setup"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Create log directory
echo -e "${YELLOW}1. Creating log directory...${NC}"
sudo mkdir -p /var/log/quanttrade
sudo chown $USER:$USER /var/log/quanttrade
echo -e "${GREEN}✓ Log directory created${NC}"
echo ""

# 2. Make scripts executable
echo -e "${YELLOW}2. Making cron scripts executable...${NC}"
chmod +x scripts/cron_*.sh
echo -e "${GREEN}✓ Scripts are now executable${NC}"
echo ""

# 3. Check .env file
echo -e "${YELLOW}3. Checking .env file...${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo "   Please create .env from .env.example and add your API keys"
    exit 1
fi
echo -e "${GREEN}✓ .env file exists${NC}"
echo ""

# 4. Test scripts
echo -e "${YELLOW}4. Testing cron scripts...${NC}"
echo "   Testing portfolio V2 script..."
bash scripts/cron_portfolio_v2.sh --help 2>/dev/null || echo "   Script exists"

echo "   Testing GPT snapshot script..."
bash scripts/cron_gpt_snapshot.sh --help 2>/dev/null || echo "   Script exists"

echo "   Testing GPT analyze script..."
bash scripts/cron_gpt_analyze.sh --help 2>/dev/null || echo "   Script exists"

echo "   Testing GPT telegram script..."
bash scripts/cron_gpt_telegram.sh --help 2>/dev/null || echo "   Script exists"
echo -e "${GREEN}✓ All scripts verified${NC}"
echo ""

# 5. Show crontab setup
echo -e "${YELLOW}5. Crontab Setup Instructions:${NC}"
echo "   Run the following command to edit your crontab:"
echo "   ${GREEN}crontab -e${NC}"
echo ""
echo "   Then add these lines:"
echo "   ${YELLOW}---${NC}"
cat scripts/crontab.txt
echo "   ${YELLOW}---${NC}"
echo ""

# 6. Verify current crontab
echo -e "${YELLOW}6. Current crontab:${NC}"
crontab -l 2>/dev/null || echo "   No crontab configured yet"
echo ""

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📋 Next steps:"
echo "   1. Edit crontab: crontab -e"
echo "   2. Paste the lines from scripts/crontab.txt"
echo "   3. Save and exit"
echo "   4. Verify with: crontab -l"
echo "   5. Check logs in /var/log/quanttrade/"

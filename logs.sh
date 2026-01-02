#!/bin/bash

# Configuration
SERVER="root@104.248.224.80"
PM2_ID="25"

echo "📡 Connecting to $SERVER to listen to PM2 logs for ID $PM2_ID..."
echo "💡 Press Ctrl+C to stop listening and exit."
echo ""

# SSH and run pm2 logs with robust environment loading
ssh -t $SERVER "bash -i -c '
  [ -f ~/.bashrc ] && source ~/.bashrc;
  [ -f ~/.nvm/nvm.sh ] && source ~/.nvm/nvm.sh;
  pm2 logs $PM2_ID
'"

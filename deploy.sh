#!/bin/bash

# Configuration
SERVER="root@104.248.224.80"
APP_DIR="/applications/techvando-slack-automation"
PM2_ID="25"
DISK_THRESHOLD=90

echo "🚀 Starting deployment to $SERVER..."

# Execute commands on server
# We use << 'EOF' (quoted) to prevent local expansion of variables like $DISK_USAGE
ssh -t $SERVER "bash -i" << 'EOF'
  # Load full environment if bash -i isn't enough
  [ -f ~/.bashrc ] && source ~/.bashrc
  [ -f ~/.profile ] && source ~/.profile
  [ -f ~/.nvm/nvm.sh ] && source ~/.nvm/nvm.sh
  
  echo "🔍 Checking server health..."
  DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
  
  # Note: DISK_THRESHOLD is local, so we hardcode 90 here or it will be empty
  if [ "$DISK_USAGE" -gt 90 ]; then
    echo "⚠️ WARNING: Disk usage is at ${DISK_USAGE}%! Consider cleaning up space soon."
  else
    echo "✅ Disk usage is at ${DISK_USAGE}%."
  fi

  echo "📂 Navigating to /applications/techvando-slack-automation..."
  cd /applications/techvando-slack-automation || exit

  echo "⬇️ Pulling latest changes from develop..."
  git pull origin develop

  echo "🔄 Restarting PM2 process 25..."
  # If pm2 still can't find node, we try to locate it
  if ! command -v pm2 &> /dev/null; then
    echo "❌ Error: pm2 could not be found. Checking PATH..."
    echo "PATH is: $PATH"
    exit 1
  fi
  
  pm2 restart 25

  echo "📊 PM2 Status:"
  pm2 status 25

  echo "🚪 Exiting server..."
EOF

echo "✅ Deployment script finished."

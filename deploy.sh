#!/bin/bash

# Configuration
SERVER="root@104.248.224.80"
APP_DIR="/applications/techvando-slack-automation"
PM2_ID="25"

echo "🚀 Starting deployment to $SERVER..."

# Execute commands on server
ssh -t $SERVER << EOF
  echo "📂 Navigating to $APP_DIR..."
  cd $APP_DIR || exit

  echo "⬇️ Pulling latest changes from develop..."
  git pull origin develop

  echo "🔄 Restarting PM2 process $PM2_ID..."
  pm2 restart $PM2_ID

  echo "📊 PM2 Status:"
  pm2 status $PM2_ID

  echo "📜 Showing recent logs (Ctrl+C to exit logs)..."
  pm2 logs $PM2_ID --lines 20 --no-daemon
EOF

echo "✅ Deployment script finished."

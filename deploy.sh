#!/bin/bash

# Configuration
SERVER="root@104.248.224.80"
APP_DIR="/applications/techvando-slack-automation"
PM2_ID="25"
DISK_THRESHOLD=90

echo "🚀 Starting deployment to $SERVER..."

# Execute commands on server using a login shell to ensure PATH is loaded
ssh -t $SERVER "bash -l" << EOF
  echo "🔍 Checking server health..."
  DISK_USAGE=\$(df / | tail -1 | awk '{print \$5}' | sed 's/%//')
  if [ "\$DISK_USAGE" -gt "$DISK_THRESHOLD" ]; then
    echo "⚠️ WARNING: Disk usage is at \${DISK_USAGE}%! Consider cleaning up space soon."
  else
    echo "✅ Disk usage is at \${DISK_USAGE}%."
  fi

  echo "📂 Navigating to $APP_DIR..."
  cd $APP_DIR || exit

  echo "⬇️ Pulling latest changes from develop..."
  git pull origin develop

  echo "🔄 Restarting PM2 process $PM2_ID..."
  pm2 restart $PM2_ID

  echo "📊 PM2 Status:"
  pm2 status $PM2_ID

  echo "📜 Showing last 20 lines of logs..."
  # Get the out log path and tail it
  OUT_LOG=$(pm2 show $PM2_ID | grep "out log path" | awk '{print $NF}')
  ERR_LOG=$(pm2 show $PM2_ID | grep "error log path" | awk '{print $NF}')
  
  echo "--- Output Log ---"
  tail -n 15 "$OUT_LOG"
  echo "--- Error Log ---"
  tail -n 15 "$ERR_LOG"

  echo "🚪 Exiting server..."
  exit
EOF

echo "✅ Deployment script finished."

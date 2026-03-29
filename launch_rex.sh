#!/bin/bash
# Kill any existing Rex or tunnel instances
pkill -f "streamlit run" 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
pkill -f "oauth_callback_server" 2>/dev/null

# Always run from the project directory so rex.db and .env resolve correctly
cd /Users/bigdaddy/Desktop/AI/rex-mac

# Start the OAuth callback server on port 8502.
# The Cloudflare tunnel routes rex.myeasyapp.com → localhost:8502.
# This lightweight server handles OAuth callbacks (code exchange + token save)
# then redirects the browser to localhost:8501 where Streamlit works properly.
/Library/Developer/CommandLineTools/usr/bin/python3 oauth_callback_server.py \
  >> /tmp/oauth_callback.log 2>&1 &

# Start Cloudflare tunnel (routes rex.myeasyapp.com → localhost:8502)
/opt/homebrew/bin/cloudflared tunnel run --token eyJhIjoiN2E0ZjkwMWZjNTkyYTM1ODJiNzRlMzU1ZjZhNDFiZDYiLCJzIjoiZlV0VnpyVDdDSUlzMGlIbHk2c3J3Vkh0WEc4YlZRVm44RVZDdTVZVG0xMD0iLCJ0IjoiNDRhMDFiZjktNWQyMy00Y2IyLTg1MzYtOGRhODMyY2EwYzVmIn0= >> /tmp/cloudflared.log 2>&1 &

# Launch Streamlit in the background
/Library/Developer/CommandLineTools/usr/bin/python3 -m streamlit run \
  app.py \
  >> /tmp/rex.log 2>&1 &

# Wait until the server is ready (up to 15 seconds)
for i in $(seq 1 15); do
  sleep 1
  if curl -s http://localhost:8501 > /dev/null; then
    break
  fi
done

# Open in browser
open http://localhost:8501

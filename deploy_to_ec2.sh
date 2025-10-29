#!/usr/bin/env bash
set -euo pipefail

# AWS EC2 Deployment Script for Flight Network Diagnostics Server
# Usage: ./deploy_to_ec2.sh <EC2_IP> [profile_name]
#
# Examples:
#   ./deploy_to_ec2.sh 3.123.45.67 idle-reset-probe
#   ./deploy_to_ec2.sh ec2-3-123-45-67.compute-1.amazonaws.com

EC2_IP=${1:-}
PROFILE=${2:-idle-reset-probe}
KEY_FILE=${3:-~/.ssh/id_rsa}

if [ -z "$EC2_IP" ]; then
    echo "Usage: $0 <EC2_IP> [profile_name] [key_file]"
    echo "Example: $0 3.123.45.67 idle-reset-probe ~/.ssh/my-key.pem"
    exit 1
fi

echo "🚀 Deploying Flight Server to EC2 instance: $EC2_IP"
echo "📋 Using profile: $PROFILE"
echo "🔑 Using key file: $KEY_FILE"

# Create deployment package
echo "📦 Creating deployment package..."
tar -czf flight-server-deploy.tar.gz \
    server/ \
    shared/ \
    profiles/ \
    requirements.txt \
    --exclude="*.log" \
    --exclude="__pycache__" \
    --exclude=".venv"

# Copy files to EC2
echo "📤 Copying files to EC2..."
scp -i "$KEY_FILE" flight-server-deploy.tar.gz ubuntu@$EC2_IP:~/

# Deploy and run on EC2
echo "🔧 Installing and starting server on EC2..."
ssh -i "$KEY_FILE" ubuntu@$EC2_IP << EOF
    set -euo pipefail
    
    # Extract files
    tar -xzf flight-server-deploy.tar.gz
    
    # Install system dependencies
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip
    
    # Create virtual environment and install Python dependencies
    cd server
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Create logs directory
    mkdir -p logs
    
    # Start server with specified profile (run in background)
    echo "🚀 Starting Flight server with profile: $PROFILE"
    nohup python flight_server.py --config ../profiles/$PROFILE/server.yaml > logs/server_output.log 2>&1 &
    
    # Wait a moment and check if server started
    sleep 3
    if pgrep -f "flight_server.py" > /dev/null; then
        echo "✅ Server started successfully!"
        echo "📊 Server is running on port 8815"
        echo "📝 Logs: ~/server/logs/"
    else
        echo "❌ Server failed to start. Check logs:"
        tail -20 logs/server_output.log
        exit 1
    fi
EOF

# Clean up local deployment package
rm flight-server-deploy.tar.gz

echo ""
echo "🎉 Deployment complete!"
echo "📍 Server running at: $EC2_IP:8815"
echo "📋 Profile: $PROFILE"
echo ""
echo "🔍 To check server status:"
echo "   ssh -i $KEY_FILE ubuntu@$EC2_IP 'pgrep -f flight_server.py && echo \"Server running\" || echo \"Server not running\"'"
echo ""
echo "📝 To view server logs:"
echo "   ssh -i $KEY_FILE ubuntu@$EC2_IP 'tail -f server/logs/server_output.log'"
echo ""
echo "🛑 To stop server:"
echo "   ssh -i $KEY_FILE ubuntu@$EC2_IP 'pkill -f flight_server.py'"

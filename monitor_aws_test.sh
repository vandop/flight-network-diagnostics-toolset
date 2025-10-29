#!/usr/bin/env bash
set -euo pipefail

# AWS Idle Test Monitor
# Usage: ./monitor_aws_test.sh <EC2_IP> [key_file]

EC2_IP=${1:-}
KEY_FILE=${2:-~/.ssh/id_rsa}

if [ -z "$EC2_IP" ]; then
    echo "Usage: $0 <EC2_IP> [key_file]"
    echo "Example: $0 3.123.45.67 ~/.ssh/my-key.pem"
    exit 1
fi

echo "📊 AWS Idle Timeout Test Monitor"
echo "🎯 EC2 Server: $EC2_IP"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Function to get server status
get_server_status() {
    ssh -i "$KEY_FILE" ubuntu@$EC2_IP 'pgrep -f flight_server.py > /dev/null && echo "✅ Running" || echo "❌ Stopped"' 2>/dev/null || echo "🔌 Connection failed"
}

# Function to get latest server log entries
get_server_logs() {
    ssh -i "$KEY_FILE" ubuntu@$EC2_IP 'tail -5 server/logs/aws_idle_test_server.log 2>/dev/null || echo "No server logs yet"' 2>/dev/null
}

# Function to get client log summary
get_client_summary() {
    if [ -f "clients/python/logs/aws_idle_test_client.log" ]; then
        echo "📈 Client Progress:"
        tail -3 clients/python/logs/aws_idle_test_client.log | grep -E "(Sending message|completed|Idle)" || echo "No recent client activity"
    else
        echo "📈 Client: Not started yet"
    fi
}

# Monitor loop
while true; do
    clear
    echo "📊 AWS Idle Timeout Test Monitor - $(date)"
    echo "🎯 EC2 Server: $EC2_IP"
    echo "=================================="
    echo ""
    
    echo "🖥️  Server Status: $(get_server_status)"
    echo ""
    
    echo "📝 Latest Server Logs:"
    get_server_logs
    echo ""
    
    get_client_summary
    echo ""
    
    echo "🔄 Refreshing in 10 seconds... (Ctrl+C to stop)"
    sleep 10
done

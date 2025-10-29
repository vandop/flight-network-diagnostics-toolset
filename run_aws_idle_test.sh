#!/usr/bin/env bash
set -euo pipefail

# AWS Idle Timeout Test Runner
# Usage: ./run_aws_idle_test.sh <EC2_IP>

EC2_IP=${1:-}

if [ -z "$EC2_IP" ]; then
    echo "Usage: $0 <EC2_IP>"
    echo "Example: $0 3.123.45.67"
    exit 1
fi

echo "🧪 Starting AWS Idle Timeout Test"
echo "🎯 Target EC2 Server: $EC2_IP:8815"
echo ""

# Update client config with EC2 IP
sed "s/REPLACE_WITH_EC2_IP/$EC2_IP/g" profiles/aws-idle-test/client.yaml > /tmp/aws_client_config.yaml

# Test connectivity first
echo "🔍 Testing connectivity to EC2 server..."
if timeout 5 bash -c "</dev/tcp/$EC2_IP/8815"; then
    echo "✅ Connection to $EC2_IP:8815 successful"
else
    echo "❌ Cannot connect to $EC2_IP:8815"
    echo "   Check:"
    echo "   - EC2 instance is running"
    echo "   - Security group allows port 8815"
    echo "   - Flight server is running on EC2"
    exit 1
fi

echo ""
echo "🚀 Starting client test..."
echo "📊 This will test progressively longer idle periods:"
echo "   - Start: 1 minute idle"
echo "   - Multiplier: 1.2x each iteration"
echo "   - Max: 30 minutes idle"
echo "   - Total iterations: 20"
echo ""
echo "⏱️  Expected AWS idle timeout: ~350-400 seconds (5-7 minutes)"
echo "📝 Watch for connection resets around that time"
echo ""

# Setup Python environment if needed
if [ ! -d "clients/python/.venv" ]; then
    echo "🔧 Setting up Python environment..."
    cd clients/python
    ./setup_env.sh
    cd ../..
fi

# Create logs directory
mkdir -p clients/python/logs

# Run the test
cd clients/python
source .venv/bin/activate
python flight_client.py --config /tmp/aws_client_config.yaml

echo ""
echo "🎉 Test completed!"
echo "📝 Check logs at: clients/python/logs/aws_idle_test_client.log"
echo ""
echo "🔍 To analyze results:"
echo "   grep -E '(Idle|completed|failed|reset|timeout)' clients/python/logs/aws_idle_test_client.log"

# AWS Idle Timeout Testing Guide

This guide helps you test real-world AWS idle timeouts by running the Flight server on EC2 and the client on your local machine.

## 🎯 What This Tests

- **AWS Network Infrastructure**: How AWS handles idle TCP connections
- **Expected Behavior**: AWS typically resets idle connections after ~350-400 seconds (5-7 minutes)
- **Real-World Scenario**: Client-server communication across AWS network boundaries

## 📋 Prerequisites

1. **AWS Account** with EC2 access
2. **SSH Key Pair** for EC2 access
3. **Local Machine** with this repository cloned

## 🚀 Step-by-Step Setup

### Step 1: Launch EC2 Instance

1. **Launch Ubuntu 22.04 LTS instance** (t3.micro is sufficient)
2. **Configure Security Group**:
   ```
   Type: SSH
   Port: 22
   Source: Your IP
   
   Type: Custom TCP  
   Port: 8815
   Source: Your IP (or 0.0.0.0/0 for testing)
   ```
3. **Note the Public IP** (e.g., `3.123.45.67`)

### Step 2: Deploy Server to EC2

```bash
# Deploy server with idle-reset-probe profile
./deploy_to_ec2.sh <EC2_PUBLIC_IP> aws-idle-test ~/.ssh/your-key.pem

# Example:
./deploy_to_ec2.sh 3.123.45.67 aws-idle-test ~/.ssh/my-aws-key.pem
```

### Step 3: Run Local Client Test

```bash
# Start the idle timeout test
./run_aws_idle_test.sh <EC2_PUBLIC_IP>

# Example:
./run_aws_idle_test.sh 3.123.45.67
```

### Step 4: Monitor the Test (Optional)

In a separate terminal:
```bash
# Monitor server and client status
./monitor_aws_test.sh <EC2_PUBLIC_IP> ~/.ssh/your-key.pem
```

## 📊 What to Expect

### Test Progression
- **Message 1**: 1 minute idle → Should succeed
- **Message 2**: 1.2 minutes idle → Should succeed  
- **Message 3**: 1.44 minutes idle → Should succeed
- **...continuing with 1.2x multiplier...**
- **Message ~8-10**: ~5-7 minutes idle → **Expected to fail with connection reset**

### AWS Idle Timeout Behavior
- **Typical timeout**: 350-400 seconds (5-7 minutes)
- **Symptoms**: Connection reset, gRPC errors
- **Recovery**: Client should reconnect and continue

## 📝 Analyzing Results

### Check Client Logs
```bash
# View full client log
cat clients/python/logs/aws_idle_test_client.log

# Filter for key events
grep -E "(Idle|completed|failed|reset|timeout|reconnect)" clients/python/logs/aws_idle_test_client.log
```

### Check Server Logs
```bash
# SSH to EC2 and check server logs
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>
tail -f server/logs/aws_idle_test_server.log
```

## 🔍 Key Metrics to Look For

1. **Idle Duration Before Failure**: How long was the connection idle before reset?
2. **Error Type**: Connection reset, timeout, or gRPC error?
3. **Recovery Time**: How quickly did the client reconnect?
4. **Consistency**: Does the timeout happen at the same idle duration repeatedly?

## 🛠️ Troubleshooting

### Server Won't Start
```bash
# Check server status
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP> 'pgrep -f flight_server.py'

# View server startup logs
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP> 'cat server/logs/server_output.log'
```

### Client Can't Connect
```bash
# Test basic connectivity
telnet <EC2_IP> 8815

# Check security group allows port 8815
# Check EC2 instance is running
```

### Stop Server
```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP> 'pkill -f flight_server.py'
```

## 🧪 Advanced Testing

### Test Different Profiles
```bash
# Test with gRPC keepalives
./deploy_to_ec2.sh <EC2_IP> grpc-keepalive-60s

# Test with TCP keepalives  
./deploy_to_ec2.sh <EC2_IP> tcp-keepalive-60s
```

### Modify Idle Intervals
Edit `profiles/aws-idle-test/client.yaml`:
```yaml
interval:
  strategy: multiplier
  initial_ms: 30000      # Start with 30 seconds
  multiplier: 1.5        # Faster progression
  max_ms: 600000         # Max 10 minutes
```

## 📈 Expected Results

You should see AWS reset connections after approximately **5-7 minutes** of idle time, which is consistent with AWS's documented network timeout behavior for idle TCP connections.

This test will help you understand:
- Real-world AWS network behavior
- How your applications should handle connection resets
- Whether keepalive strategies effectively prevent timeouts

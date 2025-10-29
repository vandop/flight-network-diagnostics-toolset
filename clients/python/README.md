# Python Flight Client

This client connects to the configurable Flight echo server and repeatedly sends a
message while exercising various networking options and delay strategies.

## Quick start

```bash
cd clients/python
./setup_env.sh
source .venv/bin/activate
python flight_client.py --config config.yaml
```

Edit `config.yaml` to control the message payload, repetition count, delay strategy,
interval strategy, and gRPC/TCP networking options. Set `continue_on_failure` to keep
iterating after a mid-run disconnect and `reconnect_on_failure` to force a brand new
channel for the next attempt—handy when probing for idle resets. The client logs every
request and response to both stdout and the configured log file. Ready-made
configurations for common experiments live in `profiles/`.

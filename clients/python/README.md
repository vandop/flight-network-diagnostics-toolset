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
interval strategy, and gRPC networking options. The client logs every request and
response to both stdout and the configured log file.

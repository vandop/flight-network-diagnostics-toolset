# Flight Echo Server

This server wraps the Apache Arrow Flight server implementation with a YAML-driven
configuration file so you can exercise various gRPC and TCP keep-alive settings. It
logs every message to both the console and the configured log file and applies
configurable reply delays.

## Quick start

```bash
cd server
./setup_env.sh
source .venv/bin/activate
python flight_server.py --config config.yaml
```

The default configuration listens on `0.0.0.0:8815`. You can edit `config.yaml`
to change the host, port, logging, delay strategy, and gRPC/TCP settings.

## Delay behaviour

The `delay` section in the configuration controls how long the server waits before
replying. Strategies:

- `fixed`: respond with the same delay every time.
- `linear`: increment the delay by `linear_increment_ms` each time.
- `multiplier`: multiply the delay by `multiplier` each time.
- `exponential`: raise `exponential_base` to the power of the previous delay (in seconds).

Requests may also override the delay via headers (`x-delay-*`) if
`allow_header_overrides` is set to `true` in the configuration.

## Deployment helpers

The `deploy/` directory contains thin convenience scripts for Debian/Ubuntu based
cloud images:

- `deploy_aws.sh`
- `deploy_azure.sh`
- `deploy_gcp.sh`

Each script installs Python, bootstraps a virtual environment, installs
requirements, and launches the server with the given configuration file path.

# Flight Network Diagnostics Toolset

This repository contains a configurable Apache Arrow Flight server and matching
clients designed to stress-test TCP and gRPC keep-alive settings. The components
make it easy to simulate different message cadences, reply delays, and connection
options so you can observe how proxies and network appliances behave over time.

## Repository layout

- `server/` – Configurable Flight echo server with deployment helpers for AWS, Azure, and GCP.
- `clients/python/` – Python Flight client exercising the server.
- `shared/` – Utilities shared between the server and clients.
- `tests/` – Integration test that launches the server and client together.

## Integration test

After creating the virtual environments (`server/setup_env.sh` and
`clients/python/setup_env.sh`), run the integration test from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt -r clients/python/requirements.txt pytest
pytest
```

The integration test starts the server and client locally with their default
configurations and asserts that they exchange at least one message.

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
- `profiles/` – Ready-to-run client/server configuration pairs covering common
  keep-alive scenarios.

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

## Docker Compose quickstart

To experiment without installing dependencies locally, build and run the
included Docker Compose stack from the repository root:

```bash
docker compose up --build
```

The compose file launches the Flight server and client in separate containers,
rewriting their configuration files at runtime so they talk to each other over
the internal Docker network. Logs from both services stream to the console.

To exercise one of the documented profiles, point the services at the matching
configuration pair using environment variables. For example, to run the
`no-keepalive-exponential` scenario:

```bash
SERVER_CONFIG=profiles/no-keepalive-exponential/server.yaml \
CLIENT_CONFIG=profiles/no-keepalive-exponential/client.yaml \
docker compose up --build
```

You can swap in any of the other profile directories the same way. When the
client finishes its configured repetitions, stop the stack with `Ctrl+C`.

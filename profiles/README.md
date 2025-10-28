# Scenario Profiles

The `profiles/` directory packages ready-to-run client and server configuration
pairs so you can exercise different combinations of gRPC and TCP keep-alive
behaviour together with long running delay/interval strategies. Each scenario
contains a `server.yaml` and `client.yaml` file that can be supplied directly to
`server/flight_server.py` and `clients/python/flight_client.py`.

All scenarios use exponential growth (implemented via the multiplier delay
strategy) with one-minute starting values so the cadence between requests grows
significantly over time. Adjust the `initial_ms`, `multiplier`, or `max_ms`
fields to tailor the pacing for your environment.

| Scenario | Description |
| --- | --- |
| `no-keepalive-exponential` | Baseline configuration without TCP or gRPC keep-alives. |
| `grpc-keepalive-1000s` | Enables 1,000 second gRPC keep-alives on both client and server. |
| `tcp-keepalive-1000s` | Enables 1,000 second TCP keep-alives on both client and server. |
| `grpc-keepalive-60s` | Enables 60 second gRPC keep-alives on both client and server. |
| `tcp-keepalive-60s` | Enables 60 second TCP keep-alives on both client and server. |

## Running a profile

From the repository root, activate your virtual environments and then provide
the scenario-specific configuration paths when launching the server and client.
For example, to try the 1,000 second gRPC keep-alive profile:

```bash
python -m server.flight_server --config profiles/grpc-keepalive-1000s/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/grpc-keepalive-1000s/client.yaml
kill $SERVER_PID
```

The sections below provide ready-to-run commands for each scenario.

### Baseline without keep-alives

```bash
python -m server.flight_server --config profiles/no-keepalive-exponential/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/no-keepalive-exponential/client.yaml
kill $SERVER_PID
```

### gRPC keep-alives every 1,000 seconds

```bash
python -m server.flight_server --config profiles/grpc-keepalive-1000s/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/grpc-keepalive-1000s/client.yaml
kill $SERVER_PID
```

### TCP keep-alives every 1,000 seconds

```bash
python -m server.flight_server --config profiles/tcp-keepalive-1000s/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/tcp-keepalive-1000s/client.yaml
kill $SERVER_PID
```

### gRPC keep-alives every 60 seconds

```bash
python -m server.flight_server --config profiles/grpc-keepalive-60s/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/grpc-keepalive-60s/client.yaml
kill $SERVER_PID
```

### TCP keep-alives every 60 seconds

```bash
python -m server.flight_server --config profiles/tcp-keepalive-60s/server.yaml &
SERVER_PID=$!
python -m clients.python.flight_client --config profiles/tcp-keepalive-60s/client.yaml
kill $SERVER_PID
```

The log paths inside each profile use descriptive filenames so you can easily
collect traces from multiple runs without overwriting earlier results.

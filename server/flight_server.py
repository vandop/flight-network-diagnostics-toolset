"""Configurable Apache Arrow Flight echo server."""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import pyarrow as pa
import pyarrow.flight as flight
import yaml

from shared.delay import DelayConfigurationError, DelayStrategy


class HeadersMiddleware(flight.ServerMiddleware):
    """Captures headers for each incoming call."""

    def __init__(self, headers: Optional[Iterable] = None) -> None:
        normalized: Dict[str, str] = {}
        for entry in headers or []:
            try:
                key, value = entry[0], entry[1]
            except (TypeError, IndexError):
                continue
            if isinstance(key, bytes):
                key_str = key.decode("utf8")
            else:
                key_str = str(key)
            if isinstance(value, bytes):
                value_str = value.decode("utf8")
            else:
                value_str = str(value)
            normalized[key_str.lower()] = value_str
        self._headers = normalized

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    def call_completed(self, exception: Optional[Exception]) -> None:  # pragma: no cover - hook for future use
        pass

    def sending_headers(self) -> Dict[bytes, bytes]:  # pragma: no cover - no-op middleware hook
        return {}


class HeadersMiddlewareFactory(flight.ServerMiddlewareFactory):
    """Factory that creates header-capturing middleware instances."""

    def start_call(self, info: flight.CallInfo, headers: List[Tuple[bytes, bytes]]) -> HeadersMiddleware:
        return HeadersMiddleware(headers)

LOGGER = logging.getLogger("flight_server")


class ConfigurationError(Exception):
    """Raised when the configuration file is invalid."""


def _load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "server" not in data:
        raise ConfigurationError("Configuration must contain a 'server' key")
    return data


def _configure_logging(log_file: Path, level: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode="a", encoding="utf8"),
        ],
    )


class EchoFlightServer(flight.FlightServerBase):
    """A Flight server that echoes payloads back to the caller."""

    def __init__(self, location: str, delay_strategy: DelayStrategy, allow_header_overrides: bool,
                 generic_options: Optional[List[Tuple[str, str]]] = None,
                 network_settings: Optional[Dict[str, object]] = None) -> None:
        middleware = {"headers": HeadersMiddlewareFactory()}
        super().__init__(location=location, middleware=middleware)
        self._delay_strategy = delay_strategy
        self._allow_header_overrides = allow_header_overrides
        self._lock = threading.Lock()
        self._network_settings = network_settings or {}
        self._generic_options = generic_options or []

    def _compute_delay(self, context: flight.ServerCallContext) -> float:
        strategy = self._delay_strategy
        if self._allow_header_overrides:
            header_strategy = self._parse_delay_overrides(context)
            if header_strategy is not None:
                strategy = header_strategy
        with self._lock:
            delay_seconds = strategy.next_delay()
        LOGGER.info("Applying delay of %.3f seconds", delay_seconds)
        return delay_seconds

    def _parse_delay_overrides(self, context: flight.ServerCallContext) -> Optional[DelayStrategy]:
        middleware = context.get_middleware("headers")
        headers = middleware.headers if middleware is not None else {}
        if not headers:
            return None

        def maybe_float(header: str) -> Optional[float]:
            value = headers.get(header)
            if value is None:
                return None
            try:
                return float(value)
            except ValueError as exc:
                raise ConfigurationError(f"Invalid float for header '{header}': {value}") from exc

        def maybe_str(header: str) -> Optional[str]:
            return headers.get(header)

        overrides = {
            "strategy": maybe_str("x-delay-strategy"),
            "initial_ms": maybe_float("x-delay-initial-ms"),
            "linear_increment_ms": maybe_float("x-delay-linear-increment-ms"),
            "multiplier": maybe_float("x-delay-multiplier"),
            "exponential_base": maybe_float("x-delay-exponential-base"),
            "max_ms": maybe_float("x-delay-max-ms"),
        }

        if all(value is None for value in overrides.values()):
            return None

        LOGGER.info("Applying header overrides: %s", json.dumps(overrides))
        return self._delay_strategy.override(**overrides)

    def do_action(self, context: flight.ServerCallContext, action: flight.Action) -> Iterable[flight.Result]:
        LOGGER.info("Received action '%s' from %s", action.type, context.peer_identity or "unknown client")
        LOGGER.info("Payload: %s", action.body.to_pybytes().decode("utf8"))

        delay_seconds = self._compute_delay(context)
        time.sleep(delay_seconds)

        metadata = {
            "delay_applied_seconds": delay_seconds,
            "strategy": self._delay_strategy.strategy,
            "server_network": self._network_settings,
        }
        result_payload = json.dumps({
            "message": action.body.to_pybytes().decode("utf8"),
            "metadata": metadata,
        }).encode("utf8")
        LOGGER.info("Sending echo response: %s", result_payload.decode("utf8"))
        yield flight.Result(pa.py_buffer(result_payload))

    # Minimal implementations to satisfy abstract base class.
    def list_flights(self, context: flight.ServerCallContext, criteria: Optional[flight.Criteria]) -> Iterator:
        return iter([])

    def get_flight_info(self, context: flight.ServerCallContext, descriptor: flight.FlightDescriptor) -> flight.FlightInfo:
        raise NotImplementedError("This server only supports actions")


def _build_generic_options(options: List[Dict[str, str]]) -> List[Tuple[str, str]]:
    generic_options: List[Tuple[str, str]] = []
    for opt in options:
        key = opt.get("key")
        value = opt.get("value")
        if not key or value is None:
            raise ConfigurationError("grpc_options entries must define 'key' and 'value'")
        generic_options.append((key, str(value)))
    return generic_options


def _apply_tcp_settings(tcp_settings: Dict[str, object]) -> None:
    if not tcp_settings:
        return
    try:
        import socket

        if not hasattr(socket, "SOL_SOCKET"):
            LOGGER.warning("TCP settings not supported on this platform")
            return

        # pyarrow.flight listens lazily; configure defaults via environment variables where possible.
        if tcp_settings.get("tcp_keepalive"):
            os.environ.setdefault("PYARROW_TCP_KEEPALIVE", "1")
        if tcp_settings.get("tcp_keepidle") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPIDLE", str(tcp_settings["tcp_keepidle"]))
        if tcp_settings.get("tcp_keepintvl") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPINTVL", str(tcp_settings["tcp_keepintvl"]))
        if tcp_settings.get("tcp_keepcnt") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPCNT", str(tcp_settings["tcp_keepcnt"]))
    except Exception as exc:  # pragma: no cover - platform specific fallback
        LOGGER.warning("Failed to apply TCP settings: %s", exc)


def run_server(config_path: Path) -> None:
    config = _load_config(config_path)
    server_cfg = config["server"]
    delay_cfg = server_cfg.get("delay", {})
    delay_strategy = DelayStrategy(
        strategy=delay_cfg.get("strategy", "fixed"),
        initial_ms=float(delay_cfg.get("initial_ms", 0.0)),
        linear_increment_ms=float(delay_cfg.get("linear_increment_ms", 0.0)),
        multiplier=float(delay_cfg.get("multiplier", 1.0)),
        exponential_base=float(delay_cfg.get("exponential_base", 2.0)),
        max_ms=float(delay_cfg["max_ms"]) if delay_cfg.get("max_ms") is not None else None,
    )

    log_file = Path(server_cfg.get("log_file", "server.log"))
    _configure_logging(log_file, server_cfg.get("log_level", "INFO"))

    _apply_tcp_settings(server_cfg.get("tcp_settings", {}))

    location = flight.Location.for_grpc_tcp(server_cfg.get("host", "0.0.0.0"), int(server_cfg.get("port", 8815)))
    generic_options = _build_generic_options(server_cfg.get("grpc_options", []))

    allow_header_overrides = bool(server_cfg.get("allow_header_overrides", False))
    network_settings = {
        "host": server_cfg.get("host", "0.0.0.0"),
        "port": int(server_cfg.get("port", 8815)),
        "grpc_options": [{"key": key, "value": value} for key, value in generic_options],
        "tcp_settings": server_cfg.get("tcp_settings", {}),
    }

    if generic_options:
        LOGGER.info("Configured gRPC options: %s", json.dumps(network_settings["grpc_options"]))

    server = EchoFlightServer(location=location, delay_strategy=delay_strategy,
                              allow_header_overrides=allow_header_overrides,
                              generic_options=generic_options,
                              network_settings=network_settings)

    def handle_signal(signum, frame):  # pragma: no cover - relies on OS signals
        LOGGER.info("Received signal %s. Shutting down.", signum)
        server.shutdown()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    LOGGER.info("Starting Flight server on %s", location)
    server.serve()
    LOGGER.info("Flight server stopped")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Configurable Flight echo server")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"),
                        help="Path to the server configuration YAML file")
    args = parser.parse_args(argv)

    try:
        run_server(args.config)
    except (ConfigurationError, DelayConfigurationError) as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch at top level
        LOGGER.exception("Unexpected error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

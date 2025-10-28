"""Configurable Apache Arrow Flight client for exercising network settings."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pyarrow.flight as flight
import yaml

# Allow running from repository root without installation
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.delay import DelayConfigurationError, DelayStrategy  # noqa: E402  pylint: disable=wrong-import-position
from shared.network import apply_tcp_settings  # noqa: E402  pylint: disable=wrong-import-position

LOGGER = logging.getLogger("flight_client")


class ClientConfigurationError(Exception):
    """Raised when the client configuration is invalid."""


def _load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "client" not in data:
        raise ClientConfigurationError("Configuration must contain a 'client' key")
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


def _build_generic_options(options: List[Dict[str, str]]) -> List[Tuple[str, str]]:
    generic_options: List[Tuple[str, str]] = []
    for opt in options:
        key = opt.get("key")
        value = opt.get("value")
        if not key or value is None:
            raise ClientConfigurationError("grpc_options entries must define 'key' and 'value'")
        generic_options.append((key, str(value)))
    return generic_options


def _build_delay_strategy(config: Dict) -> DelayStrategy:
    delay_cfg = config.get("delay", {})
    return DelayStrategy(
        strategy=delay_cfg.get("strategy", "fixed"),
        initial_ms=float(delay_cfg.get("initial_ms", 0.0)),
        linear_increment_ms=float(delay_cfg.get("linear_increment_ms", 0.0)),
        multiplier=float(delay_cfg.get("multiplier", 1.0)),
        exponential_base=float(delay_cfg.get("exponential_base", 2.0)),
        max_ms=float(delay_cfg["max_ms"]) if delay_cfg.get("max_ms") is not None else None,
    )


def _build_interval_strategy(config: Dict) -> DelayStrategy:
    interval_cfg = config.get("interval", {})
    return DelayStrategy(
        strategy=interval_cfg.get("strategy", "fixed"),
        initial_ms=float(interval_cfg.get("initial_ms", 0.0)),
        linear_increment_ms=float(interval_cfg.get("linear_increment_ms", 0.0)),
        multiplier=float(interval_cfg.get("multiplier", 1.0)),
        exponential_base=float(interval_cfg.get("exponential_base", 2.0)),
        max_ms=float(interval_cfg["max_ms"]) if interval_cfg.get("max_ms") is not None else None,
    )


def _build_headers(strategy: DelayStrategy, current_delay_s: float) -> List[Tuple[bytes, bytes]]:
    delay_ms = max(current_delay_s * 1000.0, 0.0)
    headers = [
        (b"x-delay-strategy", strategy.strategy.encode("utf8")),
        (b"x-delay-initial-ms", f"{delay_ms:.3f}".encode("utf8")),
    ]
    if strategy.strategy == "linear":
        headers.append((b"x-delay-linear-increment-ms", f"{strategy.linear_increment_ms:.3f}".encode("utf8")))
    if strategy.strategy == "multiplier":
        headers.append((b"x-delay-multiplier", f"{strategy.multiplier:.6f}".encode("utf8")))
    if strategy.strategy == "exponential":
        headers.append((b"x-delay-exponential-base", f"{strategy.exponential_base:.6f}".encode("utf8")))
    if strategy.max_ms is not None:
        headers.append((b"x-delay-max-ms", f"{strategy.max_ms:.3f}".encode("utf8")))
    return headers


def run_client(config_path: Path) -> None:
    config = _load_config(config_path)
    client_cfg = config["client"]

    log_file = Path(client_cfg.get("log_file", "client.log"))
    _configure_logging(log_file, client_cfg.get("log_level", "INFO"))

    location = flight.Location.for_grpc_tcp(client_cfg.get("host", "127.0.0.1"), int(client_cfg.get("port", 8815)))
    generic_options = _build_generic_options(client_cfg.get("grpc_options", []))

    apply_tcp_settings(client_cfg.get("tcp_settings", {}), logger=LOGGER)

    client = flight.FlightClient(location, generic_options=generic_options)

    delay_strategy = _build_delay_strategy(client_cfg)
    interval_strategy = _build_interval_strategy(client_cfg)

    repetitions = int(client_cfg.get("repetitions", 1))
    message_template = client_cfg.get("message_template", "Hello from client")

    LOGGER.info("Starting client with %d repetitions", repetitions)
    last_success_time = time.monotonic()

    for index in range(1, repetitions + 1):
        if index > 1:
            sleep_seconds = interval_strategy.next_delay()
            LOGGER.info("Sleeping %.3f seconds before next message", sleep_seconds)
            time.sleep(sleep_seconds)
        else:
            # Use the initial interval immediately.
            initial_sleep = interval_strategy.next_delay()
            if initial_sleep > 0:
                LOGGER.info("Initial sleep %.3f seconds", initial_sleep)
                time.sleep(initial_sleep)

        idle_since_last_success = time.monotonic() - last_success_time
        LOGGER.info("Idle %.3f seconds since last successful response", idle_since_last_success)

        current_delay_s = delay_strategy.next_delay()
        headers = _build_headers(delay_strategy, current_delay_s)

        message_payload = {
            "sequence": index,
            "total": repetitions,
            "client_message": message_template,
            "client_delay_strategy": {
                "strategy": delay_strategy.strategy,
                "current_delay_seconds": current_delay_s,
            },
            "client_interval_strategy": {
                "strategy": interval_strategy.strategy,
            },
            "grpc_options": [{"key": key, "value": value} for key, value in generic_options],
            "network_location": {
                "host": client_cfg.get("host", "127.0.0.1"),
                "port": int(client_cfg.get("port", 8815)),
            },
            "idle_seconds_before_request": idle_since_last_success,
            "attempt_started_epoch": time.time(),
        }
        payload_bytes = json.dumps(message_payload).encode("utf8")

        LOGGER.info("Sending message %d/%d with delay %.3f seconds", index, repetitions, current_delay_s)
        action = flight.Action("echo", payload_bytes)
        call_options = flight.FlightCallOptions(headers=headers)
        attempt_started = time.monotonic()

        try:
            results: Iterable[flight.Result] = client.do_action(action, options=call_options)

            for result in results:
                response = json.loads(result.body.to_pybytes().decode("utf8"))
                LOGGER.info("Received response: %s", json.dumps(response))

            last_success_time = time.monotonic()
            round_trip = last_success_time - attempt_started
            LOGGER.info(
                "Call %d/%d completed in %.3f seconds (idle gap %.3f seconds)",
                index,
                repetitions,
                round_trip,
                idle_since_last_success,
            )
        except Exception as exc:  # pragma: no cover - defensive top-level logging
            failure_time = time.monotonic()
            idle_before_failure = failure_time - last_success_time
            in_flight_seconds = failure_time - attempt_started
            LOGGER.error(
                "Call %d/%d failed after %.3f seconds idle and %.3f seconds in-flight: %s",
                index,
                repetitions,
                idle_before_failure,
                in_flight_seconds,
                exc,
                exc_info=exc,
            )
            raise

    LOGGER.info("Client run complete")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Configurable Flight client")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"),
                        help="Path to the client configuration YAML file")
    args = parser.parse_args(argv)

    try:
        run_client(args.config)
    except (ClientConfigurationError, DelayConfigurationError) as exc:
        LOGGER.error("Configuration error: %s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - defensive catch at top level
        LOGGER.exception("Unexpected error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

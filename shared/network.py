"""Network-related helpers shared between client and server components."""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

LOGGER = logging.getLogger(__name__)


def apply_tcp_settings(tcp_settings: Optional[Dict[str, object]], *, logger: Optional[logging.Logger] = None) -> None:
    """Apply TCP keep-alive related environment overrides for Flight sockets.

    Parameters
    ----------
    tcp_settings:
        Mapping of TCP keep-alive options. Supported keys mirror the ones exposed
        by ``PYARROW_TCP_*`` environment variables. Any false-y value causes the
        helper to skip setting the corresponding override so that existing
        environment configuration wins.
    logger:
        Optional logger used for warnings. Defaults to a module-level logger.
    """
    if not tcp_settings:
        return

    log = logger or LOGGER

    try:
        import socket  # pylint: disable=import-outside-toplevel

        if not hasattr(socket, "SOL_SOCKET"):
            log.warning("TCP settings not supported on this platform")
            return

        if tcp_settings.get("tcp_keepalive"):
            os.environ.setdefault("PYARROW_TCP_KEEPALIVE", "1")
        if tcp_settings.get("tcp_keepidle") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPIDLE", str(tcp_settings["tcp_keepidle"]))
        if tcp_settings.get("tcp_keepintvl") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPINTVL", str(tcp_settings["tcp_keepintvl"]))
        if tcp_settings.get("tcp_keepcnt") is not None:
            os.environ.setdefault("PYARROW_TCP_KEEPCNT", str(tcp_settings["tcp_keepcnt"]))
    except Exception as exc:  # pragma: no cover - platform specific fallback
        log.warning("Failed to apply TCP settings: %s", exc)

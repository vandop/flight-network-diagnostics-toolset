import asyncio
import logging
import os
import socket
import struct
import time

LOGGER = logging.getLogger("idle_proxy")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


LISTEN_HOST = _env("PROXY_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(_env("PROXY_LISTEN_PORT", "8815"))
BACKEND_HOST = _env("PROXY_BACKEND_HOST", "flight-server")
BACKEND_PORT = int(_env("PROXY_BACKEND_PORT", "8815"))
IDLE_TIMEOUT = float(_env("PROXY_IDLE_TIMEOUT_SECONDS", "300"))
IDLE_CHECK_INTERVAL = float(_env("PROXY_IDLE_CHECK_SECONDS", "1.0"))
PING_METHOD = _env("PROXY_HTTP_PING_METHOD", "GET").upper()
PING_PATH = _env("PROXY_HTTP_PING_PATH", "/ping")
PING_RESPONSE_BODY = _env("PROXY_HTTP_PING_BODY", "PONG")


class ProxyConnection:
    def __init__(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        backend_reader: asyncio.StreamReader,
        backend_writer: asyncio.StreamWriter,
    ) -> None:
        self.client_reader = client_reader
        self.client_writer = client_writer
        self.backend_reader = backend_reader
        self.backend_writer = backend_writer
        self.last_activity = time.monotonic()
        self._closed = asyncio.Event()

    def mark_activity(self) -> None:
        self.last_activity = time.monotonic()

    async def close(self, reason: str) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        LOGGER.info("Closing connection due to %s", reason)
        for writer in (self.client_writer, self.backend_writer):
            _force_close(writer)
        await asyncio.gather(
            _await_close(self.client_writer),
            _await_close(self.backend_writer),
            return_exceptions=True,
        )

    async def wait_closed(self) -> None:
        await self._closed.wait()


async def _await_close(writer: asyncio.StreamWriter) -> None:
    try:
        await writer.wait_closed()
    except Exception:  # pragma: no cover - defensive
        LOGGER.debug("wait_closed raised", exc_info=True)


def _force_close(writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    if not isinstance(sock, socket.socket):
        writer.close()
        return
    try:
        linger = struct.pack("ii", 1, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    except OSError:  # pragma: no cover - platform specific
        LOGGER.debug("Failed to set SO_LINGER", exc_info=True)
    writer.close()


def _detect_http_ping(data: bytes) -> bool:
    if not data:
        return False
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:  # pragma: no cover - decode failure unlikely
        return False
    first_line = text.splitlines()[0] if text else ""
    needle = f"{PING_METHOD} {PING_PATH} ".upper()
    return first_line.upper().startswith(needle)


def _ping_response() -> bytes:
    body = PING_RESPONSE_BODY.encode("utf-8")
    headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain; charset=utf-8",
        f"Content-Length: {len(body)}",
        "Connection: keep-alive",
        "", "",
    ]
    return "\r\n".join(headers).encode("utf-8") + body


async def handle_client(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
) -> None:
    peer = client_writer.get_extra_info("peername")
    LOGGER.info("Accepted connection from %s", peer)
    try:
        backend_reader, backend_writer = await asyncio.open_connection(
            BACKEND_HOST, BACKEND_PORT
        )
    except Exception as exc:  # pragma: no cover - connection errors
        LOGGER.error("Failed to connect to backend: %s", exc)
        _force_close(client_writer)
        return

    state = ProxyConnection(client_reader, client_writer, backend_reader, backend_writer)
    idle_task = asyncio.create_task(_idle_watchdog(state))
    forward_tasks = [
        asyncio.create_task(_pump_client_to_server(state)),
        asyncio.create_task(_pump_server_to_client(state)),
    ]

    done, pending = await asyncio.wait(
        forward_tasks + [idle_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc:
            LOGGER.debug("Task raised", exc_info=exc)

    await state.close("proxy shutdown")


async def _pump_client_to_server(state: ProxyConnection) -> None:
    while True:
        data = await state.client_reader.read(65536)
        if not data:
            await state.close("client closed")
            return
        state.mark_activity()
        if _detect_http_ping(data):
            LOGGER.debug("Responding to HTTP ping without forwarding")
            state.client_writer.write(_ping_response())
            await state.client_writer.drain()
            continue
        state.backend_writer.write(data)
        await state.backend_writer.drain()


async def _pump_server_to_client(state: ProxyConnection) -> None:
    while True:
        data = await state.backend_reader.read(65536)
        if not data:
            await state.close("backend closed")
            return
        state.mark_activity()
        state.client_writer.write(data)
        await state.client_writer.drain()


async def _idle_watchdog(state: ProxyConnection) -> None:
    if IDLE_TIMEOUT <= 0:
        return
    while True:
        await asyncio.sleep(IDLE_CHECK_INTERVAL)
        idle_for = time.monotonic() - state.last_activity
        if idle_for >= IDLE_TIMEOUT:
            LOGGER.info("Idle timeout exceeded (%.2fs)", idle_for)
            await state.close("idle timeout")
            return


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    sockets = ", ".join(
        f"{sock.getsockname()[0]}:{sock.getsockname()[1]}" for sock in server.sockets or []
    )
    LOGGER.info(
        "Proxy listening on %s -> backend %s:%s (idle timeout=%ss)",
        sockets,
        BACKEND_HOST,
        BACKEND_PORT,
        IDLE_TIMEOUT,
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        LOGGER.info("Proxy interrupted, shutting down")

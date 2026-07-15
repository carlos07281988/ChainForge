# Copyright 2026 ChainForge Contributors
# ALDP WebSocket server — zero extra dependencies, pure asyncio.

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import struct
from typing import Any

from chainforge.aldp.protocol import encode_event

_WS_GUID = b"258EAFA5-E914-47DA-95CA-5AB5B93714F7"


class WebSocketConnection:
    """A single WebSocket connection with framed message I/O."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def handshake(self) -> bool:
        try:
            request = await self._reader.readuntil(b"\r\n\r\n")
            request_str = request.decode("utf-8", errors="replace")
            key = None
            for line in request_str.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
                    break
            if not key:
                return False
            accept = base64.b64encode(hashlib.sha1(key.encode() + _WS_GUID).digest()).decode()
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            self._writer.write(response.encode())
            await self._writer.drain()
            return True
        except Exception:
            return False

    async def send(self, data: bytes) -> None:
        if self._closed:
            return
        try:
            length = len(data)
            header = bytearray()
            header.append(0x81)
            if length < 126:
                header.append(length)
            elif length < 65536:
                header.append(126)
                header.extend(struct.pack(">H", length))
            else:
                header.append(127)
                header.extend(struct.pack(">Q", length))
            self._writer.write(bytes(header) + data)
            await self._writer.drain()
        except Exception:
            self._closed = True

    async def send_event(self, event_type: str, data: dict[str, Any]) -> None:
        await self.send(encode_event(event_type, data))

    async def recv(self) -> dict[str, Any] | None:
        try:
            header = await self._reader.readexactly(2)
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F
            if opcode == 0x8:
                self._closed = True
                self._writer.write(b"\x88\x00")
                await self._writer.drain()
                return None
            if length == 126:
                ext = await self._reader.readexactly(2)
                length = struct.unpack(">H", ext)[0]
            elif length == 127:
                ext = await self._reader.readexactly(8)
                length = struct.unpack(">Q", ext)[0]
            mask_key = None
            if masked:
                mask_key = await self._reader.readexactly(4)
            payload = await self._reader.readexactly(length)
            if mask_key:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))
            elif opcode == 0x9:
                self._writer.write(b"\x8a\x00")
                await self._writer.drain()
                return await self.recv()
            return None
        except Exception:
            self._closed = True
            return None

    async def close(self) -> None:
        self._closed = True
        try:
            self._writer.write(b"\x88\x00")
            await self._writer.drain()
            self._writer.close()
        except Exception:
            pass


class ALDPServer:
    """WebSocket server for the Agent Live Debug Protocol."""

    def __init__(self, host: str = "localhost", port: int = 9229):
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._connections: list[WebSocketConnection] = []
        self._pause_event = asyncio.Event()
        self._paused = False
        self._step_mode = False

    @property
    def paused(self) -> bool:
        return self._paused

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        addr = self._server.sockets[0].getsockname()
        return self

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for conn in self._connections:
            await conn.close()

    async def wait_for_connection(self, timeout: float = 30.0) -> WebSocketConnection | None:
        for _ in range(int(timeout * 10)):
            if self._connections:
                return self._connections[0]
            await asyncio.sleep(0.1)
        return None

    async def broadcast(self, event_type: str, data: dict[str, Any]):
        for conn in self._connections[:]:
            if conn.closed:
                self._connections.remove(conn)
            else:
                await conn.send_event(event_type, data)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = WebSocketConnection(reader, writer)
        if not await conn.handshake():
            writer.close()
            return
        self._connections.append(conn)
        try:
            while not conn.closed:
                msg = await conn.recv()
                if msg is None:
                    break
                await self._handle_command(msg)
        except Exception:
            pass
        finally:
            if conn in self._connections:
                self._connections.remove(conn)
            await conn.close()

    async def _handle_command(self, msg: dict[str, Any]):
        cmd = msg.get("cmd", "")
        data = msg.get("data", {})
        if cmd == "pause" and not self._paused:
            self._paused = True
            self._pause_event.clear()
            self._step_mode = False
            await self.broadcast("paused", {"breakpoint": "user_request", "snapshot": data})
        elif cmd == "resume" and self._paused:
            self._paused = False
            self._step_mode = False
            self._pause_event.set()
            await self.broadcast("resumed", {})
        elif cmd == "step_over":
            self._paused = True
            self._step_mode = True
            self._pause_event.set()

    async def wait_if_paused(self) -> bool:
        while self._paused and not self._step_mode:
            await self._pause_event.wait()
        if self._step_mode:
            self._paused = True
            self._pause_event.clear()
            self._step_mode = False
        return True


__all__ = ["ALDPServer", "WebSocketConnection"]

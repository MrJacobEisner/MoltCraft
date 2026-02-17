import socket
import struct
import time
import os
import asyncio
from contextlib import asynccontextmanager


class RconClient:
    def __init__(self, host="localhost", port=25575, password=None):
        self.host = host
        self.port = port
        self.password = password or os.environ.get("RCON_PASSWORD", "minecraft-ai-builder")
        self.sock = None
        self.request_id = 0
        self.max_retries = 5
        self.retry_delay = 2
        self._commands_sent = 0

    def connect(self):
        self.disconnect()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(15)
        self.sock.connect((self.host, self.port))
        self._send_packet(3, self.password)
        response = self._read_packet()
        if response["id"] == -1:
            self.disconnect()
            raise Exception("RCON authentication failed")
        self._commands_sent = 0
        return True

    def disconnect(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def reconnect(self):
        self.disconnect()
        time.sleep(1)
        for attempt in range(self.max_retries):
            try:
                self.connect()
                return True
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    def command(self, cmd):
        for attempt in range(self.max_retries):
            try:
                if not self.sock:
                    self.connect()
                self._send_packet(2, cmd)
                response = self._read_packet()
                self._commands_sent += 1
                if self._commands_sent % 500 == 0:
                    time.sleep(0.1)
                return response["payload"]
            except Exception:
                self.disconnect()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    def ensure_connected(self):
        try:
            if self.sock:
                self.sock.settimeout(2)
                self._send_packet(2, "list")
                self._read_packet()
                self.sock.settimeout(15)
                return True
        except Exception:
            pass
        self.disconnect()
        return self.reconnect()

    def _send_packet(self, packet_type, payload):
        if not self.sock:
            raise ConnectionError("Not connected to RCON")
        self.request_id = (self.request_id + 1) % 2147483647
        data = struct.pack("<ii", self.request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
        packet = struct.pack("<i", len(data)) + data
        self.sock.sendall(packet)

    def _read_packet(self):
        raw_len = self._recv_exact(4)
        length = struct.unpack("<i", raw_len)[0]
        if length > 4096:
            raise Exception(f"RCON packet too large: {length}")
        data = self._recv_exact(length)
        request_id = struct.unpack("<i", data[0:4])[0]
        packet_type = struct.unpack("<i", data[4:8])[0]
        payload = data[8:-2].decode("utf-8", errors="replace")
        return {"id": request_id, "type": packet_type, "payload": payload}

    def _recv_exact(self, n):
        if not self.sock:
            raise ConnectionError("Not connected to RCON")
        data = b""
        while len(data) < n:
            try:
                chunk = self.sock.recv(n - len(data))
            except socket.timeout:
                raise ConnectionError("RCON read timed out")
            if not chunk:
                raise ConnectionError("RCON connection closed")
            data += chunk
        return data


class RconPool:
    def __init__(self, size=4, host="localhost", port=25575, password=None):
        self.size = size
        self.host = host
        self.port = port
        self.password = password
        self._clients: list[RconClient] = []
        self._available: asyncio.Queue | None = None
        self._initialized = False

    def init(self):
        self._available = asyncio.Queue(maxsize=self.size)
        for _ in range(self.size):
            client = RconClient(self.host, self.port, self.password)
            self._clients.append(client)
            self._available.put_nowait(client)
        self._initialized = True
        print(f"[RCON] Pool initialized with {self.size} connections")

    def close(self):
        for client in self._clients:
            client.disconnect()
        self._clients.clear()
        self._initialized = False
        print("[RCON] Pool closed")

    @asynccontextmanager
    async def acquire(self):
        if not self._initialized:
            self.init()
        client = await self._available.get()
        try:
            yield client
        finally:
            self._available.put_nowait(client)

    async def command(self, cmd: str) -> str:
        async with self.acquire() as client:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, client.command, cmd)

    async def command_safe(self, cmd: str, label: str = "RCON") -> str | None:
        try:
            return await self.command(cmd)
        except Exception as e:
            print(f"[RCON] {label} error: {e}")
            return None

    async def batch(self, cmds: list[str], label: str = "RCON") -> tuple[int, list[str]]:
        async with self.acquire() as client:
            loop = asyncio.get_event_loop()
            executed = 0
            errors = []
            for cmd in cmds:
                try:
                    await loop.run_in_executor(None, client.command, cmd)
                    executed += 1
                except Exception as e:
                    errors.append(f"{cmd}: {str(e)}")
                    if len(errors) > 10:
                        break
            return executed, errors

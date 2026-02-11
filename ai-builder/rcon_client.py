import socket
import struct
import time
import os


class RconClient:
    def __init__(self, host="localhost", port=25575, password=None):
        self.host = host
        self.port = port
        self.password = password or os.environ.get("RCON_PASSWORD", "minecraft-ai-builder")
        self.sock = None
        self.request_id = 0
        self.max_retries = 3
        self.retry_delay = 2

    def connect(self):
        self.disconnect()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.host, self.port))
        self._send_packet(3, self.password)
        response = self._read_packet()
        if response["id"] == -1:
            self.disconnect()
            raise Exception("RCON authentication failed")
        return True

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def command(self, cmd):
        for attempt in range(self.max_retries):
            try:
                if not self.sock:
                    self.connect()
                self._send_packet(2, cmd)
                response = self._read_packet()
                return response["payload"]
            except Exception as e:
                self.disconnect()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise

    def _send_packet(self, packet_type, payload):
        self.request_id += 1
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

    def send_commands(self, commands, delay=0.01):
        results = []
        for cmd in commands:
            try:
                result = self.command(cmd)
                results.append(result)
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                results.append(f"Error: {e}")
                self.disconnect()
                try:
                    self.connect()
                except Exception:
                    pass
        return results
